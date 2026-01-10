import requests
import sys
import os

def verify_namespaces():
    url = "http://localhost:8088/api/namespaces"
    print(f"Fetching namespaces from {url}...")
    
    username = os.environ.get("API_USERNAME")
    password = os.environ.get("API_PASSWORD")
    
    if not username or not password:
        print("API_USERNAME and API_PASSWORD environment variables must be set")
        sys.exit(1)
    
    try:
        res = requests.get(url, auth=(username, password))
        if res.status_code == 200:
            namespaces = res.json()
            print(f"Namespaces found: {len(namespaces)}")
            for ns in namespaces:
                print(f"- {ns}")
        else:
            print(f"Failed to fetch namespaces: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_namespaces()
