# Moirai v0.7.0+ Roadmap

This document outlines potential features and improvements for future versions beyond v0.6.0.

---

## 🎯 v0.7.0 Focus: Social Export & Syndication

### Feature: Bluesky Post Generation from Issues

**Motivation:** Moirai synthesizes important news into Issues (curated events). Let users share these insights on Bluesky with one click, extending Moirai's reach and increasing engagement.

**Scope:**

#### Phase 1: Core Integration (v0.7.0)
- [x] Design MCP tool for Bluesky API interaction
- [x] Create agent logic for post generation from issues
- [x] Store Bluesky credentials securely (encrypted in agent config)
- [x] Generate concise posts (300-char limit) with topic + sentiment
- [x] Add UI button "Share to Bluesky" on issue detail panel
- [x] Handle threading for longer posts (breaking into 5-tweet threads)

#### Phase 2: Analytics (v0.7.1)
- [ ] Track post engagement (likes, reposts, replies)
- [ ] Link back to Moirai issues via short URL
- [ ] Show engagement metrics in UI

#### Phase 3: Automation (v0.7.2+)
- [ ] SCHEDULED agent: auto-post daily digest
- [ ] AI-selected best issues from the day
- [ ] Customizable post templates per userspace

---

### Implementation Details

#### Architecture

```
┌──────────────────────────────┐
│  Issue Detail Panel          │
│  [Share to Bluesky] button   │
└──────────────────────────────┘
           ↓ (click)
┌──────────────────────────────┐
│  API: POST /api/issues/{id}/share
│  - userspace
│  - platform: "bluesky"
│  - content (optional override)
└──────────────────────────────┘
           ↓
┌──────────────────────────────┐
│  MCP Tool: publish_to_bluesky
│  - Query issue + related articles
│  - Call LLM to generate post
│  - Submit via Bluesky API
│  - Store post link in issue doc
└──────────────────────────────┘
           ↓
┌──────────────────────────────┐
│  Bluesky (atproto)           │
│  - Create post               │
│  - Return URI                │
└──────────────────────────────┘
```

#### Files to Create/Modify

**New Files:**
- `mcp_service/tools/social_export.py` — MCP tools for Bluesky
- `tasks/agent_logic/post_to_social.py` — Agent logic for auto-posting
- `api/social_config.py` — Social platform configuration & auth

**Modified Files:**
- `api/routes.py` — Add `/api/issues/{id}/share` endpoint
- `api/validation.py` — Add social share request models
- `ui/src/components/IssueDetail.vue` — Add "Share" button
- `CLAUDE.md` — Document social export patterns

#### Bluesky API Integration

```python
# mcp_service/tools/social_export.py
from atproto import Client, models

@mcp.tool()
def publish_to_bluesky(
    userspace: str,
    issue_id: str,
    post_content: str = None,
) -> dict:
    """
    Publish an issue to Bluesky.

    Args:
        userspace: User's workspace UUID
        issue_id: Issue/Event document ID
        post_content: Optional custom content (auto-generated if None)

    Returns:
        {
            "post_uri": "at://...",
            "post_url": "https://bsky.app/profile/...",
            "platform": "bluesky",
            "published_at": "2024-03-13T..."
        }
    """
    # Fetch issue
    issue = query_couchdb("issues", selector={"_id": issue_id, "userspace": userspace})
    if not issue:
        raise ValueError(f"Issue not found: {issue_id}")

    # Generate post if not provided
    if not post_content:
        post_content = _generate_bluesky_post(issue)

    # Connect to Bluesky
    client = Client()
    client.login(username, password)  # Or use OAuth token

    # Handle threading if >300 chars
    posts = _split_into_posts(post_content, max_length=300)
    first_post_uri = None

    for i, post_text in enumerate(posts):
        # Add metadata to last post
        if i == len(posts) - 1:
            post_text += f"\n\n🔗 Full issue: moirai.example.com/issues/{issue_id}"

        response = client.send_post(post_text)
        if i == 0:
            first_post_uri = response.uri

    # Store reference in issue document
    update_couchdb_doc_safe(
        "issues",
        issue_id,
        {
            "social_posts": {
                "bluesky": {
                    "post_uri": first_post_uri,
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                    "status": "published"
                }
            }
        }
    )

    return {
        "post_uri": first_post_uri,
        "post_url": f"https://bsky.app/profile/{username}/post/...",
        "platform": "bluesky",
        "published_at": datetime.now(timezone.utc).isoformat()
    }

def _generate_bluesky_post(issue: dict) -> str:
    """Generate a concise Bluesky post from an issue."""
    llm = get_llm_provider()
    prompt = f"""
    Generate a concise Bluesky post (max 280 chars) about this issue:

    Title: {issue['title']}
    Summary: {issue['summary']}
    Articles: {len(issue.get('articles', []))}

    Guidelines:
    - Hook the reader in first line
    - Include emoji for visual interest
    - End with call-to-action (link/question)
    - Use hashtags sparingly (max 2)
    """
    return llm.generate(prompt)
```

#### UI: Share Button

```vue
<!-- ui/src/components/IssueDetail.vue -->
<template>
  <div class="issue-detail">
    <header>
      <h2>{{ issue.title }}</h2>
      <div class="actions">
        <button @click="shareToBluesky" class="btn-social">
          📘 Share to Bluesky
        </button>
      </div>
    </header>

    <div v-if="blueskyPost" class="social-proof">
      ✅ Posted to Bluesky
      <a :href="blueskyPost.post_url" target="_blank">
        View post →
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { postToSocial } from '@/api/social'

const issue = ref()
const blueskyPost = ref()

async function shareToBluesky() {
  try {
    const response = await postToSocial('bluesky', issue.value._id)
    blueskyPost.value = response
    showNotification('✅ Posted to Bluesky!')
  } catch (error) {
    showNotification('❌ Failed to post', 'error')
  }
}
</script>

<style scoped>
.btn-social {
  background: #1185fe;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
}

.social-proof {
  background: #e7f3ff;
  padding: 1rem;
  border-radius: 4px;
  margin-top: 1rem;
}
</style>
```

#### Configuration (Admin)

```env
# .env for Bluesky
BLUESKY_ENABLED=true
BLUESKY_SERVICE_URL=https://bsky.social
# Per-user credentials stored encrypted in agent_config

# Or centralized (less secure, for demo)
BLUESKY_USERNAME=moirai@example.bsky.social
BLUESKY_PASSWORD=app-password-from-bluesky
```

---

### Security Considerations

1. **Credential Storage:** Encrypt Bluesky app passwords in CouchDB using `cryptography` library
   ```python
   from cryptography.fernet import Fernet

   # Admin sets encryption key in environment
   cipher = Fernet(os.environ['ENCRYPTION_KEY'].encode())
   encrypted = cipher.encrypt(bluesky_password.encode())
   ```

2. **Rate Limiting:** Prevent spam
   ```python
   # Max 20 posts per hour per userspace
   # Use Redis to track
   ```

3. **Content Filtering:** Don't post if issue contains flagged content
   ```python
   # Check for PII, confidential info
   if contains_sensitive_data(issue):
       raise ValueError("Cannot post: contains sensitive data")
   ```

4. **Audit Trail:** Log all posts
   ```python
   logger.info(f"Posted issue {issue_id} to Bluesky: {post_uri}")
   ```

---

### Testing

```python
# tests/test_bluesky_integration.py
@patch('mcp_service.tools.social_export.Client')
def test_publish_to_bluesky(mock_bluesky_client):
    mock_client = MagicMock()
    mock_client.send_post.return_value = MagicMock(uri="at://...")
    mock_bluesky_client.return_value = mock_client

    result = publish_to_bluesky(
        userspace="test-uuid",
        issue_id="issue-1",
        post_content="Test post"
    )

    assert result["platform"] == "bluesky"
    assert "post_uri" in result
    mock_client.send_post.assert_called_once()
```

---

## Future Enhancements (v0.8+)

### Multi-Platform Support

Extend beyond Bluesky:
- 🐦 **Twitter/X** (via API v2)
- 📘 **Mastodon** (ActivityPub)
- 💼 **LinkedIn** (requires approval)
- 🔗 **Custom Webhooks** (Slack, Discord, Teams)

### Batch Sharing

- Daily digest of top 3 issues
- Weekly roundup thread
- Monthly state-of-the-union post

### Template Customization

- Per-userspace post templates
- A/B test different framings
- Custom hashtags

### Engagement Analytics

- Track clicks back to Moirai
- Measure sentiment in replies
- Feed back into issue importance scoring

---

## Dependencies to Add

```
# For Bluesky integration (add to environment.yml / requirements.txt)
atproto>=0.0.58  # Bluesky API client
cryptography>=41.0.0  # For credential encryption
```

---

## Effort Estimation

| Phase | Stories | Dev Time | Testing | Docs | Total |
|-------|---------|----------|---------|------|-------|
| Phase 1 (Core) | 6 | 15h | 5h | 2h | **22h** |
| Phase 2 (Analytics) | 3 | 8h | 3h | 1h | **12h** |
| Phase 3 (Auto) | 4 | 10h | 4h | 2h | **16h** |
| **Multi-Platform** | 8 | 20h | 8h | 3h | **31h** |

---

## Success Metrics

- ✅ Users can share issues to Bluesky in 2 clicks
- ✅ Posts include article link for attribution
- ✅ No sensitive data leaks
- ✅ Admin can monitor posted content
- ✅ Engagement metrics available

---

## Questions / Open Items

1. **Auth method:** User provides credentials, or OAuth flow?
   - Proposal: User provides app password (one-time, per-device)

2. **Post frequency:** Immediate, daily digest, or on-demand only?
   - Proposal: Start with on-demand button; add automation in v0.7.2

3. **Link tracking:** Short URLs with UTM params to track engagement?
   - Proposal: Use bitly or custom shortener to track clicks

4. **Moderation:** Who approves posts before publishing?
   - Proposal: No approval needed; admin can manually delete from Bluesky if issues

5. **Thread handling:** Should long posts auto-split into threads?
   - Proposal: Yes, automatically break at 300 chars with continuation indicator

---

## References

- [Bluesky API Docs](https://docs.bsky.app)
- [atproto Python SDK](https://github.com/MarshalX/atproto)
- [ATProto Specification](https://atproto.com)

---

**Status:** Proposed for v0.7.0+
**Owner:** TBD
**Priority:** Medium (nice-to-have, high user value)
