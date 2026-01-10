<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

interface ChatSession {
  _id: string;
  messages: any[];
}

const sessions = ref<ChatSession[]>([])
const loading = ref(true)
const router = useRouter()

const fetchSessions = async () => {
  try {
    const response = await fetch('/api/chat/history')
    if (response.ok) {
      sessions.value = await response.json()
    }
  } catch (error) {
    console.error('Error fetching chat sessions:', error)
  } finally {
    loading.value = false
  }
}

const deleteSession = async (sessionId: string) => {
  if (!confirm('Are you sure you want to delete this chat session?')) return
  try {
    const res = await fetch(`/api/chat/history/${sessionId}`, { method: 'DELETE' })
    if (res.ok) {
      sessions.value = sessions.value.filter(s => s._id !== sessionId)
    } else {
      alert('Failed to delete chat session')
    }
  } catch (e) {
    console.error(e)
    alert('Error deleting chat session')
  }
}

const viewSession = (sessionId: string) => {
  router.push(`/chat/history/${sessionId}`)
}

onMounted(() => {
  fetchSessions()
})
</script>

<template>
  <div class="chat-history-page">
    <h1>Chat History</h1>
    <div v-if="loading">Loading chat history...</div>
    <div v-else-if="sessions.length" class="session-list">
      <div v-for="session in sessions" :key="session._id" class="session-item">
        <div @click="viewSession(session._id)" class="session-info">
          <p><strong>Session ID:</strong> {{ session._id }}</p>
          <p><strong>Messages:</strong> {{ session.messages.length }}</p>
        </div>
        <button @click="deleteSession(session._id)" class="delete-btn" title="Delete Session">×</button>
      </div>
    </div>
    <div v-else>No chat history found.</div>
  </div>
</template>

<style scoped>
.chat-history-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}
.session-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  border: 1px solid #ccc;
  border-radius: 8px;
  cursor: pointer;
}
.session-item:hover {
  background-color: #f0f0f0;
}
.session-info {
  flex-grow: 1;
}
.delete-btn {
  background: none;
  border: none;
  color: #cc0000;
  font-size: 1.2rem;
  cursor: pointer;
}
</style>
