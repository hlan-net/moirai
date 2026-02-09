import hashlib
import json
import os
import random
import threading
import time
import requests
from urllib.parse import quote
from datetime import datetime, timezone
from .article_processor import ArticleProcessor
from .favicon_fetcher import fetch_favicon_url

class FetchFeedTask(threading.Thread):
    def __init__(self, url, delay_ignored=0):
        threading.Thread.__init__(self)
        self.url = url
        # Use the COUCHDB_URI environment variable if available
        uri = os.environ.get("COUCHDB_URI", "http://localhost:5984/").rstrip("/")
        user = os.environ.get("COUCHDB_USER")
        password = os.environ.get("COUCHDB_PASSWORD")
        if user and password and "@" not in uri:
            if "://" in uri:
                scheme, host = uri.split("://", 1)
            else:
                scheme, host = "http", uri
            uri = f"{scheme}://{quote(user)}:{quote(password)}@{host}"

        base_url = uri + "/"
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
            error_msg = f"Error fetching {self.url}: {e}"
            print(error_msg)
            self.record_fetch_error(str(e))

    def handle_response(self, response):
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            print(f"Failed to fetch: {self.url} with status code: {response.status_code}")
            self.record_fetch_error(error_msg)
            return

        print(f"Successfully fetched: {self.url}")
        self.clear_fetch_error()
        
        # Process articles first to extract title
        feed_title = self.process_articles(response.text)
        
        # Check for redirect
        final_url = response.url
        is_redirect = (final_url and final_url.rstrip('/') != self.url.rstrip('/'))
        if is_redirect:
            print(f"Redirect detected: {self.url} -> {final_url}")

        url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
        
        self._update_registry(url_hash, feed_title, final_url, is_redirect)
        self._store_content(url_hash, response, final_url, is_redirect)

    def _update_registry(self, url_hash, feed_title, final_url, is_redirect):
        """Update feed registry with title, resolved URL and favicon."""
        try:
            res = requests.get(f"{self.registry_url}/{url_hash}")
            if res.status_code == 200:
                self._update_existing_registry(url_hash, res.json(), feed_title, final_url, is_redirect)
            elif res.status_code == 404:
                self._create_new_registry(url_hash, feed_title, final_url, is_redirect)
        except Exception as e:
            print(f"Error checking registry: {e}")

    def _update_existing_registry(self, url_hash, reg_doc, feed_title, final_url, is_redirect):
        needs_update = False
        if feed_title and not reg_doc.get("title"):
            reg_doc["title"] = feed_title
            needs_update = True
        
        if is_redirect and reg_doc.get("url") != final_url:
            reg_doc["url"] = final_url
            needs_update = True
        
        # Fetch and store favicon if not already present
        if not reg_doc.get("favicon_url"):
            favicon_url = fetch_favicon_url(final_url if is_redirect else self.url)
            if favicon_url:
                reg_doc["favicon_url"] = favicon_url
                needs_update = True
            
        if needs_update:
            print(f"Updating registry for {self.url} (Title: {feed_title}, URL: {final_url})")
            requests.put(f"{self.registry_url}/{url_hash}", json=reg_doc)

    def _create_new_registry(self, url_hash, feed_title, final_url, is_redirect):
        print(f"Registering new feed: {self.url}")
        favicon_url = fetch_favicon_url(final_url if is_redirect else self.url)
        reg_doc = {
            "_id": url_hash,
            "url": final_url if is_redirect else self.url,
            "title": feed_title or "Unknown Feed",
            "added_at": datetime.now(timezone.utc).isoformat(),
            "category": "auto-discovered",
            "favicon_url": favicon_url
        }
        requests.put(f"{self.registry_url}/{url_hash}", json=reg_doc)

    def _store_content(self, url_hash, response, final_url, is_redirect):
        """Store the latest feed content if it has changed."""
        doc = {
            "url": final_url if is_redirect else self.url,
            "headers": dict(response.headers),
            "body": response.text,
            "fetched_at": time.time()
        }

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

    def record_fetch_error(self, error_message):
        """Record a fetch error in the feed registry."""
        url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
        try:
            res = requests.get(f"{self.registry_url}/{url_hash}")
            if res.status_code == 200:
                reg_doc = res.json()
                reg_doc["last_fetch_error"] = error_message
                reg_doc["last_fetch_at"] = datetime.now().isoformat()
                requests.put(f"{self.registry_url}/{url_hash}", json=reg_doc)
                print(f"Recorded fetch error for {self.url}: {error_message}")
        except Exception as e:
            print(f"Failed to record fetch error: {e}")

    def clear_fetch_error(self):
        """Clear any previous fetch error in the feed registry."""
        url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
        try:
            res = requests.get(f"{self.registry_url}/{url_hash}")
            if res.status_code == 200:
                reg_doc = res.json()
                if "last_fetch_error" in reg_doc:
                    del reg_doc["last_fetch_error"]
                reg_doc["last_fetch_at"] = datetime.now().isoformat()
                requests.put(f"{self.registry_url}/{url_hash}", json=reg_doc)
                print(f"Cleared fetch error for {self.url}")
        except Exception as e:
            print(f"Failed to clear fetch error: {e}")