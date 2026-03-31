from datetime import datetime
from passlib.hash import bcrypt
from ..core import mcp, auth_required
from ..db import db_request, update_doc, delete_doc, store_doc
from ..responses import (
    success,
    validation_error,
    transient_error,
    internal_error,
    error,
    MCPErrorCode,
    NextAction,
)

# --- User Management Tools ---


@mcp.tool()
@auth_required
def list_users() -> dict:
    """
    List all registered users in the system. (Admin only)

    Returns:
        Standardized MCPResponse as dict.
    """
    try:
        res = db_request(
            "GET", "users", path="/_all_docs", params={"include_docs": "true"}
        )
        if res.status_code >= 500:
            return transient_error(
                message=f"Database error listing users: HTTP {res.status_code}",
                retry_after_ms=2000,
            ).to_dict()
        if res.status_code != 200:
            return internal_error(
                message="No users database found or error connecting."
            ).to_dict()

        rows = res.json().get("rows", [])
        users = []
        for row in rows:
            doc = row["doc"]
            if doc["_id"].startswith("_design/"):
                continue
            users.append(
                {
                    "id": doc["_id"],
                    "email": doc["email"],
                    "role": doc.get("role", "user"),
                    "created_at": doc.get("created_at", None),
                }
            )

        return success(
            data={"users": users, "count": len(users)},
            message=f"Found {len(users)} user(s)",
        ).to_dict()

    except Exception as e:
        return internal_error(
            message=f"Error listing users: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def add_user(email: str, password: str, role: str = "user") -> dict:
    """
    Create a new user. (Admin only)

    Args:
        email: The user's email address.
        password: The user's password.
        role: The user's role ('admin' or 'user').

    Returns:
        Standardized MCPResponse as dict.
    """
    if not email or not password:
        return validation_error("Email and password required.").to_dict()

    if role not in ["admin", "user"]:
        return validation_error(
            f"Invalid role '{role}'. Use 'admin' or 'user'."
        ).to_dict()

    try:
        # Check if user already exists
        selector = {"email": email}
        res = db_request(
            "POST", "users", path="/_find", json_data={"selector": selector}
        )
        if res.status_code == 200 and res.json().get("docs"):
            return error(
                error_code=MCPErrorCode.DUPLICATE_RESOURCE,
                message=f"User with email {email} already exists.",
                retryable=False,
                next_action=NextAction.NONE,
            ).to_dict()
    except Exception as e:
        return internal_error(
            message=f"Error checking for existing user: {str(e)}"
        ).to_dict()

    hashed = bcrypt.hash(password)
    user_doc = {
        "email": email,
        "password_hash": hashed,
        "role": role,
        "settings": {},
        "created_at": datetime.now().isoformat(),
    }

    try:
        doc_id = store_doc("users", user_doc)
        return success(
            data={"user_id": doc_id, "email": email, "role": role},
            message=f"User created with ID: {doc_id}",
        ).to_dict()
    except Exception as e:
        return internal_error(
            message=f"Error creating user: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def delete_user(user_id: str) -> dict:
    """
    Delete a user by their unique ID. (Admin only)

    Args:
        user_id: The ID of the user to delete.

    Returns:
        Standardized MCPResponse as dict.
    """
    ok, msg = delete_doc("users", user_id)
    if ok:
        return success(
            data={"user_id": user_id},
            message=f"User {user_id} deleted successfully.",
        ).to_dict()
    else:
        return internal_error(
            message=f"Error deleting user: {msg}"
        ).to_dict()


@mcp.tool()
@auth_required
def update_user_role(user_id: str, role: str) -> dict:
    """
    Change a user's role. (Admin only)

    Args:
        user_id: The ID of the user to update.
        role: The new role ('admin' or 'user').

    Returns:
        Standardized MCPResponse as dict.
    """
    if role not in ["admin", "user"]:
        return validation_error(
            f"Invalid role '{role}'. Use 'admin' or 'user'."
        ).to_dict()

    ok, msg = update_doc("users", user_id, {"role": role})
    if ok:
        return success(
            data={"user_id": user_id, "role": role},
            message=f"User {user_id} role updated to {role}.",
        ).to_dict()
    else:
        return internal_error(
            message=f"Error updating user: {msg}"
        ).to_dict()
