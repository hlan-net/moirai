from mcp_service.core import mcp
from api.db import (
    fetch_from_couchdb,
    update_couchdb_doc,
    query_couchdb,
    delete_from_couchdb,
)
from typing import Literal

# Database names
EVENTS_DB = "events"
TRENDS_DB = "trends"


@mcp.tool(
    name="mark_entity_stale",
    description="Marks an event or trend as stale or not stale.",
)
def mark_entity_stale(
    entity_type: Literal["event", "trend"], entity_id: str, is_stale: bool
) -> dict:
    """
    Marks a specific event or trend entity with a stale flag.
    Args:
        entity_type: The type of entity to mark ('event' or 'trend').
        entity_id: The GUID of the event or trend.
        is_stale: Boolean value to set the staleness flag.
    Returns:
        A dictionary indicating success or failure.
    """
    db_name = ""
    if entity_type == "event":
        db_name = EVENTS_DB
    elif entity_type == "trend":
        db_name = TRENDS_DB
    else:
        return {
            "status": "error",
            "message": "Invalid entity_type. Must be 'event' or 'trend'.",
        }

    entity_doc = fetch_from_couchdb(db_name, entity_id)
    if not entity_doc:
        return {
            "status": "error",
            "message": f"{entity_type.capitalize()} {entity_id} not found.",
        }

    entity_doc["is_stale"] = is_stale

    if update_couchdb_doc(db_name, entity_id, entity_doc):
        return {
            "status": "success",
            "message": f"{entity_type.capitalize()} {entity_id} staleness updated to {is_stale}.",
        }
    else:
        return {
            "status": "error",
            "message": f"Failed to update staleness for {entity_type} {entity_id}.",
        }


@mcp.tool(
    name="delete_stale_entities",
    description="Deletes all entities marked as stale for a given type.",
)
def delete_stale_entities(entity_type: Literal["event", "trend"]) -> dict:
    """
    Deletes all events or trends that are currently marked as stale.
    This tool requires admin privileges to be effective.
    Args:
        entity_type: The type of entity to delete ('event' or 'trend').
    Returns:
        A dictionary indicating the number of entities deleted or an error message.
    """
    db_name = ""
    if entity_type == "event":
        db_name = EVENTS_DB
    elif entity_type == "trend":
        db_name = TRENDS_DB
    else:
        return {
            "status": "error",
            "message": "Invalid entity_type. Must be 'event' or 'trend'.",
        }

    # Query for all stale entities
    stale_entities = query_couchdb(db_name, selector={"is_stale": True})

    deleted_count = 0
    errors = []

    for entity in stale_entities:
        try:
            # MCP tools typically handle authentication and permissions
            # Assuming the caller of this tool has admin privileges to delete.
            success = delete_from_couchdb(db_name, entity["_id"], entity["_rev"])
            if success:
                deleted_count += 1
            else:
                errors.append(
                    f"Failed to delete {entity_type} {entity['_id']}: Unknown error"
                )
        except Exception as e:
            errors.append(f"Error deleting {entity_type} {entity['_id']}: {e}")

    if errors:
        return {
            "status": "error",
            "message": f"Deleted {deleted_count} {entity_type}s with errors: {'; '.join(errors)}",
        }
    else:
        return {
            "status": "success",
            "message": f"Successfully deleted {deleted_count} stale {entity_type}s.",
        }
