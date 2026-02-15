"""Shared database configuration and connection utilities.

This module provides centralized CouchDB connection configuration
to avoid code duplication across the application.
"""

import os
from urllib.parse import quote


def get_couchdb_uri():
    """
    Build and return the CouchDB connection URI with credentials.

    Returns:
        str: Complete CouchDB URI with embedded credentials if provided

    Environment Variables:
        COUCHDB_URI: Base CouchDB URI (default: http://localhost:5984/)
        COUCHDB_USER: Database username (optional)
        COUCHDB_PASSWORD: Database password (optional)
    """
    couchdb_uri = os.environ.get("COUCHDB_URI", "http://localhost:5984/").rstrip("/")
    user = os.environ.get("COUCHDB_USER")
    password = os.environ.get("COUCHDB_PASSWORD")

    # Inject credentials into URI if provided and not already present
    if user and password and "@" not in couchdb_uri:
        if "://" in couchdb_uri:
            scheme, host = couchdb_uri.split("://", 1)
        else:
            scheme, host = "http", couchdb_uri
        couchdb_uri = f"{scheme}://{quote(user)}:{quote(password)}@{host}"

    # Ensure trailing slash for consistent URL construction
    if not couchdb_uri.endswith("/"):
        couchdb_uri += "/"

    return couchdb_uri



