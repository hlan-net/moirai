# BUG FIX: Raise Issue Wizard - Missing `premises` Parameter

**Status:** 🔴 CRITICAL - Feature broken in v0.6.0
**Affected Feature:** ContextChatModal "Raise Issue" wizard
**Root Cause:** MCP `forge_issue` tool requires `premises` parameter, but chat agent doesn't provide it
**Impact:** Users cannot create issues from articles
**Severity:** High (core feature blocked)

---

## Problem

When a user clicks "Raise Issue" and the chat wizard tries to create an issue, it fails with:

```
Error executing tool forge_issue: 1 validation error for forge_issueArguments
premises
  Field required [type=missing, input_value={'logos': 'f0003c11a0202e...', ...}]
```

The wizard is calling `forge_issue` without the required `premises: list[dict]` parameter.

---

## Root Cause

**File:** `mcp_service/tools/issues.py` line 170-180

```python
@mcp.tool()
@auth_required
def forge_issue(
    logos: str,
    description: str,
    premises: list[dict],  # ← REQUIRED but agent doesn't provide it
    userspace: str,
    longevity: str = "transient",
) -> str:
    """
    (Clotho) Forge a new Issue (Resonance) from identified patterns in the sand.
    """
    return _forge_issue_internal(logos, description, premises, userspace, longevity)
```

**The agent (LLM in ContextChatModal) is:**
1. Analyzing user's issue description ✅
2. Trying to call `forge_issue` tool ✅
3. Missing `premises` parameter ❌

**The `premises` parameter should be:** A list of article dictionaries that form the basis of the issue.

---

## Solution

There are two approaches:

### Approach A: Use the `add_event` alias (Recommended)

The `add_event` tool already handles `premises` properly:

```python
@mcp.tool()
@auth_required
def add_event(
    name: str,
    description: str,
    article_links: list[str],  # ← Simple list of article IDs/URLs
    userspace: str,
) -> str:
    """
    (Alias for forge_issue) Create a new Event.
    """
    premises = [{"type": "message", "id": link} for link in article_links]
    return _forge_issue_internal(name, description, premises, userspace, "transient")
```

**Fix:** Instruct the agent to use `add_event` instead of `forge_issue`, with:
- `name`: Issue title
- `description`: Issue summary
- `article_links`: List of article IDs from the context
- `userspace`: Current userspace

### Approach B: Fix the agent prompt to build `premises`

Have the agent construct the `premises` parameter before calling `forge_issue`:

```python
# Agent should generate:
mcp_client.call_tool("forge_issue", {
    "logos": "Economic Weaponization in Global Politics",
    "description": "...",
    "premises": [
        {
            "type": "article",
            "id": "article-id-1",
            "title": "Article title",
            "url": "https://..."
        },
        # ... more articles
    ],
    "userspace": "07c39a378e3f484ba7316e3d8d0f99f7"
})
```

---

## Recommended Fix

**Use Approach A** (simpler, less error-prone):

1. **Update the agent instructions** in the chat wizard to use `add_event` instead of `forge_issue`
2. **Pass article IDs** from the message context
3. **Test end-to-end**

---

## Implementation

### Step 1: Find the Agent Instruction Prompt

The issue-raising logic lives in the chat handler. Likely locations:
- `ui/src/components/ContextChatModal.vue` - Vue component with inline prompt
- `api/routes.py` - `/api/chat` endpoint with agent instructions
- A separate agent prompt file

### Step 2: Update the Prompt

Change from:
```
"Call forge_issue to create the issue with the analysis"
```

To:
```
"Call add_event to create the issue. Pass:
- name: The issue title
- description: Your analysis
- article_links: [The article IDs from the conversation context]
- userspace: The current userspace UUID"
```

### Step 3: Ensure Article Context is Available

The prompt needs to know which articles to reference:
- Extract article IDs from the user's message context
- Pass them to the agent/LLM
- The agent includes them in the `article_links` parameter

### Step 4: Test

Create a test case:
```python
def test_raise_issue_from_article():
    """Test that the chat wizard can raise an issue from an article."""
    article_id = "test-article-1"
    user_message = f"Create an issue from article {article_id}"
    # ... chat interaction ...
    # Verify issue created with proper premises
```

---

## Verification Checklist

- [ ] Agent can call `add_event` successfully
- [ ] Issue is created in CouchDB with `premises` field populated
- [ ] Issue appears in the UI (EVENTS column)
- [ ] Issue has correct `logos`, `description`, `premises`, `longevity`
- [ ] No 400/validation errors in agent response
- [ ] Works with 1 article and multiple articles
- [ ] Works across different userspace IDs

---

## Files to Review

1. **`mcp_service/tools/issues.py`** — MCP tool definitions (no changes needed)
2. **`ui/src/components/ContextChatModal.vue`** — Chat wizard component (update prompt)
3. **`api/routes.py`** — Chat endpoint (update agent instructions if prompt is server-side)
4. **`tests/test_*`** — Add test cases for the fix

---

## Timeline

- **Investigation:** 30 min (reading this doc)
- **Locate prompt:** 30 min (find where agent instructions are)
- **Update prompt:** 15 min (change forge_issue to add_event)
- **Test:** 30 min (manual + unit tests)
- **Total:** ~2 hours

---

## Related Issues

- Issue-raising wizard was marked as v0.6.0 complete, but feature is broken
- May indicate other untested agent interactions in the codebase
- Suggests need for integration tests for chat workflows

---

## Prevention

For future features:
1. **Integration test** any chat agent interaction end-to-end
2. **Don't rely on LLM** to build complex parameter structures (use aliases)
3. **Validate tool parameters** at the MCP layer with clear error messages
4. **Log failed tool calls** with full context for debugging

---

## References

- **Broken tool:** `forge_issue` in `mcp_service/tools/issues.py`
- **Working alias:** `add_event` in same file (lines 241-251)
- **Pydantic docs:** Error indicates missing required field in tool call validation
- **User report:** Chat shows repeated failures to call `forge_issue` with validation errors

