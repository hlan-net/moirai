"""REST API for session logs (agent runs and chat turns)."""

import logging

from flask import Blueprint, abort, g, jsonify, request

from api.auth import jwt_required
from api.extensions import get_redis_client, get_session_logger
from api.userspace_ops import can_access_userspace, get_default_userspace

logger = logging.getLogger(__name__)

_ADMIN_ROLE = "admin"
_ACCESS_DENIED = "Access denied"
_SESSION_NOT_FOUND = "Session not found"

session_blueprint = Blueprint("sessions", __name__)


def _user_owns_userspace(userspace_id: str) -> bool:
    """Return True if the authenticated user may access the given userspace."""
    return can_access_userspace(userspace_id, g.user_id, g.user_role)


@session_blueprint.route("/sessions", methods=["GET"])
@jwt_required
def list_sessions():
    """List recent sessions for the caller's userspaces.

    Query params
    ------------
    userspace : optional UUID; defaults to the deployment's userspace
                (admins without it see every session).
    limit     : default 50, max 200.
    offset    : default 0.
    """
    userspace = request.args.get("userspace")
    if not userspace and g.user_role != _ADMIN_ROLE:
        userspace = get_default_userspace()
    if userspace:
        if not _user_owns_userspace(userspace):
            abort(403, description=_ACCESS_DENIED)
    elif g.user_role != _ADMIN_ROLE:
        abort(400, description="'userspace' parameter is required")

    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        abort(400, description="limit and offset must be integers")

    sl = get_session_logger()
    sessions = sl.list_sessions(userspace=userspace, limit=limit, offset=offset)
    return jsonify(sessions)


@session_blueprint.route("/sessions/<session_id>", methods=["GET"])
@jwt_required
def get_session(session_id: str):
    """Fetch a single session log by ID."""
    sl = get_session_logger()
    session = sl.get_session(session_id)
    if not session:
        abort(404, description=_SESSION_NOT_FOUND)

    userspace = session.get("userspace")
    if userspace and not _user_owns_userspace(userspace):
        abort(403, description=_ACCESS_DENIED)

    return jsonify(session)


@session_blueprint.route("/sessions/<session_id>/steps", methods=["GET"])
@jwt_required
def get_session_steps(session_id: str):
    """Return step-level traces for a session."""
    sl = get_session_logger()
    session = sl.get_session(session_id)
    if not session:
        abort(404, description=_SESSION_NOT_FOUND)

    userspace = session.get("userspace")
    if userspace and not _user_owns_userspace(userspace):
        abort(403, description=_ACCESS_DENIED)

    steps = sl.get_steps(session_id)
    return jsonify(steps)


@session_blueprint.route("/sessions/<session_id>/cancel", methods=["POST"])
@jwt_required
def cancel_session(session_id: str):
    """Request cancellation of a running agent session."""
    sl = get_session_logger()
    session = sl.get_session(session_id)
    if not session:
        abort(404, description=_SESSION_NOT_FOUND)

    userspace = session.get("userspace")
    if userspace and not _user_owns_userspace(userspace):
        abort(403, description=_ACCESS_DENIED)

    if session.get("status") != "running":
        abort(409, description="Session is not running")

    redis_client = get_redis_client()
    if not redis_client:
        abort(503, description="Redis unavailable")

    cancel_key = f"session:cancel:{session_id}"
    redis_client.set(cancel_key, "1", ex=600)

    logger.info("Session cancel requested")
    return jsonify({"session_id": session_id, "status": "cancel_requested"})
