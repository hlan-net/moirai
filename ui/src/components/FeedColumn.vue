<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface Feed {
  _id: string;
  url: string;
  title?: string;
  category?: string;
}

const feeds = ref<Feed[]>([])
const loading = ref(true)
const refreshing = ref(false)

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

const triggerRefresh = async () => {
    refreshing.value = true
    try {
        const res = await fetch('/api/feeds/refresh', { method: 'POST' })
        if (res.ok) {
            const data = await res.json()
            alert(`Started refreshing ${data.count} feeds.`)
        } else {
            alert("Failed to trigger refresh.")
        }
    } catch (e) {
        console.error(e)
        alert("Error triggering refresh.")
    } finally {
        refreshing.value = false
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

function getHostname(urlStr: string) {
  try {
    return new URL(urlStr).hostname
  } catch (e) {
    return urlStr
  }
}
</script>

<template>
  <div class="column-container">
    <div class="column-header">
        <h2>Feeds ({{ feeds.length }})</h2>
        <button @click="triggerRefresh" :disabled="refreshing" class="refresh-btn" title="Refresh All Feeds">
            {{ refreshing ? '...' : '↻' }}
        </button>
    </div>

    <div v-if="loading">Loading...</div>
    <ul v-else-if="feeds.length" class="feed-list">
      <li v-for="feed in feeds" :key="feed._id" class="feed-item">
        <div class="feed-info">
          <a :href="feed.url" target="_blank" class="feed-link" :title="feed.url">{{ feed.title || getHostname(feed.url) }}</a>
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
.column-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #eee;
    padding-bottom: 10px;
    margin-bottom: 10px;
    margin-top: 30px;
}
h2 {
  margin: 0;
  color: #42b983;
}
.refresh-btn {
    background: none;
    border: 1px solid #ccc;
    padding: 2px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1.2rem;
    color: var(--text-color);
}
.refresh-btn:hover:not(:disabled) {
    background: var(--button-bg);
    color: var(--primary-color);
    border-color: var(--primary-color);
}
.refresh-btn:disabled {
    opacity: 0.5;
    cursor: wait;
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