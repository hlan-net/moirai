import os
import requests
import datetime
import logging
from api.db_config import get_couchdb_uri
from api.db import _request, get_user_by_email, create_user
from api.auth import hash_password
from .cleanup_task import CleanupTask
from tenacity import retry, stop_after_delay, wait_fixed, retry_if_exception_type

logger = logging.getLogger(__name__)

# initialise the CouchDB database if they don't yet exists

ARTICLE_VALIDATE_DOC = r"""
function(newDoc, oldDoc, userCtx, secObj) {
  if (newDoc._deleted) {
    return;
  }
  if (newDoc._id && newDoc._id.indexOf('_design/') === 0) {
    return;
  }

  var required = ['feed_url', 'title', 'link', 'published', 'language'];
  for (var i = 0; i < required.length; i++) {
    var field = required[i];
    if (!newDoc[field]) {
      throw({forbidden: 'Missing required field: ' + field});
    }
  }

  if (typeof newDoc.feed_url !== 'string' || newDoc.feed_url.length === 0) {
    throw({forbidden: 'feed_url must be a non-empty string'});
  }
  if (typeof newDoc.title !== 'string' || newDoc.title.length === 0) {
    throw({forbidden: 'title must be a non-empty string'});
  }
  if (typeof newDoc.link !== 'string' || newDoc.link.length === 0) {
    throw({forbidden: 'link must be a non-empty string'});
  }

  if (typeof newDoc.language !== 'string' || !/^[A-Za-z]{2}$/.test(newDoc.language)) {
    throw({forbidden: 'language must be a 2-character ISO code'});
  }

  var isoDate = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$/;
  if (typeof newDoc.published !== 'string' || !isoDate.test(newDoc.published)) {
    throw({forbidden: 'published must be an ISO 8601 datetime'});
  }
}
"""

FEED_VALIDATE_DOC = r"""
function(newDoc, oldDoc, userCtx, secObj) {
  if (newDoc._deleted) {
    return;
  }
  if (newDoc._id && newDoc._id.indexOf('_design/') === 0) {
    return;
  }

  var required = ['url', 'original_url', 'category', 'added_at'];
  for (var i = 0; i < required.length; i++) {
    var field = required[i];
    if (!newDoc[field]) {
      throw({forbidden: 'Missing required field: ' + field});
    }
  }

  if (typeof newDoc.url !== 'string' || newDoc.url.length === 0) {
    throw({forbidden: 'url must be a non-empty string'});
  }
  if (typeof newDoc.original_url !== 'string' || newDoc.original_url.length === 0) {
    throw({forbidden: 'original_url must be a non-empty string'});
  }
  if (typeof newDoc.category !== 'string' || newDoc.category.length === 0) {
    throw({forbidden: 'category must be a non-empty string'});
  }
  if (newDoc.title !== undefined && newDoc.title !== null && typeof newDoc.title !== 'string') {
    throw({forbidden: 'title must be a string when provided'});
  }

  var isoDate = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$/;
  if (typeof newDoc.added_at !== 'string' || !isoDate.test(newDoc.added_at)) {
    throw({forbidden: 'added_at must be an ISO 8601 datetime'});
  }
}
"""


def ensure_db(db_name):
    try:
        response = _request("PUT", f"{get_couchdb_uri()}{db_name}", timeout=10)
        if response.status_code in (200, 201):
            logger.info(f"Database '{db_name}' created.")
        elif response.status_code == 412:
            # Database already exists
            pass
        else:
            logger.error(f"Failed to ensure database '{db_name}': {response.text}")
    except Exception as e:
        logger.error(f"Error ensuring database '{db_name}': {e}")


def create_index(db_name, fields, name):
    url = f"{get_couchdb_uri()}{db_name}/_index"
    payload = {"index": {"fields": fields}, "name": name, "type": "json"}
    try:
        # Ensure DB exists before index creation
        ensure_db(db_name)

        response = _request("POST", url, json=payload, timeout=10)
        if response.status_code in (200, 201):
            logger.info(f"Index '{name}' created/verified on '{db_name}'")
        else:
            logger.error(f"Failed to create index '{name}' on '{db_name}': {response.text}")
    except Exception as e:
        logger.error(f"Error creating index on '{db_name}': {e}")


def ensure_design_doc(db_name, design_doc_name, views=None, validate_doc_update=None):
    url = f"{get_couchdb_uri()}{db_name}/_design/{design_doc_name}"
    desired_views = views if views is not None else {}

    # Check if exists to get current rev
    try:
        response = _request("GET", url, timeout=10)

        # Start from existing design doc (if present) to preserve other fields
        if response.status_code == 200:
            current = response.json()
            current_views = current.get("views", {})
            current_validate = current.get("validate_doc_update")
            if current_views == desired_views and current_validate == validate_doc_update:
                return
            design_doc = current
            design_doc["views"] = desired_views
            if validate_doc_update is None:
                design_doc.pop("validate_doc_update", None)
            else:
                design_doc["validate_doc_update"] = validate_doc_update
            # Ensure we keep the latest revision to avoid conflicts
            design_doc["_rev"] = current.get("_rev", design_doc.get("_rev"))
        else:
            # Design doc does not exist (or other non-200) – create a new one
            design_doc = {"views": desired_views}
            if validate_doc_update is not None:
                design_doc["validate_doc_update"] = validate_doc_update
        response = _request("PUT", url, json=design_doc, timeout=10)
        if response.status_code in (200, 201):
            logger.info(f"Design doc '{design_doc_name}' on '{db_name}' updated.")
        else:
            logger.error(f"Failed to update design doc '{design_doc_name}': {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error ensuring design doc on '{db_name}': {e}")


@retry(
    stop=stop_after_delay(60),
    wait=wait_fixed(2),
    retry=retry_if_exception_type(
        (requests.exceptions.RequestException, ConnectionError)
    ),
    reraise=True,
)
def init_db():
    # Skip network check as initContainer handles it
    logger.info("Assuming CouchDB is ready (handled by initContainer).")

    # Ensure all databases exist
    allowed_dbs = [
        "feeds",
        "articles",
        "config",
        "chat_history",
        "users",
        "feed_content",
    ]
    for db in allowed_dbs:
        ensure_db(db)

    # Create indexes
    create_index("articles", ["published"], "published-index")
    create_index("articles", ["feed_url"], "feed-url-index")
    create_index("users", ["email"], "users-email-index")

    ensure_design_doc(
        "articles",
        "validation",
        views={},
        validate_doc_update=ARTICLE_VALIDATE_DOC.strip(),
    )

    ensure_design_doc(
        "feeds",
        "validation",
        views={},
        validate_doc_update=FEED_VALIDATE_DOC.strip(),
    )

    # Create MapReduce views for statistics
    ensure_design_doc(
        "articles",
        "stats",
        {
            "by_language": {
                "map": "function(doc) { if (doc.language) emit(doc.language, 1); }",
                "reduce": "_count",
            }
        },
    )

    ensure_design_doc(
        "feeds",
        "health",
        {
            "status": {
                "map": "function(doc) { if (doc.last_fetch_error) { emit('error', 1); } else { emit('success', 1); } }",
                "reduce": "_count",
            }
        },
    )

    return


def ensure_default_user():
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if not admin_username or not admin_password:
        logger.info(
            "No ADMIN_USERNAME/ADMIN_PASSWORD found. Skipping default user creation."
        )
        return

    try:
        admin_email = f"{admin_username}@localhost.local"
        existing = get_user_by_email(admin_email)
        if existing:
            logger.info(f"Default admin user '{admin_email}' already exists.")
            return

        logger.info(f"Creating default admin user '{admin_email}'...")
        hashed = hash_password(admin_password)
        user_doc = {
            "email": admin_email,
            "password_hash": hashed,
            "role": "admin",
            "settings": {},
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        success, result = create_user(user_doc)
        if success:
            logger.info(f"Default admin user '{admin_email}' created successfully.")
        else:
            logger.error(f"Failed to create default user: {result}")

    except Exception as e:
        logger.error(f"Error ensuring default user: {e}")


def run():
    logger.info("Initialising database...")
    init_db()
    ensure_default_user()

    logger.info("Starting cleanup task...")
    cleanup = CleanupTask()
    cleanup.start()
