<script setup lang="ts">
import { onMounted, ref, computed, inject, onUnmounted, type Ref } from 'vue'

interface Trend {
  _id: string
  name: string
  description: string
  event_ids: string[]
}

const trends = ref<Trend[]>([])
const loading = ref(true)
const refreshing = ref(false)
const expandedTrends = ref<Set<string>>(new Set())
const searchQuery = ref('')
const events = ref<any[]>([]) // To check which events link to selected feed's articles
const articles = ref<any[]>([]) // To check article origins
let refreshInterval: number | null = null

// Inject selected feed from parent
const selectedFeedUrl = inject<Ref<string | null>>('selectedFeedUrl', ref(null))

// Computed: Filtered trends based on search query and selected feed
const filteredTrends = computed(() => {
  let filtered = trends.value
  
  // Filter by selected feed - show only trends with events that have articles from that feed
  if (selectedFeedUrl.value) {
    const feedArticles = articles.value.filter(a => a.feed_url === selectedFeedUrl.value)
    const feedArticleLinks = new Set(feedArticles.map(a => a.link))
    
    const relevantEventIds = new Set(
      events.value
        .filter(event => event.article_links?.some((link: string) => feedArticleLinks.has(link)))
        .map(event => event._id)
    )
    
    filtered = filtered.filter(trend => 
      (trend.event_ids || []).some(eventId => relevantEventIds.has(eventId))
    )
  }
  
  // Filter by search query
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(trend => {
      const name = trend.name.toLowerCase()
      const description = trend.description.toLowerCase()
      return name.includes(query) || description.includes(query)
    })
  }
  
  return filtered
})

const fetchTrends = async (isRefresh = false) => {
  if (isRefresh) {
    refreshing.value = true
  } else {
    loading.value = true
  }
  
  try {
    const [trendsResponse, eventsResponse, articlesResponse] = await Promise.all([
      fetch('/api/trends'),
      fetch('/api/events'),
      fetch('/api/articles?limit=10000'),
    ])

    if (trendsResponse.ok) {
      const data = await trendsResponse.json()
      console.log('Trends API response:', data)
      const allTrends = Array.isArray(data) ? data : []
      trends.value = allTrends.filter((t: Trend) => !t._id.startsWith('_design/'))
    }
    
    if (eventsResponse.ok) {
      try {
        events.value = await eventsResponse.json()
      } catch (e) {
        console.error('Error parsing events:', e)
      }
    }
    
    if (articlesResponse.ok) {
      try {
        const data = await articlesResponse.json()
        articles.value = data.articles || []
      } catch (e) {
        console.error('Error parsing articles:', e)
      }
    }
  } catch (error) {
    console.error('Error fetching data:', error)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const deleteTrend = async (id: string) => {
  if (!confirm('Delete this trend?')) return
  try {
    const res = await fetch(`/api/trends/${id}`, { method: 'DELETE' })
    if (res.ok) {
      trends.value = trends.value.filter(t => t._id !== id)
      expandedTrends.value.delete(id)
    }
  } catch (error) {
    console.error(error)
  }
}

const removeEvent = async (trendId: string, eventId: string) => {
  if (!confirm('Remove this event from the trend?')) return
  try {
    const res = await fetch(`/api/trends/${trendId}/events`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_id: eventId }),
    })
    if (res.ok) {
      const updatedTrend = await res.json()
      const index = trends.value.findIndex(t => t._id === trendId)
      if (index !== -1) {
        trends.value[index] = updatedTrend
      }
    }
  } catch (error) {
    console.error(error)
  }
}

const toggleExpand = (id: string) => {
  if (expandedTrends.value.has(id)) {
    expandedTrends.value.delete(id)
  } else {
    expandedTrends.value.add(id)
  }
}

onMounted(() => {
  fetchTrends()
  // Refresh every 30 seconds
  refreshInterval = window.setInterval(() => fetchTrends(true), 30000)
})

onUnmounted(() => {
  if (refreshInterval !== null) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="trend-column">
    <div class="column-header">
      <h2>
        Trends ({{ filteredTrends.length }})
        <span v-if="refreshing" class="update-badge">↻</span>
      </h2>
      <button 
        @click="() => fetchTrends(true)" 
        :disabled="refreshing"
        class="action-btn"
        title="Refresh trends"
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
        placeholder="Search trends by name or description..." 
        class="search-input"
      />
      <button v-if="searchQuery" @click="searchQuery = ''" class="clear-search-btn" title="Clear search">
        ×
      </button>
    </div>

    <div v-if="loading" class="loading-state">Loading trends...</div>
    <div v-else-if="!filteredTrends.length" class="no-results">
      <span v-if="searchQuery">No trends match "{{ searchQuery }}"</span>
      <span v-else>No trends found yet.</span>
    </div>
    <div v-else class="trend-list">
      <div v-for="trend in filteredTrends" :key="trend._id" class="trend-card">
        <div class="card-header">
          <h3 @click="toggleExpand(trend._id)" class="clickable">{{ trend.name }}</h3>
          <button @click="deleteTrend(trend._id)" class="delete-btn" title="Delete Trend">×</button>
        </div>
        <p class="summary">{{ trend.description }}</p>

        <div v-if="expandedTrends.has(trend._id)" class="events-section">
          <h4>Linked Events ({{ (trend.event_ids || []).length }})</h4>
          <ul>
            <li v-for="eid in (trend.event_ids || [])" :key="eid">
              <span class="event-id">{{ eid.substring(0, 8) }}...</span>
              <button
                @click="removeEvent(trend._id, eid)"
                class="remove-event-btn"
                title="Remove event"
              >
                -
              </button>
            </li>
          </ul>
        </div>
        <div v-else class="expand-hint" @click="toggleExpand(trend._id)">
          {{ (trend.event_ids || []).length }} events (click to expand)
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-container {
  position: relative;
  margin: 0.75rem 0;
}

.search-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.6rem 2.5rem 0.6rem 0.75rem;
  border: 1px solid #444;
  border-radius: 4px;
  background: #2a2a2a;
  color: #e0e0e0;
  font-size: 0.9rem;
  transition: border-color 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: #007bff;
}

.search-input::placeholder {
  color: #888;
}

.clear-search-btn {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0 0.5rem;
  line-height: 1;
  transition: color 0.2s;
}

.clear-search-btn:hover {
  color: #e0e0e0;
}

.no-results {
  padding: 2rem 1rem;
  text-align: center;
  color: #888;
  font-style: italic;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #444;
  padding-bottom: 10px;
  margin-bottom: 10px;
  margin-top: 0;
}

.trend-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

h2 {
  color: #6a0dad;
  margin-top: 0;
  position: sticky;
  top: 0;
  background: transparent;
  padding: 10px 0;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.update-badge {
  font-size: 0.9rem;
  color: #666;
  animation: spin 1s linear infinite;
  margin-left: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border: 1px solid #444;
  border-radius: 4px;
  background: transparent;
  color: #e0e0e0;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: rgba(0, 123, 255, 0.1);
  border-color: #007bff;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn svg.spinning {
  animation: spin-action 1s linear infinite;
}

@keyframes spin-action {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.loading-state {
  text-align: center;
  padding: 20px;
  color: var(--text-color);
  opacity: 0.7;
}

.trend-list {
  overflow-y: auto;
  flex: 1;
}

.trend-card {
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

.events-section {
  margin-top: 10px;
  border-top: 1px solid var(--border-color);
  padding-top: 5px;
}
.events-section h4 {
  font-size: 0.9rem;
  margin: 5px 0;
}
.events-section ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.events-section li {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  margin-bottom: 3px;
  align-items: center;
}
.event-id {
  font-family: monospace;
  color: var(--text-color);
  opacity: 0.6;
}
.remove-event-btn {
  border: none;
  background: var(--bg-color);
  color: var(--text-color);
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
  line-height: 1;
}
.remove-event-btn:hover {
  background: #cc0000;
  color: white;
}
</style>