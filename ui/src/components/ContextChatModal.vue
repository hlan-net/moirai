<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { authFetch } from '../utils/authFetch'
import { useChatContextStore } from '../stores/chatContext'

interface Message {
  role: 'user' | 'assistant'
  content: string
  tool_calls?: Array<{ name?: string; status?: string; error?: string }>
  tool_execution_errors?: number
}

const chatContextStore = useChatContextStore()

const messages = ref<Message[]>([])
const input = ref('')
const loading = ref(false)
const sessionId = ref<string | null>(null)
const copyStatus = ref('')

const currentLlmEndpoint = ref(localStorage.getItem('moirai_llm_endpoint') || 'ollama')

const modelSettingsMap: Record<string, string> = {
  openai: 'moirai_openai_model',
  gemini: 'moirai_gemini_model',
  ollama: 'moirai_model',
}

const defaultModels: Record<string, string> = {
  openai: 'gpt-4-turbo',
  gemini: 'gemini-1.5-pro',
  ollama: 'llama3.1:latest',
}

const currentModel = ref(
  localStorage.getItem(modelSettingsMap[currentLlmEndpoint.value] || 'moirai_model') ||
    defaultModels[currentLlmEndpoint.value] ||
    'llama3.1:latest'
)

const modalContentRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
const previousActiveElement = ref<HTMLElement | null>(null)

let modalKeydownListenerAttached = false

const contextLabel = computed(() => {
  switch (chatContextStore.contextType) {
    case 'article':
      return 'Article'
    case 'issue':
      return 'Issue'
    case 'feed':
      return 'Feed'
    default:
      return 'Context'
  }
})

const contextEmoji = computed(() => {
  switch (chatContextStore.contextType) {
    case 'article':
      return '📰'
    case 'issue':
      return '🔗'
    case 'feed':
      return '📡'
    default:
      return '💬'
  }
})

const contextTitle = computed(() => {
  const data = chatContextStore.entityData || {}
  if (chatContextStore.contextType === 'article') {
    return String(data.title || 'Untitled article')
  }
  if (chatContextStore.contextType === 'issue') {
    return String(data.logos || 'Untitled issue')
  }
  if (chatContextStore.contextType === 'feed') {
    return String(data.title || data.url || 'Untitled feed')
  }
  return 'Context chat'
})

const quickActions = computed(() => {
  if (chatContextStore.contextType === 'article') {
    return [
      {
        label: 'Raise as Issue',
        message: 'Please create a new Issue from this article',
      },
    ]
  }
  if (chatContextStore.contextType === 'issue') {
    return [
      {
        label: 'Refine Description',
        message: 'Help me refine the description of this Issue based on its linked articles',
      },
    ]
  }
  if (chatContextStore.contextType === 'feed') {
    return [
      {
        label: "What's new?",
        message: 'What has this feed been covering recently?',
      },
    ]
  }
  return []
})

const stripInternalReminders = (content: string) => {
  if (!content) return content
  return content.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/gi, '').trim()
}

const renderMarkdown = (content: string) => {
  const cleaned = DOMPurify.sanitize(marked.parse(content || '') as string)
  return cleaned
}

const closeModal = () => {
  chatContextStore.close()
}

const handleModalKeydown = (event: KeyboardEvent) => {
  if (!modalContentRef.value) return

  if (event.key === 'Escape' || event.key === 'Esc') {
    closeModal()
    return
  }

  if (event.key !== 'Tab') return

  const focusableElements = modalContentRef.value.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  )
  if (!focusableElements.length) return

  const firstElement = focusableElements[0] as HTMLElement
  const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement

  if (event.shiftKey) {
    if (document.activeElement === firstElement) {
      event.preventDefault()
      lastElement.focus()
    }
  } else if (document.activeElement === lastElement) {
    event.preventDefault()
    firstElement.focus()
  }
}

const attachModalKeyListener = () => {
  if (modalKeydownListenerAttached) return
  globalThis.addEventListener('keydown', handleModalKeydown)
  modalKeydownListenerAttached = true
}

const detachModalKeyListener = () => {
  if (!modalKeydownListenerAttached) return
  globalThis.removeEventListener('keydown', handleModalKeydown)
  modalKeydownListenerAttached = false
}

const initializeModalState = async () => {
  messages.value = []
  sessionId.value = null
  input.value = chatContextStore.initialMessage || ''

  await nextTick()
  if (inputRef.value) {
    inputRef.value.focus()
  }
}

watch(
  () => chatContextStore.isOpen,
  async (isOpen) => {
    if (isOpen) {
      previousActiveElement.value = document.activeElement as HTMLElement
      await initializeModalState()
      attachModalKeyListener()
      return
    }

    detachModalKeyListener()
    if (previousActiveElement.value) {
      previousActiveElement.value.focus()
    }
  }
)

onUnmounted(() => {
  detachModalKeyListener()
})

const ensureSession = async (userMsg: string) => {
  if (sessionId.value) return true

  try {
    const response = await authFetch('/api/chat/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: userMsg,
        model: currentModel.value,
        llm_endpoint: currentLlmEndpoint.value,
        context: chatContextStore.contextPayload,
      }),
    })

    if (!response.ok) {
      return false
    }

    const payload = await response.json()
    sessionId.value = payload._id
    return true
  } catch (error) {
    console.error('Failed to create context chat session:', error)
    return false
  }
}

const updateSession = async () => {
  if (!sessionId.value) return
  try {
    await authFetch(`/api/chat/history/${sessionId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: messages.value,
        model: currentModel.value,
        llm_endpoint: currentLlmEndpoint.value,
        context: chatContextStore.contextPayload,
      }),
    })
  } catch (error) {
    console.error('Failed to persist context chat session:', error)
  }
}

const sendMessage = async () => {
  if (!input.value.trim() || loading.value || !chatContextStore.contextPayload) {
    return
  }

  const userMsg = input.value.trim()
  input.value = ''
  messages.value.push({ role: 'user', content: userMsg })
  loading.value = true

  try {
    await ensureSession(userMsg)

    const history = messages.value.slice(0, -1).map((message) => ({
      role: message.role,
      content: message.content,
    }))

    const response = await authFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userMsg,
        history,
        model: currentModel.value,
        llm_endpoint: currentLlmEndpoint.value,
        context: chatContextStore.contextPayload,
      }),
    })

    if (response.ok) {
      const payload = await response.json()
      messages.value.push({
        role: 'assistant',
        content: stripInternalReminders(payload.response || ''),
        tool_calls: Array.isArray(payload.tool_calls) ? payload.tool_calls : [],
        tool_execution_errors: Number(payload.tool_execution_errors || 0),
      })
    } else {
      const text = await response.text()
      messages.value.push({ role: 'assistant', content: `Error: ${text || response.statusText}` })
    }

    await updateSession()
  } catch (error) {
    messages.value.push({ role: 'assistant', content: `Error: ${String(error)}` })
    await updateSession()
  } finally {
    loading.value = false
  }
}

const applyQuickAction = (message: string) => {
  input.value = message
  if (inputRef.value) {
    inputRef.value.focus()
  }
}

const fallbackMarkdown = () => {
  return messages.value
    .map((msg) => `## ${msg.role === 'user' ? 'User' : 'Assistant'}\n\n${msg.content}`)
    .join('\n\n---\n\n')
}

const copyChat = async () => {
  try {
    let markdown = ''
    if (sessionId.value) {
      const response = await authFetch(`/api/chat/history/${sessionId.value}/export`)
      if (response.ok) {
        markdown = await response.text()
      }
    }

    if (!markdown) {
      markdown = fallbackMarkdown()
    }

    await navigator.clipboard.writeText(markdown)
    copyStatus.value = 'Copied'
  } catch (error) {
    console.error('Failed to copy contextual chat:', error)
    copyStatus.value = 'Copy failed'
  } finally {
    globalThis.setTimeout(() => {
      copyStatus.value = ''
    }, 1500)
  }
}
</script>

<template>
  <div v-if="chatContextStore.isOpen" class="modal-overlay" @click="closeModal">
    <dialog
      ref="modalContentRef"
      open
      class="context-chat-drawer"
      aria-labelledby="context-chat-title"
      @click.stop
    >
      <header class="drawer-header">
        <div class="header-title-block">
          <span class="context-badge">{{ contextEmoji }} {{ contextLabel }}</span>
          <h3 id="context-chat-title" class="context-title" :title="contextTitle">{{ contextTitle }}</h3>
          <p class="model-meta">{{ currentLlmEndpoint }} / {{ currentModel }}</p>
        </div>
        <div class="header-actions">
          <button
            class="icon-btn"
            @click="copyChat"
            :title="copyStatus || 'Copy chat to clipboard'"
            aria-label="Copy chat to clipboard"
          >
            {{ copyStatus || '📋' }}
          </button>
          <button class="close-btn" @click="closeModal" aria-label="Close contextual chat">×</button>
        </div>
      </header>

      <div v-if="quickActions.length" class="quick-actions">
        <button
          v-for="action in quickActions"
          :key="action.label"
          class="quick-action-btn"
          @click="applyQuickAction(action.message)"
        >
          {{ action.label }}
        </button>
      </div>

      <div class="messages-area">
        <div v-if="!messages.length" class="empty-state">
          Ask a question about this {{ contextLabel.toLowerCase() }}.
        </div>
        <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
          <div class="bubble" v-html="renderMarkdown(message.content)"></div>
        </div>
      </div>

      <footer class="input-row">
        <input
          ref="inputRef"
          v-model="input"
          type="text"
          placeholder="Ask about this context..."
          @keyup.enter="sendMessage"
        />
        <button @click="sendMessage" :disabled="loading || !input.trim()">
          {{ loading ? 'Sending...' : 'Send' }}
        </button>
      </footer>
    </dialog>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 2000;
  display: flex;
  justify-content: flex-end;
}

.context-chat-drawer {
  margin: 0 0 0 auto;
  padding: 0;
  border: none;
  outline: none;
  max-width: none;
  max-height: none;
  width: min(620px, 100%);
  height: 100%;
  background: var(--card-bg);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  box-shadow: -12px 0 24px rgba(0, 0, 0, 0.35);
}

.context-chat-drawer::backdrop {
  background: transparent;
}

.drawer-header {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  padding: 14px;
  border-bottom: 1px solid var(--border-color);
  background: var(--card-bg);
}

.header-title-block {
  min-width: 0;
}

.context-badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--button-bg);
  border: 1px solid var(--border-color);
}

.context-title {
  margin: 6px 0 2px;
  font-size: 1rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-meta {
  margin: 0;
  opacity: 0.6;
  font-size: 0.8rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  border: 1px solid var(--border-color);
  background: var(--button-bg);
  color: var(--text-color);
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 0.85rem;
}

.close-btn {
  border: none;
  background: transparent;
  color: var(--text-color);
  font-size: 1.4rem;
  cursor: pointer;
}

.quick-actions {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
}

.quick-action-btn {
  border: 1px solid var(--border-color);
  background: var(--button-bg);
  color: var(--text-color);
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 0.85rem;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.empty-state {
  opacity: 0.75;
  font-size: 0.9rem;
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
  max-width: 85%;
  padding: 10px 12px;
  border-radius: 10px;
  line-height: 1.45;
}

.message.user .bubble {
  background: var(--primary-color);
  color: white;
}

.message.assistant .bubble {
  background: var(--button-bg);
  border: 1px solid var(--border-color);
}

.input-row {
  display: flex;
  gap: 8px;
  padding: 12px 14px 14px;
  border-top: 1px solid var(--border-color);
}

.input-row input {
  flex: 1;
}

@media (max-width: 767px) {
  .context-chat-drawer {
    width: 100%;
  }
}
</style>
