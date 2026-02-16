import hashlib
import os
import random
import threading
import time
import requests
import logging
from datetime import datetime, timezone
from .favicon_fetcher import fetch_favicon_url
from api.db_config import get_couchdb_uri
import feedparser

logger = logging.getLogger(__name__)


class FetchFeedTask(threading.Thread):
    def __init__(self, feed_id, url, original_url, delay_ignored=0):
        threading.Thread.__init__(self)
        self.feed_id = feed_id
        self.url = url  # The current URL of the feed
        self.original_url = original_url  # The unchanging original URL
        
        base_url = get_couchdb_uri()
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
            # Ensure databases exist (this is an init container responsibility, but kept for robustness)
            requests.put(self.registry_url, timeout=10)
            requests.put(self.content_url, timeout=10)

            headers = {"User-Agent": self.user_agent}
            response = requests.get(self.url, headers=headers, timeout=30)
            self.handle_response(response)
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching {self.url}: {e}"
            logger.error(error_msg)
            self.record_fetch_error(str(e))

    def handle_response(self, response):
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            logger.error(
                f"Failed to fetch: {self.url} with status code: {response.status_code}"
            )
            self.record_fetch_error(error_msg)
            return

        logger.info(f"Successfully fetched: {self.url}")
        self.clear_fetch_error()

        # Process articles first to extract title
        feed_title = self.process_articles(response.text)

        # Check for redirect
        final_url = response.url
        is_redirect = final_url and final_url.rstrip("/") != self.url.rstrip("/")
        if is_redirect:
            logger.info(f"Redirect detected: {self.url} -> {final_url}")

        # Pass feed_id directly
        self._update_registry(self.feed_id, feed_title, final_url, is_redirect)
        self._store_content(self.feed_id, response, final_url, is_redirect)

    def process_articles(self, content):
        """Extract feed title using feedparser."""
        try:
            feed = feedparser.parse(content)
            return feed.feed.get("title", "")
        except Exception as e:
            logger.error(f"Error parsing feed for title: {e}")
            return ""

    def _update_registry(self, feed_id, feed_title, final_url, is_redirect):
        """Update feed registry with title, resolved URL and favicon."""
        try:
            res = requests.get(f"{self.registry_url}/{feed_id}", timeout=10)
            if res.status_code == 200:
                self._update_existing_registry(
                    feed_id, res.json(), feed_title, final_url, is_redirect
                )
            else:
                # This should ideally not happen if FetchFeedTask is only used for existing feeds
                # For robustness, we can log an error or attempt to re-create a minimal entry
                logger.error(f"Error: Feed {feed_id} not found in registry. Cannot update.")
        except Exception as e:
            logger.error(f"Error checking registry for {feed_id}: {e}")

    def _update_existing_registry(
        self, feed_id, reg_doc, feed_title, final_url, is_redirect
    ):
        needs_update = False
        if (
            feed_title and reg_doc.get("title") != feed_title
        ):  # Only update if title changed
            reg_doc["title"] = feed_title
            needs_update = True

        if is_redirect and reg_doc.get("url") != final_url:
            reg_doc["url"] = final_url  # Update current URL
            needs_update = True

        # Fetch and store favicon if not already present or if URL changed
        if not reg_doc.get("favicon_url") or (
            is_redirect and reg_doc.get("url") != final_url
        ):
            favicon_url = fetch_favicon_url(
                final_url
            )  # Always use final_url for favicon
            if favicon_url and reg_doc.get("favicon_url") != favicon_url:
                reg_doc["favicon_url"] = favicon_url
                needs_update = True

        if needs_update:
            logger.info(
                f"Updating registry for {reg_doc.get('original_url', feed_id)} (Title: {feed_title}, URL: {final_url})"
            )
            requests.put(f"{self.registry_url}/{feed_id}", json=reg_doc, timeout=10)

    def _store_content(self, feed_id, response, final_url, is_redirect):
        """Store the latest feed content if it has changed."""
        doc = {
            "url": final_url,  # Store final resolved URL
            "feed_id": feed_id,  # Link content to stable feed_id
            "headers": dict(response.headers),
            "body": response.text,
            "fetched_at": time.time(),
        }

        body_hash = hashlib.sha256(response.text.encode("utf-8")).hexdigest()

        try:
            # Get current content doc to check revision and change
            res = requests.get(f"{self.content_url}/{feed_id}", timeout=10)
            if res.status_code == 200:
                current_doc = res.json()
                current_body_hash = hashlib.sha256(
                    current_doc.get("body", "").encode("utf-8")
                ).hexdigest()
                if body_hash == current_body_hash:
                    logger.info(f"No content changes for {self.url}. Content up to date.")
                    return
                doc["_rev"] = current_doc["_rev"]

            # Update latest content
            res = requests.put(f"{self.content_url}/{feed_id}", json=doc, timeout=10)
            if res.status_code in (200, 201):
                logger.info(f"Stored latest content for {self.url}")
            else:
                logger.error(f"Failed to store content: {res.text}")
        except Exception as e:
            logger.error(f"Error updating content: {e}")

    def record_fetch_error(self, error_message):
        """Record a fetch error in the feed registry."""
        feed_id = self.feed_id  # Use stable feed_id
        try:
            res = requests.get(f"{self.registry_url}/{feed_id}", timeout=10)
            if res.status_code == 200:
                reg_doc = res.json()
                reg_doc["last_fetch_error"] = error_message
                reg_doc["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
                requests.put(f"{self.registry_url}/{feed_id}", json=reg_doc, timeout=10)
                logger.info(
                    f"Recorded fetch error for {reg_doc.get('original_url', feed_id)}: {error_message}"
                )
        except Exception as e:
            logger.error(f"Failed to record fetch error for {feed_id}: {e}")

    def clear_fetch_error(self):
        """Clear any previous fetch error in the feed registry."""
        feed_id = self.feed_id  # Use stable feed_id
        try:
            res = requests.get(f"{self.registry_url}/{feed_id}", timeout=10)
            if res.status_code == 200:
                reg_doc = res.json()
                if "last_fetch_error" in reg_doc:
                    del reg_doc["last_fetch_error"]
                reg_doc["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
                requests.put(f"{self.registry_url}/{feed_id}", json=reg_doc, timeout=10)
                logger.info(f"Cleared fetch error for {reg_doc.get('original_url', feed_id)}")
        except Exception as e:
            logger.error(f"Failed to clear fetch error for {feed_id}: {e}")
