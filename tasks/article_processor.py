import feedparser
import hashlib
import json
import os
import requests
import logging
from datetime import datetime, timedelta
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from api.db_config import get_couchdb_uri

# Ensure consistent results for language detection
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)


class ArticleProcessor:
    def __init__(self):
        self.couchdb_url = get_couchdb_uri() + "articles"
        self.expiration_days = int(os.environ.get("ARTICLE_EXPIRATION_DAYS", 30))

    def detect_language(self, text):
        """Detect language of a given text."""
        if not text or len(text.strip()) < 10:
            return None
        try:
            return detect(text)
        except LangDetectException:
            return None

    def process_feed(self, feed_url, feed_content):
        """Parses the feed content using feedparser and extracts articles.
        Returns: tuple (feed_title, articles_list)
        """
        articles = []
        feed_title = "Unknown Feed"

        try:
            parsed_feed = feedparser.parse(feed_content)
            feed_title = parsed_feed.feed.get("title", "Unknown Feed")
            feed_lang = (
                parsed_feed.feed.get("language", "").split("-")[0].lower()
                if parsed_feed.feed.get("language")
                else None
            )

            for entry in parsed_feed.entries:
                published_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published_date = datetime(*entry.published_parsed[:6])
                    except (ValueError, TypeError) as err:
                        logger.warning(
                            f"Could not parse date for article '{entry.get('title', 'No Title')}': {err}"
                        )

                if published_date and (datetime.now() - published_date) > timedelta(
                    days=self.expiration_days
                ):
                    continue

                content_value = ""
                if "content" in entry:
                    content_value = entry.content[0].value
                elif "summary" in entry:
                    content_value = entry.summary

                # Detect language
                text_to_detect = entry.get("title", "") + " " + entry.get("summary", "")
                detected_lang = self.detect_language(text_to_detect)

                # Use feed language as fallback if detection is uncertain or fails
                article_lang = detected_lang or feed_lang or "unknown"

                article = {
                    "feed_url": feed_url,
                    "feed_title": feed_title,  # Added to avoid extra lookups in UI
                    "title": entry.get("title", "No Title"),
                    "link": entry.get("link", ""),
                    "published": published_date.isoformat() + "Z"
                    if published_date
                    else datetime.now().isoformat(),
                    "summary": entry.get("summary", ""),
                    "content": content_value,
                    "language": article_lang,
                }

                articles.append(article)
        except (ValueError, TypeError) as err:
            logger.error(f"Error parsing feed content for {feed_url}: {err}")
        except Exception as err:
            logger.error(f"Unexpected error parsing feed for {feed_url}: {err}")

        return feed_title, articles

    def store_article(self, article):
        """Stores the article in CouchDB if it doesn't already exist."""
        hash_payload = {
            "title": article["title"],
            "link": article["link"],
            "feed_url": article["feed_url"],
        }
        article_hash = hashlib.sha256(
            json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        article["_id"] = article_hash

        try:
            response = requests.head(f"{self.couchdb_url}/{article_hash}", timeout=10)
            if response.status_code == 200:
                return

            response = requests.post(self.couchdb_url, json=article, timeout=10)
            if response.status_code not in (200, 201):
                logger.error(
                    f"Failed to store article {article_hash}: {response.status_code} {response.text}"
                )
        except requests.exceptions.RequestException as err:
            logger.error(f"Error storing article {article_hash}: {err}")
        except Exception as err:
            logger.error(f"Unexpected error storing article {article_hash}: {err}")
