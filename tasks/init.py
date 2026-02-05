import os
import requests
from api.db import COUCHDB_URI
from .cleanup_task import CleanupTask

# initialise the CouchDB database if they don't yet exists

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
        # Ensure DB exists
        requests.put(f"{COUCHDB_URI}/{db_name}")
        
        response = requests.post(url, json=payload)
        if response.status_code in (200, 201):
             print(f"Index '{name}' created/verified on '{db_name}'")
        else:
             print(f"Failed to create index '{name}' on '{db_name}': {response.text}")
    except Exception as e:
        print(f"Error creating index on '{db_name}': {e}")

def init_db():
  # Skip network check as initContainer handles it
  print("Assuming CouchDB is ready (handled by initContainer).")
  
  # Create indexes
  create_index("articles", ["published"], "published-index")
  create_index("events", ["article_links"], "events-links-index")
  create_index("trends", ["event_ids"], "trends-events-index")
  
  return

def run():
  print("Initialising database...")
  init_db()
  
  print("Starting cleanup task...")
  cleanup = CleanupTask()
  cleanup.start()
