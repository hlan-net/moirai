import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import bleach
import httpx
from bs4 import BeautifulSoup
from flask import Blueprint, abort, g, jsonify, request
from mcp import ClientSession
from mcp.client.sse import sse_client

from .llm.factory import LLMProviderFactory
from .db import (
    fetch_from_couchdb,
    update_couchdb_doc,
    delete_from_couchdb,
    query_couchdb,
)
from .auth import jwt_required

chat_blueprint = Blueprint("chat", __name__)

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:8090/sse")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1"
)
DEFAULT_LLM_PROVIDER = os.environ.get("DEFAULT_LLM_PROVIDER", "ollama")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.1")

CHAT_HISTORY_LIMIT = 6
MAX_AGENT_TURNS = int(os.environ.get("MAX_AGENT_TURNS", "8"))
LLM_TIMEOUT_SECONDS = 600.0
CHAT_SESSION_NOT_FOUND = "Chat session not found"
ERROR_ACCESS_DENIED = "Access denied"
CHAT_EXPORT_VERBOSE_SETTING = "chat_export_verbose"

SYSTEM_PROMPT = (
    "You are Moirai, a GenAI-native press review agent. "
    "You DO NOT have access to real-time information or the internet directly. "
    "You MUST use the provided tools (like `list_feeds`, `read_feed`, `get_recent_articles`, `search_articles`) to fetch any news or external data. "
    "Do not hallucinate headlines. If you need news, CALL A TOOL. "
    "When asked for recent articles or news, use `get_recent_articles` to see what's already in the database. "
    "To fetch fresh articles from a specific feed, use `read_feed` with the feed URL. "
    "To see available feeds, use `list_feeds`. "
    "Some reliable Linux news feeds are: LWN (https://lwn.net/headlines/rss), Phoronix (https://www.phoronix.com/phoronix-rss.php), "
    "and Kernel.org (https://www.kernel.org/feeds/kall.xml)."
)

logger = logging.getLogger(__name__)

llm_provider_factory = LLMProviderFactory()


def extract_tool_calls_from_content(content):
    if not content:
        return []
    tools = []
    # Find all JSON-like blocks.
    # We look for something starting with { and ending with } that contains "name" and "parameters"
    # Use non-greedy matching .*? to find multiple separate JSON blocks
    matches = re.findall(
        r'(\{[^{}]*"name"\s*:\s*".*?".*?"parameters"\s*:\s*\{.*?\}.*?\})',
        content,
        re.DOTALL,
    )

    for match in matches:
        try:
            data = json.loads(match)
            if "name" in data and "parameters" in data:
                tools.append(data)
        except Exception:
            continue

    return tools


def _is_verbose_chat_export_enabled(config_doc: dict | None) -> bool:
    if not config_doc:
        return False
    return bool(config_doc.get(CHAT_EXPORT_VERBOSE_SETTING, False))


def _format_tool_call_markdown(tool_calls) -> str:
    if not tool_calls:
        return ""
    rows = []
    for tool_call in tool_calls:
        func_name = "unknown"
        func_args = "{}"
        func_status = None
        if isinstance(tool_call, dict):
            if "name" in tool_call:
                func_name = tool_call.get("name", func_name)
                func_status = tool_call.get("status")
                func_args = tool_call.get("arguments") or tool_call.get("args") or func_args
            else:
                function_data = tool_call.get("function") or {}
                func_name = function_data.get("name", func_name)
                func_args = function_data.get("arguments", func_args)
        else:
            function_data = getattr(tool_call, "function", None)
            if function_data:
                func_name = getattr(function_data, "name", func_name)
                func_args = getattr(function_data, "arguments", func_args)
        if func_status:
            rows.append(f"- `{func_name}` status: `{func_status}` args: `{func_args}`")
        else:
            rows.append(f"- `{func_name}` args: `{func_args}`")
    return "\n".join(rows)


def _strip_internal_reminders(text: str) -> str:
    if not text:
        return text
    if "<system-reminder>" not in text.lower():
        return text.strip()
    try:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup.find_all("system-reminder"):
            tag.decompose()
        return str(soup).strip()
    except Exception:
        return text.strip()


def _sanitize_export_value(value):
    if isinstance(value, str):
        return _strip_internal_reminders(value)
    if isinstance(value, dict):
        return {k: _sanitize_export_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_export_value(item) for item in value]
    return value


def _flatten_exception_messages(exc: Exception, limit: int = 6) -> list[str]:
    """Collect concise messages from nested exceptions / exception groups."""
    seen = set()
    messages: list[str] = []

    def _add(message: str):
        text = (message or "").strip()
        if not text:
            return
        if text in seen:
            return
        seen.add(text)
        messages.append(text)

    def _walk(err, depth: int = 0):
        if err is None or len(messages) >= limit or depth > 8:
            return

        _add(f"{type(err).__name__}: {err}")

        if hasattr(err, "exceptions"):
            for inner in getattr(err, "exceptions", []) or []:
                _walk(inner, depth + 1)

        _walk(getattr(err, "__cause__", None), depth + 1)
        _walk(getattr(err, "__context__", None), depth + 1)

    _walk(exc)
    return messages


def _format_agent_error_message(
    llm_endpoint: str,
    ollama_base_url: str | None,
    messages: list[str],
) -> str:
    """Build user-facing error text with provider-specific guidance."""
    if llm_endpoint == "ollama":
        connection_markers = [
            "APIConnectionError",
            "ConnectError",
            "Connection error",
            "Name or service not known",
            "Temporary failure in name resolution",
            "Connection refused",
            "timed out",
        ]
        if any(any(marker in msg for marker in connection_markers) for msg in messages):
            endpoint = ollama_base_url or OLLAMA_BASE_URL
            return (
                "Agent Error: Could not reach Ollama endpoint "
                f"`{endpoint}`. Check Settings -> Ollama Endpoint URL and ensure the host is reachable from the API pod."
            )

    if messages:
        return f"Agent Error: {'; '.join(messages[:3])}"
    return "Agent Error: Unknown error while running the agent loop."


def _latest_user_message(messages) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return (message.get("content") or "").lower()
    return ""


def _should_prefetch_recent_articles(user_message: str) -> bool:
    prompt = (user_message or "").lower()
    trigger_terms = [
        "latest",
        "recent",
        "currently",
        "news",
        "headlines",
        "what is happening",
        "what's happening",
        "where is",
    ]
    return any(term in prompt for term in trigger_terms)


async def _prefetch_recent_articles_context(session, messages, userspace_id, user_message):
    statuses = []

    async def _call_tool(tool_name, args, context_title):
        try:
            if userspace_id:
                args["userspace"] = userspace_id
            result = await session.call_tool(tool_name, args)
            result_text = result.content[0].text if result.content else "[]"
            messages.append(
                {
                    "role": "system",
                    "content": f"Tool context from {context_title} (JSON):\n{result_text[:8000]}",
                }
            )
            statuses.append((tool_name, "ok", None))
        except Exception as exc:
            logger.warning(f"Prefetch {tool_name} failed: {exc}")
            statuses.append((tool_name, "error", str(exc)))

    await _call_tool("get_recent_articles", {"limit": 20}, "get_recent_articles")
    await _call_tool(
        "search_articles",
        {"query": user_message, "limit": 20},
        "search_articles",
    )
    return statuses


def _record_tool_trace(
    trace: dict,
    name: str,
    status: str,
    arguments: str | None = None,
    error: str | None = None,
):
    entry = {"name": name, "status": status}
    if arguments:
        entry["arguments"] = arguments
    if error:
        entry["error"] = error
    trace["tool_calls"].append(entry)
    if status == "error":
        trace["tool_execution_errors"] += 1


def _has_recent_articles_tool_result(messages) -> bool:
    for message in messages:
        if message.get("role") == "tool" and message.get("name") == "get_recent_articles":
            return True
    return False


def _should_force_recent_articles(messages, assistant_content: str) -> bool:
    user_text = _latest_user_message(messages)
    if not user_text:
        return False

    news_intent_terms = [
        "latest",
        "recent",
        "currently",
        "news",
        "headlines",
        "what is happening",
        "what's happening",
        "where is",
    ]
    no_data_terms = [
        "don't have access",
        "do not have access",
        "real-time",
        "cannot provide current",
        "no recent articles",
    ]

    has_news_intent = any(term in user_text for term in news_intent_terms)
    returned_no_data = any(term in assistant_content.lower() for term in no_data_terms)

    return has_news_intent and returned_no_data and not _has_recent_articles_tool_result(messages)


def _create_get_recent_articles_call():
    tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
    mock_call = SimpleNamespace(
        id=tool_call_id,
        function=SimpleNamespace(name="get_recent_articles", arguments=json.dumps({"limit": 20})),
        type="function",
    )
    mock_data = {
        "id": tool_call_id,
        "type": "function",
        "function": {"name": "get_recent_articles", "arguments": json.dumps({"limit": 20})},
    }
    return mock_call, mock_data


def _truncate_text(value, max_length=240):
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _safe_text(value, max_length=240):
    return _truncate_text(bleach.clean(str(value or ""), strip=True), max_length)


def _build_article_context_lines(entity_data):
    title = _safe_text(entity_data.get("title", "Untitled article"), 240)
    published = _safe_text(entity_data.get("published", ""), 80)
    source = _safe_text(
        entity_data.get("feed_title") or entity_data.get("feed_url") or entity_data.get("source") or "",
        160,
    )
    language = _safe_text(entity_data.get("language", ""), 32)
    summary = _safe_text(
        entity_data.get("description") or entity_data.get("summary") or entity_data.get("content") or "",
        480,
    )

    issue_names = []
    for issue in entity_data.get("issues") or []:
        if isinstance(issue, dict) and issue.get("logos"):
            issue_names.append(_safe_text(issue.get("logos"), 120))

    lines = [
        f"Article title: {title}",
        f"Article published: {published or 'unknown'}",
        f"Article source: {source or 'unknown'}",
        f"Article language: {language or 'unknown'}",
        f"Article summary: {summary or 'none'}",
    ]
    if issue_names:
        lines.append(f"Currently linked issues: {', '.join(issue_names[:8])}")
    else:
        lines.append("Currently linked issues: none")
    return lines


def _build_issue_context_lines(entity_data):
    logos = _safe_text(entity_data.get("logos", "Untitled issue"), 240)
    description = _safe_text(entity_data.get("description", ""), 480)
    longevity = _safe_text(entity_data.get("longevity", ""), 32)
    status = _safe_text(entity_data.get("status", ""), 32)
    premises = entity_data.get("premises")
    premises_count = len(premises) if isinstance(premises, list) else 0
    return [
        f"Issue logos: {logos}",
        f"Issue description: {description or 'none'}",
        f"Issue longevity: {longevity or 'unknown'}",
        f"Issue status: {status or 'unknown'}",
        f"Issue premises_count: {premises_count}",
    ]


def _build_feed_context_lines(entity_data):
    title = _safe_text(entity_data.get("title") or entity_data.get("url") or "Untitled feed", 240)
    url = _safe_text(entity_data.get("url", ""), 240)
    category = _safe_text(entity_data.get("category", ""), 80)
    last_fetch = _safe_text(entity_data.get("last_fetch_at", ""), 80)
    return [
        f"Feed title: {title}",
        f"Feed url: {url or 'unknown'}",
        f"Feed category: {category or 'unknown'}",
        f"Feed last_fetch_at: {last_fetch or 'unknown'}",
    ]


CONTEXT_LINE_BUILDERS = {
    "article": _build_article_context_lines,
    "issue": _build_issue_context_lines,
    "feed": _build_feed_context_lines,
}


def _build_context_preamble(context):
    if not isinstance(context, dict):
        return ""

    context_type = str(context.get("type") or "").strip().lower()
    entity_id = context.get("entity_id") or ""
    entity_data = context.get("entity_data")

    line_builder = CONTEXT_LINE_BUILDERS.get(context_type)
    if line_builder is None or not isinstance(entity_data, dict):
        return ""

    lines = [
        "You are in a contextual chat session.",
        f"Context type: {context_type}",
    ]

    if entity_id:
        lines.append(f"Context entity_id: {_safe_text(entity_id, 120)}")

    lines.extend(line_builder(entity_data))

    lines.append(
        "Use this context to ground your response and actions. If asked to create/update issues, call tools explicitly."
    )
    return "\n".join(lines)


def _derive_context_session_title(context, fallback_title="New Chat"):
    if not isinstance(context, dict):
        return fallback_title

    context_type = str(context.get("type") or "").strip().lower()
    entity_data = context.get("entity_data")
    if context_type not in {"article", "issue", "feed"} or not isinstance(entity_data, dict):
        return fallback_title

    if context_type == "article":
        label = "Article"
        name = entity_data.get("title") or "Untitled"
    elif context_type == "issue":
        label = "Issue"
        name = entity_data.get("logos") or "Untitled"
    else:
        label = "Feed"
        name = entity_data.get("title") or entity_data.get("url") or "Untitled"

    return f"{label}: {_safe_text(name, 80)}"


def run_agent_sync(
    user_message,
    history,
    userspace_id,
    context=None,
    model=None,
    llm_endpoint=None,
    api_key=None,
    ollama_base_url=None,
    auth_token=None,
):
    return asyncio.run(
        run_agent(
            user_message,
            history,
            userspace_id,
            context,
            model,
            llm_endpoint,
            api_key,
            ollama_base_url,
            auth_token,
        )
    )


async def run_agent(
    user_message,
    history,
    userspace_id,
    context=None,
    model=None,
    llm_endpoint=None,
    api_key=None,
    ollama_base_url=None,
    auth_token=None,
):
    # Limit history to prevent token overflow
    if len(history) > CHAT_HISTORY_LIMIT:
        history = history[-CHAT_HISTORY_LIMIT:]

    messages = list(history)

    # System prompt
    _ensure_system_message(messages)

    context_preamble = _build_context_preamble(context)
    if context_preamble:
        messages.insert(1, {"role": "system", "content": context_preamble})

    messages.append({"role": "user", "content": user_message})

    # Determine API Key based on provider if not passed in headers
    final_api_key = _get_api_key(llm_endpoint, api_key)

    llm_provider = llm_provider_factory.get_provider(
        llm_endpoint, final_api_key, ollama_base_url or OLLAMA_BASE_URL
    )

    target_model = model or MODEL_NAME

    trace = {"tool_calls": [], "tool_execution_errors": 0}

    try:
        # Connect to MCP Server
        # Force Host header to localhost to bypass TrustedHostMiddleware in FastMCP
        headers = {"Host": "localhost:8090"}
        if auth_token:
            headers["Authorization"] = auth_token

        # Create async HTTP client factory for proper DNS resolution in Kubernetes
        async with sse_client(
            MCP_SERVER_URL, headers=headers, httpx_client_factory=_create_http_client
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # List Tools
                mcp_tools = await session.list_tools()
                openai_tools = _convert_to_openai_tools(mcp_tools)

                if _should_prefetch_recent_articles(user_message):
                    prefetch_statuses = await _prefetch_recent_articles_context(
                        session, messages, userspace_id, user_message
                    )
                    for name, status, error in prefetch_statuses:
                        _record_tool_trace(trace, name, status, error)

                final_response = await _run_agent_loop(
                    messages,
                    llm_provider,
                    target_model,
                    openai_tools,
                    session,
                    userspace_id,
                    trace,
                )
                return {
                    "response": final_response,
                    "tool_calls": trace["tool_calls"],
                    "tool_execution_errors": trace["tool_execution_errors"],
                }

    except Exception as e:
        logger.error("Error running agent loop", exc_info=True)
        error_msgs = _flatten_exception_messages(e)
        response_text = _format_agent_error_message(llm_endpoint, ollama_base_url, error_msgs)
        return {
            "response": response_text,
            "tool_calls": trace["tool_calls"],
            "tool_execution_errors": trace["tool_execution_errors"],
        }


@chat_blueprint.route("/models", methods=["GET"])
@jwt_required
def list_models():
    llm_endpoint = request.args.get("llm_endpoint")

    # Get API key from user settings if available
    user = fetch_from_couchdb("users", g.user_id)
    user_settings = user.get("settings", {}) if user else {}

    api_key = None
    if llm_endpoint == "openai":
        api_key = user_settings.get("moirai_openai_api_key")
    elif llm_endpoint == "gemini":
        api_key = user_settings.get("moirai_gemini_api_key")

    # Fallback to headers (or env vars in _get_api_key)
    if not api_key:
        api_key = request.headers.get("x-openai-api-key")
    if not api_key:
        api_key = request.headers.get("x-gemini-api-key")

    ollama_base_url = user_settings.get(
        "moirai_ollama_endpoint_url"
    ) or request.headers.get("x-ollama-base-url")

    # Determine API Key based on provider if not passed
    final_api_key = _get_api_key(llm_endpoint, api_key)

    llm_provider = llm_provider_factory.get_provider(
        llm_endpoint, final_api_key, ollama_base_url or OLLAMA_BASE_URL
    )
    try:
        model_names = llm_provider.list_models()
        return jsonify(model_names)
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return jsonify({"error": str(e)}), 500


@chat_blueprint.route("/chat", methods=["POST"])
@jwt_required
def chat():
    data = request.json
    user_message = data.get("message")
    history = data.get("history", [])
    context = data.get("context")
    model = data.get("model")
    llm_endpoint = data.get("llm_endpoint") or DEFAULT_LLM_PROVIDER

    # Get user settings
    user = fetch_from_couchdb("users", g.user_id)
    user_settings = user.get("settings", {}) if user else {}

    api_key = None
    if llm_endpoint == "openai":
        api_key = user_settings.get("moirai_openai_api_key")
    elif llm_endpoint == "gemini":
        api_key = user_settings.get("moirai_gemini_api_key")

    # Fallback
    if not api_key:
        api_key = request.headers.get("x-openai-api-key")
    if not api_key:
        api_key = request.headers.get("x-gemini-api-key")

    api_key = _get_api_key(llm_endpoint, api_key)

    if llm_endpoint in {"openai", "gemini"} and not api_key:
        return (
            jsonify(
                {
                    "response": (
                        f"Error: Missing API key for provider '{llm_endpoint}'. "
                        "Add it in Settings or send it in request headers."
                    )
                }
            ),
            400,
        )

    ollama_base_url = user_settings.get(
        "moirai_ollama_endpoint_url"
    ) or request.headers.get("x-ollama-base-url")

    auth_token = request.headers.get("Authorization")

    request_started = time.perf_counter()

    try:
        response = run_agent_sync(
            user_message,
            history,
            g.user_id,
            context,
            model,
            llm_endpoint,
            api_key,
            ollama_base_url,
            auth_token,
        )
        elapsed_ms = int((time.perf_counter() - request_started) * 1000)
        if isinstance(response, dict):
            response["timing_ms"] = elapsed_ms
            return jsonify(response)
        return jsonify(
            {
                "response": response,
                "tool_calls": [],
                "tool_execution_errors": 0,
                "timing_ms": elapsed_ms,
            }
        )
    except Exception as exc:
        logger.error("Error in /api/chat", exc_info=True)
        elapsed_ms = int((time.perf_counter() - request_started) * 1000)
        return jsonify({"response": f"Error: {str(exc)}", "timing_ms": elapsed_ms}), 500


@chat_blueprint.route("/chat/history", methods=["GET"])
@jwt_required
def list_chat_history():
    # Filter by user_id
    history = query_couchdb("chat_history", {"user_id": g.user_id})
    return jsonify(history)


@chat_blueprint.route("/chat/history/<session_id>", methods=["GET"])
@jwt_required
def get_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description=CHAT_SESSION_NOT_FOUND)

    # Check ownership
    if session.get("user_id") != g.user_id:
        abort(403, description=ERROR_ACCESS_DENIED)

    return jsonify(session)


@chat_blueprint.route("/chat/history", methods=["POST"])
@jwt_required
def create_chat_session():
    data = request.json
    context = data.get("context")
    title = _derive_context_session_title(context, data.get("title", "New Chat"))
    session_id = str(uuid.uuid4())
    session = {
        "_id": session_id,
        "user_id": g.user_id,
        "title": title,
        "messages": [],
        "model": data.get("model"),
        "llm_endpoint": data.get("llm_endpoint"),
        "context": context if isinstance(context, dict) else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if update_couchdb_doc("chat_history", session_id, session):
        return jsonify(session)
    else:
        abort(500, description="Failed to create chat session")


@chat_blueprint.route("/chat/history/<session_id>", methods=["PUT"])
@jwt_required
def update_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description=CHAT_SESSION_NOT_FOUND)

    if session.get("user_id") != g.user_id:
        abort(403, description=ERROR_ACCESS_DENIED)

    data = request.json

    # Update fields if provided
    if "messages" in data:
        session["messages"] = data["messages"]
    if "model" in data:
        session["model"] = data["model"]
    if "llm_endpoint" in data:
        session["llm_endpoint"] = data["llm_endpoint"]
    if "title" in data:
        session["title"] = data["title"]
    if "context" in data:
        session["context"] = data["context"] if isinstance(data["context"], dict) else None

    if update_couchdb_doc("chat_history", session_id, session):
        return jsonify(session)
    else:
        abort(500, description="Failed to update chat session")


def _format_export_message(msg, verbose_export):
    sanitized_msg = _sanitize_export_value(msg)
    role = sanitized_msg.get("role", "unknown").capitalize()
    content = sanitized_msg.get("content", "")
    
    if isinstance(content, str):
        content = bleach.clean(content, strip=True)
        content = content.replace("\n### ", "\n\\#\\#\\# ")
        if content.startswith("### "):
            content = "\\#\\#\\# " + content[4:]
            
    markdown_chunk = f"### {role}\n{content}\n\n"
    
    tool_calls = sanitized_msg.get("tool_calls")
    tool_count = len(tool_calls) if tool_calls else 0
    error_count = 1 if sanitized_msg.get("role") == "tool" and isinstance(content, str) and "Tool Execution Error" in content else 0
    
    if tool_calls and verbose_export:
        markdown_chunk += "*(Tool Calls)*\n"
        markdown_chunk += _format_tool_call_markdown(tool_calls)
        markdown_chunk += "\n\n"
        
    if verbose_export:
        markdown_chunk += "*(Message Metadata)*\n```json\n"
        markdown_chunk += json.dumps(sanitized_msg, indent=2, default=str)
        markdown_chunk += "\n```\n\n"
        
    return markdown_chunk, tool_count, error_count

@chat_blueprint.route("/chat/history/<session_id>/export", methods=["GET"])
@jwt_required
def export_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description=CHAT_SESSION_NOT_FOUND)

    if session.get("user_id") != g.user_id:
        abort(403, description=ERROR_ACCESS_DENIED)

    config_doc = fetch_from_couchdb("config", "main")
    verbose_export = _is_verbose_chat_export_enabled(config_doc)

    title = session.get("title", "Untitled Chat")
    safe_title = re.sub(r"[^a-zA-Z0-9_\-]", "_", title)
    messages = session.get("messages", [])
    model = session.get("model", "Unknown")
    llm_endpoint = session.get("llm_endpoint", "Unknown")

    markdown_content = f"# {title}\n\n"
    markdown_content += f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    markdown_content += f"Provider: {llm_endpoint}\n"
    markdown_content += f"Model: {model}\n\n"
    markdown_content += f"Verbose Export: {'enabled' if verbose_export else 'disabled'}\n\n"
    markdown_content += "---\n\n"

    tool_call_total = 0
    tool_error_total = 0

    for msg in messages:
        chunk, t_count, e_count = _format_export_message(msg, verbose_export)
        markdown_content += chunk
        tool_call_total += t_count
        tool_error_total += e_count

    if verbose_export:
        markdown_content += "---\n\n"
        markdown_content += "## Agent Trace Summary\n"
        markdown_content += f"- Total messages: {len(messages)}\n"
        markdown_content += f"- Tool calls requested: {tool_call_total}\n"
        markdown_content += f"- Tool execution errors: {tool_error_total}\n\n"

    markdown_content = _strip_internal_reminders(markdown_content)

    from flask import Response

    return Response(
        markdown_content,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment;filename={safe_title}.md"},
    )

@chat_blueprint.route("/chat/history/<session_id>", methods=["DELETE"])
@jwt_required
def delete_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description=CHAT_SESSION_NOT_FOUND)

    if session.get("user_id") != g.user_id:
        abort(403, description=ERROR_ACCESS_DENIED)

    if delete_from_couchdb("chat_history", session_id, session["_rev"]):
        return jsonify({"status": "deleted"})
    else:
        abort(500, description="Failed to delete chat session")


async def _run_agent_turn(
    messages, llm_provider, target_model, openai_tools, session, userspace_id, trace
):
    # Filter messages to ensure clean JSON for API
    clean_messages = []
    for m in messages:
        # Exclude 'tool_calls' if it's None to avoid validation errors in some clients
        clean_m = {k: v for k, v in m.items() if v is not None}
        # Also handle tool_calls in history correctly if they are SimpleNamespace (mock objects)
        clean_messages.append(clean_m)

    response = llm_provider.create_chat_completion(
        messages=clean_messages,
        model=target_model,
        tools=openai_tools if openai_tools else None,
        tool_choice="auto" if openai_tools else None,
    )

    response_message = response.choices[0].message
    logger.debug(f"Model Raw Response Content: {response_message.content}")

    # Store message in history
    sanitized_content = _strip_internal_reminders(response_message.content or "")

    msg_dict = {
        "role": response_message.role,
        "content": sanitized_content,
        "tool_calls": response_message.tool_calls,
    }
    messages.append(msg_dict)

    tool_calls = response_message.tool_calls or []

    # Fallback: Check content for leaked JSON tool calls
    if not tool_calls and sanitized_content:
        extracted = extract_tool_calls_from_content(sanitized_content)
        if extracted:
            tool_calls, mock_tool_calls_data = _create_mock_tool_calls(extracted)
            msg_dict["tool_calls"] = mock_tool_calls_data

    if tool_calls:
        await _execute_tool_calls(session, tool_calls, messages, userspace_id, trace)
        return None  # Continue loop
    else:
        if _should_force_recent_articles(messages, sanitized_content):
            forced_call, forced_call_data = _create_get_recent_articles_call()
            msg_dict["tool_calls"] = [forced_call_data]
            await _execute_tool_calls(session, [forced_call], messages, userspace_id, trace)
            return None
        # Final response
        return sanitized_content


def _create_http_client(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    """Custom factory that creates AsyncClient for proper DNS resolution"""
    if timeout is None:
        # Very generous timeout for slow LLMs with multi-turn tool calls (10 minutes)
        timeout = httpx.Timeout(LLM_TIMEOUT_SECONDS)
    return httpx.AsyncClient(
        headers=headers, timeout=timeout, auth=auth, follow_redirects=True
    )


def _ensure_system_message(messages):
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] += f"\n\n{SYSTEM_PROMPT}"
    else:
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})


def _create_mock_tool_calls(extracted_tools):
    tool_calls = []
    mock_tool_calls_data = []

    for ext in extracted_tools:
        mock_id = f"call_{uuid.uuid4().hex[:8]}"
        mock_call = SimpleNamespace(
            id=mock_id,
            function=SimpleNamespace(
                name=ext["name"], arguments=json.dumps(ext["parameters"])
            ),
            type="function",
        )
        tool_calls.append(mock_call)

        mock_tool_calls_data.append(
            {
                "id": mock_id,
                "type": "function",
                "function": {
                    "name": ext["name"],
                    "arguments": json.dumps(ext["parameters"]),
                },
            }
        )
    return tool_calls, mock_tool_calls_data


async def _execute_tool_calls(session, tool_calls, messages, userspace_id, trace):
    for tool_call in tool_calls:
        func_name = tool_call.function.name
        func_args = json.loads(tool_call.function.arguments)

        # Inject userspace_id if not already present
        if userspace_id and "userspace" not in func_args:
            func_args["userspace"] = userspace_id

        args_for_trace = json.dumps(func_args, ensure_ascii=True, sort_keys=True)

        try:
            logger.info(f"Agent calling tool: {func_name} with args: {func_args}")
            result = await session.call_tool(func_name, func_args)
            result_text = result.content[0].text if result.content else "Success"
            logger.debug(f"Tool result (truncated): {result_text[:200]}...")

            result_is_error = bool(getattr(result, "isError", False))
            if not result_is_error and result_text.strip().lower().startswith("error"):
                result_is_error = True

            if result_is_error:
                _record_tool_trace(
                    trace,
                    func_name,
                    "error",
                    arguments=args_for_trace,
                    error=result_text[:500],
                )
            else:
                _record_tool_trace(trace, func_name, "ok", arguments=args_for_trace)
        except Exception as tool_err:
            result_text = f"Tool Execution Error: {tool_err}"
            logger.error(f"Tool Error: {tool_err}")
            _record_tool_trace(
                trace,
                func_name,
                "error",
                arguments=args_for_trace,
                error=str(tool_err),
            )

        messages.append(
            {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": func_name,
                "content": result_text,
            }
        )


def _get_api_key(llm_endpoint, header_api_key):
    if header_api_key:
        return header_api_key

    if llm_endpoint == "gemini":
        return GEMINI_API_KEY
    elif llm_endpoint == "openai":
        return OPENAI_API_KEY
    return ""


def _convert_to_openai_tools(mcp_tools):
    openai_tools = []
    for tool in mcp_tools.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
        )
    return openai_tools


async def _run_agent_loop(
    messages, llm_provider, target_model, openai_tools, session, userspace_id, trace
):
    for _ in range(MAX_AGENT_TURNS):
        result = await _run_agent_turn(
            messages, llm_provider, target_model, openai_tools, session, userspace_id, trace
        )
        if result:
            return result

    last_tool_name = None
    for msg in reversed(messages):
        if msg.get("role") == "tool" and msg.get("name"):
            last_tool_name = msg.get("name")
            break

    if last_tool_name:
        return (
            "I hit the agent turn limit while repeatedly using tool "
            f"`{last_tool_name}`. The conversation is saved, so you can continue in Chat and I can finish there."
        )

    return "I hit the agent turn limit before producing a final answer. The conversation is saved, so you can continue in Chat."
