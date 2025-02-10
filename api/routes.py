from flask import Blueprint, jsonify
import os
import requests

api_blueprint = Blueprint('api', __name__)

@api_blueprint.route("/fetch_urls", methods=["GET"])
def fetch_urls():
    feeds_directory = 'feeds'
    urls = fetch_urls_from_files(feeds_directory)
    return jsonify(urls)

def fetch_urls_from_files(directory):
    urls = []
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            with open(filepath, 'r') as file:
                file_urls = file.readlines()
                for url in file_urls:
                    url = url.strip()
                    if url:
                        urls.append(fetch_url(url))
    return urls

def fetch_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return {"url": url, "status": "success"}
        else:
            return {"url": url, "status": "failed", "code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status": "error", "message": str(e)}