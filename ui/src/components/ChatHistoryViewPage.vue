<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ChatSession {
  _id: string;
  messages: Message[];
}

const session = ref<ChatSession | null>(null)
const loading = ref(true)
const route = useRoute()

const fetchSession = async () => {
  try {
    const sessionId = route.params.id
    const response = await fetch(`/api/chat/history/${sessionId}`)
    if (response.ok) {
      session.value = await response.json()
    }
  } catch (error) {
    console.error('Error fetching chat session:', error)
  } finally {
    loading.value = false
  }
}

const parsedContent = (content: string) => {
  return marked(content)
}

onMounted(() => {
  fetchSession()
})
</script>

<template>
  <div class="chat-history-view-page">
    <h1>Chat History</h1>
    <div v-if="loading">Loading chat session...</div>
    <div v-else-if="session" class="chat-container">
      <div class="messages">
        <div 
          v-for="(msg, idx) in session.messages" 
          :key="idx" 
          :class="['message', msg.role]"
        >
          <div class="bubble">
            <strong>{{ msg.role === 'user' ? 'You' : 'GenAI' }}:</strong>
            <div class="msg-content" v-html="parsedContent(msg.content)"></div>
          </div>
        </div>
      </div>
    </div>
    <div v-else>Chat session not found.</div>
  </div>
</template>

<style scoped>
.chat-history-view-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}
.chat-container {
  border: 1px solid #ccc;
  border-radius: 8px;
  background: white;
}
.messages {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.message {
  display: flex;
}
.message.user {
  justify-content: flex-end;
}
.message.assistant {
  justify-content: flex-start;
}
.bubble {
  padding: 10px 15px;
  border-radius: 8px;
  max-width: 80%;
  word-wrap: break-word;
}
.user .bubble {
  background: #007acc;
  color: white;
}
.assistant .bubble {
  background: #f0f0f0;
  color: #333;
}
.msg-content {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0;
}
</style>
