import os
import functools
import uuid
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Moirai MCP Server", dependencies=["requests", "feedparser"])

# Auth Configuration
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable must be set for MCP server")


def auth_required(func):
    """Decorator to require ADMIN_PASSWORD for a tool call."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # We expect 'api_key' to be passed in kwargs for top-level tools
        api_key = kwargs.pop("api_key", None)
        if api_key != ADMIN_PASSWORD:
            return "Error: Unauthorized. Valid 'api_key' is required."
        return func(*args, **kwargs)

    return wrapper


def validate_userspace(userspace_guid: str):
    """Validate that the userspace is a valid GUID/UUID."""
    if not userspace_guid:
        return False, "Error: 'userspace' parameter is required."
    try:
        uuid.UUID(userspace_guid)
        return True, ""
    except ValueError:
        return False, "Error: 'userspace' must be a valid GUID/UUID."
