import bleach
import uuid
from flask import Blueprint, abort, g, jsonify, request
from pydantic import ValidationError
from typing import Any, cast

from api.auth import jwt_required
from api.db import delete_from_couchdb, fetch_from_couchdb, query_couchdb, update_couchdb_doc
from api.validation import (
    AgentConfigCreateRequest,
    AgentConfigUpdateRequest,
    validate_userspace_param,
)

agent_blueprint = Blueprint("agents", __name__)


def _userspace_selector(userspace: str) -> dict:
    return {"$or": [{"userspace": userspace}, {"namespace": userspace}]}


def _extract_userspace(doc: dict) -> str | None:
    return doc.get("userspace") or doc.get("namespace")


def _sanitize_agent_payload(payload: dict) -> dict:
    sanitized = dict(payload)
    for field in ["name", "logic_module", "schedule_interval"]:
        if field in sanitized and isinstance(sanitized[field], str):
            sanitized[field] = bleach.clean(sanitized[field], strip=True)
    return sanitized


def _sanitize_create_payload(payload: dict) -> dict:
    return _sanitize_agent_payload(payload)


def _sanitize_update_payload(payload: dict) -> dict:
    return _sanitize_agent_payload(payload)


def _enforce_owner(owner_user_id: str | None) -> str:
    if owner_user_id and owner_user_id != g.user_id and g.user_role != "admin":
        abort(403, description="Cannot manage agent configs for another user")
    return owner_user_id or g.user_id


def _validate_userspace(userspace: str | None, field_name: str) -> str:
    if not userspace:
        abort(400, description=f"'{field_name}' is required")
    validated_userspace = cast(str, userspace)
    try:
        validate_userspace_param(validated_userspace)
    except ValueError as exc:
        abort(400, description=str(exc))
    return validated_userspace


def _get_owned_agent_doc(agent_id: str, userspace: str) -> dict[str, Any]:
    doc = fetch_from_couchdb("agent_configs", agent_id)
    if not isinstance(doc, dict) or _extract_userspace(doc) != userspace:
        abort(404, description="Agent configuration not found")
    doc_data = cast(dict[str, Any], doc)

    if g.user_role != "admin" and doc_data.get("owner_user_id") != g.user_id:
        abort(404, description="Agent configuration not found")

    return doc_data


@agent_blueprint.route("/agents", methods=["GET"])
@jwt_required
def list_agents():
    userspace = _validate_userspace(request.args.get("userspace"), "userspace")

    owner_only = request.args.get("owner_only", "true").lower() != "false"
    selector: dict = _userspace_selector(userspace)
    if owner_only or g.user_role != "admin":
        selector = {"$and": [selector, {"owner_user_id": g.user_id}]}

    docs = query_couchdb("agent_configs", selector=selector)
    return jsonify(docs)


@agent_blueprint.route("/agents", methods=["POST"])
@jwt_required
def create_agent():
    payload = _sanitize_create_payload(request.get_json() or {})
    payload["owner_user_id"] = _enforce_owner(payload.get("owner_user_id"))
    validated: dict = {}

    try:
        validated = AgentConfigCreateRequest(**payload).model_dump()
    except ValidationError as exc:
        abort(400, description=str(exc))

    agent_id = str(uuid.uuid4())
    doc = {"_id": agent_id, **validated}

    if not update_couchdb_doc("agent_configs", agent_id, doc):
        abort(500, description="Failed to create agent configuration")

    return jsonify(doc), 201


@agent_blueprint.route("/agents/<agent_id>", methods=["GET"])
@jwt_required
def get_agent(agent_id: str):
    userspace = _validate_userspace(request.args.get("userspace"), "userspace")
    doc = _get_owned_agent_doc(agent_id, userspace)
    return jsonify(doc)


@agent_blueprint.route("/agents/<agent_id>", methods=["PUT"])
@jwt_required
def update_agent(agent_id: str):
    payload = _sanitize_update_payload(request.get_json() or {})

    userspace = _validate_userspace(
        payload.get("userspace") or request.args.get("userspace"), "userspace"
    )
    doc_data = _get_owned_agent_doc(agent_id, userspace)

    if "owner_user_id" in payload:
        payload["owner_user_id"] = _enforce_owner(payload.get("owner_user_id"))

    validated: dict = {}
    try:
        validated = AgentConfigUpdateRequest(**payload).model_dump(exclude_unset=True)
    except ValidationError as exc:
        abort(400, description=str(exc))

    doc_data.update(validated)
    if not update_couchdb_doc("agent_configs", agent_id, doc_data):
        abort(500, description="Failed to update agent configuration")

    return jsonify(doc_data)


@agent_blueprint.route("/agents/<agent_id>", methods=["DELETE"])
@jwt_required
def delete_agent(agent_id: str):
    userspace = _validate_userspace(request.args.get("userspace"), "userspace")
    doc_data = _get_owned_agent_doc(agent_id, userspace)

    rev = doc_data.get("_rev")
    if not rev or not delete_from_couchdb("agent_configs", agent_id, rev):
        abort(500, description="Failed to delete agent configuration")

    return jsonify({"status": "deleted", "agent_id": agent_id})
