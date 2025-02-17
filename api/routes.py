from flask import Blueprint, jsonify, abort
import os
import requests

api_blueprint = Blueprint('api', __name__)

@api_blueprint.route("/feeds", methods=["GET"])
def list_feeds():
    feeds_directory = 'feeds'
    feeds = [feed for feed in os.listdir(feeds_directory) if not feed.startswith('.')]
    return jsonify(feeds)

@api_blueprint.route("/feeds/<int:feed_id>", methods=["GET"])
def get_feed(feed_id):
    feeds_directory = 'feeds'
    feeds = [feed for feed in os.listdir(feeds_directory) if not feed.startswith('.')]
    if feed_id < 0 or feed_id >= len(feeds):
        abort(404, description="Feed not found")
    feed_filename = feeds[feed_id]
    feed_filepath = os.path.join(feeds_directory, feed_filename)
    if os.path.isfile(feed_filepath):
        with open(feed_filepath, 'r') as file:
            file_urls = file.readlines()
            urls = [fetch_url(url.strip()) for url in file_urls if url.strip()]
        return jsonify(urls)
    else:
        abort(404, description="Feed file not found")

@api_blueprint.route("/articles", methods=["GET"])
def list_articles():
    articles_directory = 'articles'
    articles = [article for article in os.listdir(articles_directory) if not article.startswith('.')]
    return jsonify(articles)

@api_blueprint.route("/articles/<int:article_id>", methods=["GET"])
def get_article(article_id):
    articles_directory = 'articles'
    articles = [article for article in os.listdir(articles_directory) if not article.startswith('.')]
    if article_id < 0 or article_id >= len(articles):
        abort(404, description="Article not found")
    article_filename = articles[article_id]
    article_filepath = os.path.join(articles_directory, article_filename)
    if os.path.isfile(article_filepath):
        with open(article_filepath, 'r') as file:
            article_content = file.read()
        return jsonify({"content": article_content})
    else:
        abort(404, description="Article file not found")

def fetch_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return {"url": url, "status": "success"}
        else:
            return {"url": url, "status": "failed", "code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status": "error", "message": str(e)}