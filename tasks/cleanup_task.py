import os
import time
import requests
import datetime
import threading
from urllib.parse import quote
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.db_config import COUCHDB_URI


def get_all_docs(db_name):
    try:
        url = f"{COUCHDB_URI}{db_name}/_all_docs?include_docs=true"
        res = requests.get(url)
        if res.status_code == 200:
            return [row["doc"] for row in res.json().get("rows", [])]
    except Exception as e:
        print(f"Cleanup: Error fetching {db_name}: {e}")
    return []


def delete_doc(db_name, doc_id, rev):
    try:
        url = f"{COUCHDB_URI}{db_name}/{quote(doc_id, safe='')}?rev={rev}"
        res = requests.delete(url)
        return res.status_code in (200, 202)
    except Exception as e:
        print(f"Cleanup: Error deleting {doc_id} from {db_name}: {e}")
    return False


def parse_date(date_str):
    if not date_str:
        return datetime.datetime.now()
    # Handle various formats or fallback
    try:
        # ISO format
        return datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    return datetime.datetime.now()


def run_cleanup():
    print("Cleanup: Starting maintenance cycle...")

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Fetch Trends to find active Events
    trends = get_all_docs("trends")
    linked_event_ids = set()
    for t in trends:
        if "event_ids" in t and isinstance(t["event_ids"], list):
            for eid in t["event_ids"]:
                linked_event_ids.add(eid)

    print(
        f"Cleanup: Found {len(trends)} trends referencing {len(linked_event_ids)} events."
    )

    # 2. Fetch Events, Delete Orphans, and Collect Active Article Links
    events = get_all_docs("events")
    active_article_links = set()
    events_deleted = 0
    events_kept = 0

    for e in events:
        eid = e.get("_id")
        created_at = e.get("created_at")

        dt = parse_date(created_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        age = now - dt

        # Check if Event should be deleted
        # Condition: Not in any Trend AND older than 1 year (365 days)
        if eid not in linked_event_ids and age.days > 365:
            print(f"Cleanup: Deleting orphaned event {eid} (Age: {age.days} days)")
            if delete_doc("events", eid, e.get("_rev")):
                events_deleted += 1
        else:
            # Event is kept. Collect its articles.
            events_kept += 1
            if "article_links" in e and isinstance(e["article_links"], list):
                for link in e["article_links"]:
                    active_article_links.add(link)

    print(
        f"Cleanup: Events processed. Deleted: {events_deleted}. Kept: {events_kept}. Active referenced articles: {len(active_article_links)}"
    )

    # 3. Fetch Articles and Delete Orphans
    articles = get_all_docs("articles")
    articles_deleted = 0

    for a in articles:
        link = a.get("link")
        aid = a.get("_id")
        published = a.get("published")

        dt = parse_date(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        age = now - dt

        # Check if Article should be deleted
        # Condition: Not linked to any *surviving* Event AND older than 30 days
        # Note: 'link' is the URL, which is the foreign key used in events
        if link not in active_article_links and age.days > 30:
            print(f"Cleanup: Deleting orphaned article {aid} (Age: {age.days} days)")
            if delete_doc("articles", aid, a.get("_rev")):
                articles_deleted += 1

    print(
        f"Cleanup: Finished. Deleted {events_deleted} events and {articles_deleted} articles."
    )


class CleanupTask(threading.Thread):
    def __init__(self, interval=86400):  # Default 24 hours
        threading.Thread.__init__(self)
        self.interval = interval
        self.daemon = True

    def run(self):
        while True:
            try:
                run_cleanup()
            except Exception as e:
                print(f"Cleanup: Unexpected error in loop: {e}")
            time.sleep(self.interval)
