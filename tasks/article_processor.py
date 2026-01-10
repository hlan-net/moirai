import feedparser
import hashlib
import json
import os
import requests
from datetime import datetime, timedelta

class ArticleProcessor:
    def __init__(self):
        self.couchdb_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/") + "articles"
        self.expiration_days = int(os.environ.get("ARTICLE_EXPIRATION_DAYS", 30))

    def process_feed(self, feed_url, feed_content):
        """Parses the feed content using feedparser and extracts articles.
           Returns: tuple (feed_title, articles_list)
        """
        articles = []
        feed_title = "Unknown Feed"

        try:
            parsed_feed = feedparser.parse(feed_content)
            feed_title = parsed_feed.feed.get("title", "Unknown Feed")

            for entry in parsed_feed.entries:
                published_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published_date = datetime(*entry.published_parsed[:6])
                    except (ValueError, TypeError) as err:
                        print(f"Warning: Could not parse date for article '{entry.get('title', 'No Title')}': {err}")

                if published_date and (datetime.now() - published_date) > timedelta(days=self.expiration_days):
                    continue

                content_value = ""
                if "content" in entry:
                    content_value = entry.content[0].value
                elif "summary" in entry:
                    content_value = entry.summary

                article = {
                    "feed_url": feed_url,
                    "title": entry.get("title", "No Title"),
                    "link": entry.get("link", ""),
                    "published": published_date.isoformat() + "Z" if published_date else datetime.now().isoformat(),
                    "summary": entry.get("summary", ""),
                    "content": content_value,
                }

                articles.append(article)
        except (ValueError, TypeError) as err:
            print(f"Error parsing feed content for {feed_url}: {err}")
        except Exception as err:
            print(f"Unexpected error parsing feed for {feed_url}: {err}")

        return feed_title, articles

    def store_article(self, article):
        """Stores the article in CouchDB if it doesn't already exist."""
        hash_payload = {
            "title": article["title"],
            "link": article["link"],
            "feed_url": article["feed_url"],
        }
        article_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True).encode("utf-8")).hexdigest()
        article["_id"] = article_hash

        try:
            response = requests.head(f"{self.couchdb_url}/{article_hash}")
            if response.status_code == 200:
                return

            response = requests.post(self.couchdb_url, json=article)
            if response.status_code not in (200, 201):
                print(f"Failed to store article {article_hash}: {response.status_code} {response.text}")
        except requests.exceptions.RequestException as err:
            print(f"Error storing article {article_hash}: {err}")
        except Exception as err:
            print(f"Unexpected error storing article {article_hash}: {err}")
