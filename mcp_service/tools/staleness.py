from mcp_service.core import mcp
from api.db import (
    fetch_from_couchdb,
    update_couchdb_doc,
    query_couchdb,
    delete_from_couchdb,
)
from typing import Literal

# Database names
ISSUES_DB = "issues"


@mcp.tool(
    name="mark_entity_stale",
    description="Marks an issue (resonance) as stale or not stale. Maps event/trend to issue longevity.",
)
def mark_entity_stale(
    entity_type: Literal["event", "trend", "issue"], entity_id: str, is_stale: bool
) -> dict:
    """
    Marks a specific issue with a stale flag.
    Args:
        entity_type: The type of entity ('event', 'trend', or 'issue').
        entity_id: The GUID of the entity.
        is_stale: Boolean value to set the staleness flag.
    Returns:
        A dictionary indicating success or failure.
    """
    # All map to the issues database in the 2nd iteration
    db_name = ISSUES_DB

    entity_doc = fetch_from_couchdb(db_name, entity_id)
    if not entity_doc:
        return {
            "status": "error",
            "message": f"Issue {entity_id} not found.",
        }

    entity_doc["is_stale"] = is_stale

    if update_couchdb_doc(db_name, entity_id, entity_doc):
        return {
            "status": "success",
            "message": f"Issue {entity_id} staleness updated to {is_stale}.",
        }
    else:
        return {
            "status": "error",
            "message": f"Failed to update staleness for issue {entity_id}.",
        }


@mcp.tool(
    name="delete_stale_entities",
    description="Deletes all issues marked as stale for a given type (event/trend scale).",
)
def delete_stale_entities(entity_type: Literal["event", "trend", "issue"]) -> dict:
    """
    Deletes all issues that are currently marked as stale.
    Args:
        entity_type: The type of entity to delete ('event', 'trend', or 'issue').
    Returns:
        A dictionary indicating the number of entities deleted or an error message.
    """
    db_name = ISSUES_DB
    
    # Map entity_type to longevity if it's event or trend
    longevity_map = {
        "event": "transient",
        "trend": "temporal"
    }
    
    selector = {"is_stale": True}
    if entity_type in longevity_map:
        selector["longevity"] = longevity_map[entity_type]

    # Query for all stale entities
    stale_entities = query_couchdb(db_name, selector=selector)

    deleted_count = 0
    errors = []

    for entity in stale_entities:
        try:
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
            "message": f"Deleted {deleted_count} issues with errors: {'; '.join(errors)}",
        }
    else:
        return {
            "status": "success",
            "message": f"Successfully deleted {deleted_count} stale {entity_type}s.",
        }
