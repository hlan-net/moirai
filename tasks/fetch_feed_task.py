import hashlib
import json
import os
import random
import threading
import time
import requests
from .article_processor import ArticleProcessor

class FetchFeedTask(threading.Thread):
    def __init__(self, url, delay_ignored=0):
        threading.Thread.__init__(self)
        self.url = url
        # Use the COUCHDB_URI environment variable if available
        self.couchdb_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/") + "feeds"
        self.user_agent = "MoiraiBot/1.0 (+https://github.com/hlan-net/moirai)"

    def run(self):
        # Add random jitter to avoid thundering herd and be polite
        # Sleep between 1 and 30 seconds
        time.sleep(random.uniform(1, 30))
        self.fetch_url()

    def fetch_url(self):
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(self.url, headers=headers, timeout=30)
            self.handle_response(response)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {self.url}: {e}")

    def handle_response(self, response):
        if response.status_code == 200:
            print(f"Successfully fetched: {self.url}")
            # Prepare document with headers and body to store in CouchDB
            doc = {
                "url": self.url,
                "headers": dict(response.headers),
                "body": response.text
            }

            # Calculate hash of the document
            doc_hash = hashlib.sha256(json.dumps(doc, sort_keys=True).encode('utf-8')).hexdigest()

            # Check if the document already exists based on the hash
            if self.is_duplicate(doc_hash):
                print("Feed already exists and hasn't changed. Skipping storage.")
                return

            doc["_id"] = doc_hash  # Use the hash as the document ID

            try:
                res = requests.post(self.couchdb_url, json=doc)
                if res.status_code in (200, 201):
                    print("Feed stored successfully in CouchDB.")
                    # Process articles from the feed
                    self.process_articles(response.text)
                elif res.status_code == 404:
                    print("Database not found in CouchDB, cannot store feed.")
                    return
                else:
                    print(f"Failed to store feed in CouchDB: {res.text}")
                    return
            except requests.exceptions.RequestException as e:
                print(f"Error storing feed in CouchDB: {e}")
                return
        else:
            print(f"Failed to fetch: {self.url} with status code: {response.status_code}")

    def is_duplicate(self, doc_hash):
        """
        Checks if a document with the given hash already exists in CouchDB.
        """
        try:
            # Attempt to retrieve the document by its ID (hash)
            response = requests.get(f"{self.couchdb_url}/{doc_hash}")
            if response.status_code == 200:
                # Document exists
                return True
            elif response.status_code == 404:
                # Document does not exist
                return False
            else:
                print(f"Error checking for duplicate: {response.text}")
                return True
        except requests.exceptions.RequestException as e:
            print(f"Error checking for duplicate: {e}")
            return True
    
    def process_articles(self, feed_content):
        """
        Process individual articles from the RSS feed.
        """
        try:
            processor = ArticleProcessor()
            articles = processor.process_feed(self.url, feed_content)
            
            print(f"Processed {len(articles)} articles from {self.url}")
            
            # Store each article
            for article in articles:
                processor.store_article(article)
                
        except Exception as e:
            print(f"Error processing articles from {self.url}: {e}")