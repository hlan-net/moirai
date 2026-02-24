import re
import uuid
import logging
import asyncio
import os  # Re-added
import json  # Re-added
from datetime import datetime, timezone  # Re-added
from types import SimpleNamespace
from flask import Blueprint, request, jsonify, abort, g
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
import httpx  # Moved import to top

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
MAX_AGENT_TURNS = 5
LLM_TIMEOUT_SECONDS = 600.0

CHAT_HISTORY_LIMIT = 6
MAX_AGENT_TURNS = 5
LLM_TIMEOUT_SECONDS = 600.0
CHAT_SESSION_NOT_FOUND = "Chat session not found"
ERROR_ACCESS_DENIED = "Access denied"

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


def run_agent_sync(
    user_message,
    history,
    userspace_id,
    model=None,
    llm_endpoint=None,
    api_key=None,
    ollama_base_url=None,
):
    return asyncio.run(
        run_agent(
            user_message,
            history,
            userspace_id,
            model,
            llm_endpoint,
            api_key,
            ollama_base_url,
        )
    )


async def run_agent(
    user_message,
    history,
    userspace_id,
    model=None,
    llm_endpoint=None,
    api_key=None,
    ollama_base_url=None,
):
    # Limit history to prevent token overflow
    if len(history) > CHAT_HISTORY_LIMIT:
        history = history[-CHAT_HISTORY_LIMIT:]

    messages = list(history)

    # System prompt
    _ensure_system_message(messages)

    messages.append({"role": "user", "content": user_message})

    # Determine API Key based on provider if not passed in headers
    final_api_key = _get_api_key(llm_endpoint, api_key)

    llm_provider = llm_provider_factory.get_provider(
        llm_endpoint, final_api_key, ollama_base_url or OLLAMA_BASE_URL
    )

    target_model = model or MODEL_NAME

    try:
        # Connect to MCP Server
        # Force Host header to localhost to bypass TrustedHostMiddleware in FastMCP
        headers = {"Host": "localhost:8090"}

        # Create async HTTP client factory for proper DNS resolution in Kubernetes
        async with sse_client(
            MCP_SERVER_URL, headers=headers, httpx_client_factory=_create_http_client
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # List Tools
                mcp_tools = await session.list_tools()
                openai_tools = _convert_to_openai_tools(mcp_tools)

                return await _run_agent_loop(
                    messages,
                    llm_provider,
                    target_model,
                    openai_tools,
                    session,
                    userspace_id,
                )

    except Exception as e:
        logger.error("Error running agent loop", exc_info=True)

        # Unwrap ExceptionGroup if present (common in anyio/asyncio)
        if hasattr(e, "exceptions"):
            error_msgs = []
            for exc in e.exceptions:
                error_msgs.append(str(exc))
            return f"Agent Error: {'; '.join(error_msgs)}"

        return f"System Error: {str(e)}"


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

    ollama_base_url = user_settings.get(
        "moirai_ollama_endpoint_url"
    ) or request.headers.get("x-ollama-base-url")

    response = run_agent_sync(
        user_message, history, g.user_id, model, llm_endpoint, api_key, ollama_base_url
    )
    return jsonify({"response": response})


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
    title = data.get("title", "New Chat")
    session_id = str(uuid.uuid4())
    session = {
        "_id": session_id,
        "user_id": g.user_id,
        "title": title,
        "messages": [],
        "model": data.get("model"),
        "llm_endpoint": data.get("llm_endpoint"),
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

    if update_couchdb_doc("chat_history", session_id, session):
        return jsonify(session)
    else:
        abort(500, description="Failed to update chat session")


@chat_blueprint.route("/chat/history/<session_id>/export", methods=["GET"])
@jwt_required
def export_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description=CHAT_SESSION_NOT_FOUND)

    if session.get("user_id") != g.user_id:
        abort(403, description=ERROR_ACCESS_DENIED)

    title = session.get("title", "Untitled Chat")
    safe_title = re.sub(r"[^a-zA-Z0-9_\-]", "_", title)
    messages = session.get("messages", [])
    model = session.get("model", "Unknown")
    llm_endpoint = session.get("llm_endpoint", "Unknown")

    markdown_content = f"# {title}\n\n"
    markdown_content += f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    markdown_content += f"Provider: {llm_endpoint}\n"
    markdown_content += f"Model: {model}\n\n"
    markdown_content += "---\n\n"

    for msg in messages:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "")
        markdown_content += f"### {role}\n{content}\n\n"

        # Include tool calls if present (for debugging context)
        if "tool_calls" in msg and msg["tool_calls"]:
            markdown_content += "*(Tool Calls)*\n```json\n"
            markdown_content += json.dumps(msg["tool_calls"], indent=2)
            markdown_content += "\n```\n\n"

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
    messages, llm_provider, target_model, openai_tools, session, userspace_id
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
    msg_dict = {
        "role": response_message.role,
        "content": response_message.content,
        "tool_calls": response_message.tool_calls,
    }
    messages.append(msg_dict)

    tool_calls = response_message.tool_calls or []

    # Fallback: Check content for leaked JSON tool calls
    if not tool_calls and response_message.content:
        extracted = extract_tool_calls_from_content(response_message.content)
        if extracted:
            tool_calls, mock_tool_calls_data = _create_mock_tool_calls(extracted)
            msg_dict["tool_calls"] = mock_tool_calls_data

    if tool_calls:
        await _execute_tool_calls(session, tool_calls, messages, userspace_id)
        return None  # Continue loop
    else:
        # Final response
        return response_message.content


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


async def _execute_tool_calls(session, tool_calls, messages, userspace_id):
    # Get admin password for MCP tool authentication
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        logger.error(
            "ADMIN_PASSWORD environment variable not set - MCP tool calls will fail"
        )

    for tool_call in tool_calls:
        func_name = tool_call.function.name
        func_args = json.loads(tool_call.function.arguments)

        # Inject api_key for MCP tool authentication if not already present
        if admin_password and "api_key" not in func_args:
            func_args["api_key"] = admin_password

        # Inject userspace_id if not already present
        if userspace_id and "userspace" not in func_args:
            func_args["userspace"] = userspace_id

        try:
            logger.info(f"Agent calling tool: {func_name} with args: {func_args}")
            result = await session.call_tool(func_name, func_args)
            result_text = result.content[0].text if result.content else "Success"
            logger.debug(f"Tool result (truncated): {result_text[:200]}...")
        except Exception as tool_err:
            result_text = f"Tool Execution Error: {tool_err}"
            logger.error(f"Tool Error: {tool_err}")

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
    messages, llm_provider, target_model, openai_tools, session, userspace_id
):
    for _ in range(MAX_AGENT_TURNS):
        result = await _run_agent_turn(
            messages, llm_provider, target_model, openai_tools, session, userspace_id
        )
        if result:
            return result
    return "Agent max turns reached without final answer."
