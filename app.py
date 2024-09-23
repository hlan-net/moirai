from flask import Flask, render_template, request
from flask_pymongo import PyMongo
import feedparser
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

app = Flask(__name__)

# MongoDB configuration
app.config["MONGO_URI"] = "mongodb://mongo:27017/rss_aggregator"
mongo = PyMongo(app)

def read_feed_urls(file_path):
    """Read feed URLs from a given file."""
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def save_feed_urls(feed_urls):
    """Save feed URLs to MongoDB."""
    for url in feed_urls:
        if not mongo.db.feeds.find_one({"url": url}):
            mongo.db.feeds.insert_one({"url": url})

def get_feed_urls():
    """Get feed URLs from MongoDB."""
    return [feed['url'] for feed in mongo.db.feeds.find()]

def fetch_feeds(feed_urls):
    """Fetch feeds from the provided URLs."""
    feeds = []
    articles = []  # Store articles for correlation
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            feeds.append(feed)
            for entry in feed.entries:
                article = {
                    'title': entry.title,
                    'link': entry.link,
                    'feed_title': feed.feed.title
                }
                articles.append(article)
                mongo.db.articles.replace_one(
                    {'link': entry.link},  # Filter by link
                    article,               # Document to insert/replace
                    upsert=True            # Insert if no match is found
                )
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
    return feeds, articles

def correlate_articles(articles):
    """Correlate articles based on cosine similarity of their titles."""
    titles = [article['title'] for article in articles]
    vectorizer = TfidfVectorizer().fit_transform(titles)
    vectors = vectorizer.toarray()

    cosine_matrix = cosine_similarity(vectors)
    correlated_articles = defaultdict(list)

    for i in range(len(titles)):
        correlated_indices = np.where(cosine_matrix[i] > 0.5)[0]  # Adjust threshold as needed
        for index in correlated_indices:
            if index != i:
                correlated_articles[titles[i]].append(articles[index]['link'])

    return correlated_articles

@app.route("/", methods=["GET", "POST"])
def index():
    feeds = []
    if request.method == "POST":
        file = request.files['file']
        if file:
            file_path = "feeds.txt"
            file.save(file_path)  # Save uploaded file
            feed_urls = read_feed_urls(file_path)  # Read feed URLs from the uploaded file
            save_feed_urls(feed_urls)  # Save feeds to MongoDB
            feeds, articles = fetch_feeds(feed_urls)  # Fetch feeds
            return render_template("index.html", feeds=feeds)
    else:
        feed_urls = get_feed_urls()  # Get feed URLs from MongoDB
        feeds, articles = fetch_feeds(feed_urls)  # Fetch feeds
    return render_template("index.html", feeds=feeds)

@app.route("/correlated")
def correlated():
    """Display correlated articles based on title similarity."""
    all_articles = mongo.db.articles.find()
    articles = [{'title': a['title'], 'link': a['link']} for a in all_articles]
    correlated_articles = correlate_articles(articles)

    return render_template("correlated.html", articles=correlated_articles)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
