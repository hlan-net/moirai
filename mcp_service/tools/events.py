import json
from datetime import datetime
from ..core import mcp, auth_required, validate_namespace
from ..db import store_doc, db_request, get_doc, update_doc, delete_doc

# --- Events Tools ---

@mcp.tool()
@auth_required
def add_event(name: str, description: str, article_links: list[str], namespace: str, api_key: str = None) -> str:
    """
    Create a new Event grouping multiple related articles about a SINGLE occurrence.
    
    Args:
        name: Name of the event.
        description: Description of the event.
        article_links: List of article link URLs.
        namespace: GUID of the namespace to isolate this event.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid: return err

    event_doc = {
        "name": name,
        "description": description,
        "article_links": article_links,
        "namespace": namespace,
        "created_at": datetime.now().isoformat(),
        "type": "event"
    }
    
    try:
        doc_id = store_doc("events", event_doc)
        return f"Event created with ID: {doc_id} in namespace {namespace}"
    except Exception as e:
        return f"Error creating event: {e}"

@mcp.tool()
@auth_required
def list_events(namespace: str, api_key: str = None) -> str:
    """
    List all created events in a specific namespace.
    
    Args:
        namespace: GUID of the namespace to filter by.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid: return err

    # Use Mango query to filter by namespace
    selector = {"type": "event", "namespace": namespace}
    res = db_request("POST", "events", path="/_find", json_data={"selector": selector})
    
    if res.status_code != 200:
        return f"Error fetching events: {res.text}"
    
    docs = res.json().get("docs", [])
    events = []
    for doc in docs:
        events.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nArticles: {len(doc.get('article_links', []))}\n")
    
    return "\n---\n".join(events) if events else f"No events found in namespace {namespace}."

@mcp.tool()
@auth_required
def read_event(event_id: str, namespace: str, api_key: str = None) -> str:
    """
    Get details of a specific event within a namespace.
    
    Args:
        event_id: The ID of the event to read.
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid: return err

    doc = get_doc("events", event_id)
    if not doc or doc.get("namespace") != namespace:
        return "Event not found or access denied."
    
    return json.dumps(doc, indent=2)

@mcp.tool()
@auth_required
def update_event(event_id: str, namespace: str, name: str = None, description: str = None, article_links: list[str] = None, api_key: str = None) -> str:
    """
    Update an existing event. Only provided fields are updated.
    
    Args:
        event_id: The ID of the event to update.
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid: return err

    existing = get_doc("events", event_id)
    if not existing or existing.get("namespace") != namespace:
        return "Event not found or access denied."
    
    updates = {}
    if name: updates["name"] = name
    if description: updates["description"] = description
    if article_links is not None: updates["article_links"] = article_links
    
    success, msg = update_doc("events", event_id, updates)
    if success:
        return f"Event {event_id} updated successfully."
    else:
        return f"Error updating event: {msg}"

@mcp.tool()
@auth_required
def delete_event(event_id: str, namespace: str, api_key: str = None) -> str:
    """
    Delete an event within a namespace.
    
    Args:
        event_id: The ID of the event to delete.
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid: return err

    existing = get_doc("events", event_id)
    if not existing or existing.get("namespace") != namespace:
        return "Event not found or access denied."
    
    success, msg = delete_doc("events", event_id)
    if success:
        return f"Event {event_id} deleted successfully."
    else:
        return f"Error deleting event: {msg}"
