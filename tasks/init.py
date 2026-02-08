import os
import requests
import datetime
from api.db import COUCHDB_URI, _request, get_user_by_email, create_user
from api.auth import hash_password
from .cleanup_task import CleanupTask
from tenacity import retry, stop_after_delay, wait_fixed, retry_if_exception_type

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
  allowed_dbs = ["feeds", "articles", "events", "trends", "config", "chat_history", "users"]
  for db in allowed_dbs:
      ensure_db(db)
  
  # Create indexes
  create_index("articles", ["published"], "published-index")
  create_index("articles", ["feed_url"], "feed-url-index")
  create_index("events", ["article_links"], "events-links-index")
  create_index("trends", ["event_ids"], "trends-events-index")
  create_index("users", ["email"], "users-email-index")
  
  return

def ensure_default_user():
    username = os.environ.get("API_USERNAME")
    password = os.environ.get("API_PASSWORD")
    
    if not username or not password:
        print("No API_USERNAME/API_PASSWORD found. Skipping default user creation.")
        return

    try:
        existing = get_user_by_email(username)
        if existing:
            print(f"Default user '{username}' already exists.")
            return

        print(f"Creating default admin user '{username}'...")
        hashed = hash_password(password)
        user_doc = {
            "email": username,
            "password_hash": hashed,
            "role": "admin",
            "settings": {},
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        success, result = create_user(user_doc)
        if success:
            print(f"Default admin user '{username}' created successfully.")
        else:
            print(f"Failed to create default user: {result}")
            
    except Exception as e:
        print(f"Error ensuring default user: {e}")

def run():
  print("Initialising database...")
  init_db()
  ensure_default_user()
  
  print("Starting cleanup task...")
  cleanup = CleanupTask()
  cleanup.start()
