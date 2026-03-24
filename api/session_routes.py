"""REST API for session logs (agent runs and chat turns)."""

from flask import Blueprint, abort, g, jsonify, request

from api.auth import jwt_required
from api.extensions import get_session_logger
from api.userspace_ops import get_userspace

session_blueprint = Blueprint("sessions", __name__)


def _user_owns_userspace(userspace_id: str) -> bool:
    """Return True if the authenticated user owns the given userspace."""
    doc = get_userspace(userspace_id)
    if not doc:
        return False
    return doc.get("owner_user_id") == g.user_id


@session_blueprint.route("/sessions", methods=["GET"])
@jwt_required
def list_sessions():
    """List recent sessions for the caller's userspaces.

    Query params
    ------------
    userspace : optional UUID to filter; must be owned by caller.
    limit     : default 50, max 200.
    offset    : default 0.
    """
    userspace = request.args.get("userspace")
    if userspace and not _user_owns_userspace(userspace):
        abort(403, description="Access denied")

    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        abort(400, description="limit and offset must be integers")

    logger = get_session_logger()
    sessions = logger.list_sessions(userspace=userspace, limit=limit, offset=offset)
    return jsonify(sessions)


@session_blueprint.route("/sessions/<session_id>", methods=["GET"])
@jwt_required
def get_session(session_id: str):
    """Fetch a single session log by ID."""
    logger = get_session_logger()
    session = logger.get_session(session_id)
    if not session:
        abort(404, description="Session not found")

    userspace = session.get("userspace")
    if userspace and not _user_owns_userspace(userspace):
        abort(403, description="Access denied")

    return jsonify(session)
