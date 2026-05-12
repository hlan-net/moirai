# Dashboard UX: Status & Performance Improvements

**Status:** Implementation Ready | **Priority:** High

This document outlines the root causes of the "erratic" dashboard behavior and provides a comprehensive, phased implementation plan.

---

## 🎯 Quick Implementation Reference

### 1. Critical Fixes (Immediate)
- **Fix 1: Sync Polling Intervals.** Articles, Events, and Trends must refresh at the same rate.
  - Create `ui/src/config/polling.ts`: `export const SYNC_REFRESH_INTERVAL = 30000`
- **Fix 2: Article Polling Bug.** Remove the condition in `ArticleColumn.vue` that stops refresh when filters are active.
- **Fix 3: Last Updated Indicator.** Add `lastUpdated` and `isRefreshing` to `filterStore` and display in `MainPage.vue`.

### 2. Performance Fixes (Backend)
- **Index 1: CouchDB Indexes.** Create indexes for `articles` (published, userspace, feed_url) and `issues` (longevity, userspace).
- **Index 2: Article Enrichment.** Replace O(n*m) loop in `enrichment.py` with cached Redis lookups.
- **Index 3: Cache Versioning.** Add `cache_version` to API responses to allow frontend to invalidate IndexedDB on backend restart.

---

## Problem Analysis

### User-Reported Symptoms
- Status updates feel "erratic" and unsynchronized
- Dashboard feels "not snappy"
- Difficult to get a feel for the system due to inconsistent behavior
- No clear indication when data is stale vs. fresh

### Current Architecture

**Frontend Components:**
```
MainPage.vue (Dashboard Root)
├── FeedColumn.vue      - No auto-refresh (loads once)
├── ArticleColumn.vue   - Polls every 120s (conditional)
├── EventColumn.vue     - Polls every 30s (always)
└── TrendColumn.vue     - Polls every 30s (always)
```

**Data Flow:**
```
Frontend Polls (30s/120s intervals)
    ↓
API Endpoints (/api/articles, /api/issues, /api/feeds)
    ↓
Redis Cache (1 hour TTL) + CouchDB
    ↓
Frontend IndexedDB Cache (1 day TTL)
```

**State Management:**
- Pinia `filterStore` - Cross-column communication
- Each column has independent refresh state
- No global coordination mechanism

---

## Root Causes

### 🔴 Critical Issues

#### 1. **Desynchronized Polling Intervals**
**Location:** Multiple component files  
**Impact:** HIGH

Different columns refresh at different rates:
- ArticleColumn: 120 seconds (`ui/src/components/ArticleColumn.vue:335`)
- EventColumn: 30 seconds (`ui/src/components/EventColumn.vue:141`)
- TrendColumn: 30 seconds (`ui/src/components/TrendColumn.vue:142`)
- FeedColumn: No polling (once on mount)

**Result:** Columns can be out of sync by up to 90 seconds, creating perception of erratic behavior.

#### 2. **Conditional Polling Bug in ArticleColumn**
**Location:** `ui/src/components/ArticleColumn.vue:336-342`  
**Impact:** CRITICAL

```typescript
refreshInterval = globalThis.setInterval(() => {
  if (!filterStore.selectedFeedId && !filterStore.selectedIssueId) {
    fetchLatestUpdates()  // ❌ Only runs if NO filters active!
  }
}, 120000)
```

**Result:** When user selects a feed or issue filter, articles stop auto-refreshing entirely. New data ingested by backend is not visible until manual refresh.

#### 3. **Multi-Layer Cache Without Coordination**
**Locations:** 
- Frontend: `ui/src/utils/articleCache.ts` (IndexedDB, 1 day TTL)
- Backend: `api/routes.py` (Redis, 1 hour TTL)

**Impact:** HIGH

Backend can invalidate Redis cache, but frontend's IndexedDB is unaware and serves stale data for up to 24 hours.

#### 4. **No Unified Update Indicator**
**Location:** All column components  
**Impact:** MEDIUM

Each column has independent loading state:
```typescript
// FeedColumn
const refreshing = ref(false)

// ArticleColumn  
const fetchingUpdates = ref(false)
const loadingMore = ref(false)

// EventColumn
const refreshing = ref(false)

// TrendColumn
const refreshing = ref(false)
```

**Result:** Multiple spinners compete for attention, creating visual confusion about overall refresh state.

### ⚠️ Performance Issues

#### 5. **CouchDB Memory Pressure**
**Evidence:** Backend logs show:
```
[info] 2026-03-20T10:51:11.726381Z alarm_handler: {set,{system_memory_high_watermark,[]}}
```

**Cause:** Mango queries without indexes scan entire collections as data grows.

#### 6. **Inefficient Article Enrichment**
**Location:** `api/enrichment.py`  
**Impact:** MEDIUM-HIGH

```python
def enrich_articles_with_issues(articles):
    # ❌ Fetches ALL issues from CouchDB
    # ❌ Iterates through articles and issues to find matches
    # ❌ O(n*m) complexity - not scalable
    # ❌ Blocking call on every /api/articles request
```

**Result:** Article fetches add significant latency, especially with many issues.

#### 7. **Missing Database Indexes**
**Location:** CouchDB collections  
**Impact:** HIGH (performance degradation as data grows)

No indexes found in code for:
- `articles` collection (published, feed_url, userspace)
- `issues` collection (longevity, userspace, feed_urls)

---

## Implementation Tiers

### TIER 1: Quick Wins (30 min - 1 hour) ⚡

**Goal:** Fix critical bugs causing erratic updates with minimal risk.

#### 1.1 Fix Conditional Polling Bug ⚠️ CRITICAL
**Priority:** P0  
**File:** `ui/src/components/ArticleColumn.vue`  
**Lines:** 335-342

**Change:**
```typescript
// BEFORE (BUGGY):
refreshInterval = globalThis.setInterval(() => {
  if (!filterStore.selectedFeedId && !filterStore.selectedIssueId) {
    fetchLatestUpdates()
  }
}, 120000)

// AFTER (FIXED):
const SYNC_REFRESH_INTERVAL = 30000 // 30 seconds

refreshInterval = globalThis.setInterval(() => {
  fetchLatestUpdates() // ✅ Always refresh, regardless of filter state
}, SYNC_REFRESH_INTERVAL)
```

**Testing:**
1. Open dashboard
2. Select a feed filter
3. Wait 30 seconds
4. Verify articles still refresh automatically

---

#### 1.2 Synchronize Polling Intervals
**Priority:** P0  
**Files:**
- `ui/src/components/ArticleColumn.vue:335`
- `ui/src/components/EventColumn.vue:141`
- `ui/src/components/TrendColumn.vue:142`

**Implementation:**

**Step 1:** Create shared constants file
```typescript
// ui/src/config/polling.ts
export const SYNC_REFRESH_INTERVAL = 30000 // 30 seconds
export const FAST_REFRESH_INTERVAL = 10000 // 10 seconds (optional, for future use)
```

**Step 2:** Update ArticleColumn
```typescript
import { SYNC_REFRESH_INTERVAL } from '@/config/polling'

// In onMounted:
refreshInterval = globalThis.setInterval(() => {
  fetchLatestUpdates()
}, SYNC_REFRESH_INTERVAL) // Changed from 120000
```

**Step 3:** Update EventColumn
```typescript
import { SYNC_REFRESH_INTERVAL } from '@/config/polling'

// In onMounted:
refreshInterval = globalThis.setInterval(() => fetchIssues(true), SYNC_REFRESH_INTERVAL)
```

**Step 4:** Update TrendColumn
```typescript
import { SYNC_REFRESH_INTERVAL } from '@/config/polling'

// In onMounted:
refreshInterval = globalThis.setInterval(() => fetchIssues(true), SYNC_REFRESH_INTERVAL)
```

**Testing:**
1. Add console.log with timestamps in each refresh function
2. Verify all columns log at approximately the same time (±500ms)

---

#### 1.3 Add Unified "Last Updated" Indicator
**Priority:** P1  
**File:** `ui/src/components/MainPage.vue`

**Implementation:**

**Step 1:** Add to filter store
```typescript
// ui/src/stores/filter.ts
import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useFilterStore = defineStore('filter', () => {
  // ... existing state ...
  
  const lastUpdated = ref<Date | null>(null)
  const isRefreshing = ref(false)
  
  function markRefreshStart() {
    isRefreshing.value = true
  }
  
  function markRefreshComplete() {
    isRefreshing.value = false
    lastUpdated.value = new Date()
  }
  
  return {
    // ... existing exports ...
    lastUpdated,
    isRefreshing,
    markRefreshStart,
    markRefreshComplete,
  }
})
```

**Step 2:** Add UI to MainPage
```vue
<!-- ui/src/components/MainPage.vue -->
<template>
  <div class="main-page">
    <!-- Add at top of dashboard -->
    <div class="dashboard-status">
      <div v-if="filterStore.isRefreshing" class="status-indicator refreshing">
        <span class="spinner"></span>
        Refreshing data...
      </div>
      <div v-else-if="filterStore.lastUpdated" class="status-indicator">
        <span class="check-icon">✓</span>
        Updated {{ formatTimeAgo(filterStore.lastUpdated) }}
      </div>
    </div>
    
    <!-- Existing columns -->
    <div class="columns-container">
      <FeedColumn />
      <ArticleColumn />
      <EventColumn />
      <TrendColumn />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useFilterStore } from '@/stores/filter'
import { ref, onMounted, onUnmounted } from 'vue'

const filterStore = useFilterStore()

// Update time ago display every 10 seconds
let timeUpdateInterval: number | null = null

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  
  if (seconds < 10) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

onMounted(() => {
  timeUpdateInterval = window.setInterval(() => {
    // Force re-render of time display
  }, 10000)
})

onUnmounted(() => {
  if (timeUpdateInterval) clearInterval(timeUpdateInterval)
})
</script>

<style scoped>
.dashboard-status {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
  padding: 0.5rem 1rem;
  display: flex;
  justify-content: flex-end;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--color-text-secondary);
}

.status-indicator.refreshing {
  color: var(--color-primary);
}

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.check-icon {
  color: var(--color-success);
  font-weight: bold;
}
</style>
```

**Step 3:** Call from each column component

In ArticleColumn, EventColumn, TrendColumn - wrap fetch calls:
```typescript
async function fetchData() {
  filterStore.markRefreshStart()
  try {
    // ... existing fetch logic ...
  } finally {
    filterStore.markRefreshComplete()
  }
}
```

**Testing:**
1. Open dashboard
2. Verify "Updated X seconds ago" appears
3. Wait for auto-refresh
4. Verify indicator changes to "Refreshing data..." then back to updated time

---

#### 1.4 Unified Loading State (Optional - can defer to Tier 2)
**Priority:** P2  
**Approach:** Remove individual column spinners, rely on unified indicator from 1.3

---

### TIER 2: Medium Impact (2-4 hours) 🔧

**Goal:** Optimize backend performance and improve cache coordination.

#### 2.1 Add CouchDB Indexes
**Priority:** P0 (Performance)  
**Location:** Database initialization

**Implementation:**

**Step 1:** Create index initialization script
```python
# api/db_indexes.py
"""
CouchDB index initialization for Moirai.

Run once on deployment or database setup to create performance indexes.
"""
from api.couchdb_utils import get_couchdb_connection
import logging

logger = logging.getLogger(__name__)

def create_articles_indexes():
    """Create indexes for articles collection."""
    db_url = get_couchdb_connection()
    
    indexes = [
        {
            "index": {
                "fields": ["published"]
            },
            "name": "idx_published",
            "type": "json"
        },
        {
            "index": {
                "fields": ["userspace", "published"]
            },
            "name": "idx_userspace_published",
            "type": "json"
        },
        {
            "index": {
                "fields": ["feed_url", "published"]
            },
            "name": "idx_feed_url_published",
            "type": "json"
        },
        {
            "index": {
                "fields": ["userspace", "feed_url", "published"]
            },
            "name": "idx_userspace_feed_published",
            "type": "json"
        },
    ]
    
    for index_def in indexes:
        try:
            response = requests.post(
                f"{db_url}/articles/_index",
                json=index_def,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.info(f"✓ Created index: {index_def['name']}")
        except Exception as e:
            logger.error(f"✗ Failed to create index {index_def['name']}: {e}")

def create_issues_indexes():
    """Create indexes for issues collection."""
    db_url = get_couchdb_connection()
    
    indexes = [
        {
            "index": {
                "fields": ["longevity"]
            },
            "name": "idx_longevity",
            "type": "json"
        },
        {
            "index": {
                "fields": ["userspace", "longevity"]
            },
            "name": "idx_userspace_longevity",
            "type": "json"
        },
        {
            "index": {
                "fields": ["feed_urls"]
            },
            "name": "idx_feed_urls",
            "type": "json"
        },
    ]
    
    for index_def in indexes:
        try:
            response = requests.post(
                f"{db_url}/issues/_index",
                json=index_def,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.info(f"✓ Created index: {index_def['name']}")
        except Exception as e:
            logger.error(f"✗ Failed to create index {index_def['name']}: {e}")

def create_feeds_indexes():
    """Create indexes for feeds collection."""
    db_url = get_couchdb_connection()
    
    indexes = [
        {
            "index": {
                "fields": ["userspace"]
            },
            "name": "idx_userspace",
            "type": "json"
        },
    ]
    
    for index_def in indexes:
        try:
            response = requests.post(
                f"{db_url}/feeds/_index",
                json=index_def,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.info(f"✓ Created index: {index_def['name']}")
        except Exception as e:
            logger.error(f"✗ Failed to create index {index_def['name']}: {e}")

def initialize_all_indexes():
    """Create all indexes for Moirai collections."""
    logger.info("Initializing CouchDB indexes...")
    create_articles_indexes()
    create_issues_indexes()
    create_feeds_indexes()
    logger.info("Index initialization complete")

if __name__ == "__main__":
    initialize_all_indexes()
```

**Step 2:** Add to startup script
```python
# main.py or app initialization
from api.db_indexes import initialize_all_indexes

# Run on startup (idempotent - safe to run multiple times)
try:
    initialize_all_indexes()
except Exception as e:
    logger.warning(f"Failed to initialize indexes: {e}")
```

**Testing:**
1. Run initialization script
2. Check CouchDB Fauxton UI at `http://localhost:5984/_utils`
3. Navigate to each database → Design Documents
4. Verify indexes are listed
5. Run query with `explain=true` to verify index usage

---

#### 2.2 Optimize Article Enrichment
**Priority:** P1 (Performance)  
**Location:** `api/enrichment.py`

**Current Implementation (SLOW):**
```python
def enrich_articles_with_issues(articles: list[dict]) -> None:
    """Add issue references to articles. O(n*m) complexity."""
    issues = query_couchdb("issues", selector={})["docs"]  # ❌ Fetch ALL
    
    for article in articles:  # ❌ Nested loops
        article["issues"] = []
        for issue in issues:
            if article["feed_url"] in issue.get("feed_urls", []):
                article["issues"].append(issue["_id"])
```

**Optimized Implementation:**
```python
from typing import Dict, List, Set
from api.extensions import get_redis_client
import json

ISSUE_CACHE_TTL = 300  # 5 minutes

def get_cached_issues_by_feed() -> Dict[str, List[str]]:
    """
    Get cached mapping of feed_url -> [issue_ids].
    
    Returns:
        Dict mapping feed URLs to list of issue IDs that reference them.
    """
    redis_client = get_redis_client()
    cache_key = "issues_by_feed_map"
    
    # Try cache first
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Build map from database
    issues = query_couchdb("issues", selector={})["docs"]
    feed_to_issues: Dict[str, List[str]] = {}
    
    for issue in issues:
        for feed_url in issue.get("feed_urls", []):
            if feed_url not in feed_to_issues:
                feed_to_issues[feed_url] = []
            feed_to_issues[feed_url].append(issue["_id"])
    
    # Cache for 5 minutes
    redis_client.setex(cache_key, ISSUE_CACHE_TTL, json.dumps(feed_to_issues))
    
    return feed_to_issues

def enrich_articles_with_issues(articles: List[dict]) -> None:
    """
    Add issue references to articles. Optimized with caching.
    
    Complexity: O(n) instead of O(n*m)
    """
    if not articles:
        return
    
    # Get pre-built mapping (cached)
    feed_to_issues = get_cached_issues_by_feed()
    
    # Simple lookup for each article
    for article in articles:
        feed_url = article.get("feed_url")
        article["issues"] = feed_to_issues.get(feed_url, [])

def invalidate_issue_cache():
    """Call this when issues are created/updated/deleted."""
    redis_client = get_redis_client()
    redis_client.delete("issues_by_feed_map")
```

**Step 2:** Add cache invalidation to issue routes
```python
# api/routes.py - In issue create/update/delete endpoints
from api.enrichment import invalidate_issue_cache

@app.route('/api/issues', methods=['POST'])
@requires_auth
def create_issue():
    # ... existing code ...
    invalidate_issue_cache()  # ✅ Add this
    return response

@app.route('/api/issues/<issue_id>', methods=['PUT'])
@requires_auth
def update_issue(issue_id):
    # ... existing code ...
    invalidate_issue_cache()  # ✅ Add this
    return response

@app.route('/api/issues/<issue_id>', methods=['DELETE'])
@requires_auth
def delete_issue(issue_id):
    # ... existing code ...
    invalidate_issue_cache()  # ✅ Add this
    return response
```

**Performance Impact:**
- Before: O(n*m) - 100 articles × 50 issues = 5,000 comparisons
- After: O(n) - 100 articles = 100 lookups
- **50x improvement** with typical dataset

**Testing:**
1. Add timing logs around enrichment call
2. Compare before/after timing
3. Verify articles still show correct issue associations

---

#### 2.3 Smart Cache Coordination
**Priority:** P1  
**Goal:** Sync frontend IndexedDB with backend Redis cache

**Implementation:**

**Step 1:** Add cache version to API responses
```python
# api/routes.py
import time

CACHE_VERSION = int(time.time())  # Updated on deployment

@app.route('/api/articles')
@requires_auth
def get_articles():
    # ... existing code ...
    
    response_data = {
        "articles": paginated_articles,
        "has_more": has_more,
        "cache_version": CACHE_VERSION,  # ✅ Add this
    }
    
    return jsonify(response_data)
```

**Step 2:** Check version in frontend
```typescript
// ui/src/utils/articleCache.ts

const CACHE_VERSION_KEY = 'moirai_cache_version'

export async function checkCacheVersion(serverVersion: number): Promise<boolean> {
  const storedVersion = localStorage.getItem(CACHE_VERSION_KEY)
  
  if (!storedVersion || parseInt(storedVersion) !== serverVersion) {
    console.log('Cache version mismatch, clearing IndexedDB')
    await clearAllArticles()
    localStorage.setItem(CACHE_VERSION_KEY, serverVersion.toString())
    return false
  }
  
  return true
}
```

**Step 3:** Use in ArticleColumn
```typescript
// ui/src/components/ArticleColumn.vue

async function fetchArticlesAndCache(skip: number) {
  const response = await authFetch(/* ... */)
  const data = await response.json()
  
  // Check cache version
  if (data.cache_version) {
    const cacheValid = await articleCache.checkCacheVersion(data.cache_version)
    if (!cacheValid) {
      // Cache was cleared, reload from scratch
      articles.value = []
    }
  }
  
  // ... rest of logic ...
}
```

**Step 4:** Reduce IndexedDB TTL
```typescript
// ui/src/utils/articleCache.ts

// BEFORE:
const CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000 // 1 day

// AFTER:
const CACHE_MAX_AGE_MS = 60 * 60 * 1000 // 1 hour (matches Redis)
```

**Testing:**
1. Load dashboard, verify articles cached
2. Restart backend (cache version changes)
3. Refresh dashboard
4. Verify IndexedDB is cleared and repopulated

---

#### 2.4 Add Response Time Logging
**Priority:** P2  
**Location:** `api/routes.py`

**Implementation:**
```python
# api/middleware.py (create new file)
import time
import logging
from flask import request, g

logger = logging.getLogger(__name__)

def setup_request_timing(app):
    """Add request timing middleware to Flask app."""
    
    @app.before_request
    def start_timer():
        g.start_time = time.time()
    
    @app.after_request
    def log_request_time(response):
        if hasattr(g, 'start_time'):
            elapsed = (time.time() - g.start_time) * 1000  # ms
            
            # Log slow requests (>500ms)
            if elapsed > 500:
                logger.warning(
                    f"SLOW REQUEST: {request.method} {request.path} "
                    f"took {elapsed:.2f}ms"
                )
            
            # Add header for debugging
            response.headers['X-Response-Time'] = f"{elapsed:.2f}ms"
        
        return response
```

**Step 2:** Enable in main.py
```python
# main.py
from api.middleware import setup_request_timing

app = Flask(__name__)
setup_request_timing(app)
```

**Testing:**
1. Make API requests
2. Check response headers for `X-Response-Time`
3. Check logs for slow request warnings

---

#### 2.5 Visual Feedback Improvements
**Priority:** P2  
**Files:** Various component files

**Changes:**

**A. Skeleton Loaders During Initial Load**
```vue
<!-- ui/src/components/ArticleColumn.vue -->
<template>
  <div class="article-column">
    <!-- Show skeleton during initial load -->
    <div v-if="loading" class="skeleton-container">
      <div v-for="i in 5" :key="i" class="skeleton-article">
        <div class="skeleton-title"></div>
        <div class="skeleton-meta"></div>
        <div class="skeleton-excerpt"></div>
      </div>
    </div>
    
    <!-- Normal content -->
    <div v-else>
      <!-- ... existing article list ... -->
    </div>
  </div>
</template>

<style scoped>
.skeleton-article {
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
}

.skeleton-title,
.skeleton-meta,
.skeleton-excerpt {
  background: linear-gradient(
    90deg,
    var(--color-background-soft) 25%,
    var(--color-background-mute) 50%,
    var(--color-background-soft) 75%
  );
  background-size: 200% 100%;
  animation: loading 1.5s infinite;
  border-radius: 4px;
}

.skeleton-title {
  height: 1.5rem;
  width: 80%;
  margin-bottom: 0.5rem;
}

.skeleton-meta {
  height: 1rem;
  width: 60%;
  margin-bottom: 0.5rem;
}

.skeleton-excerpt {
  height: 3rem;
  width: 100%;
}

@keyframes loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
```

**B. Toast Notifications for Errors**
```typescript
// ui/src/utils/toast.ts (create new file)
export function showToast(message: string, type: 'success' | 'error' | 'info' = 'info') {
  const toast = document.createElement('div')
  toast.className = `toast toast-${type}`
  toast.textContent = message
  
  document.body.appendChild(toast)
  
  // Fade in
  setTimeout(() => toast.classList.add('show'), 10)
  
  // Fade out and remove
  setTimeout(() => {
    toast.classList.remove('show')
    setTimeout(() => toast.remove(), 300)
  }, 3000)
}

// Add to style.css:
.toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  padding: 1rem 1.5rem;
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  opacity: 0;
  transform: translateY(1rem);
  transition: all 0.3s ease;
  z-index: 1000;
}

.toast.show {
  opacity: 1;
  transform: translateY(0);
}

.toast-error {
  border-color: var(--color-error);
  background: var(--color-error-soft);
}

.toast-success {
  border-color: var(--color-success);
  background: var(--color-success-soft);
}
```

**C. Use in Components**
```typescript
// ui/src/components/ArticleColumn.vue
import { showToast } from '@/utils/toast'

async function fetchArticlesAndCache(skip: number) {
  try {
    // ... existing code ...
  } catch (error) {
    console.error('Failed to fetch articles:', error)
    showToast('Failed to load articles. Please try again.', 'error')  // ✅ Add this
  }
}
```

---

### TIER 3: Major Overhaul (1-2 days) 🚀

**Goal:** Eliminate polling entirely with real-time push architecture.

#### 3.1 Server-Sent Events (SSE) Implementation
**Priority:** P1 (after Tier 1 & 2 validated)  
**Impact:** Eliminates all polling lag

**Architecture Decision:**

**Option A: Dedicated SSE Endpoint (Recommended)**
- Separate endpoint `/api/events/stream`
- Doesn't block main Flask workers
- Can use gevent/eventlet for long-lived connections

**Option B: Multiplex Through Flask**
- Use Flask-SSE extension
- Simpler setup but may impact performance

**Recommended: Option A**

**Implementation:**

**Step 1: Backend SSE Endpoint**
```python
# api/sse.py (create new file)
"""
Server-Sent Events (SSE) implementation for real-time updates.
"""
from flask import Response, stream_with_context
import json
import time
import redis
from typing import Generator

def event_stream(userspace: str) -> Generator[str, None, None]:
    """
    SSE event stream for dashboard updates.
    
    Subscribes to Redis pub/sub for real-time events.
    """
    redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
    pubsub = redis_client.pubsub()
    
    # Subscribe to channels
    pubsub.subscribe(
        f'moirai:updates:{userspace}',
        f'moirai:updates:all',
    )
    
    # Send initial connection event
    yield f"data: {json.dumps({'type': 'connected', 'timestamp': time.time()})}\n\n"
    
    # Listen for events
    for message in pubsub.listen():
        if message['type'] == 'message':
            # Forward event to client
            yield f"data: {message['data']}\n\n"

@app.route('/api/events/stream')
@requires_auth
def sse_stream():
    """SSE endpoint for real-time dashboard updates."""
    userspace = request.args.get('userspace')
    
    if not userspace:
        return jsonify({"error": "userspace required"}), 400
    
    return Response(
        stream_with_context(event_stream(userspace)),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
        }
    )
```

**Step 2: Publish Events on Data Changes**
```python
# api/events.py (create new file)
"""Event publishing utilities."""
import json
from api.extensions import get_redis_client

def publish_update(event_type: str, data: dict, userspace: str = None):
    """
    Publish update event to SSE subscribers.
    
    Args:
        event_type: Type of update (article_added, issue_detected, feed_updated)
        data: Event payload
        userspace: Optional userspace (if None, broadcasts to all)
    """
    redis_client = get_redis_client()
    
    event = {
        'type': event_type,
        'data': data,
        'timestamp': time.time(),
    }
    
    event_json = json.dumps(event)
    
    # Publish to specific userspace
    if userspace:
        redis_client.publish(f'moirai:updates:{userspace}', event_json)
    
    # Also publish to global channel
    redis_client.publish('moirai:updates:all', event_json)
```

**Step 3: Use in Article Ingestion**
```python
# tasks/article_processor.py

from api.events import publish_update

def process_articles(feed_url: str, userspace: str):
    """Process articles and publish events."""
    # ... existing processing ...
    
    # After successfully adding article:
    publish_update(
        event_type='article_added',
        data={
            'feed_url': feed_url,
            'article_id': article['_id'],
            'title': article['title'],
        },
        userspace=userspace
    )
```

**Step 4: Frontend SSE Client**
```typescript
// ui/src/utils/sse.ts (create new file)
import { ref } from 'vue'
import type { Ref } from 'vue'

export interface SSEEvent {
  type: string
  data: any
  timestamp: number
}

export class SSEClient {
  private eventSource: EventSource | null = null
  private reconnectTimer: number | null = null
  private readonly reconnectDelay = 5000 // 5 seconds
  
  public connected: Ref<boolean> = ref(false)
  public lastError: Ref<Error | null> = ref(null)
  
  constructor(
    private url: string,
    private onEvent: (event: SSEEvent) => void
  ) {}
  
  connect() {
    if (this.eventSource) {
      return // Already connected
    }
    
    console.log('SSE: Connecting to', this.url)
    this.eventSource = new EventSource(this.url)
    
    this.eventSource.onopen = () => {
      console.log('SSE: Connected')
      this.connected.value = true
      this.lastError.value = null
    }
    
    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this.onEvent(data)
      } catch (error) {
        console.error('SSE: Failed to parse event', error)
      }
    }
    
    this.eventSource.onerror = (error) => {
      console.error('SSE: Connection error', error)
      this.connected.value = false
      this.lastError.value = new Error('SSE connection failed')
      
      // Attempt reconnection
      this.disconnect()
      this.scheduleReconnect()
    }
  }
  
  disconnect() {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
      this.connected.value = false
    }
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }
  
  private scheduleReconnect() {
    if (this.reconnectTimer) return
    
    console.log(`SSE: Reconnecting in ${this.reconnectDelay}ms`)
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, this.reconnectDelay)
  }
}
```

**Step 5: Use SSE in MainPage**
```typescript
// ui/src/components/MainPage.vue
import { SSEClient } from '@/utils/sse'
import { useAuthStore } from '@/stores/auth'
import { useFilterStore } from '@/stores/filter'

const authStore = useAuthStore()
const filterStore = useFilterStore()

let sseClient: SSEClient | null = null

function handleSSEEvent(event: SSEEvent) {
  console.log('Received SSE event:', event)
  
  switch (event.type) {
    case 'article_added':
      // Trigger article refresh
      filterStore.markRefreshStart()
      // ArticleColumn listens to this and refetches
      break
      
    case 'issue_detected':
      // Trigger issues refresh
      break
      
    case 'feed_updated':
      // Trigger feed refresh
      break
  }
  
  filterStore.markRefreshComplete()
}

onMounted(() => {
  // Connect to SSE
  const userspace = authStore.userspace
  const token = authStore.token
  
  sseClient = new SSEClient(
    `/api/events/stream?userspace=${userspace}&token=${token}`,
    handleSSEEvent
  )
  
  sseClient.connect()
})

onUnmounted(() => {
  sseClient?.disconnect()
})
```

**Benefits:**
- ✅ Zero polling lag - updates appear instantly
- ✅ Reduced server load - no constant polling
- ✅ Better battery life - connection maintained, not recreated
- ✅ Scalable - Redis pub/sub handles many subscribers

**Fallback Strategy:**
```typescript
// If SSE fails to connect, fall back to polling
if (!sseClient.connected.value) {
  console.warn('SSE not available, falling back to polling')
  // Use existing polling logic
}
```

---

#### 3.2 Global Sync Store
**Priority:** P2  
**Location:** `ui/src/stores/sync.ts` (create new)

**Implementation:**
```typescript
// ui/src/stores/sync.ts
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useSyncStore = defineStore('sync', () => {
  const lastUpdated = ref<Date | null>(null)
  const refreshingColumns = ref<Set<string>>(new Set())
  
  const isRefreshing = computed(() => refreshingColumns.value.size > 0)
  
  function startRefresh(columnName: string) {
    refreshingColumns.value.add(columnName)
  }
  
  function endRefresh(columnName: string) {
    refreshingColumns.value.delete(columnName)
    if (refreshingColumns.value.size === 0) {
      lastUpdated.value = new Date()
    }
  }
  
  function refreshAll() {
    // Emit event for all columns to refresh
    window.dispatchEvent(new CustomEvent('moirai:refresh-all'))
  }
  
  return {
    lastUpdated,
    isRefreshing,
    startRefresh,
    endRefresh,
    refreshAll,
  }
})
```

---

#### 3.3 Differential Updates
**Priority:** P3  
**Goal:** Only fetch changes since last update

**Implementation sketch:**
```python
# Backend
@app.route('/api/articles/changes')
def get_article_changes():
    since_timestamp = request.args.get('since')
    
    # Query only articles added/modified since timestamp
    selector = {
        "userspace": userspace,
        "updated_at": {"$gt": since_timestamp}
    }
    
    return jsonify({
        "added": [...],
        "modified": [...],
        "deleted": [...]
    })
```

---

### TIER 4: Polish & Optimization 💎

#### 4.1 CouchDB Memory Optimization
**Location:** `docker-compose.yml`

**Current:**
```yaml
couchdb:
  image: couchdb:3.3
  # No memory limits set
```

**Optimized:**
```yaml
couchdb:
  image: couchdb:3.3
  deploy:
    resources:
      limits:
        memory: 2G  # Increase from default
      reservations:
        memory: 1G
  environment:
    # Add CouchDB memory tuning
    - ERL_FLAGS=-setcookie monster +K true +A 16
```

**Add query limits:**
```python
# api/couchdb_utils.py
DEFAULT_QUERY_LIMIT = 100
MAX_QUERY_LIMIT = 500

def query_couchdb(db_name, selector, limit=DEFAULT_QUERY_LIMIT, **kwargs):
    # Enforce maximum
    limit = min(limit, MAX_QUERY_LIMIT)
    # ... rest of implementation ...
```

---

#### 4.2 Frontend Bundle Optimization
**Location:** `ui/vite.config.ts`

```typescript
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['vue', 'pinia', 'vue-router'],
          'utils': ['./src/utils/articleCache', './src/utils/authFetch'],
        },
      },
    },
  },
  optimizeDeps: {
    include: ['vue', 'pinia', 'vue-router'],
  },
})
```

---

## Testing Strategy

### Tier 1 Testing (Critical)

**1. Polling Synchronization Test**
```typescript
// Add temporary logging in all columns
console.log(`[${columnName}] Refresh triggered at ${Date.now()}`)

// Expected: All columns log within 500ms of each other
```

**2. Filter Refresh Test**
```
Steps:
1. Open dashboard
2. Select a feed filter
3. Add new article to that feed (via MCP/backend)
4. Wait 30 seconds
5. Verify: Article appears automatically (was broken before)
```

**3. Visual Indicator Test**
```
Steps:
1. Open dashboard
2. Verify "Updated X ago" shows at top
3. Wait for refresh cycle
4. Verify indicator changes to "Refreshing..."
5. Verify it returns to "Updated X ago" with new time
```

### Tier 2 Testing (Performance)

**1. Index Usage Verification**
```bash
# CouchDB Fauxton
# Run query with explain=true
curl -X POST http://admin:password@localhost:5984/articles/_explain \
  -H "Content-Type: application/json" \
  -d '{"selector": {"published": {"$gt": "2026-01-01"}}, "sort": [{"published": "desc"}]}'

# Expected: "index" field should reference our created index
```

**2. Response Time Test**
```bash
# Before optimization
time curl http://localhost/api/articles?limit=50

# After optimization
time curl http://localhost/api/articles?limit=50

# Expected: >2x improvement
```

**3. Cache Coordination Test**
```
Steps:
1. Load dashboard (populates IndexedDB)
2. Check IndexedDB version in localStorage
3. Restart backend (changes cache version)
4. Reload dashboard
5. Verify: IndexedDB cleared and repopulated
6. Check console for "Cache version mismatch" log
```

### Tier 3 Testing (SSE)

**1. SSE Connection Test**
```typescript
// Browser console
// Should show:
// "SSE: Connecting to /api/events/stream?userspace=..."
// "SSE: Connected"
```

**2. Real-time Update Test**
```
Steps:
1. Open dashboard in browser A
2. Add article via MCP in terminal
3. Verify: Article appears in browser A within 1 second (no polling!)
```

**3. Reconnection Test**
```
Steps:
1. Open dashboard (SSE connected)
2. Restart backend container
3. Verify: Dashboard shows "Reconnecting..." then reconnects automatically
4. Verify: Updates resume working
```

### Load Testing

```bash
# Install apache bench
sudo apt-get install apache2-utils

# Test concurrent requests
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
  http://localhost/api/articles

# Expected: <100ms average response time after optimizations
```

---

## Rollback Plan

### Quick Rollback (Tier 1)
If Tier 1 changes cause issues:

```bash
# Revert git commits
git revert HEAD~3  # Last 3 commits

# Or restore specific files
git checkout HEAD~3 -- ui/src/components/ArticleColumn.vue
git checkout HEAD~3 -- ui/src/components/EventColumn.vue
git checkout HEAD~3 -- ui/src/components/TrendColumn.vue

# Rebuild and redeploy
cd ui && yarn build
docker compose up -d --build
```

### Database Rollback (Tier 2)
Indexes are non-destructive - they only improve performance. If issues arise:

```python
# Drop indexes via CouchDB API
import requests

indexes_to_remove = ['idx_published', 'idx_userspace_published', ...]

for index_name in indexes_to_remove:
    requests.delete(f'http://admin:password@localhost:5984/articles/_index/{index_name}')
```

### SSE Rollback (Tier 3)
SSE is additive - old polling code remains as fallback:

```typescript
// ui/src/components/MainPage.vue

const USE_SSE = false  // ✅ Feature flag - set to false to disable SSE

if (USE_SSE && sseAvailable()) {
  // Use SSE
} else {
  // Fall back to polling (existing code)
}
```

---

## Performance Targets

### Current Performance (Baseline)
- Article fetch: ~500-1000ms (with enrichment)
- Column sync lag: Up to 90 seconds
- Update notification: Never (no indicator)
- Cache efficiency: Low (1 day stale tolerance)

### Post-Tier 1 Targets
- ✅ Column sync lag: 0 seconds (synchronized)
- ✅ Update notification: Visible within 1 second
- ✅ Filter refresh: Works correctly
- ✅ Perceived responsiveness: Significantly improved

### Post-Tier 2 Targets
- ✅ Article fetch: <200ms (indexed queries)
- ✅ Enrichment overhead: <50ms (cached lookups)
- ✅ Cache staleness: Max 1 hour (coordinated)
- ✅ CouchDB memory: Stable (no warnings)

### Post-Tier 3 Targets
- ✅ Update latency: <1 second (SSE push)
- ✅ Server load: 60% reduction (no polling)
- ✅ Concurrent users: 100+ (pub/sub scales)

---

## Migration Path

### Phase 1: Quick Wins (Week 1)
- Monday: Implement Tier 1.1-1.2 (polling fixes)
- Tuesday: Implement Tier 1.3-1.4 (indicators)
- Wednesday: Testing and bug fixes
- Thursday: Deploy to staging
- Friday: Deploy to production

### Phase 2: Performance (Week 2)
- Monday: Create indexes (Tier 2.1)
- Tuesday: Optimize enrichment (Tier 2.2)
- Wednesday: Cache coordination (Tier 2.3)
- Thursday: Response time logging + testing
- Friday: Deploy optimizations

### Phase 3: SSE (Week 3-4)
- Week 3: Implement SSE backend + frontend client
- Week 4: Testing, fallback logic, production deployment

---

## Monitoring & Metrics

### Key Metrics to Track

**Frontend (Browser DevTools):**
```typescript
// Add performance tracking
const metrics = {
  timeToFirstArticle: 0,  // Time from mount to first article rendered
  cacheHitRate: 0,         // IndexedDB hits / total fetches
  refreshCount: 0,         // Number of background refreshes
  errorRate: 0,            // Failed requests / total requests
}
```

**Backend (Logs):**
- Average response time per endpoint
- Slow query warnings (>500ms)
- Cache hit rate (Redis)
- Database query execution time

**CouchDB (Fauxton):**
- Memory usage trends
- Query execution statistics
- Index usage statistics

### Alert Thresholds
- Response time >1s: Warning
- Response time >3s: Critical
- Error rate >5%: Warning
- Error rate >10%: Critical
- CouchDB memory >80%: Warning

---

## Open Questions

1. **SSE vs WebSockets:** Should we consider WebSockets for bidirectional communication?
   - **Answer:** SSE is simpler and sufficient for one-way updates. WebSockets add complexity.

2. **Polling Interval:** 30 seconds vs 15 seconds vs 60 seconds?
   - **Recommendation:** 30 seconds balances freshness vs. server load.
   - **Future:** SSE eliminates this question entirely.

3. **Cache Strategy:** Should IndexedDB cache be cleared on every deployment?
   - **Recommendation:** Yes, use cache versioning to force refresh on backend changes.

4. **CouchDB Alternatives:** Should we consider migrating to PostgreSQL?
   - **Answer:** Not urgent. Indexes + optimization should resolve current issues.
   - **Future:** Consider for v2.0 if scaling issues persist.

---

## Success Criteria

### Tier 1 Success
- [ ] All columns refresh at same interval
- [ ] Articles refresh even with filters active
- [ ] "Last updated" indicator shows at top of dashboard
- [ ] No console errors
- [ ] User reports "feels much snappier"

### Tier 2 Success
- [ ] Article fetch time reduced by >50%
- [ ] CouchDB memory warnings eliminated
- [ ] Cache staleness reduced from 24h to 1h
- [ ] Response time headers show <200ms for /api/articles

### Tier 3 Success
- [ ] Updates appear in <1 second (no polling delay)
- [ ] SSE connection stable for >1 hour
- [ ] Fallback to polling works if SSE unavailable
- [ ] Server CPU usage reduced by >30%

---

## Appendix

### Related Files

**Frontend:**
- `ui/src/components/MainPage.vue` - Dashboard root
- `ui/src/components/ArticleColumn.vue` - Articles (polling bug)
- `ui/src/components/EventColumn.vue` - Events
- `ui/src/components/TrendColumn.vue` - Trends
- `ui/src/stores/filter.ts` - Cross-column state
- `ui/src/utils/articleCache.ts` - IndexedDB cache

**Backend:**
- `api/routes.py` - API endpoints
- `api/enrichment.py` - Article enrichment (slow)
- `api/extensions.py` - Redis client
- `api/couchdb_utils.py` - Database queries
- `tasks/article_processor.py` - Background ingestion

**Infrastructure:**
- `docker-compose.yml` - Service configuration
- `api/Dockerfile` - Backend container
- `ui/Dockerfile` - Frontend container

### Commands Reference

```bash
# Frontend development
cd ui
yarn dev                    # Start dev server
yarn build                  # Production build
yarn playwright test        # Run E2E tests

# Backend development
python main.py              # Start API server
PYTHONPATH=. pytest         # Run tests
PYTHONPATH=. pytest -v -k "test_articles"  # Specific test

# Docker operations
docker compose up -d        # Start services
docker compose logs -f api  # View API logs
docker compose restart api  # Restart API service
docker compose down         # Stop all services

# Database operations
curl http://admin:password@localhost:5984/_all_dbs  # List databases
curl http://localhost:5984/articles/_design/idx    # View indexes

# Cache operations
docker exec -it moirai-redis-1 redis-cli
> KEYS *                    # List all cache keys
> GET articles_default_json # View cached articles
> FLUSHDB                   # Clear cache (testing only!)
```

---

## Version History

- **v1.0** (2026-03-20): Initial analysis and improvement plan
- **v1.1** (TBD): Post-Tier 1 implementation notes
- **v1.2** (TBD): Post-Tier 2 performance results
- **v2.0** (TBD): SSE implementation complete

---

## Contact & Support

For questions about this improvement plan:
- Review the detailed exploration report in task session `ses_2f51ef3c0ffejzj367NHu5SWK0`
- Check implementation progress in git commit history
- Refer to `docs/RELEASE.md` for deployment procedures

**Implementation Status:** 🟡 READY FOR IMPLEMENTATION

---

*End of Document*
