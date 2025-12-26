<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface Feed {
  _id: string;
  url: string;
  category?: string;
}

const feeds = ref<Feed[]>([])
const loading = ref(true)

const fetchFeeds = async () => {
  try {
    const response = await fetch('/api/feeds')
    if (response.ok) {
        feeds.value = await response.json()
    }
  } catch (error) {
    console.error('Error fetching feeds:', error)
  } finally {
    loading.value = false
  }
}

const deleteFeed = async (id: string) => {
  if (!confirm("Are you sure you want to delete this feed?")) return;
  
  try {
    const res = await fetch(`/api/feeds/${id}`, { method: 'DELETE' })
    if (res.ok) {
      feeds.value = feeds.value.filter(f => f._id !== id)
    } else {
      alert("Failed to delete feed")
    }
  } catch (e) {
    console.error(e)
    alert("Error deleting feed")
  }
}

onMounted(() => {
  fetchFeeds()
})
</script>

<template>
  <div class="column-container">
    <h2>Feeds</h2>
    <div v-if="loading">Loading...</div>
    <ul v-else-if="feeds.length" class="feed-list">
      <li v-for="feed in feeds" :key="feed._id" class="feed-item">
        <div class="feed-info">
          <a :href="feed.url" target="_blank" class="feed-link">{{ feed.url }}</a>
          <span v-if="feed.category" class="category-tag">{{ feed.category }}</span>
        </div>
        <button @click="deleteFeed(feed._id)" class="delete-btn" title="Delete Feed">×</button>
      </li>
    </ul>
    <div v-else>No feeds found.</div>
  </div>
</template>

<style scoped>
.column-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
h2 {
  margin-top: 30px;
  color: #42b983;
}
.feed-list {
  list-style-type: none;
  padding: 0;
  overflow-y: auto;
  flex: 1;
}
.feed-item {
  margin: 10px 0;
  padding: 8px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.feed-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
}
.feed-link {
  color: #42b983;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 250px;
}
.feed-link:hover {
  text-decoration: underline;
}
.category-tag {
  font-size: 0.75rem;
  background: #eef;
  color: #669;
  padding: 2px 6px;
  border-radius: 4px;
  align-self: flex-start;
}
.delete-btn {
  background: none;
  border: none;
  color: #cc0000;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0 5px;
}
.delete-btn:hover {
  color: #ff0000;
  font-weight: bold;
}
</style>