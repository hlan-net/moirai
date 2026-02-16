import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import validators

logger = logging.getLogger(__name__)

DEFAULT_AGENT_NAME = "Unnamed Agent"


# Placeholder for LLM interaction - this would typically use mcp_client.call_tool('llm_chat', ...)
# or directly interact with the LLM API using user-specific keys.
def _call_llm(
    mcp_client, prompt: str, llm_config: Dict[str, Any], user_id: str
) -> Optional[str]:
    logger.info(f"Calling LLM for user {user_id} with config {llm_config}")
    # In a real scenario, this would dynamically call a tool like 'llm_chat' or 'llm_extract'
    # using the provided mcp_client and user-specific authentication/configuration.
    # For now, it's a mock.
    logger.debug(f"LLM Prompt: {prompt}")
    # Simulate LLM response
    if "event" in prompt.lower():
        return "New event suggested: AI breakthrough. Related articles: article1, article2."
    return "LLM response simulated."


def create_event_from_articles(
    agent_config: Dict[str, Any], mcp_client, new_articles: List[Dict[str, Any]]
):
    """
    Agent logic to analyze new articles and potentially create new events.
    """
    user_id = agent_config.get("user_id")
    agent_name = agent_config.get("name", DEFAULT_AGENT_NAME)
    llm_config = agent_config.get("llm_model_config", {})
    params = agent_config.get("parameters", {})

    if not new_articles:
        logger.info(
            f"Agent '{agent_name}' ({user_id}) - No new articles to process for event creation."
        )
        return

    logger.info(
        f"Agent '{agent_name}' ({user_id}) - Processing {len(new_articles)} new articles for event creation."
    )

    # Construct a prompt for the LLM to identify potential new events
    article_summaries = "\n".join(
        [
            f"- {a.get('title', 'No Title')}: {a.get('summary', '')[:100]}..."
            for a in new_articles
        ]
    )
    prompt = f"""Analyze the following new articles and suggest if a new significant event should be created. If so, provide a concise name and description for the event, and list the relevant article IDs:

{article_summaries}

Agent parameters: {params}"""

    llm_response = _call_llm(mcp_client, prompt, llm_config, user_id)

    if llm_response and "New event suggested" in llm_response:
        # Parse LLM response to create event
        event_name = "LLM Suggested Event"
        event_description = llm_response  # Simplified parsing for example
        article_links = [
            a["link"] for a in new_articles
        ]  # For now, all links from new articles

        logger.info(
            f"Agent '{agent_name}' ({user_id}) - Proposing new event: {event_name}"
        )
        # Call MCP tool to add event
        try:
            # MCP tools typically return dict with 'status' and 'message' or 'event'
            result = mcp_client.call_tool(
                "add_event",
                user_id=user_id,
                name=event_name,
                description=event_description,
                article_links=article_links,
            )
            if result.get("status") == "success":
                logger.info(
                    f"Agent '{agent_name}' ({user_id}) - Successfully created event: {result['event']['_id']}"
                )
            else:
                logger.error(
                    f"Agent '{agent_name}' ({user_id}) - Failed to create event: {result.get('message', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(
                f"Agent '{agent_name}' ({user_id}) - Error calling add_event MCP tool: {e}"
            )


def add_articles_to_event(
    agent_config: Dict[str, Any], mcp_client, new_articles: List[Dict[str, Any]]
):
    """
    Agent logic to analyze new articles and add relevant ones to a specific event.
    """
    user_id = agent_config.get("user_id")
    agent_name = agent_config.get("name", DEFAULT_AGENT_NAME)
    llm_config = agent_config.get("llm_model_config", {})
    event_id = agent_config.get("linked_entity_id")
    params = agent_config.get("parameters", {})

    if not event_id:
        logger.warning(
            f"Agent '{agent_name}' ({user_id}) - No linked_entity_id (event_id) specified for adding articles."
        )
        return
    if not new_articles:
        logger.info(
            f"Agent '{agent_name}' ({user_id}) - No new articles to process for event {event_id}."
        )
        return

    logger.info(
        f"Agent '{agent_name}' ({user_id}) - Processing {len(new_articles)} new articles for event {event_id}."
    )

    # Fetch the event to get its current context
    event_doc_result = mcp_client.call_tool("get_event", event_id=event_id)
    if event_doc_result.get("status") != "success":
        logger.error(
            f"Agent '{agent_name}' ({user_id}) - Failed to retrieve event {event_id}: {event_doc_result.get('message')}"
        )
        return
    event_doc = event_doc_result["event"]

    # Construct a prompt for the LLM to identify relevant articles
    current_event_context = f"""Event Name: {event_doc.get("name")}
Event Description: {event_doc.get("description")}
Existing Article Links: {", ".join(event_doc.get("article_links", []))}"""
    article_summaries = "\n".join(
        [
            f"- {a.get('title', 'No Title')}: {a.get('summary', '')[:100]}..."
            for a in new_articles
        ]
    )

    prompt = f"""Given the following event context:
{current_event_context}

And these new articles:
{article_summaries}

Identify which new articles are relevant to this event. List the full URLs of relevant articles only. Agent parameters: {params}"""

    llm_response = _call_llm(mcp_client, prompt, llm_config, user_id)

    if llm_response:
        relevant_article_links = [
            line.strip()
            for line in llm_response.split("\n")
            if validators.url(line.strip())
        ]  # Simplified parsing
        if relevant_article_links:
            # Call MCP tool to update event with new articles
            try:
                # Assuming update_event can take new article_links to add/merge
                updated_links = list(
                    set(event_doc.get("article_links", []) + relevant_article_links)
                )
                result = mcp_client.call_tool(
                    "update_event",
                    user_id=user_id,
                    event_id=event_id,
                    article_links=updated_links,
                )
                if result.get("status") == "success":
                    logger.info(
                        f"Agent '{agent_name}' ({user_id}) - Successfully added {len(relevant_article_links)} articles to event {event_id}."
                    )
                else:
                    logger.error(
                        f"Agent '{agent_name}' ({user_id}) - Failed to add articles to event {event_id}: {result.get('message', 'Unknown error')}"
                    )
            except Exception as e:
                logger.error(
                    f"Agent '{agent_name}' ({user_id}) - Error calling update_event MCP tool: {e}"
                )


def _update_staleness_status(mcp_client, agent_name: str, user_id: str, event_id: str, should_be_stale: bool):
    """Helper to update event staleness via MCP tool."""
    action = "marking it as stale" if should_be_stale else "unmarking it"
    logger.info(f"Agent '{agent_name}' ({user_id}) - Event {event_id} status change: {action}.")
    
    result = mcp_client.call_tool(
        "mark_entity_stale",
        entity_type="event",
        entity_id=event_id,
        is_stale=should_be_stale,
    )
    
    if result.get("status") == "success":
        logger.info(f"Agent '{agent_name}' ({user_id}) - Successfully updated event {event_id}.")
    else:
        logger.error(f"Agent '{agent_name}' ({user_id}) - Failed to update event {event_id}: {result.get('message', 'Unknown error')}")

def check_event_staleness(agent_config: Dict[str, Any], mcp_client):
    """
    Agent logic to check if a linked event is stale and mark it as such.
    """
    user_id = agent_config.get("user_id")
    agent_name = agent_config.get("name", DEFAULT_AGENT_NAME)
    event_id = agent_config.get("linked_entity_id")
    params = agent_config.get("parameters", {})
    staleness_threshold_days = params.get("staleness_threshold_days", 30)

    if not event_id:
        logger.warning(f"Agent '{agent_name}' ({user_id}) - No event_id specified for staleness check.")
        return

    # Fetch the event
    event_doc_result = mcp_client.call_tool("get_event", event_id=event_id)
    if event_doc_result.get("status") != "success":
        logger.error(f"Agent '{agent_name}' ({user_id}) - Failed to retrieve event {event_id}: {event_doc_result.get('message')}")
        return
    
    event_doc = event_doc_result["event"]
    last_activity_at_str = event_doc.get("updated_at") or event_doc.get("created_at")
    
    if not last_activity_at_str:
        logger.warning(f"Agent '{agent_name}' ({user_id}) - Event {event_id} missing activity timestamps.")
        return

    try:
        last_activity_date = datetime.fromisoformat(last_activity_at_str.replace("Z", "+00:00"))
        if last_activity_date.tzinfo is None:
            last_activity_date = last_activity_date.replace(tzinfo=timezone.utc)
    except ValueError:
        logger.error(f"Agent '{agent_name}' ({user_id}) - Invalid date format in event {event_id}")
        return

    now = datetime.now(timezone.utc)
    days_since_activity = (now - last_activity_date).days
    is_currently_stale = event_doc.get("is_stale", False)
    is_beyond_threshold = days_since_activity > staleness_threshold_days

    if is_beyond_threshold and not is_currently_stale:
        _update_staleness_status(mcp_client, agent_name, user_id, event_id, True)
    elif not is_beyond_threshold and is_currently_stale:
        _update_staleness_status(mcp_client, agent_name, user_id, event_id, False)
    else:
        status_msg = "stale" if is_currently_stale else "active"
        logger.info(f"Agent '{agent_name}' ({user_id}) - Event {event_id} remains {status_msg} ({days_since_activity} days).")

