import json
from datetime import datetime, timezone
from ..core import mcp, auth_required, validate_userspace
from ..db import store_doc, db_request, get_doc, update_doc, delete_doc
from .constants import ERROR_ISSUE_NOT_FOUND_OR_DENIED
from .userspace import build_userspace_selector, extract_userspace, with_userspace

# --- Internal Logic (No Auth Decorators) ---

def _forge_issue_internal(
    logos: str,
    description: str,
    premises: list[dict],
    userspace: str,
    longevity: str = "transient"
) -> str:
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    if longevity not in ["transient", "temporal", "epic"]:
        return "Error: Invalid longevity scale. Use transient, temporal, or epic."

    issue_doc = {
        "logos": logos,
        "description": description,
        "premises": premises,
        "longevity": longevity,
        "status": "active",
        "born_at": datetime.now(timezone.utc).isoformat(),
        "passed_at": None,
        "type": "issue"
    }
    with_userspace(issue_doc, userspace)

    try:
        doc_id = store_doc("issues", issue_doc)
        return f"Issue forged with ID: {doc_id} in userspace {userspace} (Scale: {longevity})"
    except Exception as e:
        return f"Error forging issue: {e}"


def _measure_issue_internal(
    issue_id: str,
    userspace: str,
    longevity: str = None,
    description: str = None,
    add_premises: list[dict] = None
) -> str:
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    existing = get_doc("issues", issue_id)
    if not existing or extract_userspace(existing) != userspace:
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


def _seal_issue_internal(issue_id: str, userspace: str) -> str:
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    existing = get_doc("issues", issue_id)
    if not existing or extract_userspace(existing) != userspace:
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
    userspace: str,
    longevity: str = None, 
    status: str = None
) -> str:
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    selector = {"type": "issue", **build_userspace_selector(userspace)}
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
        else f"No matching issues found in userspace {userspace}."
    )


def _read_issue_internal(issue_id: str, userspace: str) -> str:
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    doc = get_doc("issues", issue_id)
    if not doc or extract_userspace(doc) != userspace:
        return ERROR_ISSUE_NOT_FOUND_OR_DENIED

    return json.dumps(doc, indent=2)


def _delete_issue_internal(issue_id: str, userspace: str) -> str:
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    existing = get_doc("issues", issue_id)
    if not existing or extract_userspace(existing) != userspace:
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
    userspace: str,
    longevity: str = "transient",
) -> str:
    """
    (Clotho) Forge a new Issue (Resonance) from identified patterns in the sand.
    """
    return _forge_issue_internal(logos, description, premises, userspace, longevity)


@mcp.tool()
@auth_required
def measure_issue(
    issue_id: str,
    userspace: str,
    longevity: str = None,
    description: str = None,
    add_premises: list[dict] = None,
) -> str:
    """
    (Lachesis) Measure and modulate an existing resonance.
    """
    return _measure_issue_internal(issue_id, userspace, longevity, description, add_premises)


@mcp.tool()
@auth_required
def seal_issue(
    issue_id: str,
    userspace: str,
) -> str:
    """
    (Atropos) Cut the thread of an active resonance.
    """
    return _seal_issue_internal(issue_id, userspace)


@mcp.tool()
@auth_required
def list_issues(
    userspace: str,
    longevity: str = None, 
    status: str = None
) -> str:
    """
    List forged issues in a userspace.
    """
    return _list_issues_internal(userspace, longevity, status)


@mcp.tool()
@auth_required
def read_issue(issue_id: str, userspace: str) -> str:
    """Read full details of a specific issue."""
    return _read_issue_internal(issue_id, userspace)


@mcp.tool()
@auth_required
def delete_issue(issue_id: str, userspace: str) -> str:
    """Irreversibly remove an issue record."""
    return _delete_issue_internal(issue_id, userspace)


# --- Backward Compatibility Aliases (Legacy Events/Trends) ---

@mcp.tool()
@auth_required
def add_event(
    name: str,
    description: str,
    article_links: list[str],
    userspace: str,
) -> str:
    """
    (Alias for forge_issue) Create a new Event.
    """
    premises = [{"type": "message", "id": link} for link in article_links]
    return _forge_issue_internal(name, description, premises, userspace, "transient")


@mcp.tool()
@auth_required
def list_events(userspace: str) -> str:
    """
    (Alias for list_issues) List transient issues.
    """
    return _list_issues_internal(userspace, longevity="transient")


@mcp.tool()
@auth_required
def read_event(event_id: str, userspace: str) -> str:
    """
    (Alias for read_issue) Get details of a specific event.
    """
    return _read_issue_internal(event_id, userspace)


@mcp.tool()
@auth_required
def get_event(event_id: str, userspace: str) -> dict:
    """
    (Alias for read_issue) Returns the event document as a dictionary.
    """
    res = _read_issue_internal(event_id, userspace)
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
    userspace: str,
    name: str = None,
    description: str = None,
    article_links: list[str] = None,
) -> str:
    """
    (Alias for measure_issue) Update an existing event.
    """
    add_premises = None
    if article_links:
        add_premises = [{"type": "message", "id": link} for link in article_links]
    
    return _measure_issue_internal(event_id, userspace, description=description, add_premises=add_premises)


@mcp.tool()
@auth_required
def delete_event(event_id: str, userspace: str) -> str:
    """
    (Alias for delete_issue) Delete an event.
    """
    return _delete_issue_internal(event_id, userspace)


@mcp.tool()
@auth_required
def add_trend(
    name: str,
    description: str,
    event_ids: list[str],
    userspace: str,
) -> str:
    """
    (Alias for forge_issue) Create a new Trend.
    """
    premises = [{"type": "issue", "id": eid} for eid in event_ids]
    return _forge_issue_internal(name, description, premises, userspace, "temporal")


@mcp.tool()
@auth_required
def list_trends(userspace: str) -> str:
    """
    (Alias for list_issues) List temporal issues.
    """
    return _list_issues_internal(userspace, longevity="temporal")


@mcp.tool()
@auth_required
def read_trend(trend_id: str, userspace: str) -> str:
    """
    (Alias for read_issue) Get details of a specific trend.
    """
    return _read_issue_internal(trend_id, userspace)


@mcp.tool()
@auth_required
def get_trend(trend_id: str, userspace: str) -> dict:
    """
    (Alias for read_issue) Returns the trend document as a dictionary.
    """
    res = _read_issue_internal(trend_id, userspace)
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
    userspace: str,
    name: str = None,
    description: str = None,
    event_ids: list[str] = None,
) -> str:
    """
    (Alias for measure_issue) Update an existing trend.
    """
    add_premises = None
    if event_ids:
        add_premises = [{"type": "issue", "id": eid} for eid in event_ids]
    
    return _measure_issue_internal(trend_id, userspace, description=description, add_premises=add_premises)


@mcp.tool()
@auth_required
def delete_trend(trend_id: str, userspace: str) -> str:
    """
    (Alias for delete_issue) Delete a trend.
    """
    return _delete_issue_internal(trend_id, userspace)
