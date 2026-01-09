import hashlib
import json
import os
import random
import threading
import time
import requests
from datetime import datetime
from .article_processor import ArticleProcessor

class FetchFeedTask(threading.Thread):
    def __init__(self, url, delay_ignored=0):
        threading.Thread.__init__(self)
        self.url = url
        # Use the COUCHDB_URI environment variable if available
        base_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/")
        self.registry_url = base_url + "feeds"
        self.content_url = base_url + "feed_content"
        self.user_agent = "MoiraiBot/1.0 (+https://github.com/hlan-net/moirai)"

    def run(self):
        # Add random jitter to avoid thundering herd and be polite
        # Sleep between 1 and 30 seconds
        time.sleep(random.uniform(1, 30))
        self.fetch_url()

    def fetch_url(self):
        try:
            # Ensure databases exist
            requests.put(self.registry_url)
            requests.put(self.content_url)
            
            headers = {'User-Agent': self.user_agent}
            response = requests.get(self.url, headers=headers, timeout=30)
            self.handle_response(response)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {self.url}: {e}")

    def handle_response(self, response):
        if response.status_code == 200:
            print(f"Successfully fetched: {self.url}")
            
            # Process articles first to extract title
            feed_title = self.process_articles(response.text)
            
            # Check for redirect
            final_url = response.url
            is_redirect = False
            if final_url and final_url != self.url:
                # Basic check, maybe ignore trailing slashes
                if final_url.rstrip('/') != self.url.rstrip('/'):
                    is_redirect = True
                    print(f"Redirect detected: {self.url} -> {final_url}")

            # 1. Update Registry (Title + potentially new URL)
            url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
            try:
                res = requests.get(f"{self.registry_url}/{url_hash}")
                if res.status_code == 200:
                    reg_doc = res.json()
                    needs_update = False
                    
                    if feed_title and reg_doc.get("title") != feed_title:
                        reg_doc["title"] = feed_title
                        needs_update = True
                    
                    if is_redirect and reg_doc.get("url") != final_url:
                        reg_doc["url"] = final_url
                        needs_update = True
                        
                    if needs_update:
                        print(f"Updating registry for {self.url} (Title: {feed_title}, URL: {final_url})")
                        requests.put(f"{self.registry_url}/{url_hash}", json=reg_doc)
                elif res.status_code == 404:
                    print(f"Registering new feed: {self.url}")
                    reg_doc = {
                        "_id": url_hash,
                        "url": final_url if is_redirect else self.url,
                        "title": feed_title or "Unknown Feed",
                        "added_at": datetime.now().isoformat(),
                        "category": "auto-discovered"
                    }
                    requests.put(f"{self.registry_url}/{url_hash}", json=reg_doc)
            except Exception as e:
                print(f"Error checking registry: {e}")

            # 2. Store Content (latest only)
            doc = {
                "url": final_url if is_redirect else self.url, # Store under the resolved URL? Or original?
                # Actually, if we update the registry to point to final_url, we should probably record that.
                # But the ID of the content doc is also based on self.url in my previous edit?
                # Let's see... I used url_hash = hashlib.sha256(self.url...) for content doc too.
                # So we keep using the ID based on the ORIGINAL URL (from the text file/task input).
                "headers": dict(response.headers),
                "body": response.text,
                "fetched_at": time.time()
            }

            # Check for changes using body hash
            body_hash = hashlib.sha256(response.text.encode('utf-8')).hexdigest()
            
            try:
                # Get current content doc to check revision and change
                res = requests.get(f"{self.content_url}/{url_hash}")
                if res.status_code == 200:
                    current_doc = res.json()
                    current_body_hash = hashlib.sha256(current_doc.get("body", "").encode('utf-8')).hexdigest()
                    if body_hash == current_body_hash:
                        print(f"No changes for {self.url}. Content up to date.")
                        return
                    doc["_rev"] = current_doc["_rev"]
                
                # Update latest content
                res = requests.put(f"{self.content_url}/{url_hash}", json=doc)
                if res.status_code in (200, 201):
                    print(f"Stored latest content for {self.url}")
                else:
                    print(f"Failed to store content: {res.text}")
            except Exception as e:
                print(f"Error updating content: {e}")
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
        Returns: feed_title (str)
        """
        try:
            processor = ArticleProcessor()
            feed_title, articles = processor.process_feed(self.url, feed_content)
            
            print(f"Processed {len(articles)} articles from {self.url} ('{feed_title}')")
            
            # Store each article
            for article in articles:
                processor.store_article(article)
            
            return feed_title
                
        except Exception as e:
            print(f"Error processing articles from {self.url}: {e}")
            return None