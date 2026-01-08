import re
import uuid
from types import SimpleNamespace
from flask import Blueprint, request, jsonify
import os
import json
import asyncio
from openai import OpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client

chat_blueprint = Blueprint('chat', __name__)

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:8090/sse")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-dummy")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://host.docker.internal:11434/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.1")

def extract_tool_call_from_content(content):
    if not content: return None
    try:
        # Find all JSON-like blocks. 
        # We look for something starting with { and ending with } that contains "name" and "parameters"
        matches = re.findall(r'(\{.*"name"\s*:\s*".*?".*"parameters"\s*:\s*\{.*\}\})', content, re.DOTALL)
        if matches:
            # Take the last one likely
            last_match = matches[-1]
            data = json.loads(last_match)
            if "name" in data and "parameters" in data:
                return data
    except Exception:
        pass
    
    return None

def run_agent_sync(user_message, history, model=None, namespace=None):
    return asyncio.run(run_agent(user_message, history, model, namespace))

async def run_agent(user_message, history, model=None, namespace=None):
    messages = list(history)
    
    # Inject namespace context if provided
    if namespace:
        system_prompt = f"You are operating within the Namespace GUID: {namespace}. When calling tools that require a namespace (like add_event, list_events), you MUST use this GUID."
        # Check if there is already a system message, if so append, otherwise insert
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] += f"\n\n{system_prompt}"
        else:
            messages.insert(0, {"role": "system", "content": system_prompt})
            
    messages.append({"role": "user", "content": user_message})

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    
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

                    response = client.chat.completions.create(
                        model=target_model,
                        messages=clean_messages,
                        tools=openai_tools if openai_tools else None,
                        tool_choice="auto" if openai_tools else None
                    )
                    
                    response_message = response.choices[0].message
                    
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
                        extracted = extract_tool_call_from_content(response_message.content)
                        if extracted:
                            # Create a mock tool call compatible with the loop below
                            mock_call = SimpleNamespace(
                                id=f"call_{uuid.uuid4().hex[:8]}",
                                function=SimpleNamespace(
                                    name=extracted["name"],
                                    arguments=json.dumps(extracted["parameters"])
                                ),
                                type="function"
                            )
                            tool_calls = [mock_call]
                            
                            # We update the last message in history to include this 'fake' tool call
                            # so the model sees it in the next turn as if it generated it properly.
                            # However, we can't easily modify 'msg_dict' to have a real tool_calls object that the API likes
                            # if we send it back.
                            # But since we strip 'tool_calls' if None, we need to ensure we structure it correctly 
                            # if we want to send it back.
                            # Actually, for the API, we need 'tool_calls' to be a list of dicts.
                            msg_dict["tool_calls"] = [{
                                "id": mock_call.id,
                                "type": "function",
                                "function": {
                                    "name": mock_call.function.name,
                                    "arguments": mock_call.function.arguments
                                }
                            }]

                    if tool_calls:
                        for tool_call in tool_calls:
                            func_name = tool_call.function.name
                            func_args = json.loads(tool_call.function.arguments)
                            
                            # Execute via MCP
                            try:
                                result = await session.call_tool(func_name, func_args)
                                result_text = result.content[0].text if result.content else "Success"
                            except Exception as tool_err:
                                result_text = f"Tool Execution Error: {tool_err}"

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
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    try:
        models_response = client.models.list()
        # models_response.data is a list of Model objects
        model_names = [m.id for m in models_response.data]
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
    
    response = run_agent_sync(user_message, history, model, namespace)
    return jsonify({"response": response})