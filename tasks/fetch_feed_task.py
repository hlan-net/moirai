import hashlib
import json
import os
import random
import threading
import time
import requests
from urllib.parse import quote
from datetime import datetime, timezone
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
        if response.status_code == 200:
            print(f"Successfully fetched: {self.url}")
            
            # Clear any previous fetch errors on success
            self.clear_fetch_error()
            
            # Check for redirect
            final_url = response.url
            is_redirect = False
            if final_url and final_url != self.url:
                # Basic check, maybe ignore trailing slashes
                if final_url.rstrip('/') != self.url.rstrip('/'):
                    is_redirect = True
                    print(f"Redirect detected: {self.url} -> {final_url}")

            # 1. Update Registry (potentially new URL + favicon)
            url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
            try:
                res = requests.get(f"{self.registry_url}/{url_hash}")
                if res.status_code == 200:
                    reg_doc = res.json()
                    needs_update = False
                    
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
                        print(f"Updating registry for {self.url} (URL: {final_url})")
                        requests.put(f"{self.registry_url}/{url_hash}", json=reg_doc)
                elif res.status_code == 404:
                    print(f"Registering new feed: {self.url}")
                    # Fetch favicon for new feed
                    favicon_url = fetch_favicon_url(final_url if is_redirect else self.url)
                    reg_doc = {
                        "_id": url_hash,
                        "url": final_url if is_redirect else self.url,
                        "title": "Pending Enrichment...",
                        "added_at": datetime.now(timezone.utc).isoformat(),
                        "category": "auto-discovered",
                        "favicon_url": favicon_url
                    }
                    requests.put(f"{self.registry_url}/{url_hash}", json=reg_doc)
            except Exception as e:
                print(f"Error checking registry: {e}")

            # 2. Store Content (latest only)
            doc = {
                "url": final_url if is_redirect else self.url, 
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
                
                # Update latest content - This will trigger the enrichment worker via _changes
                res = requests.put(f"{self.content_url}/{url_hash}", json=doc)
                if res.status_code in (200, 201):
                    print(f"Stored latest content for {self.url}")
                else:
                    print(f"Failed to store content: {res.text}")
            except Exception as e:
                print(f"Error updating content: {e}")
        else:
            error_msg = f"HTTP {response.status_code}"
            print(f"Failed to fetch: {self.url} with status code: {response.status_code}")
            self.record_fetch_error(error_msg)

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