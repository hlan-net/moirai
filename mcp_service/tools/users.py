import json
from datetime import datetime
from passlib.hash import bcrypt
from ..core import mcp, auth_required
from ..db import db_request, get_doc, update_doc, delete_doc, store_doc

# --- User Management Tools ---

@mcp.tool()
@auth_required
def list_users(api_key: str = None) -> str:
    """
    List all registered users in the system. (Admin only)
    Requires valid 'api_key'.
    """
    res = db_request("GET", "users", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "No users database found or error connecting."
    
    rows = res.json().get("rows", [])
    users = []
    for row in rows:
        doc = row["doc"]
        # Skip design docs
        if doc["_id"].startswith("_design/"):
            continue
        users.append(f"ID: {doc['_id']}\nEmail: {doc['email']}\nRole: {doc.get('role', 'user')}\nCreated: {doc.get('created_at', 'N/A')}\n")
    
    return "\n---\n".join(users) if users else "No users found."

@mcp.tool()
@auth_required
def add_user(email: str, password: str, role: str = "user", api_key: str = None) -> str:
    """
    Create a new user. (Admin only)
    
    Args:
        email: The user's email address.
        password: The user's password.
        role: The user's role ('admin' or 'user').
        api_key: Required for authentication.
    """
    if not email or not password:
        return "Email and password required."
    
    if role not in ["admin", "user"]:
        return f"Invalid role '{role}'. Use 'admin' or 'user'."

    # Check if user already exists using Mango query
    selector = {"email": email}
    try:
        res = db_request("POST", "users", path="/_find", json_data={"selector": selector})
        if res.status_code == 200 and res.json().get("docs"):
            return f"User with email {email} already exists."
    except Exception as e:
        return f"Error checking for existing user: {e}"
    
    hashed = bcrypt.hash(password)
    user_doc = {
        "email": email,
        "password_hash": hashed,
        "role": role,
        "settings": {},
        "created_at": datetime.now().isoformat()
    }
    
    try:
        # Note: store_doc generates an _id if not provided
        doc_id = store_doc("users", user_doc)
        return f"User created with ID: {doc_id}"
    except Exception as e:
        return f"Error creating user: {e}"

@mcp.tool()
@auth_required
def delete_user(user_id: str, api_key: str = None) -> str:
    """
    Delete a user by their unique ID. (Admin only)
    
    Args:
        user_id: The ID of the user to delete.
        api_key: Required for authentication.
    """
    success, msg = delete_doc("users", user_id)
    if success:
        return f"User {user_id} deleted successfully."
    else:
        return f"Error deleting user: {msg}"

@mcp.tool()
@auth_required
def update_user_role(user_id: str, role: str, api_key: str = None) -> str:
    """
    Change a user's role. (Admin only)
    
    Args:
        user_id: The ID of the user to update.
        role: The new role ('admin' or 'user').
        api_key: Required for authentication.
    """
    if role not in ["admin", "user"]:
        return f"Invalid role '{role}'. Use 'admin' or 'user'."
    
    success, msg = update_doc("users", user_id, {"role": role})
    if success:
        return f"User {user_id} role updated to {role}."
    else:
        return f"Error updating user: {msg}"
