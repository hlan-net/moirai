<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { marked } from 'marked'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ChatSession {
  _id: string;
  title: string;
  messages: Message[];
  model?: string;
  llm_endpoint?: string;
}

const messages = ref<Message[]>([])
const input = ref('')
const loading = ref(false)
const sessionId = ref<string | null>(null)
const sessions = ref<ChatSession[]>([])
const loadingSessions = ref(true)

const currentLlmEndpoint = ref('ollama')
const currentModel = ref('llama3.1:latest')

onMounted(() => {
    fetchSessions()
    loadSettings()
})

const loadSettings = () => {
    currentLlmEndpoint.value = localStorage.getItem('moirai_llm_endpoint') || 'ollama'
    
    if (currentLlmEndpoint.value === 'openai') {
        currentModel.value = localStorage.getItem('moirai_openai_model') || 'gpt-4-turbo'
    } else {
        currentModel.value = localStorage.getItem('moirai_model') || 'llama3.1:latest'
    }
}

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
        body: JSON.stringify({ 
            title: userMsg,
            model: currentModel.value,
            llm_endpoint: currentLlmEndpoint.value
        })
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
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    if (currentLlmEndpoint.value === 'openai') {
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
          model: currentModel.value,
          llm_endpoint: currentLlmEndpoint.value
      })
    })
    
    if (res.ok) {
      const data = await res.json()
      messages.value.push({ role: 'assistant', content: data.response })

      if (sessionId.value) {
        await fetch(`/api/chat/history/${sessionId.value}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
              messages: messages.value,
              model: currentModel.value,
              llm_endpoint: currentLlmEndpoint.value
          })
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

const downloadChat = () => {
  if (!sessionId.value) return
  window.location.href = `/api/chat/history/${sessionId.value}/export`
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
        <div class="model-info">
            <span class="provider-label">{{ currentLlmEndpoint }}</span>
            <span class="model-name">{{ currentModel }}</span>
        </div>
        <button v-if="sessionId" @click="downloadChat" class="download-btn" title="Download Chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
          </svg>
          Download
        </button>
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
  background: var(--button-bg);
  padding: 10px;
  border-right: 1px solid var(--border-color);
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
  border-bottom: 1px solid var(--border-color);
  color: var(--text-color);
  font-size: 0.9rem;
}
.session-item:hover, .session-item.active {
  background: var(--bg-color);
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}
.chat-header {
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 5px;
    max-width: 800px;
    width: 100%;
    margin: 0 auto 10px auto;
}
.model-info {
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-size: 0.9rem;
    color: var(--text-color);
}
.provider-label {
    font-weight: bold;
    text-transform: capitalize;
    background: var(--primary-color);
    color: var(--bg-color);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.8rem;
}
.model-name {
    opacity: 0.9;
    font-family: monospace;
}
.download-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-color);
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s;
}

.download-btn:hover {
    background: var(--button-bg);
    border-color: var(--primary-color);
    color: var(--primary-color);
}

.download-btn svg {
    vertical-align: middle;
}
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
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
  background: var(--primary-color);
  color: var(--bg-color);
}
.assistant .bubble {
  background: var(--button-bg);
  color: var(--text-color);
  border: 1px solid var(--border-color);
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
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 10px;
}
input {
  flex: 1;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--input-bg);
  color: var(--input-text);
}
button {
  padding: 10px 20px;
  background: var(--primary-color);
  color: var(--bg-color);
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
button:disabled {
  background: #ccc;
}
</style>
