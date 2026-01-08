<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

const props = defineProps<{ namespace?: string }>()

interface Trend {
  _id: string
  name: string
  description: string
  event_ids: string[]
}

const trends = ref<Trend[]>([])
const loading = ref(true)
const expandedTrends = ref<Set<string>>(new Set())

const fetchTrends = async () => {
  try {
    let url = '/api/trends'
    if (props.namespace) {
      url += `?namespace=${props.namespace}`
    }
    const response = await fetch(url)
    if (response.ok) {
      trends.value = await response.json()
    }
  } catch (error) {
    console.error('Error fetching trends:', error)
  } finally {
    loading.value = false
  }
}

watch(() => props.namespace, () => {
  fetchTrends()
})

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
  <div class="column-container">
    <h2>Trends ({{ trends.length }})</h2>
    <div v-if="loading">Loading trends...</div>
    <div v-else-if="trends.length" class="trend-list">
      <div v-for="trend in trends" :key="trend._id" class="trend-card">
        <div class="card-header">
          <h3 @click="toggleExpand(trend._id)" class="clickable">{{ trend.name }}</h3>
          <button @click="deleteTrend(trend._id)" class="delete-btn" title="Delete Trend">×</button>
        </div>
        <p class="desc">{{ trend.description }}</p>

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
.column-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
h2 {
  color: #6a0dad;
  margin-top: 30px;
}
.trend-list {
  overflow-y: auto;
  flex: 1;
}
.trend-card {
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
  background: #fdfdfd;
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
  color: #333;
}
.desc {
  font-size: 0.9rem;
  color: #555;
  margin: 5px 0;
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
  color: #888;
  cursor: pointer;
  margin-top: 5px;
}
.events-section {
  margin-top: 10px;
  border-top: 1px solid #eee;
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
  color: #666;
}
.remove-event-btn {
  border: none;
  background: #eee;
  color: #666;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
  line-height: 1;
}
.remove-event-btn:hover {
  background: #ddd;
  color: #000;
}
</style>
