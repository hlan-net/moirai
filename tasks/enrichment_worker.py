import threading
import time
import requests
from api.db_config import COUCHDB_URI
from .article_processor import ArticleProcessor

class EnrichmentWorker(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.db_name = "feed_content"
        self.registry_name = "feeds"
        self.changes_url = f"{COUCHDB_URI}{self.db_name}/_changes"
        self.registry_url = f"{COUCHDB_URI}{self.registry_name}"
        self.processor = ArticleProcessor()
        self.last_seq = "0"
        self.running = True

    def run(self):
        print("EnrichmentWorker started.")
        # Try to get last sequence from DB config if possible, else start from now
        self.last_seq = self.get_last_seq()
        
        while self.running:
            try:
                self.process_changes()
            except Exception as e:
                print(f"EnrichmentWorker error: {e}")
                time.sleep(5) # Backoff

    def get_last_seq(self):
        """Get the last processed sequence from the config DB."""
        try:
            res = requests.get(f"{COUCHDB_URI}config/enrichment_last_seq")
            if res.status_code == 200:
                return res.json().get("value", "0")
        except Exception as e:
            print(f"Failed to get last sequence: {e}")
        return "now"

    def save_last_seq(self, seq):
        """Save the last processed sequence to the config DB."""
        try:
            doc = {"_id": "enrichment_last_seq", "value": seq}
            res = requests.get(f"{COUCHDB_URI}config/enrichment_last_seq")
            if res.status_code == 200:
                doc["_rev"] = res.json()["_rev"]
            result = requests.put(f"{COUCHDB_URI}config/enrichment_last_seq", json=doc)
            if result.status_code not in (200, 201):
                print(f"Failed to save last sequence: HTTP {result.status_code}")
        except Exception as e:
            print(f"Failed to save last sequence: {e}")

    def process_changes(self):
        params = {
            "feed": "longpoll",
            "since": self.last_seq,
            "include_docs": "true",
            "timeout": 30000
        }
        
        response = requests.get(self.changes_url, params=params, timeout=35)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            for change in results:
                doc = change.get("doc")
                if not doc or doc.get("_id", "").startswith("_design/"):
                    continue
                
                self.process_feed_content(doc)
            
            if data.get("last_seq"):
                self.last_seq = data.get("last_seq")
                self.save_last_seq(self.last_seq)
        elif response.status_code == 404:
            # DB doesn't exist yet
            time.sleep(10)
        else:
            print(f"EnrichmentWorker: Unexpected status {response.status_code}")
            time.sleep(10)

    def process_feed_content(self, content_doc):
        feed_url = content_doc.get("url")
        body = content_doc.get("body")
        content_doc_id = content_doc.get("_id")
        
        if not feed_url or not body or not content_doc_id:
            return

        print(f"Enriching articles for feed: {feed_url}")
        
        try:
            feed_title, articles = self.processor.process_feed(feed_url, body)
            
            # Store each article
            for article in articles:
                self.processor.store_article(article)
            
            print(f"Asynchronously processed {len(articles)} articles for {feed_url}")
            
            # Update feed title in registry if it was missing
            if feed_title:
                self.update_feed_title(content_doc_id, feed_title)
                
        except Exception as e:
            print(f"Error in EnrichmentWorker processing {feed_url}: {e}")

    def update_feed_title(self, registry_doc_id, feed_title):
        """Update the feed title in the registry if it is currently 'Pending Enrichment...' or empty.
        
        Args:
            registry_doc_id: The document ID from the feed_content document's _id field.
                            This corresponds to the hash of the original feed URL.
            feed_title: The title to set in the registry
        """
        try:
            res = requests.get(f"{self.registry_url}/{registry_doc_id}")
            if res.status_code == 200:
                reg_doc = res.json()
                current_title = reg_doc.get("title", "")
                
                if not current_title or current_title == "Pending Enrichment..." or current_title == "Unknown Feed":
                    reg_doc["title"] = feed_title
                    requests.put(f"{self.registry_url}/{registry_doc_id}", json=reg_doc)
                    print(f"Updated registry title for {registry_doc_id} -> {feed_title}")
        except Exception as e:
            print(f"Failed to update registry title: {e}")

# Global instance
worker = EnrichmentWorker()
