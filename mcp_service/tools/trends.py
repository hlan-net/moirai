import json
from datetime import datetime
from ..core import mcp, auth_required, validate_namespace
from ..db import store_doc, db_request, get_doc, update_doc, delete_doc

# --- Trends Tools ---


@mcp.tool()
@auth_required
def add_trend(
    name: str,
    description: str,
    event_ids: list[str],
    namespace: str,
    api_key: str = None,
) -> str:
    """
    Create a new high-level Trend grouping multiple related Events.

    Args:
        name: Name of the trend.
        description: Description of the trend.
        event_ids: List of Event document IDs.
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    trend_doc = {
        "name": name,
        "description": description,
        "event_ids": event_ids,
        "namespace": namespace,
        "created_at": datetime.now().isoformat(),
        "type": "trend",
    }

    try:
        doc_id = store_doc("trends", trend_doc)
        return f"Trend created with ID: {doc_id} in namespace {namespace}"
    except Exception as e:
        return f"Error creating trend: {e}"


@mcp.tool()
@auth_required
def list_trends(namespace: str, api_key: str = None) -> str:
    """
    List all trends in a specific namespace.

    Args:
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    selector = {"type": "trend", "namespace": namespace}
    res = db_request("POST", "trends", path="/_find", json_data={"selector": selector})

    if res.status_code != 200:
        return f"Error fetching trends: {res.text}"

    docs = res.json().get("docs", [])
    trends = []
    for doc in docs:
        trends.append(
            f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nEvents: {len(doc.get('event_ids', []))}\n"
        )

    return (
        "\n---\n".join(trends)
        if trends
        else f"No trends found in namespace {namespace}."
    )


@mcp.tool()
@auth_required
def read_trend(trend_id: str, namespace: str, api_key: str = None) -> str:
    """
    Get details of a specific trend with namespace verification.

    Args:
        trend_id: The ID of the trend.
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    doc = get_doc("trends", trend_id)
    if not doc or doc.get("namespace") != namespace:
        return "Trend not found or access denied."

    return json.dumps(doc, indent=2)


@mcp.tool()
@auth_required
def update_trend(
    trend_id: str,
    namespace: str,
    name: str = None,
    description: str = None,
    event_ids: list[str] = None,
    api_key: str = None,
) -> str:
    """
    Update an existing trend. Only provided fields are updated.

    Args:
        trend_id: The ID of the trend.
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    existing = get_doc("trends", trend_id)
    if not existing or existing.get("namespace") != namespace:
        return "Trend not found or access denied."

    updates = {}
    if name:
        updates["name"] = name
    if description:
        updates["description"] = description
    if event_ids is not None:
        updates["event_ids"] = event_ids

    success, msg = update_doc("trends", trend_id, updates)
    if success:
        return f"Trend {trend_id} updated successfully."
    else:
        return f"Error updating trend: {msg}"


@mcp.tool()
@auth_required
def delete_trend(trend_id: str, namespace: str, api_key: str = None) -> str:
    """
    Delete a trend within a namespace.

    Args:
        trend_id: The ID of the trend.
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    existing = get_doc("trends", trend_id)
    if not existing or existing.get("namespace") != namespace:
        return "Trend not found or access denied."

    success, msg = delete_doc("trends", trend_id)
    if success:
        return f"Trend {trend_id} deleted successfully."
    else:
        return f"Error deleting trend: {msg}"
