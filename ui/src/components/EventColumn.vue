<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'

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
const expandedEvents = ref<Set<string>>(new Set())
const searchQuery = ref('')

const normalizeEvent = (event: any): Event => ({
  _id: event._id,
  name: event.name || event.title || 'Unnamed Event',
  description: event.description || '',
  article_links: Array.isArray(event.article_links) ? event.article_links : [],
  trend_id: event.trend_id,
})

// Computed: Filtered events based on search query
const filteredEvents = computed(() => {
  if (!searchQuery.value.trim()) return events.value
  
  const query = searchQuery.value.toLowerCase()
  return events.value.filter(event => {
    const name = event.name.toLowerCase()
    const description = event.description.toLowerCase()
    return name.includes(query) || description.includes(query)
  })
})

const fetchEventsAndTrends = async () => {
  loading.value = true
  try {
    const [eventsResponse, trendsResponse] = await Promise.all([
      fetch('/api/events'),
      fetch('/api/trends'),
    ])

    if (eventsResponse.ok) {
      const eventsData = await eventsResponse.json()
      events.value = Array.isArray(eventsData) ? eventsData.map(normalizeEvent) : []
    } else {
      events.value = []
    }

    if (trendsResponse.ok) {
      const trendsData = await trendsResponse.json()
      trends.value = Array.isArray(trendsData) ? trendsData : []
    } else {
      trends.value = []
    }
  } catch (error) {
    console.error('Error fetching events or trends:', error)
    events.value = []
    trends.value = []
  } finally {
    loading.value = false
  }
}

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
})
</script>

<template>
  <div class="column-container">
    <h2>Events ({{ filteredEvents.length }})</h2>

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

    <div v-if="loading">Loading events...</div>
    <div v-else-if="!filteredEvents.length && searchQuery" class="no-results">
      No events match "{{ searchQuery }}"
    </div>
    <div v-else-if="filteredEvents.length" class="event-list">
      <div v-for="event in filteredEvents" :key="event._id" class="event-card">
        <div class="card-header">
          <h3 @click="toggleExpand(event._id)" class="clickable">{{ event.name }}</h3>
          <button @click="deleteEvent(event._id)" class="delete-btn" title="Delete Event">×</button>
        </div>
        <p v-if="event.description" class="desc">{{ event.description }}</p>
        <div v-if="event.trend_id" class="trend-link">
          <span class="trend-label">Related Trend:</span>
          <span class="trend-name">{{ getTrendDisplayName(event.trend_id) }}</span>
        </div>

        <div v-if="expandedEvents.has(event._id)" class="links-section">
          <h4>Linked Articles ({{ event.article_links.length }})</h4>
          <ul>
            <li v-for="link in event.article_links" :key="link">
              <a :href="link" target="_blank" rel="noopener noreferrer">{{ link }}</a>
              <button
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
          {{ event.article_links.length }} articles (click to expand)
        </div>
      </div>
    </div>
    <div v-else>No events found.</div>
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

.column-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
h2 {
  color: #d83b01;
  margin-top: 0;
}
.event-list {
  overflow-y: auto;
  flex: 1;
}
.event-card {
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
  background: var(--button-bg);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.clickable {
  cursor: pointer;
}
.clickable:hover {
  text-decoration: underline;
}
h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-color);
}
.desc {
  font-size: 0.9rem;
  color: var(--text-color);
  opacity: 0.8;
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
  color: #cc0000;
  font-size: 1.2rem;
  cursor: pointer;
}
.expand-hint {
  font-size: 0.8rem;
  color: var(--text-color);
  opacity: 0.5;
  cursor: pointer;
  margin-top: 5px;
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
