from flask import Flask, render_template, request
import feedparser

app = Flask(__name__)

def read_feed_urls(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def fetch_feeds(feed_urls):
    feeds = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            feeds.append(feed)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
    return feeds

@app.route("/", methods=["GET", "POST"])
def index():
    feeds = []
    if request.method == "POST":
        file = request.files['file']
        if file:
            file_path = "feeds.txt"
            file.save(file_path)  # Save uploaded file
            feed_urls = read_feed_urls(file_path)
            feeds = fetch_feeds(feed_urls)
    return render_template("index.html", feeds=feeds)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
