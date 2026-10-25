"""
Userspace operations — fetch userspace documents and resolve LLM config.

The userspace document is the authoritative source for LLM provider credentials
and preferences. Chat and agent sessions resolve config from here rather than
from individual user settings or agent configs.
"""

import logging
import os
import uuid
from typing import Optional

from api.db import fetch_from_couchdb, store_to_couchdb

logger = logging.getLogger(__name__)

USERSPACES_DB = "userspaces"

_default_userspace_cache: str | None = None


def get_userspace(userspace_id: str) -> Optional[dict]:
    """Fetch a userspace document by its ID."""
    return fetch_from_couchdb(USERSPACES_DB, userspace_id)


def resolve_llm_config(userspace_id: str) -> dict:
    """Return the llm_config block from a userspace document.

    Returns an empty dict if the userspace does not exist or has no llm_config.
    Callers should check for required fields (provider, model) before use.
    """
    doc = get_userspace(userspace_id)
    if doc:
        return doc.get("llm_config") or {}
    return {}


def get_default_userspace() -> str | None:
    """Return the deployment's single implicit userspace UUID.

    Moirai runs as a single-tenant deployment: everything belongs to one
    default userspace. Resolution order:

    1. ``DEFAULT_USERSPACE`` env var (must be a UUID).
    2. The only document in the ``userspaces`` database, when exactly one exists.

    Returns None when neither yields a value; the result is cached once found.
    """
    global _default_userspace_cache
    if _default_userspace_cache:
        return _default_userspace_cache

    configured = os.environ.get("DEFAULT_USERSPACE", "").strip()
    if configured:
        try:
            _default_userspace_cache = str(uuid.UUID(configured))
            return _default_userspace_cache
        except ValueError:
            logger.error("DEFAULT_USERSPACE is not a valid UUID: %r", configured)
            return None

    docs = [
        doc
        for doc in (fetch_from_couchdb(USERSPACES_DB) or [])
        if not doc.get("_id", "").startswith("_design/")
    ]
    if len(docs) == 1:
        _default_userspace_cache = docs[0]["_id"]
        return _default_userspace_cache

    logger.warning(
        "Cannot resolve default userspace: DEFAULT_USERSPACE unset and %d userspace "
        "documents exist",
        len(docs),
    )
    return None


def migrate_user_llm_settings_to_userspace(user_doc: dict) -> bool:
    """Create a userspace document for an existing user if one does not exist yet.

    Migrates LLM credentials from ``user.settings`` into the new
    ``userspace.llm_config`` structure.  The userspace ``_id`` is the same
    UUID as the user ``_id`` so that all existing feeds/articles/issues
    (which already store this UUID as their ``userspace`` field) continue
    to resolve correctly without any data changes.

    Returns True if a new document was created, False if it already existed.
    """
    user_id = user_doc.get("_id")
    if not user_id:
        return False

    existing = get_userspace(user_id)
    if existing:
        return False

    settings = user_doc.get("settings") or {}

    llm_config = {
        "provider": settings.get("moirai_llm_provider", "ollama"),
        "model": settings.get("moirai_model", "llama3.1"),
        "openai_api_key": settings.get("moirai_openai_api_key"),
        "gemini_api_key": settings.get("moirai_gemini_api_key"),
        "ollama_endpoint": settings.get("moirai_ollama_endpoint_url"),
    }

    userspace_doc = {
        "_id": user_id,
        "type": "userspace",
        "owner_user_id": user_id,
        "name": "Default",
        "llm_config": llm_config,
        "preferences": {},
    }

    result = store_to_couchdb(USERSPACES_DB, userspace_doc)
    if result and result.get("ok"):
        logger.info("Created userspace document for user %s", user_id)
        return True
    logger.error("Failed to create userspace document for user %s", user_id)
    return False
