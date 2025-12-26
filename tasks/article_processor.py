import feedparser
import hashlib
import json
import os
import requests
from datetime import datetime

class ArticleProcessor:
    def __init__(self):
        self.couchdb_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/") + "articles"

    def process_feed(self, feed_url, feed_content):
        """
        Parses the feed content using feedparser and extracts articles.
        """
        parsed_feed = feedparser.parse(feed_content)
        articles = []
        
        for entry in parsed_feed.entries:
            # Extract content, preferring 'content' then 'summary' then empty
            content_value = ""
            if "content" in entry:
                content_value = entry.content[0].value
            elif "summary" in entry:
                content_value = entry.summary

            article = {
                "feed_url": feed_url,
                "title": entry.get("title", "No Title"),
                "link": entry.get("link", ""),
                "published": entry.get("published", datetime.now().isoformat()),
                "summary": entry.get("summary", ""),
                "content": content_value
            }
            articles.append(article)
            
        return articles

    def store_article(self, article):
        """
        Stores the article in CouchDB if it doesn't already exist.
        """
        # Create a deterministic hash for the article to avoid duplicates.
        # We exclude 'published' to avoid duplicates if the feed updates the timestamp but not content.
        hash_payload = {
            "title": article["title"],
            "link": article["link"],
            "feed_url": article["feed_url"]
        }
        article_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True).encode('utf-8')).hexdigest()
        
        article["_id"] = article_hash
        
        try:
            # Check if article exists (HEAD request is more efficient)
            response = requests.head(f"{self.couchdb_url}/{article_hash}")
            if response.status_code == 200:
                # Article exists, skip
                return

            # Store the article
            response = requests.post(self.couchdb_url, json=article)
            if response.status_code not in (200, 201):
                print(f"Failed to store article {article_hash}: {response.status_code} {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error storing article {article_hash}: {e}")
