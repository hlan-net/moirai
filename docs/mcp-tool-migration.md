# MCP Tool Migration Guide

## Overview

This guide explains how to migrate MCP tools from legacy string-based responses to the standardized response envelope defined in `mcp_service/responses.py`.

**Background:** Part of v0.7.1 improvement #1 (MCP Tool Contract Hardening) - see `TODO_0.7.1.md`.

---

## Why Standardize?

**Before (Legacy):**
```python
@mcp.tool()
def add_feed(url: str, userspace: str) -> str:
    if not valid_userspace(userspace):
        return "Error: Invalid userspace"  # Agent must parse string
    
    try:
        doc_id = store_doc("feeds", {...})
        return f"Feed added with ID: {doc_id}"  # Mixed success format
    except Exception as e:
        return f"Error: {e}"  # No retry guidance
```

**Problems:**
- Agents must parse strings to detect errors
- No structured retry guidance
- No way to distinguish transient vs. permanent failures
- No correlation IDs for tracing
- Inconsistent response formats across tools

**After (Standardized):**
```python
@mcp.tool()
def add_feed(url: str, userspace: str) -> dict:
    if not valid_userspace(userspace):
        return validation_error("Invalid userspace").to_dict()
    
    try:
        doc_id = store_doc("feeds", {...})
        return success(
            data={"feed_id": doc_id},
            message="Feed added successfully"
        ).to_dict()
    except requests.exceptions.Timeout:
        return transient_error(
            message="Database timeout",
            retry_after_ms=2000,
            max_retries=3
        ).to_dict()
```

**Benefits:**
- Agents branch on `status` and `retryable` fields
- Structured retry guidance with delays
- Correlation IDs for end-to-end tracing
- Canonical error codes for patterns
- Agent runtime can auto-retry transient failures

---

## Response Envelope Structure

All MCP tools return a dictionary with this structure:

```json
{
  "status": "success|error|partial",
  "data": {...},              // Response payload (null on error)
  "message": "...",            // Human-readable message
  "correlation_id": "uuid",    // Unique trace ID
  "timestamp": "ISO8601",      // Response timestamp
  
  // On error only:
  "error_code": "VALIDATION_ERROR",
  "retryable": true,
  "next_action": "retry|replan|escalate|continue|none",
  "retry_after_ms": 1000,      // Suggested retry delay
  "max_retries_hint": 3        // Suggested max attempts
}
```

---

## Migration Steps

### 1. Import Response Helpers

```python
from ..responses import (
    success,
    error,
    validation_error,
    not_found_error,
    transient_error,
    conflict_error,
    internal_error,
    partial_success,
    MCPErrorCode,
    NextAction,
)
```

### 2. Change Return Type

```python
# Before
def my_tool(...) -> str:

# After
def my_tool(...) -> dict:
```

### 3. Update Docstring

Add a "Returns" section documenting the standardized response:

```python
"""
My MCP tool description.

Args:
    param1: Description
    
Returns:
    Standardized MCPResponse as dict with:
    - status: success/error/partial
    - data: {specific fields for this tool}
    - error_code: canonical code on error
    - retryable: bool indicating if operation can be retried
    - next_action: suggested next step for agent
"""
```

### 4. Replace String Returns with Helpers

#### Success Case

```python
# Before
return f"Feed '{title}' added with ID: {doc_id}"

# After
return success(
    data={
        "feed_id": doc_id,
        "title": title,
        "userspace": userspace,
    },
    message=f"Feed '{title}' added successfully"
).to_dict()
```

#### Validation Errors

```python
# Before
return "Error: Invalid userspace UUID"

# After
return validation_error("Invalid userspace UUID").to_dict()
```

#### Not Found Errors

```python
# Before
return f"Feed {feed_id} not found or access denied"

# After
return not_found_error("feed", feed_id).to_dict()
```

#### Duplicate Resource

```python
# Before
return f"Feed already exists in userspace {userspace}"

# After
return error(
    error_code=MCPErrorCode.DUPLICATE_RESOURCE,
    message=f"Feed already exists in userspace {userspace}",
    retryable=False,
    next_action=NextAction.NONE  # Not an error - already registered
).to_dict()
```

#### Transient Network Errors

```python
# Before
except Exception as e:
    return f"Error: {e}"

# After
except requests.exceptions.Timeout:
    return transient_error(
        message="Database operation timed out",
        retry_after_ms=2000,
        max_retries=3
    ).to_dict()

except requests.exceptions.ConnectionError:
    return transient_error(
        message="Failed to connect to database",
        retry_after_ms=5000,
        max_retries=3
    ).to_dict()
```

#### Conflict/Revision Errors

```python
# Before
except RevisionConflict:
    return "Error: Document was modified, retry with fresh copy"

# After
except RevisionConflict:
    return conflict_error(
        message="Document revision mismatch - refetch and retry"
    ).to_dict()
```

#### Internal Errors (Unexpected)

```python
# Before
except Exception as e:
    return f"Unexpected error: {e}"

# After
except Exception as e:
    return internal_error(
        message=f"Unexpected error: {str(e)}"
    ).to_dict()
```

---

## Canonical Error Codes

Use these for consistent error classification:

| Error Code | Retryable | Next Action | Use Case |
|------------|-----------|-------------|----------|
| `VALIDATION_ERROR` | No | REPLAN | Invalid parameters, bad input |
| `INVALID_USERSPACE` | No | REPLAN | Userspace UUID validation failed |
| `PERMISSION_DENIED` | No | ESCALATE | Authorization failure |
| `FEED_NOT_FOUND` | No | REPLAN | Feed doesn't exist in userspace |
| `ISSUE_NOT_FOUND` | No | REPLAN | Issue doesn't exist in userspace |
| `DUPLICATE_RESOURCE` | No | NONE | Resource already exists |
| `CONFLICT_REVISION` | Yes | RETRY | CouchDB revision conflict |
| `TRANSIENT_NETWORK` | Yes | RETRY | Network timeout, connection error |
| `DATABASE_UNAVAILABLE` | Yes | RETRY | DB service down |
| `RATE_LIMITED` | Yes | RETRY | API rate limit hit |
| `INTERNAL_ERROR` | No | ESCALATE | Unexpected server error |

---

## Data Field Guidelines

### List Operations

Return structured data with count:

```python
return success(
    data={
        "feeds": [
            {"id": "...", "title": "...", "url": "..."},
            ...
        ],
        "count": 42,
        "userspace": userspace
    },
    message=f"Found {count} feed(s)"
).to_dict()
```

### Create Operations

Return the created resource with ID:

```python
return success(
    data={
        "feed_id": doc_id,
        "url": url,
        "title": title,
        "category": category,
        "added_at": timestamp
    },
    message=f"Feed '{title}' created successfully"
).to_dict()
```

### Update Operations

Return what changed:

```python
return success(
    data={
        "issue_id": issue_id,
        "updated_fields": ["longevity", "description"],
        "longevity": new_longevity
    },
    message="Issue updated successfully"
).to_dict()
```

### Delete Operations

Return confirmation with ID:

```python
return success(
    data={
        "feed_id": feed_id,
        "deleted": True
    },
    message=f"Feed {feed_id} deleted from userspace"
).to_dict()
```

---

## Testing

After migration, ensure tests validate:

1. **Success response structure:**
   ```python
   result = my_tool(valid_params)
   assert result["status"] == "success"
   assert "data" in result
   assert result["data"]["expected_field"] is not None
   ```

2. **Error code classification:**
   ```python
   result = my_tool(invalid_params)
   assert result["status"] == "error"
   assert result["error_code"] == "VALIDATION_ERROR"
   assert result["retryable"] is False
   ```

3. **Retry guidance for transient errors:**
   ```python
   # Mock a timeout
   result = my_tool(params)
   assert result["retryable"] is True
   assert result["next_action"] == "retry"
   assert result["retry_after_ms"] > 0
   ```

---

## Gradual Migration Path

### Phase 1: Core CRUD Tools (v0.7.1)
- ✅ `add_feed`
- ✅ `list_feeds`
- `delete_feed`
- `forge_issue`
- `measure_issue`
- `seal_issue`
- `search_articles`

### Phase 2: Complex Operations (v0.7.2)
- `get_user_preferences`
- `update_annotation`
- `export_to_bluesky`

### Phase 3: Legacy Wrapper (Transitional)

For tools not yet migrated, use `wrap_legacy_response()`:

```python
from ..responses import wrap_legacy_response

@mcp.tool()
def legacy_tool(...) -> dict:
    # Old implementation
    result_str = old_logic(...)
    
    # Wrap in standardized envelope
    return wrap_legacy_response(result_str).to_dict()
```

This allows the agent runtime to work with both formats during migration.

---

## Agent Runtime Integration

Once tools return standardized responses, the agent runtime can:

```python
response = call_mcp_tool("add_feed", params)

if response["retryable"] and attempt < response.get("max_retries_hint", 3):
    delay_ms = response.get("retry_after_ms", 1000)
    await asyncio.sleep(delay_ms / 1000)
    response = call_mcp_tool("add_feed", params)  # Retry

if response["status"] == "success":
    return response["data"]
elif response["next_action"] == "replan":
    # Ask LLM to generate alternative plan
    ...
elif response["next_action"] == "escalate":
    # Log for human review
    ...
```

See TODO_0.7.1.md #2 (Agent Observability) and #4 (Plan/Execute/Reflect) for runtime integration details.

---

## Reference Implementation

See `mcp_service/tools/feeds.py` for fully migrated examples:
- `add_feed()` - Create with duplicate detection
- `list_feeds()` - List with structured data

---

## Questions?

- Response envelope design: See `mcp_service/responses.py`
- Error code taxonomy: See `MCPErrorCode` enum
- Agent runtime behavior: See TODO_0.7.1.md #2 and #4
