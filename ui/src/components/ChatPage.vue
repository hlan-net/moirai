<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { marked } from 'marked'
import { authFetch } from '../utils/authFetch'

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
const renamingSessionId = ref<string | null>(null)
const newSessionTitle = ref('')

const currentLlmEndpoint = ref('ollama')
const currentModel = ref('llama3.1:latest')
const modelSelectOpen = ref(false)
const loadingModels = ref(false)
const modelFetchError = ref('')
const availableModels = ref<string[]>([])
const availableOpenAiModels = ref<string[]>([])
const availableGeminiModels = ref<string[]>([])

const modelSettingsMap: Record<string, string> = {
  openai: 'moirai_openai_model',
  gemini: 'moirai_gemini_model',
  ollama: 'moirai_model'
}

const defaultModels: Record<string, string> = {
  openai: 'gpt-4-turbo',
  gemini: 'gemini-1.5-pro',
  ollama: 'llama3.1:latest'
}

const endpointSelection = computed({
  get: () => currentLlmEndpoint.value,
  set: (value: string) => {
    updateEndpoint(value)
  }
})

const modelSelection = computed({
  get: () => currentModel.value,
  set: (value: string) => {
    updateModel(value)
  }
})

const modelOptions = computed(() => {
  switch (currentLlmEndpoint.value) {
    case 'openai':
      return availableOpenAiModels.value
    case 'gemini':
      return availableGeminiModels.value
    default:
      return availableModels.value
  }
})

onMounted(() => {
    fetchConfig()
    fetchSessions()
    loadSettings()
})

const _setInitialModelDefaults = (config: any) => {
  // Use server defaults if no local override
  if (!localStorage.getItem('moirai_llm_endpoint') && config.default_llm_provider) {
    currentLlmEndpoint.value = config.default_llm_provider
    
    const settingsKey = modelSettingsMap[config.default_llm_provider]
    if (settingsKey && !localStorage.getItem(settingsKey)) {
       currentModel.value = config.default_model_name
    }
  }
}

const _applyUserSettings = (settings: any) => {
  if (settings.moirai_llm_endpoint && !localStorage.getItem('moirai_llm_endpoint')) {
    currentLlmEndpoint.value = settings.moirai_llm_endpoint
  }
  
  const settingsKey = modelSettingsMap[currentLlmEndpoint.value] || 'moirai_model'
  if (settings[settingsKey] && !localStorage.getItem(settingsKey)) {
    currentModel.value = settings[settingsKey]
  }
}

const fetchConfig = async () => {
  try {
    const response = await authFetch('/api/config')
    if (response.ok) {
      const config = await response.json()
      _setInitialModelDefaults(config)
    }

    // Fetch user-specific settings to populate model selector
    const userRes = await authFetch('/api/auth/me')
    if (userRes.ok) {
      const userData = await userRes.json()
      _applyUserSettings(userData.settings || {})
    }
  } catch (error) {
    console.error('Error fetching config:', error)
  }
}

const loadSettings = () => {
    currentLlmEndpoint.value = localStorage.getItem('moirai_llm_endpoint') || 'ollama'

    const settingsKey = modelSettingsMap[currentLlmEndpoint.value] || 'moirai_model'
    const defaultModel = defaultModels[currentLlmEndpoint.value] || 'llama3.1:latest'
    
    currentModel.value = localStorage.getItem(settingsKey) || defaultModel
}

const saveUserSetting = async (key: string, value: string) => {
  try {
    await authFetch('/api/auth/me/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [key]: value })
    })
  } catch (error) {
    console.error(`Failed to save setting ${key} to server:`, error)
  }
}

const updateEndpoint = (value: string) => {
  if (currentLlmEndpoint.value === value) return
  currentLlmEndpoint.value = value
  localStorage.setItem('moirai_llm_endpoint', value)
  saveUserSetting('moirai_llm_endpoint', value)

  const settingsKey = modelSettingsMap[value] || 'moirai_model'
  const defaultModel = defaultModels[value] || 'llama3.1:latest'
  currentModel.value = localStorage.getItem(settingsKey) || defaultModel
  loadModelsForEndpoint(value)
}

const updateModel = (value: string) => {
  currentModel.value = value
  const settingsKey = modelSettingsMap[currentLlmEndpoint.value] || 'moirai_model'
  localStorage.setItem(settingsKey, value)
  saveUserSetting(settingsKey, value)
}

const _fetchModels = async (endpoint: string, apiKey: string | null, headers: Record<string, string> = {}) => {
  let url = '/api/models'
  if (endpoint !== 'ollama') {
    url += `?llm_endpoint=${endpoint}`
  }
  
  if (apiKey) {
    headers[`x-${endpoint}-api-key`] = apiKey
  }

  const res = await authFetch(url, { headers })
  if (res.ok) {
    return await res.json()
  }
  throw new Error(`Failed to load ${endpoint} models.`)
}

const _loadOpenAiModels = async () => {
  if (availableOpenAiModels.value.length > 0) return
  const openaiApiKey = localStorage.getItem('moirai_openai_api_key')
  if (!openaiApiKey) {
    modelFetchError.value = 'Add an OpenAI API key in Settings to fetch models.'
    return
  }
  loadingModels.value = true
  try {
    availableOpenAiModels.value = await _fetchModels('openai', openaiApiKey)
  } catch (error) {
    console.error('Error fetching OpenAI models:', error)
    modelFetchError.value = 'Failed to load OpenAI models.'
  } finally {
    loadingModels.value = false
  }
}

const _loadGeminiModels = async () => {
  if (availableGeminiModels.value.length > 0) return
  const geminiApiKey = localStorage.getItem('moirai_gemini_api_key')
  if (!geminiApiKey) {
    modelFetchError.value = 'Add a Gemini API key in Settings to fetch models.'
    return
  }
  loadingModels.value = true
  try {
    availableGeminiModels.value = await _fetchModels('gemini', geminiApiKey)
  } catch (error) {
    console.error('Error fetching Gemini models:', error)
    modelFetchError.value = 'Failed to load Gemini models.'
  } finally {
    loadingModels.value = false
  }
}

const _loadOllamaModels = async () => {
  if (availableModels.value.length > 0) return
  loadingModels.value = true
  try {
    const headers: Record<string, string> = {}
    const ollamaEndpointUrl = localStorage.getItem('moirai_ollama_endpoint_url')
    if (ollamaEndpointUrl) {
      headers['x-ollama-base-url'] = ollamaEndpointUrl
    }
    availableModels.value = await _fetchModels('ollama', null, headers)
  } catch (error) {
    console.error('Error fetching Ollama models:', error)
    modelFetchError.value = 'Failed to load Ollama models.'
  } finally {
    loadingModels.value = false
  }
}

const loadModelsForEndpoint = async (endpoint: string) => {
  modelFetchError.value = ''

  if (endpoint === 'openai') {
    await _loadOpenAiModels()
  } else if (endpoint === 'gemini') {
    await _loadGeminiModels()
  } else {
    await _loadOllamaModels()
  }
}

const toggleModelSelect = () => {
  modelSelectOpen.value = !modelSelectOpen.value
  if (modelSelectOpen.value) {
    loadModelsForEndpoint(currentLlmEndpoint.value)
  }
}

const parsedContent = (content: string) => {
  return marked(content)
}

const fetchSessions = async () => {
  try {
    const response = await authFetch('/api/chat/history')
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
  loading.value = false
}

const getHeaders = () => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    if (currentLlmEndpoint.value === 'openai') {
      const openaiApiKey = localStorage.getItem('moirai_openai_api_key')
      if (openaiApiKey) {
        headers['x-openai-api-key'] = openaiApiKey
      }
    } else if (currentLlmEndpoint.value === 'gemini') {
      const geminiApiKey = localStorage.getItem('moirai_gemini_api_key')
      if (geminiApiKey) {
        headers['x-gemini-api-key'] = geminiApiKey
      }
    } else {
      const ollamaEndpointUrl = localStorage.getItem('moirai_ollama_endpoint_url')
      if (ollamaEndpointUrl) {
        headers['x-ollama-base-url'] = ollamaEndpointUrl
      }
    }
    return headers
}

const _ensureSession = async (userMsg: string) => {
  if (sessionId.value) return true
  
  try {
    const res = await authFetch('/api/chat/history', { 
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
      return true
    }
  } catch (e) {
    console.error('Failed to create session:', e)
  }
  return false
}

const _updateSessionMessages = async () => {
  if (!sessionId.value) return
  
  try {
    await authFetch(`/api/chat/history/${sessionId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
          messages: messages.value,
          model: currentModel.value,
          llm_endpoint: currentLlmEndpoint.value
      })
    })
  } catch (e) {
    console.error('Failed to update session messages:', e)
  }
}

const sendMessage = async () => {
  if (!input.value.trim() || loading.value) return
  
  const userMsg = input.value.trim()
  input.value = ''
  
  messages.value.push({ role: 'user', content: userMsg })
  loading.value = true
  
  try {
    await _ensureSession(userMsg)

    const history = messages.value.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content
    }))
    
    const res = await authFetch('/api/chat', {
      method: 'POST',
      headers: getHeaders(),
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
      await _updateSessionMessages()
    } else {
      messages.value.push({ role: 'assistant', content: `Error: ${res.statusText}` })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: `Error: ${e}` })
  } finally {
    loading.value = false
  }
}

const downloadChat = async () => {
  if (!sessionId.value) return
  const response = await authFetch(`/api/chat/history/${sessionId.value}/export`)
  if (!response.ok) return
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = disposition.match(/filename="?([^";]+)"?/)
  link.download = match?.[1] ?? 'chat.md'
  link.click()
  URL.revokeObjectURL(url)
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
    const response = await authFetch(`/api/chat/history/${id}`, {
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
  if (!provider) return '#444'
  switch (provider.toLowerCase()) {
    case 'openai': return '#0d8a68'  // Darker green for better contrast
    case 'ollama': return '#4651d9'  // Darker blue for better contrast
    case 'gemini': return '#1a66c9'  // Darker blue for better contrast
    default: return '#444'
  }
}

const startRename = (session: ChatSession, event: Event) => {
  event.stopPropagation()
  renamingSessionId.value = session._id
  newSessionTitle.value = session.title
}

const cancelRename = () => {
  renamingSessionId.value = null
  newSessionTitle.value = ''
}

const renameSession = async (session: ChatSession) => {
  try {
    const response = await authFetch(`/api/chat/history/${session._id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: newSessionTitle.value,
        messages: session.messages,
        model: session.model,
        llm_endpoint: session.llm_endpoint
      })
    })
    if (response.ok) {
      const updatedSession = await response.json()
      const index = sessions.value.findIndex(s => s._id === updatedSession._id)
      if (index !== -1) {
        sessions.value[index] = updatedSession
      }
      cancelRename()
    } else {
      console.error('Failed to rename session')
    }
  } catch (error) {
    console.error('Error renaming session:', error)
  }
}
</script>

<template>
  <div class="chat-page">
    <div class="sidebar">
      <button @click="newChat" class="new-chat-btn">New Chat</button>
      
      <!-- Search Input -->
      <div class="search-container">
        <input 
          v-model="searchQuery" 
          type="text" 
          placeholder="Search chats by title, model, or provider..." 
          class="search-input"
        />
        <button v-if="searchQuery" @click="searchQuery = ''" class="clear-search-btn" title="Clear search">
          ×
        </button>
      </div>
      
      <div v-if="loadingSessions">Loading...</div>
      <div v-else-if="filteredSessions.length" class="session-list">
        <div 
          v-for="session in filteredSessions" 
          :key="session._id" 
          @click="loadSession(session)"
          :class="['session-item', { active: sessionId === session._id }]"
        >
          <!-- Rename mode -->
          <div v-if="renamingSessionId === session._id" class="rename-mode" @click.stop>
            <input 
              v-model="newSessionTitle" 
              @keyup.enter="renameSession(session)" 
              @keyup.esc="cancelRename"
              class="rename-input"
              autofocus
            />
            <div class="rename-actions">
              <button @click="renameSession(session)" class="rename-save">Save</button>
              <button @click="cancelRename" class="rename-cancel">Cancel</button>
            </div>
          </div>
          
          <!-- Normal view -->
          <div v-else>
            <div class="session-header">
              <span class="session-title" @dblclick="startRename(session, $event)">{{ session.title }}</span>
              <div class="session-actions">
                <button 
                  @click="startRename(session, $event)" 
                  class="action-btn rename-btn"
                  title="Rename chat"
                >
                  ✎
                </button>
                <button 
                  @click="confirmDelete(session._id, $event)" 
                  class="action-btn delete-btn"
                  title="Delete chat"
                >
                  ×
                </button>
              </div>
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
        <span v-if="searchQuery">No chats match "{{ searchQuery }}"</span>
        <span v-else>No chats yet</span>
      </div>
    </div>
    <div class="chat-main">
      <div class="chat-header">
        <button
          class="model-info"
          @click="toggleModelSelect"
          @keyup.enter.prevent="toggleModelSelect"
          @keyup.space.prevent="toggleModelSelect"
        >
            <span class="provider-label">{{ currentLlmEndpoint }}</span>
            <span class="model-name">{{ currentModel }}</span>
            <span class="model-caret" :class="{ open: modelSelectOpen }">▾</span>
        </button>
        <button v-if="sessionId" @click="downloadChat" class="download-btn" title="Download Chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
          </svg>
          Download
        </button>
      </div>
      <div v-if="modelSelectOpen" class="model-select-panel">
        <div class="model-select-row">
          <label class="model-select-label" for="chat-provider">Provider</label>
          <select id="chat-provider" v-model="endpointSelection" class="model-select">
            <option value="ollama">Ollama</option>
            <option value="openai">OpenAI</option>
            <option value="gemini">Gemini</option>
          </select>
        </div>
        <div class="model-select-row">
          <label class="model-select-label" for="chat-model">Model</label>
          <select
            v-if="modelOptions.length"
            id="chat-model"
            v-model="modelSelection"
            class="model-select"
          >
            <option v-for="model in modelOptions" :key="model" :value="model">
              {{ model }}
            </option>
          </select>
          <input
            v-else
            id="chat-model"
            v-model="modelSelection"
            class="model-input"
            placeholder="e.g. llama3.1:latest"
          />
        </div>
        <div class="model-select-meta">
          <span v-if="loadingModels">Loading models...</span>
          <span v-else-if="modelFetchError">{{ modelFetchError }}</span>
          <span v-else-if="!modelOptions.length">No models fetched. You can type a model name.</span>
        </div>
        <button class="model-select-close" @click="modelSelectOpen = false">Done</button>
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
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0));
  padding: 16px 12px 16px 16px;
  border-right: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

:global(.light-theme) .sidebar {
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.04), rgba(0, 0, 0, 0));
}
.new-chat-btn {
  margin-bottom: 0;
}
.search-container {
  position: relative;
}

.search-input {
  width: 100%;
  padding: 8px 2rem 8px 8px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--input-bg);
  color: var(--input-text);
  font-size: 0.9rem;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.search-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.search-input::placeholder {
  color: #888;
}

.clear-search-btn {
  position: absolute;
  right: 0.25rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #888;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0 0.25rem;
  line-height: 1;
  transition: color 0.2s;
}

.clear-search-btn:hover {
  color: var(--text-color);
}
.session-list {
  flex: 1;
  overflow-y: auto;
}
.session-item {
  padding: 10px;
  cursor: pointer;
  border-bottom: none;
  border-radius: 8px;
  color: var(--text-color);
  font-size: 0.9rem;
  position: relative;
  transition: background-color 0.2s;
}
.session-item:hover, .session-item.active {
  background: rgba(255, 255, 255, 0.05);
}

:global(.light-theme) .session-item:hover,
:global(.light-theme) .session-item.active {
  background: rgba(0, 0, 0, 0.05);
}
.session-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 5px;
  margin-bottom: 4px;
}
.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: text;
  text-align: left;
  font-size: 0.95rem;
  font-weight: 500;
}
.session-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}
.action-btn {
  background: transparent;
  border: none;
  color: #999;
  font-size: 18px;
  line-height: 1;
  padding: 0;
  width: 20px;
  height: 20px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.rename-btn {
  font-size: 16px;
}
.rename-btn:hover {
  background: rgba(66, 185, 131, 0.15);
  color: #2d8a5f;
}
.delete-btn {
  font-size: 22px;
}
.delete-btn:hover {
  background: rgba(255, 59, 48, 0.15);
  color: #cc2e24;
}
.session-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 2px;
}
.tag {
  font-size: 0.6rem;
  padding: 1px 4px;
  border-radius: 2px;
  color: white;
  font-weight: 500;
  text-transform: capitalize;
  line-height: 1.2;
}
.provider-tag {
  /* Background color set dynamically */
}
.model-tag {
  background: #444;
  font-family: monospace;
  font-size: 0.55rem;
}
.rename-mode {
  padding: 5px 0;
}
.rename-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--primary-color);
  border-radius: 4px;
  background: var(--input-bg);
  color: var(--input-text);
  font-size: 0.9rem;
  margin-bottom: 6px;
  box-sizing: border-box;
}
.rename-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(66, 185, 131, 0.2);
}
.rename-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}
.rename-save, .rename-cancel {
  padding: 4px 10px;
  border: none;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
}
.rename-save {
  background: var(--primary-color);
  color: var(--bg-color);
}
.rename-save:hover {
  opacity: 0.9;
}
.rename-cancel {
  background: #666;
  color: white;
}
.rename-cancel:hover {
  background: #777;
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
  background: #444;
  color: white;
}
.no-results {
  padding: 2rem 1rem;
  text-align: center;
  color: #888;
  font-style: italic;
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}
.chat-header {

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
    cursor: pointer;
    user-select: none;
    background: transparent;
    border: none;
    padding: 0;
    font-family: inherit;
}
.model-info:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
    border-radius: 6px;
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
.model-caret {
    font-size: 0.8rem;
    opacity: 0.7;
    transition: transform 0.2s;
}
.model-caret.open {
    transform: rotate(180deg);
}
.model-select-panel {
    max-width: 800px;
    width: 100%;
    margin: 0 auto 12px auto;
    padding: 12px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--card-bg) 80%, transparent);
    border: 1px solid color-mix(in srgb, var(--border-color) 60%, transparent);
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.model-select-row {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 10px;
    align-items: center;
}
.model-select-label {
    font-size: 0.85rem;
    opacity: 0.8;
}
.model-select,
.model-input {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--input-bg);
    color: var(--input-text);
    font-size: 0.9rem;
}
.model-select:focus,
.model-input:focus {
    outline: none;
    border-color: var(--primary-color);
}
.model-select-meta {
    font-size: 0.8rem;
    opacity: 0.75;
}
.model-select-close {
    align-self: flex-end;
    padding: 6px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.2s;
}
.model-select-close:hover {
    background: var(--button-bg);
    border-color: var(--primary-color);
    color: var(--primary-color);
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
