<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNamespace } from '../composables/useNamespace'
import { marked } from 'marked'

const { currentNamespace, namespaces, initNamespace } = useNamespace()

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ChatSession {
  _id: string;
  title: string;
  messages: Message[];
}

const messages = ref<Message[]>([])
const input = ref('')
const loading = ref(false)
const sessionId = ref<string | null>(null)
const sessions = ref<ChatSession[]>([])
const loadingSessions = ref(true)

onMounted(() => {
    initNamespace()
    fetchSessions()
})

const parsedContent = (content: string) => {
  return marked(content)
}

const fetchSessions = async () => {
  try {
    const response = await fetch('/api/chat/history')
    if (response.ok) {
      sessions.value = await response.json()
    }
  } catch (error) {
    console.error('Error fetching chat sessions:', error)
  } finally {
    loadingSessions.value = false
  }
}

const loadSession = (session: ChatSession) => {
  sessionId.value = session._id
  messages.value = session.messages
}

const newChat = () => {
  sessionId.value = null
  messages.value = []
}

const sendMessage = async () => {
  if (!input.value.trim() || loading.value) return
  
  const userMsg = input.value.trim()
  input.value = ''
  
  messages.value.push({ role: 'user', content: userMsg })
  loading.value = true
  
  try {
    if (!sessionId.value) {
      const res = await fetch('/api/chat/history', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: userMsg })
      })
      if (res.ok) {
        const data = await res.json()
        sessionId.value = data._id
        sessions.value.unshift(data)
      }
    }

    const history = messages.value.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content
    }))
    
    const llmEndpoint = localStorage.getItem('moirai_llm_endpoint') || 'ollama'
    let model = localStorage.getItem('moirai_model') || 'llama3.1:latest'
    if (llmEndpoint === 'openai') {
      model = localStorage.getItem('moirai_openai_model') || 'gpt-4-turbo'
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    if (llmEndpoint === 'openai') {
      const openaiApiKey = localStorage.getItem('moirai_openai_api_key')
      if (openaiApiKey) {
        headers['x-openai-api-key'] = openaiApiKey
      }
    } else {
      const ollamaEndpointUrl = localStorage.getItem('moirai_ollama_endpoint_url')
      if (ollamaEndpointUrl) {
        headers['x-ollama-base-url'] = ollamaEndpointUrl
      }
    }

    const res = await fetch('/api/chat', {
      method: 'POST',
      headers,
      body: JSON.stringify({ 
          message: userMsg, 
          history, 
          model,
          namespace: currentNamespace.value,
          llm_endpoint: llmEndpoint
      })
    })
    
    if (res.ok) {
      const data = await res.json()
      messages.value.push({ role: 'assistant', content: data.response })

      if (sessionId.value) {
        await fetch(`/api/chat/history/${sessionId.value}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: messages.value })
        })
      }
    } else {
      messages.value.push({ role: 'assistant', content: `Error: ${res.statusText}` })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: `Error: ${e}` })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="chat-page">
    <div class="sidebar">
      <button @click="newChat" class="new-chat-btn">New Chat</button>
      <div v-if="loadingSessions">Loading...</div>
      <div v-else-if="sessions.length" class="session-list">
        <div 
          v-for="session in sessions" 
          :key="session._id" 
          @click="loadSession(session)"
          :class="['session-item', { active: sessionId === session._id }]"
        >
          {{ session.title }}
        </div>
      </div>
    </div>
    <div class="chat-main">
      <div class="chat-header">
         <select v-model="currentNamespace" class="ns-select">
          <option value="">-- No Context (Global) --</option>
          <option v-for="ns in namespaces" :key="ns" :value="ns">
            {{ ns }}
          </option>
        </select>
      </div>
      <div class="chat-container">
        <div class="messages">
          <div 
            v-for="(msg, idx) in messages" 
            :key="idx" 
            :class="['message', msg.role]"
          >
            <div class="bubble">
              <strong>{{ msg.role === 'user' ? 'You' : 'GenAI' }}:</strong>
              <div class="msg-content" v-html="parsedContent(msg.content)"></div>
            </div>
          </div>
          <div v-if="loading" class="message assistant">
            <div class="bubble loading">Thinking...</div>
          </div>
        </div>
        
        <div class="input-area">
          <input 
            v-model="input" 
            @keyup.enter="sendMessage" 
            placeholder="Ask Moirai..." 
            :disabled="loading"
          />
          <button @click="sendMessage" :disabled="loading">Send</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.sidebar {
  width: 250px;
  background: #f0f0f0;
  padding: 10px;
  border-right: 1px solid #ccc;
  display: flex;
  flex-direction: column;
}
.new-chat-btn {
  margin-bottom: 10px;
}
.session-list {
  flex: 1;
  overflow-y: auto;
}
.session-item {
  padding: 10px;
  cursor: pointer;
  border-bottom: 1px solid #ddd;
}
.session-item:hover, .session-item.active {
  background: #e0e0e0;
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}
.chat-header {
    text-align: center;
    margin-bottom: 10px;
}
.ns-select {
  padding: 8px;
  width: 300px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid #ccc;
  border-radius: 8px;
  background: white;
}
.messages {
  flex: 1;
  overflow-y: auto;
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
.loading {
  font-style: italic;
  color: #888;
}
.msg-content {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0;
}
.input-area {
  padding: 15px;
  border-top: 1px solid #eee;
  display: flex;
  gap: 10px;
}
input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}
button {
  padding: 10px 20px;
  background: #007acc;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
button:disabled {
  background: #ccc;
}
</style>
