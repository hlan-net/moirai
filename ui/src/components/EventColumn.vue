<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface Event {
  _id: string;
  name: string;
  description: string;
  article_links: string[];
}

const events = ref<Event[]>([])
const loading = ref(true)
const expandedEvents = ref<Set<string>>(new Set())

const fetchEvents = async () => {
  try {
    const response = await fetch('/api/events')
    if (response.ok) {
        events.value = await response.json()
    }
  } catch (error) {
    console.error('Error fetching events:', error)
  } finally {
    loading.value = false
  }
}

const deleteEvent = async (id: string) => {
  if (!confirm("Delete this event?")) return;
  try {
    const res = await fetch(`/api/events/${id}`, { method: 'DELETE' })
    if (res.ok) {
      events.value = events.value.filter(e => e._id !== id)
    }
  } catch (e) {
    console.error(e)
  }
}

const removeLink = async (eventId: string, link: string) => {
  if (!confirm("Remove this article from the event?")) return;
  try {
    const res = await fetch(`/api/events/${eventId}/links`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ link })
    })
    if (res.ok) {
      const updatedEvent = await res.json()
      const index = events.value.findIndex(e => e._id === eventId)
      if (index !== -1) {
        events.value[index] = updatedEvent
      }
    }
  } catch (e) {
    console.error(e)
  }
}

const toggleExpand = (id: string) => {
  if (expandedEvents.value.has(id)) {
    expandedEvents.value.delete(id)
  } else {
    expandedEvents.value.add(id)
  }
}

onMounted(() => {
  fetchEvents()
})
</script>

<template>
  <div class="column-container">
    <h2>Events</h2>
    <div v-if="loading">Loading events...</div>
    <div v-else-if="events.length" class="event-list">
      <div v-for="event in events" :key="event._id" class="event-card">
        <div class="card-header">
           <h3 @click="toggleExpand(event._id)" class="clickable">{{ event.name }}</h3>
           <button @click="deleteEvent(event._id)" class="delete-btn" title="Delete Event">×</button>
        </div>
        <p class="desc">{{ event.description }}</p>
        
        <div v-if="expandedEvents.has(event._id)" class="links-section">
          <h4>Linked Articles ({{ event.article_links.length }})</h4>
          <ul>
            <li v-for="link in event.article_links" :key="link">
              <a :href="link" target="_blank">{{ link }}</a>
              <button @click="removeLink(event._id, link)" class="remove-link-btn" title="Remove link">-</button>
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
.column-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
h2 {
  color: #d83b01;
  margin-top: 30px;
}
.event-list {
  overflow-y: auto;
  flex: 1;
}
.event-card {
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
  background: #fff;
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
.links-section {
  margin-top: 10px;
  border-top: 1px solid #eee;
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
  max-width: 200px;
  color: #007acc;
}
.remove-link-btn {
  border: none;
  background: #eee;
  color: #666;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
  line-height: 1;
}
.remove-link-btn:hover {
  background: #ddd;
  color: #000;
}
</style>