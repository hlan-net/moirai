from flask import abort
import os
import requests
import urllib.parse

COUCHDB_URI = os.environ.get("COUCHDB_URI", "http://localhost:5984/").rstrip("/")
user = os.environ.get("COUCHDB_USER")
password = os.environ.get("COUCHDB_PASSWORD")
if user and password and "@" not in COUCHDB_URI:
    from urllib.parse import quote
    if "://" in COUCHDB_URI:
        scheme, host = COUCHDB_URI.split("://", 1)
    else:
        scheme, host = "http", COUCHDB_URI
    COUCHDB_URI = f"{scheme}://{quote(user)}:{quote(password)}@{host}"

def fetch_from_couchdb(db_name, doc_id=None):
    """Fetches data from CouchDB. If doc_id is None, lists all documents in the database."""
    allowed_dbs = {"feeds", "articles", "events", "trends", "config", "chat_history"}
    if db_name not in allowed_dbs:
        abort(400, description="Invalid database name.")
    
    try:
        if doc_id:
            safe_db_name = urllib.parse.quote(db_name, safe="")
            safe_doc_id = urllib.parse.quote(doc_id, safe="")
            response = requests.get(f"{COUCHDB_URI}/{safe_db_name}/{safe_doc_id}")
        else:
            # Check if DB exists first (lazy check for 'trends', 'config')
            requests.put(f"{COUCHDB_URI}/{db_name}") 
            response = requests.get(f"{COUCHDB_URI}/{db_name}/_all_docs", params={"include_docs": "true"})

        if response.status_code == 404:
             return None if doc_id else []
        
        response.raise_for_status()
        
        if doc_id:
            return response.json()
        else:
            docs = [row["doc"] for row in response.json().get("rows", [])]
            return docs
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from CouchDB: {e}")
        return None

def delete_from_couchdb(db_name, doc_id, rev):
    safe_db_name = urllib.parse.quote(db_name, safe="")
    safe_doc_id = urllib.parse.quote(doc_id, safe="")
    try:
        response = requests.delete(f"{COUCHDB_URI}/{safe_db_name}/{safe_doc_id}", params={"rev": rev})
        return response.status_code in (200, 202)
    except requests.exceptions.RequestException:
        return False

def update_couchdb_doc(db_name, doc_id, doc):
    safe_db_name = urllib.parse.quote(db_name, safe="")
    safe_doc_id = urllib.parse.quote(doc_id, safe="")
    try:
        # Ensure DB exists
        create_res = requests.put(f"{COUCHDB_URI}/{safe_db_name}")
        if create_res.status_code not in (200, 201, 412):
             print(f"DB Creation Failed: {create_res.status_code} {create_res.text}")
        
        response = requests.put(f"{COUCHDB_URI}/{safe_db_name}/{safe_doc_id}", json=doc)
        if response.status_code in (200, 201):
            return True
        else:
            print(f"DB Update Failed: {response.status_code} {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"DB Update Error: {e}")
        return False

def query_couchdb(db_name, selector, limit=None, skip=0, sort=None, fields=None):
    """Query CouchDB using Mango query syntax for efficient filtering."""
    allowed_dbs = {"feeds", "articles", "events", "trends", "config", "chat_history"}
    if db_name not in allowed_dbs:
        abort(400, description="Invalid database name.")
    
    safe_db_name = urllib.parse.quote(db_name, safe="")
    
    try:
        # Ensure DB exists
        requests.put(f"{COUCHDB_URI}/{safe_db_name}")
        
        # Build Mango query
        query = {"selector": selector}
        if limit:
            query["limit"] = limit
        if skip:
            query["skip"] = skip
        if sort:
            query["sort"] = sort
        if fields:
            query["fields"] = fields
        
        response = requests.post(
            f"{COUCHDB_URI}/{safe_db_name}/_find",
            json=query,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 404:
            return []
        
        response.raise_for_status()
        return response.json().get("docs", [])
    except requests.exceptions.RequestException as e:
        print(f"Error querying CouchDB: {e}")
        return []
