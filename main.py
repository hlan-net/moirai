from flask import Flask
import os
import requests

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello from GenAI Press Review Service!"

def fetch_urls_from_files(directory):
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            with open(filepath, 'r') as file:
                urls = file.readlines()
                for url in urls:
                    url = url.strip()
                    if url:
                        fetch_url(url)

def fetch_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Successfully fetched: {url}")
        else:
            print(f"Failed to fetch: {url} with status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")

if __name__ == "__main__":
    feeds_directory = 'feeds'
    fetch_urls_from_files(feeds_directory)
    app.run(host="0.0.0.0", port=80)
