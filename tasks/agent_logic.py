"""
Agent logic modules for the AgentOrchestrator.

Each function is a self-contained unit of autonomous work triggered either
on a schedule or when new articles arrive. The orchestrator calls:

    logic_function(agent_config=..., mcp_client=..., llm_config=..., new_articles=...)

All functions must accept **kwargs to absorb unused keyword arguments.
LLM config is resolved by the orchestrator via resolve_llm_config(userspace)
before dispatch — logic modules must NOT re-resolve it themselves.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _handle_mcp_response(result: Any, context: str) -> tuple[bool, Any]:
    """
    Handle MCP tool response (standardized dict or legacy string).
    
    Returns:
        (success: bool, data: Any)
        - success: True if operation succeeded, False on error
        - data: The data payload from response, or None on error
        
    Logs errors and warnings as appropriate.
    """
    # New standardized response format (dict)
    if isinstance(result, dict):
        status = result.get("status")
        
        if status == "success":
            return True, result.get("data")
        
        elif status == "error":
            error_code = result.get("error_code", "UNKNOWN")
            message = result.get("message", "No error message")
            retryable = result.get("retryable", False)
            next_action = result.get("next_action", "unknown")
            
            if retryable:
                retry_after_ms = result.get("retry_after_ms", 1000)
                logger.warning(
                    "%s: Retryable error (%s) - %s (retry in %dms, action: %s)",
                    context, error_code, message, retry_after_ms, next_action
                )
            else:
                logger.error(
                    "%s: Non-retryable error (%s) - %s (action: %s)",
                    context, error_code, message, next_action
                )
            
            return False, None
        
        elif status == "partial":
            logger.warning("%s: Partial success - %s", context, result.get("message"))
            return True, result.get("data")  # Treat partial as success for now
        
        else:
            logger.error("%s: Unknown response status: %s", context, status)
            return False, None
    
    # Legacy string response format
    elif isinstance(result, str):
        if "error" in result.lower():
            logger.error("%s: %s", context, result)
            return False, None
        else:
            logger.info("%s: %s", context, result)
            return True, result
    
    else:
        logger.error("%s: Unexpected response type: %s", context, type(result))
        return False, None

_OLLAMA_DEFAULT_ENDPOINT = "http://host.docker.internal:11434/v1"
_WARN_MISSING_USERSPACE = "Agent '%s': missing userspace, skipping."


def _call_llm(
    prompt: str,
    llm_config: dict,
    mcp_client: object = None,
) -> Optional[str]:
    """Call the configured LLM with a prompt and return the text response.

    If *mcp_client* is a :class:`TracingMCPClient` (or any object exposing
    ``session_logger`` / ``session_id`` attributes), the call is recorded as
    an ``llm_call`` step for observability.
    """
    import time as _time
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz
    from api.llm.factory import LLMProviderFactory

    provider_name = llm_config.get("provider", "ollama")
    model = llm_config.get("model", "llama3.1")

    if provider_name == "openai":
        api_key = llm_config.get("openai_api_key") or ""
    elif provider_name == "gemini":
        api_key = llm_config.get("gemini_api_key") or ""
    else:
        api_key = ""

    ollama_base_url = llm_config.get("ollama_endpoint") or _OLLAMA_DEFAULT_ENDPOINT
    llm_provider = LLMProviderFactory().get_provider(provider_name, api_key, ollama_base_url)

    # Resolve tracing handles (no-op if mcp_client is not a TracingMCPClient)
    _session_logger = getattr(mcp_client, "session_logger", None)
    _session_id = getattr(mcp_client, "session_id", None)

    start = _time.monotonic()
    try:
        response = llm_provider.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            tools=None,
            tool_choice=None,
        )
        text = response.choices[0].message.content.strip()

        if _session_logger and _session_id:
            latency_ms = int((_time.monotonic() - start) * 1000)
            _session_logger.add_step(_session_id, {
                "step_id": str(_uuid.uuid4()),
                "step_type": "llm_call",
                "tool_name": f"{provider_name}/{model}",
                "input_summary": prompt[:500],
                "output_summary": (text or "")[:500],
                "status": "success",
                "latency_ms": latency_ms,
                "correlation_id": str(_uuid.uuid4()),
                "attempt": 1,
                "risk_level": "normal",
                "timestamp": _dt.now(_tz.utc).isoformat(),
            })

        return text
    except Exception as exc:
        if _session_logger and _session_id:
            latency_ms = int((_time.monotonic() - start) * 1000)
            _session_logger.add_step(_session_id, {
                "step_id": str(_uuid.uuid4()),
                "step_type": "llm_call",
                "tool_name": f"{provider_name}/{model}",
                "input_summary": prompt[:500],
                "output_summary": "",
                "status": "error",
                "error_message": str(exc),
                "latency_ms": latency_ms,
                "correlation_id": str(_uuid.uuid4()),
                "attempt": 1,
                "risk_level": "normal",
                "timestamp": _dt.now(_tz.utc).isoformat(),
            })
        logger.error("LLM call failed: %s", exc)
        return None


def _parse_json_response(text: Optional[str], context: str) -> Optional[dict]:
    """Parse a JSON object from an LLM response, tolerating markdown code fences."""
    if not text:
        return None
    # Strip markdown code fences if present
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(stripped)
    except ValueError:
        logger.warning("%s: could not parse LLM JSON response: %.200s", context, text)
        return None


def create_event_from_articles(
    agent_config: dict[str, Any],
    mcp_client,
    new_articles: list[dict[str, Any]] = None,
    llm_config: dict = None,
    **kwargs,
):
    """Analyse new articles and create a new Event if warranted.

    Uses the LLM to decide whether the batch of new articles represents a
    significant event worth tracking, then calls the add_event MCP tool.
    """
    userspace = agent_config.get("userspace")
    agent_name = agent_config.get("name", "create_event_from_articles")
    llm_config = llm_config or {}

    if not userspace:
        logger.warning(_WARN_MISSING_USERSPACE, agent_name)
        return

    if not new_articles:
        logger.info("Agent '%s' (%s): no new articles to process.", agent_name, userspace)
        return

    logger.info(
        "Agent '%s' (%s): analysing %d article(s) for event creation.",
        agent_name, userspace, len(new_articles),
    )

    article_lines = "\n".join(
        f"- [{a.get('_id', '?')}] {a.get('title', '(no title)')}: "
        f"{(a.get('summary') or a.get('description') or '')[:150]}"
        for a in new_articles[:20]
    )

    prompt = (
        "You are a news analysis agent. Analyse these new articles and decide "
        "whether they collectively represent a significant new event worth tracking.\n\n"
        f"Articles:\n{article_lines}\n\n"
        "If a new event should be created, reply with JSON:\n"
        '{"should_create": true, "name": "Short event name (max 80 chars)", '
        '"description": "2-3 sentence description of the event"}\n\n'
        "If no new event should be created, reply with:\n"
        '{"should_create": false}\n\n'
        "Reply with ONLY the JSON object, no other text."
    )

    raw = _call_llm(prompt, llm_config, mcp_client=mcp_client)
    decision = _parse_json_response(raw, f"Agent '{agent_name}'")
    if not decision or not decision.get("should_create"):
        logger.info("Agent '%s' (%s): LLM decided no new event needed.", agent_name, userspace)
        return

    name = (decision.get("name") or "").strip()
    description = (decision.get("description") or "").strip()
    if not name:
        logger.warning("Agent '%s' (%s): LLM returned empty event name.", agent_name, userspace)
        return

    article_ids = [a["_id"] for a in new_articles if a.get("_id")]

    try:
        result = mcp_client.call_tool(
            "add_event",
            userspace=userspace,
            name=name,
            description=description,
            article_links=article_ids,
        )
        
        success, data = _handle_mcp_response(result, f"Agent '{agent_name}' ({userspace}): add_event")
        
        if success:
            # New format includes issue_id in data
            if isinstance(data, dict) and "issue_id" in data:
                logger.info(
                    "Agent '%s' (%s): Event created - ID: %s, Name: '%s'",
                    agent_name, userspace, data["issue_id"], data.get("logos", name)
                )
            else:
                # Legacy string response
                logger.info("Agent '%s' (%s): Event created successfully", agent_name, userspace)
        else:
            logger.error("Agent '%s' (%s): Failed to create event", agent_name, userspace)
            
    except Exception as exc:
        logger.error("Agent '%s' (%s): add_event failed: %s", agent_name, userspace, exc)


def add_articles_to_event(
    agent_config: dict[str, Any],
    mcp_client,
    new_articles: list[dict[str, Any]] = None,
    llm_config: dict = None,
    **kwargs,
):
    """Analyse new articles and add relevant ones to a specific linked event.

    Uses the LLM to determine which of the new articles are relevant to the
    event specified by agent_config["linked_entity_id"], then updates it via
    the update_event MCP tool.
    """
    userspace = agent_config.get("userspace")
    agent_name = agent_config.get("name", "add_articles_to_event")
    event_id = agent_config.get("linked_entity_id")
    llm_config = llm_config or {}

    if not userspace:
        logger.warning(_WARN_MISSING_USERSPACE, agent_name)
        return

    if not event_id:
        logger.warning("Agent '%s' (%s): no linked_entity_id specified.", agent_name, userspace)
        return

    if not new_articles:
        logger.info("Agent '%s' (%s): no new articles to process.", agent_name, userspace)
        return

    logger.info(
        "Agent '%s' (%s): checking %d article(s) against event %s.",
        agent_name, userspace, len(new_articles), event_id,
    )

    # Fetch current event state
    event_result = mcp_client.call_tool("get_event", event_id=event_id, userspace=userspace)
    
    success, event_doc = _handle_mcp_response(event_result, f"Agent '{agent_name}' ({userspace}): get_event")
    
    if not success or not event_doc:
        logger.error(
            "Agent '%s' (%s): could not fetch event %s",
            agent_name, userspace, event_id,
        )
        return
    
    existing_ids = {
        (p.get("id") if isinstance(p, dict) else p)
        for p in event_doc.get("premises", [])
    }

    # Only offer articles not already linked
    candidates = [a for a in new_articles if a.get("_id") and a["_id"] not in existing_ids]
    if not candidates:
        logger.info("Agent '%s' (%s): all new articles already linked to event %s.", agent_name, userspace, event_id)
        return

    article_lines = "\n".join(
        f"- [{a['_id']}] {a.get('title', '(no title)')}: "
        f"{(a.get('summary') or a.get('description') or '')[:150]}"
        for a in candidates[:20]
    )

    prompt = (
        "You are a news analysis agent. Decide which of these new articles are "
        "relevant to the following event and should be added to it.\n\n"
        f"Event: {event_doc.get('logos', '')}\n"
        f"Description: {event_doc.get('description', '')}\n\n"
        f"Candidate articles:\n{article_lines}\n\n"
        "Reply with ONLY a JSON object listing the _id values of relevant articles:\n"
        '{"relevant_ids": ["id1", "id2"]}\n\n'
        "If none are relevant, reply with:\n"
        '{"relevant_ids": []}'
    )

    raw = _call_llm(prompt, llm_config, mcp_client=mcp_client)
    decision = _parse_json_response(raw, f"Agent '{agent_name}'")
    if not decision:
        return

    relevant_ids = [str(i) for i in decision.get("relevant_ids", []) if i]
    if not relevant_ids:
        logger.info("Agent '%s' (%s): LLM found no relevant articles for event %s.", agent_name, userspace, event_id)
        return

    logger.info(
        "Agent '%s' (%s): adding %d article(s) to event %s.",
        agent_name, userspace, len(relevant_ids), event_id,
    )
    _call_update_event(agent_name, userspace, event_id, relevant_ids, mcp_client)


def _call_update_event(
    agent_name: str, userspace: str, event_id: str, article_links: list, mcp_client
) -> None:
    """Call the update_event MCP tool and log the outcome."""
    try:
        result = mcp_client.call_tool(
            "update_event",
            userspace=userspace,
            event_id=event_id,
            article_links=article_links,
        )
        
        success, data = _handle_mcp_response(result, f"Agent '{agent_name}' ({userspace}): update_event")
        
        if success:
            logger.info(
                "Agent '%s' (%s): Event %s updated with %d article(s)",
                agent_name, userspace, event_id, len(article_links)
            )
        else:
            logger.error("Agent '%s' (%s): Failed to update event %s", agent_name, userspace, event_id)
            
    except Exception as exc:
        logger.error("Agent '%s' (%s): update_event failed: %s", agent_name, userspace, exc)


def _parse_iso_timestamp(ts_str: str) -> Optional[Any]:
    """Parse an ISO-8601 timestamp string to a timezone-aware datetime, or return None on error."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def check_event_staleness(
    agent_config: dict[str, Any],
    mcp_client,
    **kwargs,
):
    """Check whether a linked event is stale and mark it accordingly.

    No LLM call — purely date-based comparison against
    agent_config["parameters"]["staleness_threshold_days"] (default 30).
    """
    from datetime import datetime, timezone

    userspace = agent_config.get("userspace")
    agent_name = agent_config.get("name", "check_event_staleness")
    event_id = agent_config.get("linked_entity_id")
    params = agent_config.get("parameters") or {}
    staleness_threshold_days = int(params.get("staleness_threshold_days", 30))

    if not userspace:
        logger.warning(_WARN_MISSING_USERSPACE, agent_name)
        return

    if not event_id:
        logger.warning("Agent '%s' (%s): no linked_entity_id specified.", agent_name, userspace)
        return

    event_result = mcp_client.call_tool("get_event", event_id=event_id, userspace=userspace)
    
    success, event_doc = _handle_mcp_response(event_result, f"Agent '{agent_name}' ({userspace}): get_event")
    
    if not success or not event_doc:
        logger.error(
            "Agent '%s' (%s): could not fetch event %s",
            agent_name, userspace, event_id,
        )
        return
    
    last_activity_str = event_doc.get("updated_at") or event_doc.get("created_at")
    if not last_activity_str:
        logger.warning("Agent '%s' (%s): event %s has no activity timestamp.", agent_name, userspace, event_id)
        return

    last_activity = _parse_iso_timestamp(last_activity_str)
    if last_activity is None:
        logger.error("Agent '%s' (%s): invalid date on event %s: %s", agent_name, userspace, event_id, last_activity_str)
        return

    now = datetime.now(timezone.utc)
    days_inactive = (now - last_activity).days
    is_stale_now = event_doc.get("is_stale", False)
    should_be_stale = days_inactive > staleness_threshold_days

    if should_be_stale == is_stale_now:
        status = "stale" if is_stale_now else "active"
        logger.info("Agent '%s' (%s): event %s remains %s (%d days).", agent_name, userspace, event_id, status, days_inactive)
        return

    action = "stale" if should_be_stale else "active"
    logger.info("Agent '%s' (%s): marking event %s as %s (%d days inactive).", agent_name, userspace, event_id, action, days_inactive)
    try:
        result = mcp_client.call_tool(
            "mark_entity_stale",
            userspace=userspace,
            entity_type="event",
            entity_id=event_id,
            is_stale=should_be_stale,
        )
        
        success, data = _handle_mcp_response(result, f"Agent '{agent_name}' ({userspace}): mark_entity_stale")
        
        if success:
            logger.info("Agent '%s' (%s): Event %s marked as %s", agent_name, userspace, event_id, action)
        else:
            logger.error("Agent '%s' (%s): Failed to mark event %s as %s", agent_name, userspace, event_id, action)
            
    except Exception as exc:
        logger.error("Agent '%s' (%s): mark_entity_stale failed: %s", agent_name, userspace, exc)
