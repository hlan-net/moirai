import os
import requests
from api.db import COUCHDB_URI, _request
from .cleanup_task import CleanupTask
from tenacity import retry, stop_after_delay, wait_fixed, retry_if_exception_type
import requests

# initialise the CouchDB database if they don't yet exists

def ensure_db(db_name):
    try:
        response = _request('PUT', f"{COUCHDB_URI}/{db_name}")
        if response.status_code in (200, 201):
            print(f"Database '{db_name}' created.")
        elif response.status_code == 412:
            # Database already exists
            pass
        else:
            print(f"Failed to ensure database '{db_name}': {response.text}")
    except Exception as e:
        print(f"Error ensuring database '{db_name}': {e}")

def create_index(db_name, fields, name):
    url = f"{COUCHDB_URI}/{db_name}/_index"
    payload = {
        "index": {
            "fields": fields
        },
        "name": name,
        "type": "json"
    }
    try:
        # Ensure DB exists before index creation
        ensure_db(db_name)
        
        response = _request('POST', url, json=payload)
        if response.status_code in (200, 201):
             print(f"Index '{name}' created/verified on '{db_name}'")
        else:
             print(f"Failed to create index '{name}' on '{db_name}': {response.text}")
    except Exception as e:
        print(f"Error creating index on '{db_name}': {e}")

def ensure_design_doc(db_name, design_doc_name, views):
    url = f"{COUCHDB_URI}/{db_name}/_design/{design_doc_name}"
    
    # Check if exists to get current rev
    try:
        response = _request('GET', url)
        design_doc = {
            "views": views
        }
        
        if response.status_code == 200:
            current = response.json()
            # Only update if views changed
            if current.get("views") == views:
                return
            design_doc["_rev"] = current["_rev"]
            
        response = _request('PUT', url, json=design_doc)
        if response.status_code in (200, 201):
            print(f"Design doc '{design_doc_name}' on '{db_name}' updated.")
        else:
            print(f"Failed to update design doc '{design_doc_name}': {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error ensuring design doc on '{db_name}': {e}")

@retry(
    stop=stop_after_delay(60),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError)),
    reraise=True
)
def init_db():
  # Skip network check as initContainer handles it
  print("Assuming CouchDB is ready (handled by initContainer).")
  
  # Ensure all databases exist
  allowed_dbs = ["feeds", "articles", "events", "trends", "config", "chat_history"]
  for db in allowed_dbs:
      ensure_db(db)
  
  # Create indexes
  create_index("articles", ["published"], "published-index")
  create_index("articles", ["feed_url"], "feed-url-index")
  create_index("events", ["article_links"], "events-links-index")
  create_index("trends", ["event_ids"], "trends-events-index")

  # Create MapReduce views for statistics
  ensure_design_doc("articles", "stats", {
      "by_language": {
          "map": "function(doc) { if (doc.language) emit(doc.language, 1); }",
          "reduce": "_count"
      }
  })
  
  ensure_design_doc("feeds", "health", {
      "status": {
          "map": "function(doc) { if (doc.last_fetch_error) { emit('error', 1); } else { emit('success', 1); } }",
          "reduce": "_count"
      }
  })
  
  return

def run():
  print("Initialising database...")
  init_db()
  
  print("Starting cleanup task...")
  cleanup = CleanupTask()
  cleanup.start()
