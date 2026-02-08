<script setup lang="ts">
import { onMounted, ref, computed, inject, onUnmounted, watch, type Ref } from 'vue'
import { useAuthStore } from '../stores/auth'

interface Event {
  _id: string
  name: string
  description: string
  article_links: string[]
  trend_id?: string
}

interface Trend {
  _id?: string
  name?: string
  title?: string
  description?: string
}

const events = ref<Event[]>([])
const trends = ref<Trend[]>([])
const loading = ref(true)
const refreshing = ref(false)
const expandedEvents = ref<Set<string>>(new Set())
const searchQuery = ref('')
let refreshInterval: number | null = null

// Inject selected feed from parent
const selectedFeedUrl = inject<Ref<string | null>>('selectedFeedUrl', ref(null))

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

const normalizeEvent = (event: any): Event => ({
  _id: event._id,
  name: event.name || event.title || 'Unnamed Event',
  description: event.description || '',
  article_links: Array.isArray(event.article_links) ? event.article_links : [],
  trend_id: event.trend_id,
})

// Computed: Filtered events based on search query
const filteredEvents = computed(() => {
  let filtered = events.value
  
  // Filter by search query
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(event => {
      const name = event.name.toLowerCase()
      const description = event.description.toLowerCase()
      return name.includes(query) || description.includes(query)
    })
  }
  
  return filtered
})

const processEventsResponse = async (response: Response, isRefresh: boolean) => {
  if (response.ok) {
    const eventsData = await response.json()
    const allEvents = Array.isArray(eventsData) ? eventsData.map(normalizeEvent) : []
    events.value = allEvents.filter(e => !e._id.startsWith('_design/'))
    return
  }
  
  if (!isRefresh) {
    events.value = []
  }
}

const processTrendsResponse = async (response: Response, isRefresh: boolean) => {
  if (response.ok) {
    try {
      const trendsData = await response.json()
      trends.value = Array.isArray(trendsData) ? trendsData : []
      return
    } catch (e) {
      console.error('Error parsing trends:', e)
    }
  }
  
  if (!isRefresh) {
    trends.value = []
  }
}

const fetchEventsAndTrends = async (isRefresh = false) => {
  if (isRefresh) {
    refreshing.value = true
  } else {
    loading.value = true
  }
  
  try {
    const params = new URLSearchParams()
    if (selectedFeedUrl.value) {
      params.append('feed_url', selectedFeedUrl.value)
    }
    const queryString = params.toString() ? `?${params.toString()}` : ''

    const [eventsResponse, trendsResponse] = await Promise.all([
      fetch(`/api/events${queryString}`),
      fetch(`/api/trends${queryString}`),
    ])

    await Promise.all([
      processEventsResponse(eventsResponse, isRefresh),
      processTrendsResponse(trendsResponse, isRefresh)
    ])
  } catch (error) {
    console.error('Error fetching events or trends:', error)
    // Only clear events if we failed to fetch them and it's not a refresh
    if (!isRefresh) {
      events.value = []
      trends.value = []
    }
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

// Watch for feed selection changes to refresh data
watch(selectedFeedUrl, () => {
  fetchEventsAndTrends()
})

const deleteEvent = async (id: string) => {
  if (!confirm('Delete this event?')) return
  try {
    const res = await fetch(`/api/events/${id}`, { method: 'DELETE' })
    if (res.ok) {
      events.value = events.value.filter(e => e._id !== id)
      expandedEvents.value.delete(id)
    }
  } catch (error) {
    console.error(error)
  }
}

const removeLink = async (eventId: string, link: string) => {
  if (!confirm('Remove this article from the event?')) return
  try {
    const res = await fetch(`/api/events/${eventId}/links`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ link }),
    })
    if (res.ok) {
      const updatedEvent = normalizeEvent(await res.json())
      const index = events.value.findIndex(e => e._id === eventId)
      if (index !== -1) {
        events.value[index] = updatedEvent
      }
    }
  } catch (error) {
    console.error(error)
  }
}

const toggleExpand = (id: string) => {
  if (expandedEvents.value.has(id)) {
    expandedEvents.value.delete(id)
  } else {
    expandedEvents.value.add(id)
  }
}

const getTrendDisplayName = (trendId?: string) => {
  if (!trendId) {
    return ''
  }
  const trend = trends.value.find(t => t._id === trendId)
  return trend?.name || trend?.title || trendId
}

onMounted(() => {
  fetchEventsAndTrends()
  // Refresh every 30 seconds
  refreshInterval = globalThis.setInterval(() => fetchEventsAndTrends(true), 30000)
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
        Events ({{ filteredEvents.length }})
        <span v-if="refreshing" class="update-badge">↻</span>
      </h2>
      <button v-if="isAdmin" 
        @click="() => fetchEventsAndTrends(true)" 
        :disabled="refreshing"
        class="action-btn"
        title="Refresh events"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" :class="{ 'spinning': refreshing }">
          <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14 .69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
        </svg>
      </button>
    </div>

    <!-- Search Input -->
    <div class="search-container">
      <input 
        v-model="searchQuery" 
        type="text" 
        placeholder="Search events by name or description..." 
        class="search-input"
      />
      <button v-if="searchQuery" @click="searchQuery = ''" class="clear-search-btn" title="Clear search">
        ×
      </button>
    </div>

    <div v-if="loading" class="loading-state">Loading events...</div>
    <div v-else-if="!filteredEvents.length" class="no-results">
      <span v-if="searchQuery">No events match "{{ searchQuery }}"</span>
      <span v-else>No events found yet.</span>
    </div>
    <div v-else class="event-list">
      <div v-for="event in filteredEvents" :key="event._id" class="event-card">
        <div class="card-header">
          <h3 @click="toggleExpand(event._id)" class="clickable">{{ event.name }}</h3>
          <button v-if="isAdmin" @click="deleteEvent(event._id)" class="delete-btn" title="Delete Event">×</button>
        </div>
        <p v-if="event.description" class="summary">{{ event.description }}</p>
        <div v-if="event.trend_id" class="trend-link">
          <span class="trend-label">Related Trend:</span>
          <span class="trend-name">{{ getTrendDisplayName(event.trend_id) }}</span>
        </div>

        <div v-if="expandedEvents.has(event._id)" class="links-section">
          <h4>Linked Articles ({{ (event.article_links || []).length }})</h4>
          <ul>
            <li v-for="link in (event.article_links || [])" :key="link">
              <a :href="link" target="_blank" rel="noopener noreferrer">{{ link }}</a>
              <button
                v-if="isAdmin"
                @click="removeLink(event._id, link)"
                class="remove-link-btn"
                title="Remove link"
              >
                -
              </button>
            </li>
          </ul>
        </div>
        <div v-else class="expand-hint" @click="toggleExpand(event._id)">
          {{ (event.article_links || []).length }} articles (click to expand)
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

.trend-link {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
  font-size: 0.9em;
}
.trend-label {
  color: var(--text-color);
  opacity: 0.6;
  margin-right: 5px;
}
.trend-name {
  color: #ff6b6b;
  font-weight: 500;
}

.delete-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0 5px;
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
}
.links-section a {
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
  color: var(--primary-color);
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
}
.remove-link-btn:hover {
  background: #cc0000;
  color: white;
}
</style>