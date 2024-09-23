from flask import Flask, render_template, request
from flask_pymongo import PyMongo
import feedparser
from collections import defaultdict

app = Flask(__name__)

# MongoDB configuration
app.config["MONGO_URI"] = "mongodb://mongo:27017/rss_aggregator"
mongo = PyMongo(app)

def read_feed_urls(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def fetch_feeds(feed_urls):
    feeds = []
    articles_map = defaultdict(list)  # To track articles by title for cross-referencing
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            feeds.append(feed)
            for entry in feed.entries:
                articles_map[entry.title].append(entry.link)  # Group links by title
                mongo.db.articles.insert_one({
                    'title': entry.title,
                    'link': entry.link,
                    'feed_title': feed.feed.title
                })
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
    return feeds, articles_map

@app.route("/", methods=["GET", "POST"])
def index():
    feeds = []
    if request.method == "POST":
        file = request.files['file']
        if file:
            file_path = "feeds.txt"
            file.save(file_path)  # Save uploaded file
            feed_urls = read_feed_urls(file_path)
            feeds, _ = fetch_feeds(feed_urls)
    return render_template("index.html", feeds=feeds)

@app.route("/cross-referenced")
def cross_referenced():
    articles_map = defaultdict(list)
    all_articles = mongo.db.articles.find()
    
    for article in all_articles:
        articles_map[article['title']].append(article['link'])

    return render_template("cross_referenced.html", articles=articles_map)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')