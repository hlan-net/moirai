<script setup lang="ts">
import { onMounted, ref, computed, onUnmounted, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useFilterStore } from '../stores/filter'
import { authFetch } from '../utils/authFetch'
import IssueChatActions from './IssueChatActions.vue'

interface Premise {
  type: 'message' | 'issue'
  id: string
}

interface Issue {
  _id: string
  logos: string
  description: string
  premises: Premise[]
  longevity: 'transient' | 'temporal' | 'epic'
  status: 'active' | 'eternal'
}

type LongevityTier = 'transient' | 'temporal' | 'epic'

const allIssues = ref<Issue[]>([])
const loading = ref(true)
const refreshing = ref(false)
const expandedIssues = ref<Set<string>>(new Set())
const searchQuery = ref('')
const collapsedSections = ref<Set<string>>(new Set())
let refreshInterval: number | null = null

const authStore = useAuthStore()
const filterStore = useFilterStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

const tierLabels: Record<LongevityTier, { label: string; color: string }> = {
  transient: { label: 'Events', color: '#d83b01' },
  temporal: { label: 'Trends', color: '#6a0dad' },
  epic: { label: 'Epics', color: '#0078d4' },
}

const tierOrder: LongevityTier[] = ['transient', 'temporal', 'epic']

// Filter issues by search query
const filtered = computed(() => {
  let items = allIssues.value
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    items = items.filter(
      (i) => i.logos.toLowerCase().includes(q) || i.description.toLowerCase().includes(q),
    )
  }
  return items
})

// Active issues grouped by longevity tier
const activeTiers = computed(() => {
  const active = filtered.value.filter((i) => i.status === 'active')
  return tierOrder.map((tier) => ({
    tier,
    ...tierLabels[tier],
    issues: active.filter((i) => i.longevity === tier),
  }))
})

// Sealed (eternal) issues — "Things that WERE"
const eternalIssues = computed(() => filtered.value.filter((i) => i.status === 'eternal'))

// Summary counts
const activeCount = computed(() => filtered.value.filter((i) => i.status === 'active').length)
const eternalCount = computed(() => eternalIssues.value.length)

const fetchIssues = async (isRefresh = false) => {
  if (isRefresh) {
    refreshing.value = true
  } else {
    loading.value = true
  }

  try {
    const params = new URLSearchParams()
    if (filterStore.selectedFeedId) {
      params.append('feed_url', filterStore.selectedFeedId)
    }
    const qs = params.toString() ? `?${params.toString()}` : ''
    const response = await authFetch(`/api/issues${qs}`)

    if (response.ok) {
      const data = await response.json()
      allIssues.value = Array.isArray(data)
        ? data.filter((i: Issue) => !i._id.startsWith('_design/'))
        : []
    } else if (!isRefresh) {
      allIssues.value = []
    }
  } catch (error) {
    console.error('Error fetching issues:', error)
    if (!isRefresh) {
      allIssues.value = []
    }
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

watch(
  () => filterStore.selectedFeedId,
  () => fetchIssues(),
)

const selectIssue = (issueId: string) => {
  filterStore.setSelectedIssueId(filterStore.selectedIssueId === issueId ? null : issueId)
}

const toggleExpand = (id: string) => {
  if (expandedIssues.value.has(id)) {
    expandedIssues.value.delete(id)
  } else {
    expandedIssues.value.add(id)
  }
}

const toggleSection = (key: string) => {
  if (collapsedSections.value.has(key)) {
    collapsedSections.value.delete(key)
  } else {
    collapsedSections.value.add(key)
  }
}

const deleteIssue = async (id: string) => {
  if (!confirm('Delete this issue?')) return
  try {
    const res = await authFetch(`/api/issues/${id}`, { method: 'DELETE' })
    if (res.ok) {
      allIssues.value = allIssues.value.filter((i) => i._id !== id)
      expandedIssues.value.delete(id)
      if (filterStore.selectedIssueId === id) {
        filterStore.setSelectedIssueId(null)
      }
    }
  } catch (error) {
    console.error(error)
  }
}

const removePremise = async (issueId: string, premiseId: string) => {
  if (!confirm('Remove this constituent?')) return
  try {
    const res = await authFetch(`/api/issues/${issueId}/premises`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: premiseId }),
    })
    if (res.ok) {
      const updatedIssue = await res.json()
      const index = allIssues.value.findIndex((i) => i._id === issueId)
      if (index !== -1) {
        allIssues.value[index] = updatedIssue
      }
    }
  } catch (error) {
    console.error(error)
  }
}

onMounted(() => {
  fetchIssues()
  refreshInterval = globalThis.setInterval(() => fetchIssues(true), 30000)
})

onUnmounted(() => {
  if (refreshInterval !== null) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="lifespan-view">
    <div class="column-header">
      <h2>
        Lifespan
        <span class="count-summary">{{ activeCount }} active / {{ eternalCount }} sealed</span>
        <span v-if="refreshing" class="update-badge">&#8635;</span>
      </h2>
      <button
        v-if="isAdmin"
        @click="() => fetchIssues(true)"
        :disabled="refreshing"
        class="action-btn"
        title="Refresh issues"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="currentColor"
          :class="{ spinning: refreshing }"
        >
          <path
            d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14 .69 4.22 1.78L13 11h7V4l-2.35 2.35z"
          />
        </svg>
      </button>
    </div>

    <!-- Search -->
    <div class="search-container">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search issues by name..."
        class="search-input"
      />
      <button
        v-if="searchQuery"
        @click="searchQuery = ''"
        class="clear-search-btn"
        title="Clear search"
      >
        &times;
      </button>
    </div>

    <div v-if="loading" class="loading-state">Loading issues...</div>

    <div v-else class="lifespan-content">
      <!-- Active section: issues grouped by longevity tier -->
      <section
        v-for="group in activeTiers"
        :key="group.tier"
        class="tier-section"
      >
        <div
          class="tier-header"
          @click="toggleSection(group.tier)"
          :style="{ borderLeftColor: group.color }"
        >
          <span class="tier-label" :style="{ color: group.color }">
            {{ group.label }} ({{ group.issues.length }})
          </span>
          <span class="collapse-icon">{{ collapsedSections.has(group.tier) ? '+' : '-' }}</span>
        </div>

        <div v-if="!collapsedSections.has(group.tier)" class="tier-list">
          <div v-if="!group.issues.length" class="no-results">
            <span v-if="searchQuery">No matches</span>
            <span v-else>None</span>
          </div>

          <div
            v-for="issue in group.issues"
            :key="issue._id"
            class="issue-card"
            :class="{ 'selected-issue': filterStore.selectedIssueId === issue._id }"
            :style="{ '--accent': group.color }"
            @click="selectIssue(issue._id)"
          >
            <div class="card-header">
              <h3 @click.stop="toggleExpand(issue._id)" class="clickable">{{ issue.logos }}</h3>
              <button
                v-if="isAdmin"
                @click.stop="deleteIssue(issue._id)"
                class="delete-btn"
                title="Delete issue"
              >
                &times;
              </button>
            </div>
            <p v-if="issue.description" class="summary">{{ issue.description }}</p>

            <IssueChatActions v-if="authStore.isAuthenticated" :issue="issue" />

            <div v-if="expandedIssues.has(issue._id)" class="premises-section">
              <h4>Constituents ({{ (issue.premises || []).length }})</h4>
              <ul>
                <li v-for="premise in issue.premises || []" :key="premise.id">
                  <span class="premise-link">{{ premise.id }}</span>
                  <button
                    v-if="isAdmin"
                    @click.stop="removePremise(issue._id, premise.id)"
                    class="remove-link-btn"
                    title="Remove constituent"
                  >
                    -
                  </button>
                </li>
              </ul>
            </div>
            <div v-else class="expand-hint" @click.stop="toggleExpand(issue._id)">
              {{ (issue.premises || []).length }} items (click to expand)
            </div>
          </div>
        </div>
      </section>

      <!-- Eternal section: sealed issues -->
      <section class="tier-section eternal-section">
        <div
          class="tier-header"
          @click="toggleSection('eternal')"
          :style="{ borderLeftColor: '#6c757d' }"
        >
          <span class="tier-label" style="color: #6c757d">
            Sealed ({{ eternalIssues.length }})
          </span>
          <span class="collapse-icon">{{ collapsedSections.has('eternal') ? '+' : '-' }}</span>
        </div>

        <div v-if="!collapsedSections.has('eternal')" class="tier-list">
          <div v-if="!eternalIssues.length" class="no-results">
            <span v-if="searchQuery">No matches</span>
            <span v-else>No sealed issues</span>
          </div>

          <div
            v-for="issue in eternalIssues"
            :key="issue._id"
            class="issue-card sealed-card"
            :class="{ 'selected-issue': filterStore.selectedIssueId === issue._id }"
            @click="selectIssue(issue._id)"
          >
            <div class="card-header">
              <h3 @click.stop="toggleExpand(issue._id)" class="clickable">{{ issue.logos }}</h3>
              <div class="card-meta">
                <span :class="['longevity-tag', issue.longevity]">{{ issue.longevity }}</span>
                <button
                  v-if="isAdmin"
                  @click.stop="deleteIssue(issue._id)"
                  class="delete-btn"
                  title="Delete issue"
                >
                  &times;
                </button>
              </div>
            </div>
            <p v-if="issue.description" class="summary">{{ issue.description }}</p>

            <IssueChatActions v-if="authStore.isAuthenticated" :issue="issue" />

            <div v-if="expandedIssues.has(issue._id)" class="premises-section">
              <h4>Constituents ({{ (issue.premises || []).length }})</h4>
              <ul>
                <li v-for="premise in issue.premises || []" :key="premise.id">
                  <span class="premise-link">{{ premise.id }}</span>
                  <button
                    v-if="isAdmin"
                    @click.stop="removePremise(issue._id, premise.id)"
                    class="remove-link-btn"
                    title="Remove constituent"
                  >
                    -
                  </button>
                </li>
              </ul>
            </div>
            <div v-else class="expand-hint" @click.stop="toggleExpand(issue._id)">
              {{ (issue.premises || []).length }} items (click to expand)
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.lifespan-view {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

h2 {
  color: var(--text-color);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.count-summary {
  font-size: 0.85rem;
  font-weight: 400;
  opacity: 0.6;
}

.loading-state {
  text-align: center;
  padding: 20px;
  color: var(--text-color);
  opacity: 0.7;
}

.lifespan-content {
  overflow-y: auto;
  flex: 1;
}

/* Tier sections */
.tier-section {
  margin-bottom: 1.5rem;
}

.tier-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-left: 4px solid;
  background: var(--card-bg);
  border-radius: 0 4px 4px 0;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.tier-header:hover {
  background: #3a3a3a;
}

:root.light-theme .tier-header:hover {
  background: #e8e8e8;
}

.tier-label {
  font-weight: 700;
  font-size: 1rem;
}

.collapse-icon {
  font-size: 1.2rem;
  color: var(--text-color);
  opacity: 0.5;
  font-weight: bold;
  width: 20px;
  text-align: center;
}

.tier-list {
  padding-left: 16px;
}

/* Issue cards */
.issue-card {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 0;
  text-align: left;
  cursor: pointer;
  transition:
    background-color 0.2s,
    border-left 0.2s;
  border-left: 3px solid transparent;
}

.issue-card:hover {
  background-color: #3a3a3a;
}

:root.light-theme .issue-card:hover {
  background-color: #efefef;
}

.issue-card.selected-issue {
  background-color: rgba(98, 0, 238, 0.15);
  border-left: 3px solid var(--accent, var(--primary-color));
}

.issue-card.selected-issue:hover {
  background-color: rgba(98, 0, 238, 0.25);
}

.sealed-card {
  opacity: 0.75;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.clickable {
  cursor: pointer;
}

.clickable:hover {
  text-decoration: underline;
}

h3 {
  margin: 0 0 5px 0;
  font-size: 1.1rem;
  color: var(--text-color);
}

.summary {
  font-size: 0.9rem;
  color: var(--text-color);
  opacity: 0.9;
  line-height: 1.4;
  margin: 5px 0;
}

.longevity-tag {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
  font-weight: 600;
}

.longevity-tag.transient {
  background: #d83b01;
  color: white;
}

.longevity-tag.temporal {
  background: #6a0dad;
  color: white;
}

.longevity-tag.epic {
  background: #0078d4;
  color: white;
}

.delete-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0 5px;
  box-shadow: none;
}

.delete-btn:hover {
  color: #cc0000;
}

.expand-hint {
  font-size: 0.8rem;
  color: var(--text-color);
  opacity: 0.5;
  cursor: pointer;
  margin-top: 10px;
}

.premises-section {
  margin-top: 10px;
  border-top: 1px solid var(--border-color);
  padding-top: 5px;
}

.premises-section h4 {
  font-size: 0.9rem;
  margin: 5px 0;
}

.premises-section ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.premises-section li {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  margin-bottom: 3px;
  align-items: center;
}

.premise-link {
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
  color: var(--primary-color);
  flex: 1;
}

.remove-link-btn {
  border: none;
  background: var(--bg-color);
  color: var(--text-color);
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
  line-height: 1;
  margin-left: 10px;
  box-shadow: none;
}

.remove-link-btn:hover {
  background: #cc0000;
  color: white;
}

/* Mobile adjustments */
@media (max-width: 767px) {
  .lifespan-view {
    padding: 10px;
  }

  .tier-list {
    padding-left: 8px;
  }
}
</style>
