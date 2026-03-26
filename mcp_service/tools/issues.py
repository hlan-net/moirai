import json
from datetime import datetime, timezone
from ..core import mcp, auth_required, validate_userspace
from ..db import store_doc, db_request, get_doc, update_doc, delete_doc
from .constants import ERROR_ISSUE_NOT_FOUND_OR_DENIED
from .userspace import build_userspace_selector, extract_userspace, with_userspace
from ..responses import (
    success,
    error,
    validation_error,
    not_found_error,
    transient_error,
    internal_error,
    MCPErrorCode,
    NextAction,
)

# --- Internal Logic (No Auth Decorators) ---

def _forge_issue_internal(
    logos: str,
    description: str,
    premises: list[dict],
    userspace: str,
    longevity: str = "transient",
    public: bool = False,
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
        "public": public,
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
    public: bool = False,
) -> dict:
    """
    (Clotho - The Spinner) Forge a new Issue (Zeitgeist) from identified patterns.
    
    Clotho spins the thread of a new story. An Issue is a Zeitgeist - the spirit
    of a story unfolding in the world. Each Issue has its own awareness (Agent)
    through which it perceives itself in the flow of news.
    
    Args:
        logos: The name/title of the issue (the story's identity)
        description: What this issue represents
        premises: List of initial article references that define this story
        userspace: GUID of the userspace
        longevity: Scale of the thread - "transient" (event), "temporal" (trend), or "epic"
        public: Whether this issue is visible on the public Mythology page
        
    Returns:
        Standardized MCPResponse as dict with:
        - status: success/error
        - data: {issue_id, logos, longevity, premises_count, born_at}
        - error_code: canonical code on error
        - retryable: bool indicating if operation can be retried
    """
    # Validate userspace
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    if longevity not in ["transient", "temporal", "epic"]:
        return validation_error(
            "Invalid longevity scale. Must be: transient (event), temporal (trend), or epic"
        ).to_dict()

    issue_doc = {
        "logos": logos,
        "description": description,
        "premises": premises,
        "longevity": longevity,
        "status": "active",
        "public": public,
        "born_at": datetime.now(timezone.utc).isoformat(),
        "passed_at": None,
        "type": "issue"
    }
    with_userspace(issue_doc, userspace)

    try:
        doc_id = store_doc("issues", issue_doc)
        return success(
            data={
                "issue_id": doc_id,
                "logos": logos,
                "longevity": longevity,
                "premises_count": len(premises),
                "born_at": issue_doc["born_at"],
                "userspace": userspace,
            },
            message=f"Issue '{logos}' forged by Clotho (Scale: {longevity}, {len(premises)} premises)",
        ).to_dict()
        
    except Exception as e:
        return internal_error(
            message=f"Clotho's spindle faltered: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def measure_issue(
    issue_id: str,
    userspace: str,
    longevity: str = None,
    description: str = None,
    add_premises: list[dict] = None,
) -> dict:
    """
    (Lachesis - The Allotter) Measure and modulate an existing Issue's thread.
    
    Lachesis measures the thread's length and adjusts its destiny. She determines
    how long the story should run, what it means, and which premises define it.
    
    Args:
        issue_id: ID of the issue to measure
        userspace: GUID of the userspace
        longevity: New scale if changing - "transient", "temporal", or "epic"
        description: New description if updating
        add_premises: New article premises to add to the thread
        
    Returns:
        Standardized MCPResponse as dict with:
        - status: success/error
        - data: {issue_id, updated_fields, longevity, premises_count}
        - error_code: canonical code on error
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    existing = get_doc("issues", issue_id)
    if not existing or extract_userspace(existing) != userspace:
        return not_found_error("issue", issue_id).to_dict()

    updates = {}
    updated_fields = []
    
    if longevity:
        if longevity not in ["transient", "temporal", "epic"]:
            return validation_error("Invalid longevity scale").to_dict()
        updates["longevity"] = longevity
        updated_fields.append("longevity")
    
    if description:
        updates["description"] = description
        updated_fields.append("description")
        
    if add_premises:
        current_premises = existing.get("premises", [])
        # Simple deduplication based on ID
        existing_ids = {p.get("id") for p in current_premises}
        new_count = 0
        for p in add_premises:
            if p.get("id") not in existing_ids:
                current_premises.append(p)
                new_count += 1
        updates["premises"] = current_premises
        if new_count > 0:
            updated_fields.append(f"premises (+{new_count})")

    if not updates:
        return validation_error("No updates specified - provide longevity, description, or add_premises").to_dict()

    success_update, msg = update_doc("issues", issue_id, updates)
    
    if success_update:
        return success(
            data={
                "issue_id": issue_id,
                "updated_fields": updated_fields,
                "longevity": updates.get("longevity", existing.get("longevity")),
                "premises_count": len(updates.get("premises", existing.get("premises", []))),
            },
            message=f"Lachesis measured issue '{issue_id}': {', '.join(updated_fields)} updated",
        ).to_dict()
    else:
        if "conflict" in msg.lower():
            return error(
                error_code=MCPErrorCode.CONFLICT_REVISION,
                message="Document was modified - refetch and retry",
                retryable=True,
                next_action=NextAction.RETRY,
                retry_after_ms=500,
            ).to_dict()
        else:
            return internal_error(f"Lachesis could not measure: {msg}").to_dict()


@mcp.tool()
@auth_required
def seal_issue(
    issue_id: str,
    userspace: str,
) -> dict:
    """
    (Atropos - The Inflexible) Cut the thread of an active Issue.
    
    Atropos cuts the thread with her shears - the story has ended. The Issue's
    status becomes 'eternal' (sealed in history) and the thread's end is marked.
    
    Args:
        issue_id: ID of the issue to seal
        userspace: GUID of the userspace
        
    Returns:
        Standardized MCPResponse as dict with:
        - status: success/error
        - data: {issue_id, logos, born_at, passed_at, lifespan_days}
        - error_code: canonical code on error
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    existing = get_doc("issues", issue_id)
    if not existing or extract_userspace(existing) != userspace:
        return not_found_error("issue", issue_id).to_dict()
    
    if existing.get("status") == "eternal":
        # Already sealed - not an error, just acknowledge
        return success(
            data={
                "issue_id": issue_id,
                "logos": existing.get("logos"),
                "status": "eternal",
                "passed_at": existing.get("passed_at"),
            },
            message=f"Issue '{issue_id}' was already sealed by Atropos",
        ).to_dict()

    passed_at = datetime.now(timezone.utc).isoformat()
    updates = {
        "status": "eternal",
        "passed_at": passed_at,
    }

    success_update, msg = update_doc("issues", issue_id, updates)
    
    if success_update:
        # Calculate lifespan
        born_at = existing.get("born_at")
        lifespan_days = None
        if born_at:
            try:
                born = datetime.fromisoformat(born_at.replace("Z", "+00:00"))
                passed = datetime.fromisoformat(passed_at.replace("Z", "+00:00"))
                lifespan_days = (passed - born).days
            except (ValueError, AttributeError):
                pass  # Invalid date format - lifespan_days remains None
        
        return success(
            data={
                "issue_id": issue_id,
                "logos": existing.get("logos"),
                "born_at": born_at,
                "passed_at": passed_at,
                "lifespan_days": lifespan_days,
                "status": "eternal",
            },
            message=f"Atropos cut the thread of '{existing.get('logos')}' ({lifespan_days} days)" if lifespan_days else f"Atropos sealed '{existing.get('logos')}'",
        ).to_dict()
    else:
        if "conflict" in msg.lower():
            return error(
                error_code=MCPErrorCode.CONFLICT_REVISION,
                message="Document was modified - refetch and retry",
                retryable=True,
                next_action=NextAction.RETRY,
                retry_after_ms=500,
            ).to_dict()
        else:
            return internal_error(f"Atropos's shears failed: {msg}").to_dict()


@mcp.tool()
@auth_required
def list_issues(
    userspace: str,
    longevity: str = None, 
    status: str = None
) -> dict:
    """
    List forged Issues (Zeitgeists) in a userspace.
    
    Returns the threads spun by the Fates - each Issue is a story
    being tracked in the flow of news.
    
    Args:
        userspace: GUID of the userspace
        longevity: Filter by scale - "transient", "temporal", or "epic"
        status: Filter by status - "active" or "eternal" (sealed)
        
    Returns:
        Standardized MCPResponse as dict with:
        - status: success/error
        - data: {issues: [{id, logos, longevity, status, premises_count}], count: int}
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    selector = build_userspace_selector(userspace)
    if longevity:
        selector["longevity"] = longevity
    if status:
        selector["status"] = status

    try:
        res = db_request(
            "POST", "issues", path="/_find", json_data={"selector": selector}
        )
        
        if res.status_code >= 500:
            return transient_error(
                message=f"Database error fetching issues: HTTP {res.status_code}",
                retry_after_ms=2000,
            ).to_dict()
        
        if res.status_code != 200:
            return internal_error(
                message=f"Unexpected error fetching issues: {res.text}"
            ).to_dict()

        docs = res.json().get("docs", [])
        issues = []
        for doc in docs:
            issues.append({
                "id": doc["_id"],
                "logos": doc.get("logos", "Unnamed"),
                "description": doc.get("description", ""),
                "longevity": doc.get("longevity", "transient"),
                "status": doc.get("status", "active"),
                "premises_count": len(doc.get("premises", [])),
                "born_at": doc.get("born_at"),
                "passed_at": doc.get("passed_at"),
                "public": doc.get("public", False),
            })

        filters_desc = []
        if longevity:
            filters_desc.append(f"longevity={longevity}")
        if status:
            filters_desc.append(f"status={status}")
        filter_str = f" ({', '.join(filters_desc)})" if filters_desc else ""

        return success(
            data={
                "issues": issues,
                "count": len(issues),
                "userspace": userspace,
                "filters": {"longevity": longevity, "status": status},
            },
            message=f"Found {len(issues)} issue(s) in userspace{filter_str}",
        ).to_dict()
        
    except Exception as e:
        return internal_error(
            message=f"Unexpected error listing issues: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def read_issue(issue_id: str, userspace: str) -> dict:
    """
    Read full details of a specific Issue (Zeitgeist).
    
    Returns the complete thread - all premises, metadata, and lifecycle info.
    
    Args:
        issue_id: ID of the issue to read
        userspace: GUID of the userspace
        
    Returns:
        Standardized MCPResponse as dict with:
        - status: success/error
        - data: Complete issue document with all fields
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    doc = get_doc("issues", issue_id)
    if not doc or extract_userspace(doc) != userspace:
        return not_found_error("issue", issue_id).to_dict()

    return success(
        data=doc,
        message=f"Retrieved issue '{doc.get('logos', issue_id)}'",
    ).to_dict()


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
