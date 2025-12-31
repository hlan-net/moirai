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

def run_agent_sync(user_message, history, model=None):
    return asyncio.run(run_agent(user_message, history, model))

async def run_agent(user_message, history, model=None):
    messages = list(history)
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
                    
                    if response_message.tool_calls:
                        for tool_call in response_message.tool_calls:
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
    
    response = run_agent_sync(user_message, history, model)
    return jsonify({"response": response})