import re
import uuid
from types import SimpleNamespace
from flask import Blueprint, request, jsonify
import os
import json
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from .llm.factory import LLMProviderFactory

chat_blueprint = Blueprint('chat', __name__)

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:8090/sse")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.1")

llm_provider_factory = LLMProviderFactory(ollama_base_url=OLLAMA_BASE_URL)

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

def run_agent_sync(user_message, history, model=None, namespace=None, llm_endpoint=None, api_key=None):
    return asyncio.run(run_agent(user_message, history, model, namespace, llm_endpoint, api_key))

async def run_agent(user_message, history, model=None, namespace=None, llm_endpoint=None, api_key=None):
    messages = list(history)
    
    # Inject namespace context if provided
    system_prompt = "You are Moirai, a GenAI-native press review agent. "
    if namespace:
        system_prompt += f"You are operating within the Namespace GUID: {namespace}. When calling tools that require a namespace (like add_event, list_events), you MUST use this GUID. "
    
    system_prompt += (
        "You DO NOT have access to real-time information or the internet directly. "
        "You MUST use the provided tools (like `list_feeds`, `read_feed`) to fetch any news or external data. "
        "Do not hallucinate headlines. If you need news, CALL A TOOL. "
        "When asked for news, FIRST check the available feeds using `list_feeds`. "
        "If no relevant feeds are found, you can try to `read_feed` with a GUESSED URL, but ensure it is a valid RSS/Atom feed URL. "
        "Some reliable Linux news feeds are: LWN (https://lwn.net/headlines/rss), Phoronix (https://www.phoronix.com/phoronix-rss.php), "
        "and Kernel.org (https://www.kernel.org/feeds/kall.xml)."
    )
    
    # Check if there is already a system message, if so append, otherwise insert
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] += f"\n\n{system_prompt}"
    else:
        messages.insert(0, {"role": "system", "content": system_prompt})
            
    messages.append({"role": "user", "content": user_message})

    llm_provider = llm_provider_factory.get_provider(llm_endpoint, api_key or OPENAI_API_KEY)
    
    target_model = model or MODEL_NAME

    try:
        # Connect to MCP Server
        # Force Host header to localhost to bypass TrustedHostMiddleware in FastMCP
        headers = {"Host": "localhost:8090"}
        async with sse_client(MCP_SERVER_URL, headers=headers) as (read, write):
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

                max_turns = 10
                for _ in range(max_turns):
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
    llm_provider = llm_provider_factory.get_provider(llm_endpoint, api_key)
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
    namespace = data.get("namespace")
    llm_endpoint = data.get("llm_endpoint")
    api_key = request.headers.get('x-openai-api-key')

    response = run_agent_sync(user_message, history, model, namespace, llm_endpoint, api_key)
    return jsonify({"response": response})