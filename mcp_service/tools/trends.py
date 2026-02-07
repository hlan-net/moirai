import json
from datetime import datetime
from ..core import mcp
from ..db import store_doc, db_request, get_doc, update_doc, delete_doc

# --- Trends Tools ---

@mcp.tool()
def add_trend(name: str, description: str, event_ids: list[str]) -> str:
    """
    Create a new Trend grouping multiple related events into a pattern.
    
    A Trend represents a broader theme or pattern emerging from multiple distinct events over time.
    """
    trend_doc = {
        "name": name,
        "description": description,
        "event_ids": event_ids,
        "created_at": datetime.now().isoformat(),
        "type": "trend"
    }
    
    try:
        if db_request("HEAD", "trends").status_code == 404:
            db_request("PUT", "trends")

        doc_id = store_doc("trends", trend_doc)
        return f"Trend created with ID: {doc_id}"
    except Exception as e:
        return f"Error creating trend: {e}"

@mcp.tool()
def list_trends() -> str:
    """List all created trends."""
    if db_request("HEAD", "trends").status_code == 404:
        return "No trends data found."

    res = db_request("GET", "trends", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "No trends data found."
    
    rows = res.json().get("rows", [])
    trends = []
    for row in rows:
        doc = row["doc"]
        trends.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nEvents: {len(doc.get('event_ids', []))}\n")
    
    return "\n---\n".join(trends) if trends else "No trends found."

@mcp.tool()
def read_trend(trend_id: str) -> str:
    """Get details of a specific trend."""
    doc = get_doc("trends", trend_id)
    if not doc:
        return "Trend not found."
    
    return json.dumps(doc, indent=2)

@mcp.tool()
def update_trend(trend_id: str, name: str = None, description: str = None, event_ids: list[str] = None) -> str:
    """Update an existing trend. Only provided fields are updated."""
    existing = get_doc("trends", trend_id)
    if not existing:
        return "Trend not found."

    updates = {}
    if name: updates["name"] = name
    if description: updates["description"] = description
    if event_ids is not None: updates["event_ids"] = event_ids
    
    success, msg = update_doc("trends", trend_id, updates)
    if success:
        return f"Trend {trend_id} updated successfully."
    else:
        return f"Error updating trend: {msg}"

@mcp.tool()
def delete_trend(trend_id: str) -> str:
    """Delete a trend."""
    existing = get_doc("trends", trend_id)
    if not existing:
        return "Trend not found."
    
    success, msg = delete_doc("trends", trend_id)
    if success:
        return f"Trend {trend_id} deleted successfully."
    else:
        return f"Error deleting trend: {msg}"
