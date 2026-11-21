<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useFilterStore } from '../stores/filter'
import { authFetch } from '../utils/authFetch'
import IssueChatActions from './IssueChatActions.vue'
import { SYNC_REFRESH_INTERVAL } from '../config/polling'
import { useIssueList, type Issue } from '../composables/useIssueList'

const authStore = useAuthStore()
const filterStore = useFilterStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

// "Events" are transient issues
const {
  loading,
  refreshing,
  expandedIssues,
  searchQuery,
  filteredIssues,
  fetchIssues,
  selectIssue,
  replaceIssue,
  deleteIssue,
  removePremise,
  toggleExpand,
} = useIssueList({
  longevity: 'transient',
  refreshMs: SYNC_REFRESH_INTERVAL,
  trackRefresh: true,
  text: {
    fetchError: 'Error fetching transient issues:',
    confirmDelete: 'Delete this event?',
    confirmRemovePremise: 'Remove this article from the event?',
  },
})

const togglePublic = async (issue: Issue) => {
  try {
    const res = await authFetch(`/api/issues/${issue._id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ public: !issue.public }),
    })
    if (res.ok) {
      replaceIssue(await res.json())
    }
  } catch (error) {
    console.error(error)
  }
}
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
            d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"
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
          <div v-if="isAdmin" class="card-actions">
            <button
              @click.stop="togglePublic(issue)"
              class="public-btn"
              :class="{ 'is-public': issue.public }"
              :title="
                issue.public ? 'Public — click to make private' : 'Private — click to make public'
              "
            >
              {{ issue.public ? '🌐' : '🔒' }}
            </button>
            <button @click.stop="deleteIssue(issue._id)" class="delete-btn" title="Delete Event">
              ×
            </button>
          </div>
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

.card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.public-btn {
  background: none;
  border: none;
  font-size: 1rem;
  cursor: pointer;
  padding: 0 4px;
  opacity: 0.5;
  line-height: 1;
}
.public-btn:hover {
  opacity: 1;
}
.public-btn.is-public {
  opacity: 1;
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
