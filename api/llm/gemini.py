import os
import google.generativeai as genai
from google.generativeai.types import content_types
from google.ai.generativelanguage import Content, Part, Tool, FunctionDeclaration, FunctionCall, FunctionResponse
import json
from types import SimpleNamespace
from .base import LLMProvider

class GeminiProvider(LLMProvider):
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.api_key = api_key

    def list_models(self):
        try:
            models = genai.list_models()
            # Filter for models that support generation
            return [m.name.replace('models/', '') for m in models if 'generateContent' in m.supported_generation_methods]
        except Exception as e:
            print(f"Error listing Gemini models: {e}")
            return ["gemini-pro"] # Fallback

    def create_chat_completion(self, messages, model, tools, tool_choice):
        # 1. Setup Model
        gemini_tools = self._convert_tools(tools)
        
        system_instruction = None
        # Extract system prompt if present
        if messages and messages[0]['role'] == 'system':
            system_instruction = messages[0]['content']
            messages = messages[1:]

        # Create model
        model_name = model if model.startswith('models/') else f'models/{model}'
        # If model name doesn't exist/invalid, might accept short name.

        generative_model = genai.GenerativeModel(
            model_name=model_name,
            tools=gemini_tools if gemini_tools else None,
            system_instruction=system_instruction
        )

        # 2. Convert History
        gemini_history = self._convert_history(messages)

        # 3. Generate Content
        # We use chat session for easier history management? 
        # But here we are stateless REST API so we reconstruct history.
        # Actually `start_chat(history=...)` and then `send_message` is good.
        
        # However, sending the LAST message separate from history is typical usage.
        if not gemini_history:
             # Should not happen typically if user sends at least one message
             return self._mock_response("No messages provided.")

        last_message = gemini_history[-1]
        history_except_last = gemini_history[:-1]

        chat = generative_model.start_chat(history=history_except_last)
        
        try:
            response = chat.send_message(last_message)
        except Exception as e:
            print(f"Gemini generation error: {e}")
            raise e

        # 4. Map Response back to OpenAI format
        return self._convert_response(response)

    def _convert_tools(self, tools):
        if not tools:
            return None
        
        gemini_tools = []
        for tool in tools:
            if tool.get('type') == 'function':
                func = tool['function']
                
                # Convert parameters schema
                # OpenAI uses JSON Schema. Gemini uses a subset.
                # Ideally we map types. For now, pass raw dict and hope client handles it 
                # (Client often accepts dicts that match the proto structure)
                # But we might need to be careful with 'type': 'object' etc.
                
                # Basic mapping:
                gemini_tools.append(
                    genai.protos.Tool(
                        function_declarations=[
                             genai.protos.FunctionDeclaration(
                                name=func['name'],
                                description=func.get('description'),
                                parameters=self._convert_schema(func.get('parameters'))
                            )
                        ]
                    )
                )
        return gemini_tools

    def _convert_schema(self, schema):
        # Recursive conversion of JSON Schema to Gemini Schema
        if not schema:
            return None
            
        type_map = {
            'string': genai.protos.Type.STRING,
            'number': genai.protos.Type.NUMBER, 
            'integer': genai.protos.Type.INTEGER,
            'boolean': genai.protos.Type.BOOLEAN,
            'array': genai.protos.Type.ARRAY,
            'object': genai.protos.Type.OBJECT
        }

        # If it's a raw type string in some simplified schema
        type_str = schema.get('type', 'object')
        
        schema_obj = {
            'type': type_map.get(type_str, genai.protos.Type.OBJECT),
            'description': schema.get('description'),
            'nullable': schema.get('nullable', False),
            'enum': schema.get('enum')
        }
        
        if 'properties' in schema:
            schema_obj['properties'] = {
                k: self._convert_schema(v) for k, v in schema['properties'].items()
            }
        
        if 'required' in schema:
            schema_obj['required'] = schema['required']
            
        if 'items' in schema:
            schema_obj['items'] = self._convert_schema(schema['items'])
            
        return schema_obj

    def _convert_history(self, messages):
        gemini_history = []
        for msg in messages:
            gemini_msg = self._convert_message_to_gemini(msg)
            if gemini_msg:
                gemini_history.append(gemini_msg)
        return gemini_history

    def _convert_message_to_gemini(self, msg):
        role = msg['role']
        content = msg.get('content')
        
        if role == 'user':
            parts = [{'text': content}] if content else []
            return {'role': 'user', 'parts': parts}
            
        elif role == 'assistant':
            parts = []
            if content:
                parts.append({'text': content})
            
            # Handle tool calls
            if 'tool_calls' in msg and msg['tool_calls']:
                for tc in msg['tool_calls']:
                    func = tc['function']
                    # FunctionCall part
                    parts.append({
                        'function_call': {
                            'name': func['name'],
                            'args': json.loads(func['arguments'])
                        }
                    })
            
            return {'role': 'model', 'parts': parts}
            
        elif role == 'tool':
            # FunctionResponse part
            parts = [{
                'function_response': {
                    'name': msg['name'],
                    'response': {'result': content}
                }
            }]
            return {'role': 'function', 'parts': parts}
            
        return None

    def _convert_response(self, response):
        # Convert Gemini response to OpenAI-like object
        # response is a GenerateContentResponse
        
        # Check for function calls
        content = None
        tool_calls = []
        
        for part in response.parts:
            if part.text:
                if content is None: content = ""
                content += part.text
            
            if part.function_call:
                # Map to OpenAI tool call
                fc = part.function_call
                tool_calls.append(SimpleNamespace(
                    id=f"call_{fc.name}", # Dummy ID as Gemini doesn't provide one
                    type='function',
                    function=SimpleNamespace(
                        name=fc.name,
                        arguments=json.dumps(dict(fc.args)) # args is a proto Map, dict() converts it
                    )
                ))

        # Create message object
        message = SimpleNamespace(
            role='assistant',
            content=content,
            tool_calls=tool_calls if tool_calls else None
        )
        
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    def _mock_response(self, text):
        return SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(
                role='assistant',
                content=text,
                tool_calls=None
            ))
        ])
