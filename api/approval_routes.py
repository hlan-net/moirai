"""REST API for agent approval workflow.

Operators can list pending approval requests for destructive tool calls
and approve or deny them.  The approval gate in :class:`TracingMCPClient`
polls Redis for decisions.
"""

import logging

from flask import Blueprint, abort, g, jsonify, request

from api.auth import jwt_required
from api.extensions import get_redis_client
from api.userspace_ops import get_userspace

logger = logging.getLogger(__name__)

_ADMIN_ROLE = "admin"

_APPROVAL_PENDING_PREFIX = "approval:pending:"
_APPROVAL_DECISION_PREFIX = "approval:decision:"
_APPROVAL_QUEUE_PREFIX = "approval:queue:"
_APPROVAL_TTL = 600

approval_blueprint = Blueprint("approvals", __name__)


def _user_owns_userspace(userspace_id: str) -> bool:
    doc = get_userspace(userspace_id)
    if not doc:
        return False
    return doc.get("owner_user_id") == g.user_id


@approval_blueprint.route("/approvals/pending", methods=["GET"])
@jwt_required
def list_pending_approvals():
    """List pending approval requests for the caller's userspaces.

    Query params
    ------------
    userspace : required UUID (must be owned by caller or caller is admin).
    """
    userspace = request.args.get("userspace")
    if not userspace:
        abort(400, description="'userspace' parameter is required")
    if not _user_owns_userspace(userspace) and g.user_role != _ADMIN_ROLE:
        abort(403, description="Access denied")

    redis_client = get_redis_client()
    if not redis_client:
        return jsonify([])

    queue_key = f"{_APPROVAL_QUEUE_PREFIX}{userspace}"
    try:
        request_ids = redis_client.lrange(queue_key, 0, 49)
    except Exception:
        logger.exception("Failed to read approval queue")
        return jsonify([])

    if not request_ids:
        return jsonify([])

    pending = [
        entry
        for rid in request_ids
        if (entry := _read_pending_request(redis_client, rid)) is not None
    ]
    return jsonify(pending)


def _read_pending_request(redis_client, rid) -> dict | None:
    """Read a single pending approval request from Redis, or return None."""
    if isinstance(rid, bytes):
        rid = rid.decode("utf-8")
    pending_key = f"{_APPROVAL_PENDING_PREFIX}{rid}"
    decision_key = f"{_APPROVAL_DECISION_PREFIX}{rid}"
    try:
        data = redis_client.hgetall(pending_key)
        if not data:
            return None
        if redis_client.exists(decision_key):
            return None
        return {
            (k.decode("utf-8") if isinstance(k, bytes) else k): (
                v.decode("utf-8") if isinstance(v, bytes) else v
            )
            for k, v in data.items()
        }
    except Exception:
        logger.exception("Failed to read approval request")
        return None


@approval_blueprint.route("/approvals/<request_id>/approve", methods=["POST"])
@jwt_required
def approve_request(request_id: str):
    """Approve a pending destructive action."""
    return _decide(request_id, "approved")


@approval_blueprint.route("/approvals/<request_id>/deny", methods=["POST"])
@jwt_required
def deny_request(request_id: str):
    """Deny a pending destructive action."""
    return _decide(request_id, "denied")


def _decide(request_id: str, decision: str):
    """Write an approval decision to Redis."""
    redis_client = get_redis_client()
    if not redis_client:
        abort(503, description="Redis unavailable")

    pending_key = f"{_APPROVAL_PENDING_PREFIX}{request_id}"
    try:
        data = redis_client.hgetall(pending_key)
    except Exception:
        logger.exception("Failed to read approval request")
        abort(500, description="Failed to read approval request")

    if not data:
        abort(404, description="Approval request not found or expired")

    # Ownership check
    userspace = data.get(b"userspace") or data.get("userspace")
    if isinstance(userspace, bytes):
        userspace = userspace.decode("utf-8")
    if userspace and not _user_owns_userspace(userspace) and g.user_role != _ADMIN_ROLE:
        abort(403, description="Access denied")

    decision_key = f"{_APPROVAL_DECISION_PREFIX}{request_id}"
    redis_client.set(decision_key, decision, ex=_APPROVAL_TTL)

    logger.info("Approval decision recorded")

    return jsonify({"request_id": request_id, "decision": decision})
