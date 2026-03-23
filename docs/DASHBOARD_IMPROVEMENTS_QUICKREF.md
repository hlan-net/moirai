# Dashboard UX Improvements - Quick Reference

**For:** AI agents and developers implementing the improvements  
**Full Details:** See `DASHBOARD_UX_IMPROVEMENTS.md`

## 🎯 Priority Order

### 1. CRITICAL FIXES (Do First)
These fix the "erratic" behavior immediately:

#### Fix 1: Conditional Polling Bug
**File:** `ui/src/components/ArticleColumn.vue:335-342`

```typescript
// BEFORE (BROKEN):
refreshInterval = globalThis.setInterval(() => {
  if (!filterStore.selectedFeedId && !filterStore.selectedIssueId) {
    fetchLatestUpdates()
  }
}, 120000)

// AFTER (FIXED):
const SYNC_REFRESH_INTERVAL = 30000
refreshInterval = globalThis.setInterval(() => {
  fetchLatestUpdates() // Remove condition!
}, SYNC_REFRESH_INTERVAL)
```

#### Fix 2: Sync All Polling Intervals
**Files:** `ArticleColumn.vue`, `EventColumn.vue`, `TrendColumn.vue`

Create `ui/src/config/polling.ts`:
```typescript
export const SYNC_REFRESH_INTERVAL = 30000 // 30 seconds
```

Update all three files to import and use this constant.

#### Fix 3: Add "Last Updated" Indicator
**File:** `ui/src/components/MainPage.vue`

Add to top of dashboard:
```vue
<div class="dashboard-status">
  <div v-if="filterStore.isRefreshing">
    Refreshing data...
  </div>
  <div v-else-if="filterStore.lastUpdated">
    Updated {{ formatTimeAgo(filterStore.lastUpdated) }}
  </div>
</div>
```

### 2. PERFORMANCE FIXES (Do Second)

#### Index 1: Create CouchDB Indexes
**Command:**
```bash
python -c "from api.db_indexes import initialize_all_indexes; initialize_all_indexes()"
```

Create `api/db_indexes.py` with indexes for:
- articles: `published`, `userspace`, `feed_url`
- issues: `longevity`, `userspace`, `feed_urls`

#### Index 2: Optimize Article Enrichment
**File:** `api/enrichment.py`

Replace O(n*m) loop with cached Redis lookup:
```python
def get_cached_issues_by_feed() -> Dict[str, List[str]]:
    # Check Redis cache first
    # Build feed_url -> [issue_ids] mapping
    # Cache for 5 minutes
```

#### Index 3: Cache Coordination
Add version header to API responses:
```python
response_data = {
    "articles": articles,
    "cache_version": CACHE_VERSION,
}
```

Frontend checks version and clears IndexedDB if mismatched.

### 3. OPTIONAL UPGRADES (Do Third)

#### Server-Sent Events (SSE)
- Eliminates polling entirely
- Real-time updates in <1 second
- See Tier 3 in full doc

---

## 🔧 Testing Checklist

After implementing fixes:

- [ ] All columns refresh at same time (30s interval)
- [ ] Articles refresh even with filter selected
- [ ] "Last updated" indicator shows and updates
- [ ] Article fetch time <200ms (check Network tab)
- [ ] No CouchDB memory warnings in logs
- [ ] IndexedDB cleared on backend restart

---

## 📊 Expected Results

### Before Fixes
- Columns update 30s-120s apart ❌
- Articles stop refreshing when filtered ❌
- No update indicator ❌
- 500-1000ms article fetch ❌

### After Tier 1+2
- All columns sync every 30s ✅
- Articles always refresh ✅
- Clear "Last updated" indicator ✅
- <200ms article fetch ✅
- 50x improvement in enrichment ✅

---

## 🚨 Rollback

If issues occur:
```bash
git revert HEAD~N  # N = number of commits to undo
cd ui && yarn build
docker compose up -d --build
```

---

## 📁 Key Files

**Must Touch:**
1. `ui/src/components/ArticleColumn.vue` - Fix polling bug
2. `ui/src/components/EventColumn.vue` - Sync interval
3. `ui/src/components/TrendColumn.vue` - Sync interval
4. `ui/src/components/MainPage.vue` - Add indicator
5. `ui/src/stores/filter.ts` - Add lastUpdated state
6. `api/enrichment.py` - Optimize algorithm
7. `api/db_indexes.py` - Create indexes (new file)

**May Touch:**
- `ui/src/config/polling.ts` - Shared constants (new file)
- `api/routes.py` - Add cache version header
- `ui/src/utils/articleCache.ts` - Version checking

---

## 🎬 Implementation Order

```
1. Create polling.ts with SYNC_REFRESH_INTERVAL constant
2. Fix ArticleColumn polling bug (remove condition)
3. Update all columns to use SYNC_REFRESH_INTERVAL
4. Add lastUpdated to filter store
5. Add dashboard status indicator to MainPage
6. Test Tier 1 changes ← VALIDATE BEFORE CONTINUING
7. Create db_indexes.py and run initialization
8. Optimize enrichment.py with Redis caching
9. Add cache versioning to API + frontend
10. Test Tier 2 changes
```

**Estimated Time:**
- Tier 1: 30-60 minutes
- Tier 2: 2-3 hours
- Total: Half day for dramatic UX improvement

---

## 💡 Pro Tips

1. **Test After Each Tier** - Don't proceed to Tier 2 until Tier 1 is validated
2. **Watch Logs** - `docker compose logs -f api` shows timing and errors
3. **Use Browser DevTools** - Network tab shows request timing
4. **Check Redis** - `docker exec -it moirai-redis-1 redis-cli` to inspect cache
5. **Verify Indexes** - CouchDB Fauxton at `http://localhost:5984/_utils`

---

**Status:** 🟢 READY TO IMPLEMENT  
**Last Updated:** 2026-03-20  
**Full Documentation:** `docs/DASHBOARD_UX_IMPROVEMENTS.md`
