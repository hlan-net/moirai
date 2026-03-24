"""
Userspace operations — fetch userspace documents and resolve LLM config.

The userspace document is the authoritative source for LLM provider credentials
and preferences. Chat and agent sessions resolve config from here rather than
from individual user settings or agent configs.
"""

import logging
from typing import Optional

from api.db import fetch_from_couchdb, query_couchdb, store_to_couchdb, update_couchdb_doc_safe

logger = logging.getLogger(__name__)

USERSPACES_DB = "userspaces"


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


def get_userspaces_for_user(owner_user_id: str) -> list[dict]:
    """Return all userspaces owned by a user."""
    return query_couchdb(USERSPACES_DB, {"owner_user_id": owner_user_id})


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
