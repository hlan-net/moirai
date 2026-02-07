from flask import abort
import os
import requests
import urllib.parse
import re
import logging
from api.db_config import COUCHDB_URI

# Configure logging for database operations
logger = logging.getLogger(__name__)

# Allowed database names for security validation
ALLOWED_DBS = {"feeds", "articles", "events", "trends", "config", "chat_history"}

# Error messages
ERROR_INVALID_DB_NAME = "Invalid database name."


def fetch_from_couchdb(db_name, doc_id=None):
    """Fetches data from CouchDB. If doc_id is None, lists all documents in the database."""
    if db_name not in ALLOWED_DBS:
        abort(400, description=ERROR_INVALID_DB_NAME)
    
    # Validate doc_id format if provided
    if doc_id and not re.match(r'^[A-Za-z0-9\-_]+$', doc_id):
        abort(400, description="Invalid document id.")
    
    try:
        if doc_id:
            safe_db_name = urllib.parse.quote(db_name, safe="")
            safe_doc_id = urllib.parse.quote(doc_id, safe="")
            response = requests.get(f"{COUCHDB_URI}{safe_db_name}/{safe_doc_id}")
        else:
            response = requests.get(f"{COUCHDB_URI}{db_name}/_all_docs", params={"include_docs": "true"})

        if response.status_code == 404:
             return None if doc_id else []
        
        response.raise_for_status()
        
        if doc_id:
            return response.json()
        else:
            docs = [row["doc"] for row in response.json().get("rows", [])]
            return docs
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching from CouchDB: {e}")
        return None


def store_to_couchdb(db_name, doc):
    """Stores a document to CouchDB."""
    if db_name not in ALLOWED_DBS:
        abort(400, description=ERROR_INVALID_DB_NAME)
    
    try:
        safe_db_name = urllib.parse.quote(db_name, safe="")
        response = requests.post(f"{COUCHDB_URI}{safe_db_name}", json=doc)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error storing to CouchDB: {e}")
        return abort(500, description="Database error")

def delete_from_couchdb(db_name, doc_id, rev):
    """Delete a document from CouchDB."""
    if db_name not in ALLOWED_DBS:
        abort(400, description=ERROR_INVALID_DB_NAME)
        
    safe_db_name = urllib.parse.quote(db_name, safe="")
    safe_doc_id = urllib.parse.quote(doc_id, safe="")
    try:
        response = requests.delete(f"{COUCHDB_URI}{safe_db_name}/{safe_doc_id}", params={"rev": rev})
        return response.status_code in (200, 202)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting from CouchDB: {e}")
        return False


def update_couchdb_doc(db_name, doc_id, doc):
    """Update a document in CouchDB."""
    if db_name not in ALLOWED_DBS:
        abort(400, description=ERROR_INVALID_DB_NAME)
        
    safe_db_name = urllib.parse.quote(db_name, safe="")
    safe_doc_id = urllib.parse.quote(doc_id, safe="")
    try:
        response = requests.put(f"{COUCHDB_URI}{safe_db_name}/{safe_doc_id}", json=doc)
        if response.status_code in (200, 201):
            return True
        else:
            logger.error(f"DB Update Failed: {response.status_code} {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"DB Update Error: {e}")
        return False

def query_couchdb(db_name, selector, limit=None, skip=0, sort=None, fields=None):
    """Query CouchDB using Mango query syntax for efficient filtering."""
    if db_name not in ALLOWED_DBS:
        abort(400, description=ERROR_INVALID_DB_NAME)
    
    safe_db_name = urllib.parse.quote(db_name, safe="")
    
    try:
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
            f"{COUCHDB_URI}{safe_db_name}/_find",
            json=query,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 404:
            return []
        
        response.raise_for_status()
        return response.json().get("docs", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error querying CouchDB: {e}")
        return []
