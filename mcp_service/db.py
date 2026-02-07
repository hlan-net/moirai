import hashlib
import json
import requests
from .config import COUCHDB_URI

# --- DB Helpers ---

def get_db_url(db_name):
    return f"{COUCHDB_URI}{db_name}"

def db_request(method, db_name, path="", json_data=None, params=None):
    url = f"{get_db_url(db_name)}{path}"
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=json_data)
        elif method == "PUT":
            response = requests.put(url, json=json_data)
        elif method == "HEAD":
            response = requests.head(url)
        
        # Don't raise for 404s if we want to handle them gracefully in callers
        if response.status_code >= 400 and response.status_code != 404:
            print(f"DB Error {method} {url}: {response.text}")
            
        return response
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Database connection error: {e}")

def get_doc(db_name, doc_id):
    res = db_request("GET", db_name, path=f"/{doc_id}")
    if res.status_code == 200:
        return res.json()
    return None

def store_doc(db_name, doc):
    if "_id" not in doc:
        # Generate hash ID if not present
        doc_hash = hashlib.sha256(json.dumps(doc, sort_keys=True).encode('utf-8')).hexdigest()
        doc["_id"] = doc_hash

    existing = get_doc(db_name, doc["_id"])
    if existing:
        return f"Document {doc['_id']} already exists."
    
    res = db_request("POST", db_name, json_data=doc)
    if res.status_code in (200, 201):
        return doc["_id"]
    else:
        raise RuntimeError(f"Failed to store doc: {res.text}")

def update_doc(db_name, doc_id, updates):
    """
    Updates a document by fetching it, applying updates, and saving it back.
    Handles revision matching.
    """
    doc = get_doc(db_name, doc_id)
    if not doc:
        return None, "Document not found."
    
    doc.update(updates)
    res = db_request("PUT", db_name, path=f"/{doc_id}", json_data=doc)
    if res.status_code in (200, 201):
        return doc_id, None
    else:
        return None, f"Failed to update doc: {res.text}"

def delete_doc(db_name, doc_id):
    """
    Deletes a document. Requires fetching first to get the revision.
    """
    doc = get_doc(db_name, doc_id)
    if not doc:
        return False, "Document not found."
    
    res = db_request("DELETE", db_name, path=f"/{doc_id}", params={"rev": doc["_rev"]})
    if res.status_code in (200, 202):
        return True, None
    else:
        return False, f"Failed to delete doc: {res.text}"
