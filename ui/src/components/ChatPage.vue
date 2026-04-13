<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { authFetch } from '../utils/authFetch'
import { supportsToolCalling } from '../utils/modelCapabilities'
import { useSettingsStore } from '../stores/settings'

interface Message {
  role: 'user' | 'assistant'
  content: string
  tool_calls?: Array<{ name?: string; status?: string; error?: string }>
  tool_execution_errors?: number
  timing_ms?: number
}

interface ChatSession {
  _id: string;
  title: string;
  messages: Message[];
  model?: string;
  llm_endpoint?: string;
  context?: {
    type?: 'article' | 'issue' | 'feed'
    entity_id?: string
    entity_data?: Record<string, unknown>
  }
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

const modelSelectOpen = ref(false)
const loadingModels = ref(false)
const modelFetchError = ref('')
const availableModels = ref<string[]>([])
const availableOpenAiModels = ref<string[]>([])
const availableGeminiModels = ref<string[]>([])
const copyStatus = ref('')

const settingsStore = useSettingsStore()

const stripInternalReminders = (content: string) => {
  if (!content) return content
  return content.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/gi, '').trim()
}

const normalizeErrorMessage = (raw: string) => {
  const withoutReminders = stripInternalReminders(raw)
  const withoutHtml = withoutReminders.replace(/<[^>]*>/g, ' ')
  const compact = withoutHtml.replace(/\s+/g, ' ').trim()
  if (!compact || compact === 'Error:') {
    return 'Error: Request failed. Check API logs for details.'
  }
  return compact
}

const endpointSelection = computed({
  get: () => settingsStore.llmEndpoint,
  set: (value: string) => {
    updateEndpoint(value)
  }
})

const modelSelection = computed({
  get: () => settingsStore.getCurrentModel(),
  set: (value: string) => {
    updateModel(value)
  }
})

const modelOptions = computed(() => {
  switch (settingsStore.llmEndpoint) {
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
})

onUnmounted(() => {
    // No need to remove listeners - Pinia handles reactivity
})

const fetchConfig = async () => {
  try {
    const response = await authFetch('/api/config')
    if (response.ok) {
      const config = await response.json()
      // Use server defaults if endpoint is still default
      if (settingsStore.llmEndpoint === 'ollama' && config.default_llm_provider) {
        settingsStore.llmEndpoint = config.default_llm_provider
        if (config.default_model_name) {
          settingsStore.setCurrentModel(config.default_model_name)
        }
      }
    }

    // Fetch user-specific settings to populate model selector
    const userRes = await authFetch('/api/auth/me')
    if (userRes.ok) {
      const userData = await userRes.json()
      if (userData.settings) {
        settingsStore.loadFromBackend(userData.settings)
      }
    }
  } catch (error) {
    console.error('Error fetching config:', error)
  }
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

const updateEndpoint = async (value: string) => {
  if (settingsStore.llmEndpoint === value) return
  settingsStore.llmEndpoint = value
  saveUserSetting('moirai_llm_endpoint', value)

  // Auto-load models when provider changes
  await loadModelsForEndpoint(value)
}

const updateModel = (value: string) => {
  // Validate tool support for Ollama models
  if (settingsStore.llmEndpoint === 'ollama' && !supportsToolCalling(value)) {
    console.warn(`Model ${value} does not support tool calling. Some features may not work.`)
    modelFetchError.value = `Warning: ${value} doesn't support tool calling. Agent features will not work.`
    // Don't prevent selection, just warn - user might want to use it anyway
  } else {
    modelFetchError.value = ''
  }

  settingsStore.setCurrentModel(value)
  const modelKey = settingsStore.getCurrentModelKey()
  saveUserSetting(modelKey, value)
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
  if (!settingsStore.openaiApiKey) {
    modelFetchError.value = 'Add an OpenAI API key in Settings to fetch models.'
    return
  }
  loadingModels.value = true
  try {
    availableOpenAiModels.value = await _fetchModels('openai', settingsStore.openaiApiKey)
  } catch (error) {
    console.error('Error fetching OpenAI models:', error)
    modelFetchError.value = 'Failed to load OpenAI models.'
  } finally {
    loadingModels.value = false
  }
}

const _loadGeminiModels = async () => {
  if (availableGeminiModels.value.length > 0) return
  if (!settingsStore.geminiApiKey) {
    modelFetchError.value = 'Add a Gemini API key in Settings to fetch models.'
    return
  }
  loadingModels.value = true
  try {
    availableGeminiModels.value = await _fetchModels('gemini', settingsStore.geminiApiKey)
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
    if (settingsStore.ollamaEndpointUrl) {
      headers['x-ollama-base-url'] = settingsStore.ollamaEndpointUrl
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
    loadModelsForEndpoint(settingsStore.llmEndpoint)
  }
}

const getProviderStatusClass = () => {
  if (settingsStore.llmEndpoint === 'ollama') return 'status-ok'

  const apiKey = settingsStore.llmEndpoint === 'openai'
    ? settingsStore.openaiApiKey
    : settingsStore.geminiApiKey

  return apiKey ? 'status-ok' : 'status-warning'
}

const getProviderStatusText = () => {
  if (settingsStore.llmEndpoint === 'ollama') return '✓ Ready'

  const apiKey = settingsStore.llmEndpoint === 'openai'
    ? settingsStore.openaiApiKey
    : settingsStore.geminiApiKey

  return apiKey ? '✓ API Key Set' : '⚠ API Key Required'
}

const getModelPlaceholder = () => {
  switch (settingsStore.llmEndpoint) {
    case 'openai':
      return 'e.g., gpt-4-turbo'
    case 'gemini':
      return 'e.g., gemini-1.5-pro'
    default:
      return 'e.g., llama3.1:latest'
  }
}

const parsedContent = (content: string) => {
  return DOMPurify.sanitize(marked(stripInternalReminders(content)) as string)
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

const getActiveSessionContext = () => {
  if (!sessionId.value) return undefined
  const session = sessions.value.find((s) => s._id === sessionId.value)
  if (!session?.context?.type || !session.context?.entity_id || !session.context?.entity_data) {
    return undefined
  }
  return {
    type: session.context.type,
    entity_id: session.context.entity_id,
    entity_data: session.context.entity_data,
  }
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
    if (settingsStore.llmEndpoint === 'openai') {
      if (settingsStore.openaiApiKey) {
        headers['x-openai-api-key'] = settingsStore.openaiApiKey
      }
    } else if (settingsStore.llmEndpoint === 'gemini') {
      if (settingsStore.geminiApiKey) {
        headers['x-gemini-api-key'] = settingsStore.geminiApiKey
      }
    } else if (settingsStore.ollamaEndpointUrl) {
      headers['x-ollama-base-url'] = settingsStore.ollamaEndpointUrl
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
          model: settingsStore.getCurrentModel(),
          llm_endpoint: settingsStore.llmEndpoint
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
          model: settingsStore.getCurrentModel(),
          llm_endpoint: settingsStore.llmEndpoint
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
          model: settingsStore.getCurrentModel(),
          llm_endpoint: settingsStore.llmEndpoint,
          context: getActiveSessionContext()
      })
    })
    
    if (res.ok) {
      const data = await res.json()
      messages.value.push({
        role: 'assistant',
        content: stripInternalReminders(data.response ?? ''),
        tool_calls: Array.isArray(data.tool_calls) ? data.tool_calls : [],
        tool_execution_errors: Number(data.tool_execution_errors || 0),
        timing_ms: Number(data.timing_ms || 0),
      })
      await _updateSessionMessages()
    } else {
      let serverMessage = ''
      try {
        const payload = await res.json()
        if (payload && typeof payload.response === 'string') {
          serverMessage = payload.response
        } else if (payload && typeof payload.error === 'string') {
          serverMessage = payload.error
        }
      } catch {
        const body = await res.text()
        serverMessage = body
      }

      const fallback = `Error: ${res.status} ${res.statusText}`
      messages.value.push({
        role: 'assistant',
        content: normalizeErrorMessage(serverMessage || fallback),
        tool_calls: [],
        tool_execution_errors: 0,
      })
      await _updateSessionMessages()
    }
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: normalizeErrorMessage(`Error: ${String(e)}`),
      tool_calls: [],
      tool_execution_errors: 0,
    })
    await _updateSessionMessages()
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
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  globalThis.setTimeout(() => URL.revokeObjectURL(url), 100)
}

const copyChat = async () => {
  if (!sessionId.value) return
  try {
    const response = await authFetch(`/api/chat/history/${sessionId.value}/export`)
    if (!response.ok) {
      copyStatus.value = 'Copy failed'
      return
    }
    const markdown = await response.text()
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(markdown)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = markdown
      textarea.style.cssText = 'position:fixed;opacity:0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    copyStatus.value = 'Copied'
  } catch (error) {
    console.error('Failed to copy chat export:', error)
    copyStatus.value = 'Copy failed'
  } finally {
    globalThis.setTimeout(() => {
      copyStatus.value = ''
    }, 2000)
  }
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

const getContextTag = (session: ChatSession) => {
  switch (session.context?.type) {
    case 'article':
      return { label: '📰 Article', color: '#0d6efd' }
    case 'issue':
      return { label: '🔗 Issue', color: '#a23bd8' }
    case 'feed':
      return { label: '📡 Feed', color: '#2e8b57' }
    default:
      return null
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
              <span
                v-if="getContextTag(session)"
                class="tag context-tag"
                :style="{ backgroundColor: getContextTag(session)?.color }"
              >
                {{ getContextTag(session)?.label }}
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
            <span class="provider-label">{{ settingsStore.llmEndpoint }}</span>
            <span class="model-name">{{ settingsStore.getCurrentModel() }}</span>
            <span class="model-caret" :class="{ open: modelSelectOpen }">▾</span>
        </button>
        <div v-if="sessionId" class="chat-header-actions">
          <button @click="copyChat" class="download-btn" :title="copyStatus || 'Copy Chat to Clipboard'">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16 1H4c-1.1 0-2 .9-2 2v12h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
            </svg>
            {{ copyStatus || 'Copy' }}
          </button>
          <button @click="downloadChat" class="download-btn" title="Download Chat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
            </svg>
            Download
          </button>
        </div>
      </div>
      <div v-if="modelSelectOpen" class="model-select-panel">
        <div class="model-select-header">
          <h3>Select Model Provider &amp; Model</h3>
          <button class="model-select-close-icon" @click="modelSelectOpen = false" title="Close">×</button>
        </div>
        
        <div class="model-select-row">
          <label class="model-select-label" for="chat-provider">
            Provider
            <span class="provider-status" :class="getProviderStatusClass()">
              {{ getProviderStatusText() }}
            </span>
          </label>
          <select id="chat-provider" v-model="endpointSelection" class="model-select">
            <option value="ollama">Ollama (Local)</option>
            <option value="openai">OpenAI (API Key Required)</option>
            <option value="gemini">Gemini (API Key Required)</option>
          </select>
        </div>
        
        <div class="model-select-row">
          <label class="model-select-label" for="chat-model">
            Model
            <span v-if="loadingModels" class="loading-indicator">⟳ Loading...</span>
          </label>
          <select
            v-if="modelOptions.length"
            id="chat-model"
            v-model="modelSelection"
            class="model-select"
            :disabled="loadingModels"
          >
            <option 
              v-for="model in modelOptions" 
              :key="model" 
              :value="model"
              :disabled="settingsStore.llmEndpoint === 'ollama' && !supportsToolCalling(model)"
            >
              {{ model }}
              {{ settingsStore.llmEndpoint === 'ollama' && !supportsToolCalling(model) ? ' (No tool support)' : '' }}
            </option>
          </select>
          <input
            v-else
            id="chat-model"
            v-model="modelSelection"
            class="model-input"
            :placeholder="getModelPlaceholder()"
            :disabled="loadingModels"
          />
        </div>
        
        <div class="model-select-footer">
          <div class="model-select-meta">
            <span v-if="modelFetchError" class="error-message">⚠ {{ modelFetchError }}</span>
            <span v-else-if="!loadingModels && !modelOptions.length" class="info-message">
              ℹ No models loaded. Enter a model name manually or check your API key in Settings.
            </span>
            <span v-else-if="!loadingModels && modelOptions.length && settingsStore.llmEndpoint === 'ollama'" class="info-message">
              ℹ {{ modelOptions.length }} model(s) available. Models without tool support are disabled.
            </span>
            <span v-else-if="!loadingModels && modelOptions.length" class="success-message">
              ✓ {{ modelOptions.length }} model(s) available
            </span>
          </div>
          <button class="model-select-apply" @click="modelSelectOpen = false">Apply &amp; Close</button>
        </div>
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
              <div v-if="msg.role === 'assistant' && msg.timing_ms" class="msg-timing">
                {{ (msg.timing_ms / 1000).toFixed(1) }}s
              </div>
              <div
                v-if="msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length"
                class="tool-usage"
              >
                Tools used: {{ msg.tool_calls.length }}
                <span v-if="msg.tool_execution_errors">(errors: {{ msg.tool_execution_errors }})</span>
              </div>
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

.context-tag {
  color: white;
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
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: 8px;
    background: var(--card-bg);
    border: 2px solid var(--border-color);
    cursor: pointer;
    transition: all 0.2s;
    font-size: 0.9rem;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}
.model-info:hover {
    background: var(--button-bg);
    border-color: var(--primary-color);
    box-shadow: 0 4px 8px rgba(139, 92, 246, 0.15);
    transform: translateY(-1px);
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
    padding: 16px;
    border-radius: 12px;
    background: var(--card-bg);
    border: 2px solid var(--primary-color);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.model-select-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color);
}
.model-select-header h3 {
    margin: 0;
    font-size: 1rem;
    color: var(--text-color);
}
.model-select-close-icon {
    background: none;
    border: none;
    color: var(--text-color);
    font-size: 1.8rem;
    line-height: 1;
    cursor: pointer;
    padding: 0;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all 0.2s;
}
.model-select-close-icon:hover {
    background: var(--button-bg);
    color: var(--primary-color);
}
.model-select-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.model-select-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.provider-status {
    font-size: 0.75rem;
    font-weight: normal;
    padding: 2px 8px;
    border-radius: 12px;
}
.provider-status.status-ok {
    background: rgba(34, 197, 94, 0.15);
    color: #4ade80;
}
.provider-status.status-warning {
    background: rgba(251, 191, 36, 0.15);
    color: #fcd34d;
}
.loading-indicator {
    font-size: 0.8rem;
    color: var(--primary-color);
    font-weight: normal;
    animation: spin 1s linear infinite;
}
@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
.model-select,
.model-input {
    width: 100%;
    padding: 10px 12px;
    border: 2px solid var(--border-color);
    border-radius: 8px;
    background: var(--input-bg);
    color: var(--input-text);
    font-size: 0.95rem;
    transition: all 0.2s;
}
.model-select:focus,
.model-input:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
}
.model-select:disabled,
.model-input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
.model-select option:disabled {
    opacity: 0.5;
    color: #999;
    font-style: italic;
}
.model-select-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
}
.model-select-meta {
    flex: 1;
    font-size: 0.85rem;
}
.error-message {
    color: #ef4444;
}
.info-message {
    color: var(--text-color);
    opacity: 0.7;
}
.success-message {
    color: #22c55e;
}
.model-select-apply {
    padding: 8px 20px;
    border: none;
    border-radius: 8px;
    background: var(--primary-color);
    color: white;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}
.model-select-apply:hover {
    background: color-mix(in srgb, var(--primary-color) 85%, black);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
}
.chat-header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
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

.msg-timing {
  margin-top: 6px;
  font-size: 12px;
  opacity: 0.75;
}

.tool-usage {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.8;
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
