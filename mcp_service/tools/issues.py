import json
from datetime import datetime, timezone
from ..core import mcp, auth_required, validate_namespace
from ..db import store_doc, db_request, get_doc, update_doc, delete_doc
from .constants import ERROR_ISSUE_NOT_FOUND_OR_DENIED

# --- Internal Logic (No Auth Decorators) ---

def _forge_issue_internal(
    logos: str,
    description: str,
    premises: list[dict],
    namespace: str,
    longevity: str = "transient"
) -> str:
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    if longevity not in ["transient", "temporal", "epic"]:
        return "Error: Invalid longevity scale. Use transient, temporal, or epic."

    issue_doc = {
        "logos": logos,
        "description": description,
        "premises": premises,
        "namespace": namespace,
        "longevity": longevity,
        "status": "active",
        "born_at": datetime.now(timezone.utc).isoformat(),
        "passed_at": None,
        "type": "issue"
    }

    try:
        doc_id = store_doc("issues", issue_doc)
        return f"Issue forged with ID: {doc_id} in namespace {namespace} (Scale: {longevity})"
    except Exception as e:
        return f"Error forging issue: {e}"


def _measure_issue_internal(
    issue_id: str,
    namespace: str,
    longevity: str = None,
    description: str = None,
    add_premises: list[dict] = None
) -> str:
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    existing = get_doc("issues", issue_id)
    if not existing or existing.get("namespace") != namespace:
        return ERROR_ISSUE_NOT_FOUND_OR_DENIED

    updates = {}
    if longevity:
        if longevity not in ["transient", "temporal", "epic"]:
            return "Error: Invalid longevity scale."
        updates["longevity"] = longevity
    
    if description:
        updates["description"] = description
        
    if add_premises:
        current_premises = existing.get("premises", [])
        # Simple deduplication based on ID
        existing_ids = {p.get("id") for p in current_premises}
        for p in add_premises:
            if p.get("id") not in existing_ids:
                current_premises.append(p)
        updates["premises"] = current_premises

    success, msg = update_doc("issues", issue_id, updates)
    if success:
        return f"Issue {issue_id} measured and modulated successfully."
    else:
        return f"Error measuring issue: {msg}"


def _seal_issue_internal(issue_id: str, namespace: str) -> str:
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    existing = get_doc("issues", issue_id)
    if not existing or existing.get("namespace") != namespace:
        return ERROR_ISSUE_NOT_FOUND_OR_DENIED

    updates = {
        "status": "eternal",
        "passed_at": datetime.now(timezone.utc).isoformat()
    }

    success, msg = update_doc("issues", issue_id, updates)
    if success:
        return f"Issue {issue_id} sealed into Eternity."
    else:
        return f"Error sealing issue: {msg}"


def _list_issues_internal(
    namespace: str, 
    longevity: str = None, 
    status: str = None
) -> str:
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    selector = {"type": "issue", "namespace": namespace}
    if longevity:
        selector["longevity"] = longevity
    if status:
        selector["status"] = status

    res = db_request("POST", "issues", path="/_find", json_data={"selector": selector})

    if res.status_code != 200:
        return f"Error fetching issues: {res.text}"

    docs = res.json().get("docs", [])
    output = []
    for doc in docs:
        output.append(
            f"ID: {doc['_id']}\nLogos: {doc.get('logos', 'Unnamed')}\nScale: {doc.get('longevity')}\nStatus: {doc.get('status')}\nPremises: {len(doc.get('premises', []))}\n"
        )

    return (
        "\n---\n".join(output)
        if output
        else f"No matching issues found in namespace {namespace}."
    )


def _read_issue_internal(issue_id: str, namespace: str) -> str:
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    doc = get_doc("issues", issue_id)
    if not doc or doc.get("namespace") != namespace:
        return ERROR_ISSUE_NOT_FOUND_OR_DENIED

    return json.dumps(doc, indent=2)


def _delete_issue_internal(issue_id: str, namespace: str) -> str:
    valid, err = validate_namespace(namespace)
    if not valid:
        return err

    existing = get_doc("issues", issue_id)
    if not existing or existing.get("namespace") != namespace:
        return ERROR_ISSUE_NOT_FOUND_OR_DENIED

    success, msg = delete_doc("issues", issue_id)
    if success:
        return f"Issue {issue_id} deleted successfully."
    else:
        return f"Error deleting issue: {msg}"


# --- Issues (Resonances) Tools ---

@mcp.tool()
@auth_required
def forge_issue(
    logos: str,
    description: str,
    premises: list[dict],
    namespace: str,
    longevity: str = "transient",
    api_key: str = None,
) -> str:
    """
    (Clotho) Forge a new Issue (Resonance) from identified patterns in the sand.
    """
    return _forge_issue_internal(logos, description, premises, namespace, longevity)


@mcp.tool()
@auth_required
def measure_issue(
    issue_id: str,
    namespace: str,
    longevity: str = None,
    description: str = None,
    add_premises: list[dict] = None,
    api_key: str = None,
) -> str:
    """
    (Lachesis) Measure and modulate an existing resonance.
    """
    return _measure_issue_internal(issue_id, namespace, longevity, description, add_premises)


@mcp.tool()
@auth_required
def seal_issue(
    issue_id: str,
    namespace: str,
    api_key: str = None,
) -> str:
    """
    (Atropos) Cut the thread of an active resonance.
    """
    return _seal_issue_internal(issue_id, namespace)


@mcp.tool()
@auth_required
def list_issues(
    namespace: str, 
    longevity: str = None, 
    status: str = None,
    api_key: str = None
) -> str:
    """
    List forged issues in a namespace.
    """
    return _list_issues_internal(namespace, longevity, status)


@mcp.tool()
@auth_required
def read_issue(issue_id: str, namespace: str, api_key: str = None) -> str:
    """Read full details of a specific issue."""
    return _read_issue_internal(issue_id, namespace)


@mcp.tool()
@auth_required
def delete_issue(issue_id: str, namespace: str, api_key: str = None) -> str:
    """Irreversibly remove an issue record."""
    return _delete_issue_internal(issue_id, namespace)


# --- Backward Compatibility Aliases (Legacy Events/Trends) ---

@mcp.tool()
@auth_required
def add_event(
    name: str,
    description: str,
    article_links: list[str],
    namespace: str,
    api_key: str = None,
) -> str:
    """
    (Alias for forge_issue) Create a new Event.
    """
    premises = [{"type": "message", "id": link} for link in article_links]
    return _forge_issue_internal(name, description, premises, namespace, "transient")


@mcp.tool()
@auth_required
def list_events(namespace: str, api_key: str = None) -> str:
    """
    (Alias for list_issues) List transient issues.
    """
    return _list_issues_internal(namespace, longevity="transient")


@mcp.tool()
@auth_required
def read_event(event_id: str, namespace: str, api_key: str = None) -> str:
    """
    (Alias for read_issue) Get details of a specific event.
    """
    return _read_issue_internal(event_id, namespace)


@mcp.tool()
@auth_required
def get_event(event_id: str, namespace: str = None, api_key: str = None) -> dict:
    """
    (Alias for read_issue) Returns the event document as a dictionary.
    """
    if not namespace:
        doc = get_doc("issues", event_id)
        if doc:
            return {"status": "success", "event": doc}
        return {"status": "error", "message": "Event not found"}
    
    res = _read_issue_internal(event_id, namespace)
    try:
        data = json.loads(res)
        if "error" in data:
            return {"status": "error", "message": data["error"]}
        return {"status": "success", "event": data}
    except Exception:
        return {"status": "error", "message": res}


@mcp.tool()
@auth_required
def update_event(
    event_id: str,
    namespace: str,
    name: str = None,
    description: str = None,
    article_links: list[str] = None,
    api_key: str = None,
) -> str:
    """
    (Alias for measure_issue) Update an existing event.
    """
    add_premises = None
    if article_links:
        add_premises = [{"type": "message", "id": link} for link in article_links]
    
    return _measure_issue_internal(event_id, namespace, description=description, add_premises=add_premises)


@mcp.tool()
@auth_required
def delete_event(event_id: str, namespace: str, api_key: str = None) -> str:
    """
    (Alias for delete_issue) Delete an event.
    """
    return _delete_issue_internal(event_id, namespace)


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
    (Alias for forge_issue) Create a new Trend.
    """
    premises = [{"type": "issue", "id": eid} for eid in event_ids]
    return _forge_issue_internal(name, description, premises, namespace, "temporal")


@mcp.tool()
@auth_required
def list_trends(namespace: str, api_key: str = None) -> str:
    """
    (Alias for list_issues) List temporal issues.
    """
    return _list_issues_internal(namespace, longevity="temporal")


@mcp.tool()
@auth_required
def read_trend(trend_id: str, namespace: str, api_key: str = None) -> str:
    """
    (Alias for read_issue) Get details of a specific trend.
    """
    return _read_issue_internal(trend_id, namespace)


@mcp.tool()
@auth_required
def get_trend(trend_id: str, namespace: str = None, api_key: str = None) -> dict:
    """
    (Alias for read_issue) Returns the trend document as a dictionary.
    """
    if not namespace:
        doc = get_doc("issues", trend_id)
        if doc:
            return {"status": "success", "trend": doc}
        return {"status": "error", "message": "Trend not found"}

    res = _read_issue_internal(trend_id, namespace)
    try:
        data = json.loads(res)
        if "error" in data:
            return {"status": "error", "message": data["error"]}
        return {"status": "success", "trend": data}
    except Exception:
        return {"status": "error", "message": res}


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
    (Alias for measure_issue) Update an existing trend.
    """
    add_premises = None
    if event_ids:
        add_premises = [{"type": "issue", "id": eid} for eid in event_ids]
    
    return _measure_issue_internal(trend_id, namespace, description=description, add_premises=add_premises)


@mcp.tool()
@auth_required
def delete_trend(trend_id: str, namespace: str, api_key: str = None) -> str:
    """
    (Alias for delete_issue) Delete a trend.
    """
    return _delete_issue_internal(trend_id, namespace)
