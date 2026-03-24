"""
Userspace CRUD routes.

Each user can own one or more userspaces.  A userspace is the environment
that owns feeds, articles, issues, agents, and LLM credentials.  All existing
data already carries the userspace UUID as a field — this API manages the
userspace document itself.
"""

import logging
import uuid
from datetime import datetime, timezone

from flask import Blueprint, abort, g, jsonify, request
from pydantic import ValidationError

from api.auth import jwt_required
from api.db import fetch_from_couchdb, store_to_couchdb, update_couchdb_doc_safe, delete_from_couchdb
from api.extensions import limiter
from api.userspace_ops import USERSPACES_DB, get_userspaces_for_user, get_userspace
from api.validation import UserspaceCreateRequest, UserspaceUpdateRequest

logger = logging.getLogger(__name__)

userspace_blueprint = Blueprint("userspaces", __name__)

ERROR_NOT_FOUND = "Userspace not found"
ERROR_ACCESS_DENIED = "Access denied"


def _check_ownership(doc: dict) -> None:
    """Abort 403 if the current user does not own this userspace."""
    if doc.get("owner_user_id") != g.user_id:
        abort(403, description=ERROR_ACCESS_DENIED)


@userspace_blueprint.route("/userspaces", methods=["GET"])
@jwt_required
@limiter.limit("60/minute")
def list_userspaces():
    docs = get_userspaces_for_user(g.user_id)
    return jsonify(docs)


@userspace_blueprint.route("/userspaces", methods=["POST"])
@jwt_required
@limiter.limit("20/minute")
def create_userspace():
    try:
        payload = UserspaceCreateRequest(**request.json)
    except (ValidationError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "_id": str(uuid.uuid4()),
        "type": "userspace",
        "owner_user_id": g.user_id,
        "name": payload.name,
        "llm_config": payload.llm_config.model_dump() if payload.llm_config else {},
        "preferences": payload.preferences or {},
        "created_at": now,
        "updated_at": now,
    }

    result = store_to_couchdb(USERSPACES_DB, doc)
    if not result or not result.get("ok"):
        logger.error("Failed to create userspace: %s", result)
        return jsonify({"error": "Failed to create userspace"}), 500

    created = fetch_from_couchdb(USERSPACES_DB, doc["_id"])
    return jsonify(created), 201


@userspace_blueprint.route("/userspaces/<userspace_id>", methods=["GET"])
@jwt_required
@limiter.limit("60/minute")
def get_userspace_route(userspace_id: str):
    doc = get_userspace(userspace_id)
    if not doc:
        abort(404, description=ERROR_NOT_FOUND)
    _check_ownership(doc)
    return jsonify(doc)


@userspace_blueprint.route("/userspaces/<userspace_id>", methods=["PATCH"])
@jwt_required
@limiter.limit("30/minute")
def update_userspace(userspace_id: str):
    doc = get_userspace(userspace_id)
    if not doc:
        abort(404, description=ERROR_NOT_FOUND)
    _check_ownership(doc)

    try:
        payload = UserspaceUpdateRequest(**request.json)
    except (ValidationError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    updates: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.llm_config is not None:
        updates["llm_config"] = payload.llm_config.model_dump()
    if payload.preferences is not None:
        updates["preferences"] = payload.preferences

    success = update_couchdb_doc_safe(USERSPACES_DB, userspace_id, updates)
    if not success:
        return jsonify({"error": "Failed to update userspace"}), 500

    updated = get_userspace(userspace_id)
    return jsonify(updated)


@userspace_blueprint.route("/userspaces/<userspace_id>", methods=["DELETE"])
@jwt_required
@limiter.limit("10/minute")
def delete_userspace(userspace_id: str):
    doc = get_userspace(userspace_id)
    if not doc:
        abort(404, description=ERROR_NOT_FOUND)
    _check_ownership(doc)

    success = delete_from_couchdb(USERSPACES_DB, userspace_id, doc["_rev"])
    if not success:
        return jsonify({"error": "Failed to delete userspace"}), 500

    return jsonify({"status": "deleted", "id": userspace_id})
