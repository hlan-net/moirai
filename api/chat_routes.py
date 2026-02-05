import re
import uuid
from types import SimpleNamespace
from flask import Blueprint, request, jsonify, abort
import os
import json
import asyncio
from datetime import datetime
from mcp import ClientSession
from mcp.client.sse import sse_client
from .llm.factory import LLMProviderFactory
from .db import fetch_from_couchdb, update_couchdb_doc, delete_from_couchdb

chat_blueprint = Blueprint('chat', __name__)

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:8090/sse")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.1")

CHAT_HISTORY_LIMIT = 6
MAX_AGENT_TURNS = 5
LLM_TIMEOUT_SECONDS = 600.0

llm_provider_factory = LLMProviderFactory()

def extract_tool_calls_from_content(content):
    if not content: return []
    tools = []
    # Find all JSON-like blocks. 
    # We look for something starting with { and ending with } that contains "name" and "parameters"
    # Use non-greedy matching .*? to find multiple separate JSON blocks
    matches = re.findall(r'(\{[^{}]*?"name"\s*:\s*".*?".*?"parameters"\s*:\s*\{.*?\}.*?\})', content, re.DOTALL)
    
    for match in matches:
        try:
            data = json.loads(match)
            if "name" in data and "parameters" in data:
                tools.append(data)
        except Exception:
            continue
    
    return tools

def run_agent_sync(user_message, history, model=None, llm_endpoint=None, api_key=None, ollama_base_url=None):
    return asyncio.run(run_agent(user_message, history, model, llm_endpoint, api_key, ollama_base_url))

async def run_agent(user_message, history, model=None, llm_endpoint=None, api_key=None, ollama_base_url=None):
    # Limit history to prevent token overflow
    if len(history) > CHAT_HISTORY_LIMIT:
        history = history[-CHAT_HISTORY_LIMIT:]
    
    messages = list(history)
    
    # System prompt
    system_prompt = (
        "You are Moirai, a GenAI-native press review agent. "
        "You DO NOT have access to real-time information or the internet directly. "
        "You MUST use the provided tools (like `list_feeds`, `read_feed`, `list_articles`) to fetch any news or external data. "
        "Do not hallucinate headlines. If you need news, CALL A TOOL. "
        "When asked for recent articles or news, use `list_articles` to see what's already in the database. "
        "To fetch fresh articles from a specific feed, use `read_feed` with the feed URL. "
        "To see available feeds, use `list_feeds`. "
        "Some reliable Linux news feeds are: LWN (https://lwn.net/headlines/rss), Phoronix (https://www.phoronix.com/phoronix-rss.php), "
        "and Kernel.org (https://www.kernel.org/feeds/kall.xml)."
    )
    
    # Check if there is already a system message, if so append, otherwise insert
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] += f"\n\n{system_prompt}"
    else:
        messages.insert(0, {"role": "system", "content": system_prompt})
            
    messages.append({"role": "user", "content": user_message})

    llm_provider = llm_provider_factory.get_provider(llm_endpoint, api_key or OPENAI_API_KEY, ollama_base_url or OLLAMA_BASE_URL)
    
    target_model = model or MODEL_NAME

    try:
        # Connect to MCP Server
        # Force Host header to localhost to bypass TrustedHostMiddleware in FastMCP
        headers = {"Host": "localhost:8090"}
        
        # Create async HTTP client factory for proper DNS resolution in Kubernetes
        import httpx
        def async_http_client_factory(
            headers: dict[str, str] | None = None,
            timeout: httpx.Timeout | None = None,
            auth: httpx.Auth | None = None
        ) -> httpx.AsyncClient:
            """Custom factory that creates AsyncClient for proper DNS resolution"""
            if timeout is None:
                # Very generous timeout for slow LLMs with multi-turn tool calls (10 minutes)
                timeout = httpx.Timeout(600.0) # TODO: Use a constant
            return httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                auth=auth,
                follow_redirects=True
            )
        
        async with sse_client(MCP_SERVER_URL, headers=headers, httpx_client_factory=async_http_client_factory) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List Tools
                mcp_tools = await session.list_tools()
                openai_tools = []
                for tool in mcp_tools.tools:
                     openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema
                        }
                    })

                for _ in range(MAX_AGENT_TURNS):
                    # Filter messages to ensure clean JSON for API
                    clean_messages = []
                    for m in messages:
                        # Exclude 'tool_calls' if it's None to avoid validation errors in some clients
                        clean_m = {k: v for k, v in m.items() if v is not None}
                        # Also handle tool_calls in history correctly if they are SimpleNamespace (mock objects)
                        # The OpenAI client expects dicts or Pydantic models. 
                        # We stored them as dicts in history below, so this should be fine.
                        clean_messages.append(clean_m)

                    response = llm_provider.create_chat_completion(
                        messages=clean_messages,
                        model=target_model,
                        tools=openai_tools if openai_tools else None,
                        tool_choice="auto" if openai_tools else None
                    )
                    
                    response_message = response.choices[0].message
                    print(f"DEBUG: Model Raw Response Content: {response_message.content}")
                    
                    # Store message in history
                    msg_dict = {
                        "role": response_message.role,
                        "content": response_message.content,
                        "tool_calls": response_message.tool_calls
                    }
                    messages.append(msg_dict)
                    
                    tool_calls = response_message.tool_calls or []
                    
                    # Fallback: Check content for leaked JSON tool calls
                    if not tool_calls and response_message.content:
                        extracted = extract_tool_calls_from_content(response_message.content)
                        if extracted:
                            tool_calls = []
                            msg_dict["tool_calls"] = []
                            for ext in extracted:
                                # Create a mock tool call compatible with the loop below
                                mock_id = f"call_{uuid.uuid4().hex[:8]}"
                                mock_call = SimpleNamespace(
                                    id=mock_id,
                                    function=SimpleNamespace(
                                        name=ext["name"],
                                        arguments=json.dumps(ext["parameters"])
                                    ),
                                    type="function"
                                )
                                tool_calls.append(mock_call)
                                
                                # Update history for API compatibility
                                msg_dict["tool_calls"].append({
                                    "id": mock_id,
                                    "type": "function",
                                    "function": {
                                        "name": ext["name"],
                                        "arguments": json.dumps(ext["parameters"])
                                    }
                                })

                    if tool_calls:
                        for tool_call in tool_calls:
                            func_name = tool_call.function.name
                            func_args = json.loads(tool_call.function.arguments)
                            
                            # Execute via MCP
                            try:
                                print(f"Agent calling tool: {func_name} with args: {func_args}")
                                result = await session.call_tool(func_name, func_args)
                                result_text = result.content[0].text if result.content else "Success"
                                print(f"Tool result (truncated): {result_text[:200]}...")
                            except Exception as tool_err:
                                result_text = f"Tool Execution Error: {tool_err}"
                                print(f"Tool Error: {tool_err}")

                            messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": func_name,
                                "content": result_text
                            })
                    else:
                        # Final response
                        return response_message.content
                        
                return "Agent max turns reached without final answer."

    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # Unwrap ExceptionGroup if present (common in anyio/asyncio)
        if hasattr(e, 'exceptions'):
            error_msgs = []
            for exc in e.exceptions:
                error_msgs.append(str(exc))
            return f"Agent Error: {'; '.join(error_msgs)}"
            
        return f"System Error: {str(e)}"

@chat_blueprint.route("/models", methods=["GET"])
def list_models():
    llm_endpoint = request.args.get('llm_endpoint')
    api_key = request.headers.get('x-openai-api-key')
    ollama_base_url = request.headers.get('x-ollama-base-url')
    llm_provider = llm_provider_factory.get_provider(llm_endpoint, api_key, ollama_base_url or OLLAMA_BASE_URL)
    try:
        model_names = llm_provider.list_models()
        return jsonify(model_names)
    except Exception as e:
        print(f"Error fetching models: {e}")
        return jsonify({"error": str(e)}), 500

@chat_blueprint.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message")
    history = data.get("history", [])
    model = data.get("model")
    llm_endpoint = data.get("llm_endpoint")
    api_key = request.headers.get('x-openai-api-key')
    ollama_base_url = request.headers.get('x-ollama-base-url')

    response = run_agent_sync(user_message, history, model, llm_endpoint, api_key, ollama_base_url)
    return jsonify({"response": response})

@chat_blueprint.route("/chat/history", methods=["GET"])
def list_chat_history():
    history = fetch_from_couchdb("chat_history")
    return jsonify(history)

@chat_blueprint.route("/chat/history/<session_id>", methods=["GET"])
def get_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description="Chat session not found")
    return jsonify(session)

@chat_blueprint.route("/chat/history", methods=["POST"])
def create_chat_session():
    data = request.json
    title = data.get("title", "New Chat")
    session_id = str(uuid.uuid4())
    session = {
        "_id": session_id,
        "title": title,
        "messages": [],
        "model": data.get("model"),
        "llm_endpoint": data.get("llm_endpoint")
    }
    if update_couchdb_doc("chat_history", session_id, session):
        return jsonify(session)
    else:
        abort(500, description="Failed to create chat session")

@chat_blueprint.route("/chat/history/<session_id>", methods=["PUT"])
def update_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description="Chat session not found")
    
    data = request.json
    if "messages" not in data:
        abort(400, description="Messages are required")
        
    session["messages"] = data["messages"]
    if "model" in data:
        session["model"] = data["model"]
    if "llm_endpoint" in data:
        session["llm_endpoint"] = data["llm_endpoint"]
    
    if update_couchdb_doc("chat_history", session_id, session):
        return jsonify(session)
    else:
        abort(500, description="Failed to update chat session")

@chat_blueprint.route("/chat/history/<session_id>/export", methods=["GET"])
def export_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description="Chat session not found")
    
    title = session.get("title", "Untitled Chat")
    safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)
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
        headers={"Content-Disposition": f"attachment;filename={safe_title}.md"}
    )

@chat_blueprint.route("/chat/history/<session_id>", methods=["DELETE"])
def delete_chat_session(session_id):
    session = fetch_from_couchdb("chat_history", session_id)
    if not session:
        abort(404, description="Chat session not found")
    
    if delete_from_couchdb("chat_history", session_id, session["_rev"]):
        return jsonify({"status": "deleted"})
    else:
        abort(500, description="Failed to delete chat session")