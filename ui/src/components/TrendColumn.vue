<script setup lang="ts">
import { onMounted, ref, computed, inject, type Ref } from 'vue'

interface Trend {
  _id: string
  name: string
  description: string
  event_ids: string[]
}

const trends = ref<Trend[]>([])
const loading = ref(true)
const expandedTrends = ref<Set<string>>(new Set())
const searchQuery = ref('')
const events = ref<any[]>([]) // To check which events link to selected feed's articles
const articles = ref<any[]>([]) // To check article origins

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
      trend.event_ids.some(eventId => relevantEventIds.has(eventId))
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

const fetchTrends = async () => {
  try {
    const [trendsResponse, eventsResponse, articlesResponse] = await Promise.all([
      fetch('/api/trends'),
      fetch('/api/events'),
      fetch('/api/articles?limit=10000'),
    ])

    if (trendsResponse.ok) {
      const data = await trendsResponse.json()
      trends.value = Array.isArray(data) ? data : []
    }
    
    if (eventsResponse.ok) {
      events.value = await eventsResponse.json()
    }
    
    if (articlesResponse.ok) {
      const data = await articlesResponse.json()
      articles.value = data.articles || []
    }
  } catch (error) {
    console.error('Error fetching trends:', error)
    trends.value = []
  } finally {
    loading.value = false
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
})
</script>

<template>
  <div class="trend-column">
    <div class="column-header">
      <h2>Trends ({{ filteredTrends.length }})</h2>
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
    <div v-else-if="!filteredTrends.length && searchQuery" class="no-results">
      No trends match "{{ searchQuery }}"
    </div>
    <div v-else-if="filteredTrends.length" class="trend-list">
      <div v-for="trend in filteredTrends" :key="trend._id" class="trend-card">
        <div class="card-header">
          <h3 @click="toggleExpand(trend._id)" class="clickable">{{ trend.name }}</h3>
          <button @click="deleteTrend(trend._id)" class="delete-btn" title="Delete Trend">×</button>
        </div>
        <p class="summary">{{ trend.description }}</p>

        <div v-if="expandedTrends.has(trend._id)" class="events-section">
          <h4>Linked Events ({{ trend.event_ids.length }})</h4>
          <ul>
            <li v-for="eid in trend.event_ids" :key="eid">
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
          {{ trend.event_ids.length }} events (click to expand)
        </div>
      </div>
    </div>
    <div v-else>No trends found.</div>
  </div>
</template>

<style scoped>
.search-container {
  position: relative;
  margin: 0.75rem 0;
}

.search-input {
  width: 100%;
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
  height: 100%;
  display: flex;
  flex-direction: column;
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