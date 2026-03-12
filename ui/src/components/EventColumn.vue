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

const issues = ref<Issue[]>([])
const loading = ref(true)
const refreshing = ref(false)
const expandedIssues = ref<Set<string>>(new Set())
const searchQuery = ref('')
let refreshInterval: number | null = null

const authStore = useAuthStore()
const filterStore = useFilterStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

// Filtered issues based on search query
const filteredIssues = computed(() => {
  let filtered = issues.value

  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter((issue) => {
      const logos = issue.logos.toLowerCase()
      const description = issue.description.toLowerCase()
      return logos.includes(query) || description.includes(query)
    })
  }

  return filtered
})

const fetchIssues = async (isRefresh = false) => {
  if (isRefresh) {
    refreshing.value = true
  } else {
    loading.value = true
  }

  try {
    const params = new URLSearchParams()
    params.append('longevity', 'transient') // "Events" are transient issues
    
    if (filterStore.selectedFeedId) {
      params.append('feed_url', filterStore.selectedFeedId) // filter_id is currently the feed URL in some contexts, but check store usage
    }
    
    const queryString = params.toString() ? `?${params.toString()}` : ''
    const response = await authFetch(`/api/issues${queryString}`)

    if (response.ok) {
      const data = await response.json()
      issues.value = Array.isArray(data) ? data.filter((i: Issue) => !i._id.startsWith('_design/')) : []
    } else if (!isRefresh) {
      issues.value = []
    }
  } catch (error) {
    console.error('Error fetching transient issues:', error)
    if (!isRefresh) {
      issues.value = []
    }
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const selectIssue = (issueId: string) => {
  filterStore.setSelectedIssueId(filterStore.selectedIssueId === issueId ? null : issueId)
}

watch(
  () => filterStore.selectedFeedId,
  () => {
    fetchIssues()
  }
)

const deleteIssue = async (id: string) => {
  if (!confirm('Delete this event?')) return
  try {
    const res = await authFetch(`/api/issues/${id}`, { method: 'DELETE' })
    if (res.ok) {
      issues.value = issues.value.filter((i) => i._id !== id)
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
  if (!confirm('Remove this article from the event?')) return
  try {
    const res = await authFetch(`/api/issues/${issueId}/premises`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: premiseId }),
    })
    if (res.ok) {
      const updatedIssue = await res.json()
      const index = issues.value.findIndex((i) => i._id === issueId)
      if (index !== -1) {
        issues.value[index] = updatedIssue
      }
    }
  } catch (error) {
    console.error(error)
  }
}

const toggleExpand = (id: string) => {
  if (expandedIssues.value.has(id)) {
    expandedIssues.value.delete(id)
  } else {
    expandedIssues.value.add(id)
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
  <div class="event-column">
    <div class="column-header">
      <h2>
        Events ({{ filteredIssues.length }})
        <span v-if="refreshing" class="update-badge">↻</span>
      </h2>
      <button
        v-if="isAdmin"
        @click="() => fetchIssues(true)"
        :disabled="refreshing"
        class="action-btn"
        title="Refresh events"
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

    <!-- Search Input -->
    <div class="search-container">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search events by name..."
        class="search-input"
      />
      <button
        v-if="searchQuery"
        @click="searchQuery = ''"
        class="clear-search-btn"
        title="Clear search"
      >
        ×
      </button>
    </div>

    <div v-if="loading" class="loading-state">Loading events...</div>
    <div v-else-if="!filteredIssues.length" class="no-results">
      <span v-if="searchQuery">No events match "{{ searchQuery }}"</span>
      <span v-else>No events found yet.</span>
    </div>
    <div v-else class="event-list">
      <div
        v-for="issue in filteredIssues"
        :key="issue._id"
        class="event-card"
        @click="selectIssue(issue._id)"
        :class="{ 'selected-event': filterStore.selectedIssueId === issue._id }"
      >
        <div class="card-header">
          <h3 @click.stop="toggleExpand(issue._id)" class="clickable">{{ issue.logos }}</h3>
          <button
            v-if="isAdmin"
            @click="deleteIssue(issue._id)"
            class="delete-btn"
            title="Delete Event"
          >
            ×
          </button>
        </div>
        <p v-if="issue.description" class="summary">{{ issue.description }}</p>

        <IssueChatActions v-if="authStore.isAuthenticated" :issue="issue" />
        
        <div class="status-tags">
            <span :class="['status-tag', issue.status]">{{ issue.status }}</span>
        </div>

        <div v-if="expandedIssues.has(issue._id)" class="links-section">
          <h4>Constituents ({{ (issue.premises || []).length }})</h4>
          <ul>
            <li v-for="premise in issue.premises || []" :key="premise.id">
              <span class="premise-link">{{ premise.id }}</span>
              <button
                v-if="isAdmin"
                @click="removePremise(issue._id, premise.id)"
                class="remove-link-btn"
                title="Remove link"
              >
                -
              </button>
            </li>
          </ul>
        </div>
        <div v-else class="expand-hint" @click="toggleExpand(issue._id)">
          {{ (issue.premises || []).length }} items (click to expand)
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.event-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

h2 {
  color: #d83b01;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-state {
  text-align: center;
  padding: 20px;
  color: var(--text-color);
  opacity: 0.7;
}

.event-list {
  overflow-y: auto;
  flex: 1;
}

.event-card {
  border-bottom: 1px solid var(--border-color);
  padding: 15px 0;
  text-align: left;
  cursor: pointer;
  transition:
    background-color 0.2s,
    border-left 0.2s;
  border-left: 3px solid transparent;
}
.event-card:hover {
  background-color: #3a3a3a;
}
.event-card.selected-event {
  background-color: #5a2e00;
  border-left: 3px solid #d83b01;
}
.event-card.selected-event:hover {
  background-color: #6a3e00;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

.status-tags {
    display: flex;
    gap: 5px;
    margin-top: 5px;
}

.status-tag {
    font-size: 0.7rem;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
}

.status-tag.active {
    background: #28a745;
    color: white;
}

.status-tag.eternal {
    background: #6c757d;
    color: white;
}

.delete-btn {
  background: none;
  border: none;
  color: var(--text-color);
  opacity: 0.7;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0 5px;
}
.delete-btn:hover {
  color: #cc0000;
  opacity: 1;
}

.expand-hint {
  font-size: 0.8rem;
  color: var(--text-color);
  opacity: 0.85;
  cursor: pointer;
  margin-top: 10px;
}

.links-section {
  margin-top: 10px;
  border-top: 1px solid var(--border-color);
  padding-top: 5px;
}
.links-section h4 {
  font-size: 0.9rem;
  margin: 5px 0;
}
.links-section ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.links-section li {
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
}
.remove-link-btn:hover {
  background: #cc0000;
  color: white;
}
</style>
