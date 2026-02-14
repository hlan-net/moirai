import os
import functools
import uuid
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Moirai MCP Server", dependencies=["requests", "feedparser"])

# Auth Configuration
API_PASSWORD = os.environ.get("API_PASSWORD", "password")


def auth_required(func):
    """Decorator to require API_PASSWORD for a tool call."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # We expect 'api_key' to be passed in kwargs for top-level tools
        api_key = kwargs.pop("api_key", None)
        if api_key != API_PASSWORD:
            return "Error: Unauthorized. Valid 'api_key' is required."
        return func(*args, **kwargs)

    return wrapper


def validate_namespace(namespace_guid: str):
    """Validate that the namespace is a valid GUID/UUID."""
    if not namespace_guid:
        return False, "Error: 'namespace' parameter is required."
    try:
        uuid.UUID(namespace_guid)
        return True, ""
    except ValueError:
        return False, "Error: 'namespace' must be a valid GUID/UUID."
