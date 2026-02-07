import json
from datetime import datetime
from ..core import mcp
from ..db import store_doc, db_request, get_doc, update_doc, delete_doc

# --- Events Tools ---

@mcp.tool()
def add_event(name: str, description: str, article_links: list[str]) -> str:
    """
    Create a new Event grouping multiple related articles about a SINGLE occurrence.
    
    An Event represents one significant story covered by multiple sources.
    Use this when different articles report on the same announcement, incident, or development.
    """
    event_doc = {
        "name": name,
        "description": description,
        "article_links": article_links,
        "created_at": datetime.now().isoformat(),
        "type": "event"
    }
    
    try:
        doc_id = store_doc("events", event_doc)
        return f"Event created with ID: {doc_id}"
    except Exception as e:
        return f"Error creating event: {e}"

@mcp.tool()
def list_events() -> str:
    """List all created events."""
    res = db_request("GET", "events", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "No events data found."
    
    rows = res.json().get("rows", [])
    events = []
    for row in rows:
        doc = row["doc"]
        if doc.get("type") == "event":
            events.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nArticles: {len(doc.get('article_links', []))}\n")
    
    return "\n---\n".join(events) if events else "No events found."

@mcp.tool()
def read_event(event_id: str) -> str:
    """Get details of a specific event."""
    doc = get_doc("events", event_id)
    if not doc:
        return "Event not found."
    
    return json.dumps(doc, indent=2)

@mcp.tool()
def update_event(event_id: str, name: str = None, description: str = None, article_links: list[str] = None) -> str:
    """Update an existing event. Only provided fields are updated."""
    existing = get_doc("events", event_id)
    if not existing:
        return "Event not found."
    
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
def delete_event(event_id: str) -> str:
    """Delete an event."""
    existing = get_doc("events", event_id)
    if not existing:
        return "Event not found."
    
    success, msg = delete_doc("events", event_id)
    if success:
        return f"Event {event_id} deleted successfully."
    else:
        return f"Error deleting event: {msg}"
