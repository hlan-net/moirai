<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
const searchQuery = ref('')
const deleteConfirmId = ref<string | null>(null)

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

const filteredSessions = computed(() => {
  if (!searchQuery.value.trim()) {
    return sessions.value
  }
  const query = searchQuery.value.toLowerCase()
  return sessions.value.filter(session => 
    session.title?.toLowerCase().includes(query) ||
    session.model?.toLowerCase().includes(query) ||
    session.llm_endpoint?.toLowerCase().includes(query)
  )
})

const confirmDelete = (id: string, event: Event) => {
  event.stopPropagation()
  deleteConfirmId.value = id
}

const cancelDelete = () => {
  deleteConfirmId.value = null
}

const deleteSession = async (id: string, event: Event) => {
  event.stopPropagation()
  try {
    const response = await fetch(`/api/chat/history/${id}`, {
      method: 'DELETE'
    })
    if (response.ok) {
      sessions.value = sessions.value.filter(s => s._id !== id)
      if (sessionId.value === id) {
        newChat()
      }
      deleteConfirmId.value = null
    } else {
      console.error('Failed to delete session')
    }
  } catch (error) {
    console.error('Error deleting session:', error)
  }
}

const getProviderColor = (provider?: string) => {
  if (!provider) return '#666'
  switch (provider.toLowerCase()) {
    case 'openai': return '#10a37f'
    case 'ollama': return '#5865F2'
    case 'gemini': return '#4285f4'
    default: return '#666'
  }
}
</script>

<template>
  <div class="chat-page">
    <div class="sidebar">
      <button @click="newChat" class="new-chat-btn">New Chat</button>
      <input 
        v-model="searchQuery" 
        type="text" 
        placeholder="Search chats..." 
        class="search-input"
      />
      <div v-if="loadingSessions">Loading...</div>
      <div v-else-if="filteredSessions.length" class="session-list">
        <div 
          v-for="session in filteredSessions" 
          :key="session._id" 
          @click="loadSession(session)"
          :class="['session-item', { active: sessionId === session._id }]"
        >
          <div class="session-header">
            <span class="session-title">{{ session.title }}</span>
            <button 
              @click="confirmDelete(session._id, $event)" 
              class="delete-btn"
              title="Delete chat"
            >
              ×
            </button>
          </div>
          <div class="session-tags">
            <span 
              class="tag provider-tag" 
              :style="{ backgroundColor: getProviderColor(session.llm_endpoint) }"
            >
              {{ session.llm_endpoint || 'ollama' }}
            </span>
            <span class="tag model-tag" v-if="session.model">
              {{ session.model }}
            </span>
          </div>
          
          <!-- Delete confirmation overlay -->
          <div v-if="deleteConfirmId === session._id" class="delete-confirm" @click.stop>
            <p>Delete this chat?</p>
            <div class="confirm-buttons">
              <button @click="deleteSession(session._id, $event)" class="confirm-yes">Delete</button>
              <button @click="cancelDelete" class="confirm-no">Cancel</button>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="no-results">
        {{ searchQuery ? 'No chats found' : 'No chats yet' }}
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
  gap: 10px;
}
.new-chat-btn {
  margin-bottom: 0;
}
.search-input {
  padding: 8px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--input-bg);
  color: var(--input-text);
  font-size: 0.9rem;
}
.search-input::placeholder {
  color: #888;
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
  position: relative;
}
.session-item:hover, .session-item.active {
  background: var(--bg-color);
}
.session-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 5px;
  margin-bottom: 6px;
}
.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.delete-btn {
  background: transparent;
  border: none;
  color: #999;
  font-size: 24px;
  line-height: 1;
  padding: 0;
  width: 24px;
  height: 24px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.delete-btn:hover {
  background: rgba(255, 59, 48, 0.1);
  color: #ff3b30;
}
.session-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.tag {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 3px;
  color: white;
  font-weight: 500;
  text-transform: capitalize;
}
.provider-tag {
  /* Background color set dynamically */
}
.model-tag {
  background: #666;
  font-family: monospace;
  font-size: 0.65rem;
}
.delete-confirm {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.95);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 10px;
  z-index: 10;
}
.delete-confirm p {
  color: white;
  margin: 0 0 10px 0;
  font-size: 0.9rem;
}
.confirm-buttons {
  display: flex;
  gap: 8px;
}
.confirm-yes, .confirm-no {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}
.confirm-yes {
  background: #ff3b30;
  color: white;
}
.confirm-no {
  background: #666;
  color: white;
}
.no-results {
  padding: 20px 10px;
  text-align: center;
  color: #888;
  font-size: 0.9rem;
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
