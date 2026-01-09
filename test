import re
import json

content = 'It seems like I encountered an unexpected issue with the RSS feed. I will try to access a different feed.\n{"name": "read_feed", "parameters": {"limit":10,"url":"https://www.linuxfoundation.org/feed/"}}'

def extract_tool_call(text):
    # look for JSON block with "name" and "parameters"
    try:
        # Find all JSON-like blocks. This is a naive regex but might work for the model's output style
        # We look for something starting with { and ending with } that contains "name" and "parameters"
        matches = re.findall(r'(\{.*"name"\s*:\s*".*?".*"parameters"\s*:\s*\{.*\}\})', text, re.DOTALL)
        if matches:
            # Take the last one likely
            last_match = matches[-1]
            data = json.loads(last_match)
            if "name" in data and "parameters" in data:
                return data
    except Exception as e:
        print(f"Regex parsing failed: {e}")
    
    return None

result = extract_tool_call(content)
print(f"Extracted: {result}")
