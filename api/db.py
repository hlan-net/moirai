from flask import abort
import requests
import urllib.parse
import re
import logging
from api.db_config import get_couchdb_uri
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Configure logging for database operations
logger = logging.getLogger(__name__)


# Retry configuration
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        )
    ),
    reraise=True,
)
def _request(method, url, **kwargs):
    """
    Helper to make HTTP requests with retry logic for transient network errors.
    Does NOT retry on HTTP 5xx errors automatically to avoid side effects,
    but handles connection/timeout errors.
    Default timeout set to 10s if not provided.
    """
    if "timeout" not in kwargs:
        kwargs["timeout"] = 10

    response = requests.request(method, url, **kwargs)
    return response


# Allowed database names for security validation
ALLOWED_DBS = {
    "feeds",
    "articles",
    "issues",
    "config",
    "chat_history",
    "users",
    "agent_configs",
}

# Error messages
ERROR_INVALID_DB_NAME = "Invalid database name."


def fetch_from_couchdb(db_name, doc_id=None):
    """Fetches data from CouchDB. If doc_id is None, lists all documents in the database."""
    if db_name not in ALLOWED_DBS:
        abort(400, description=ERROR_INVALID_DB_NAME)

    # Validate doc_id format if provided
    if doc_id and not re.match(r"^[A-Za-z0-9\-_]+$", doc_id):
        abort(400, description="Invalid document id.")

    try:
        if doc_id:
            safe_db_name = urllib.parse.quote(db_name, safe="")
            safe_doc_id = urllib.parse.quote(doc_id, safe="")
            response = _request("GET", f"{get_couchdb_uri()}{safe_db_name}/{safe_doc_id}")
        else:
            response = _request(
                "GET",
                f"{get_couchdb_uri()}{db_name}/_all_docs",
                params={"include_docs": "true"},
            )

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
        response = _request("POST", f"{get_couchdb_uri()}{safe_db_name}", json=doc)
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
        response = _request(
            "DELETE", f"{get_couchdb_uri()}{safe_db_name}/{safe_doc_id}", params={"rev": rev}
        )
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
        response = _request(
            "PUT", f"{get_couchdb_uri()}{safe_db_name}/{safe_doc_id}", json=doc
        )
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

        response = _request(
            "POST",
            f"{get_couchdb_uri()}{safe_db_name}/_find",
            json=query,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 404:
            return []

        response.raise_for_status()
        return response.json().get("docs", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error querying CouchDB: {e}")
        return []


def get_user_by_email(email):
    """Retrieve a user document by email."""
    users = query_couchdb("users", {"email": email}, limit=1)
    return users[0] if users else None


def create_user(user_doc):
    """Create a new user in the users database.
    user_doc must contain 'email' and 'password_hash'.
    """
    if "email" not in user_doc:
        return False, "Email required"

    # Check if user exists
    if get_user_by_email(user_doc["email"]):
        return False, "User already exists"

    response = store_to_couchdb("users", user_doc)
    if response and "id" in response:
        return True, response["id"]
    return False, "Database error"


def update_user(user_id, updates):
    """Update user document."""
    user = fetch_from_couchdb("users", user_id)
    if not user:
        return False, "User not found"

    user.update(updates)
    return update_couchdb_doc("users", user_id, user)


def query_couchdb_view(db_name, design_doc, view_name, group=True):
    """Query a MapReduce view."""
    if db_name not in ALLOWED_DBS:
        abort(400, description=ERROR_INVALID_DB_NAME)

    safe_db_name = urllib.parse.quote(db_name, safe="")
    safe_design_doc = urllib.parse.quote(design_doc, safe="")
    safe_view_name = urllib.parse.quote(view_name, safe="")

    url = (
        f"{get_couchdb_uri()}{safe_db_name}/_design/{safe_design_doc}/_view/{safe_view_name}"
    )
    params = {"group": "true" if group else "false"}

    try:
        response = _request("GET", url, params=params)

        # Handle 404 separately - design doc or view doesn't exist
        if response.status_code == 404:
            logger.warning(
                f"CouchDB view not found: {design_doc}/{view_name} in {db_name}"
            )
            return []

        # Raise for any other HTTP errors (401, 403, 5xx, etc.)
        # This will propagate errors properly instead of silently returning empty list
        response.raise_for_status()

        return response.json().get("rows", [])
    except requests.exceptions.HTTPError as e:
        # Log HTTP errors with full details before re-raising
        logger.error(
            f"HTTP error querying CouchDB view {design_doc}/{view_name}: {e.response.status_code} {e.response.text}"
        )
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Error querying CouchDB view {design_doc}/{view_name}: {e}")
        raise
