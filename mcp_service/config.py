import os

# Database Configuration
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

if not COUCHDB_URI.endswith("/"):
    COUCHDB_URI += "/"
