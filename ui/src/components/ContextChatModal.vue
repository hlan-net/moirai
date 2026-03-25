<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { authFetch } from '../utils/authFetch'
import { useChatContextStore } from '../stores/chatContext'
import { useSettingsStore } from '../stores/settings'

interface Message {
  role: 'user' | 'assistant'
  content: string
  tool_calls?: Array<{ name?: string; status?: string; error?: string }>
  tool_execution_errors?: number
  timing_ms?: number
}

interface QuickAction {
  label: string
  message: string
  action?: 'wizard'
}

const chatContextStore = useChatContextStore()
const settingsStore = useSettingsStore()

const messages = ref<Message[]>([])
const input = ref('')
const loading = ref(false)
const sessionId = ref<string | null>(null)
const copyStatus = ref('')
const pendingQuickAction = ref<QuickAction | null>(null)
const raiseWizardOpen = ref(false)
const raiseWizardLoading = ref(false)
const raiseWizardQuestions = ref<string[]>([])
const raiseWizardAnswers = ref<string[]>(['', '', ''])

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

const quickActions = computed<QuickAction[]>(() => {
  if (chatContextStore.contextType === 'article') {
    return [
      {
        label: 'Raise as Issue',
        message: 'Please create a new Issue from this article',
        action: 'wizard',
      },
      {
        label: 'Find Related Issues',
        message:
          'Search existing issues and find which ones this article could be linked to. ' +
          'Use keywords from the article title and summary to search. ' +
          'List the best matches with a short reason for each.',
      },
      {
        label: 'Summarize in 3 bullets',
        message:
          'Summarize the key points of this article in exactly 3 concise bullet points.',
      },
    ]
  }
  if (chatContextStore.contextType === 'issue') {
    return [
      {
        label: 'Refine Description',
        message: 'Help me refine the description of this Issue based on its linked articles',
      },
      {
        label: 'Find new coverage',
        message:
          'Search for recent articles that relate to this issue but are not yet linked to it. ' +
          'Use the issue name and description as search terms. ' +
          'List the most relevant matches and suggest which ones should be linked.',
      },
      {
        label: 'Write a brief',
        message:
          'Write a 2–3 paragraph press brief for this issue based on its description and linked articles. ' +
          'The brief should be suitable for sharing with an editorial team.',
      },
      {
        label: 'Seal this issue',
        message:
          'Help me close this issue. First provide a short closing summary of what happened and how it resolved, ' +
          'then call the seal_issue tool to mark it as sealed.',
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

  // Settings are automatically reactive from store
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
        model: settingsStore.getCurrentModel(),
        llm_endpoint: settingsStore.llmEndpoint,
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
        model: settingsStore.getCurrentModel(),
        llm_endpoint: settingsStore.llmEndpoint,
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
        model: settingsStore.getCurrentModel(),
        llm_endpoint: settingsStore.llmEndpoint,
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
        timing_ms: Number(payload.timing_ms || 0),
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

const askWizardQuestions = async () => {
  if (!chatContextStore.contextPayload) return
  raiseWizardLoading.value = true
  try {
    const response = await authFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message:
          'You are preparing issue creation from this article context. Ask exactly 3 concise clarifying questions that help define a reusable, generic issue. Return only a numbered list.',
        history: [],
        model: settingsStore.getCurrentModel(),
        llm_endpoint: settingsStore.llmEndpoint,
        context: chatContextStore.contextPayload,
      }),
    })

    if (response.ok) {
      const payload = await response.json()
      const lines = String(payload.response || '')
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => /^\d+[.)]\s+/.test(line))
        .slice(0, 3)
        .map((line) => line.replace(/^\d+[.)]\s+/, '').trim())

      if (lines.length === 3) {
        raiseWizardQuestions.value = lines
        return
      }
    }

    raiseWizardQuestions.value = [
      'What is the generic issue this article represents beyond this single event?',
      'What time horizon best matches the issue (short-term event, ongoing trend, or long arc)?',
      'Which core drivers or signals should define this issue for future matching?',
    ]
  } catch (error) {
    console.error('Failed to ask wizard questions:', error)
    raiseWizardQuestions.value = [
      'What is the generic issue this article represents beyond this single event?',
      'What time horizon best matches the issue (short-term event, ongoing trend, or long arc)?',
      'Which core drivers or signals should define this issue for future matching?',
    ]
  } finally {
    raiseWizardLoading.value = false
  }
}

const openRaiseWizard = async () => {
  raiseWizardOpen.value = true
  raiseWizardAnswers.value = ['', '', '']
  raiseWizardQuestions.value = []
  await askWizardQuestions()
}

const submitRaiseWizard = async () => {
  const q = raiseWizardQuestions.value
  const a = raiseWizardAnswers.value
  const articleId = chatContextStore.entityData?._id as string | undefined

  raiseWizardOpen.value = false
  loading.value = true

  const draftPrompt = [
    'Based on this article and the clarifications below, produce ONLY two lines:',
    'NAME: <concise generic issue name, max 100 chars>',
    'DESCRIPTION: <one-paragraph description of the issue, max 400 chars>',
    '',
    `1) ${q[0] || 'Issue framing'}: ${a[0] || '(not provided)'}`,
    `2) ${q[1] || 'Time horizon'}: ${a[1] || '(not provided)'}`,
    `3) ${q[2] || 'Core drivers'}: ${a[2] || '(not provided)'}`,
    '',
    'Output only the NAME: and DESCRIPTION: lines. No extra text.',
  ].join('\n')

  try {
    const draftRes = await authFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: draftPrompt,
        history: [],
        model: settingsStore.getCurrentModel(),
        llm_endpoint: settingsStore.llmEndpoint,
        context: chatContextStore.contextPayload,
      }),
    })

    if (!draftRes.ok) throw new Error('Failed to draft issue')

    const draft = await draftRes.json()
    const text: string = draft.response || ''
    const nameMatch = text.match(/^NAME:\s*(.+)/m)
    const descMatch = text.match(/^DESCRIPTION:\s*(.+)/ms)

    const name = nameMatch?.[1]?.trim() || 'Issue from article'
    const description = descMatch?.[1]?.split('\n')[0]?.trim() || text.trim()

    if (!articleId) {
      messages.value.push({ role: 'assistant', content: `Drafted issue but could not determine article ID. Name: **${name}**` })
      return
    }

    const createRes = await authFetch('/api/issues', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, article_links: [articleId] }),
    })

    if (createRes.ok) {
      const result = await createRes.json()
      messages.value.push({
        role: 'assistant',
        content: `Issue created: **${result.name}**\n\n${description}\n\n_ID: ${result.issue_id}_`,
      })
      await ensureSession(draftPrompt)
      await updateSession()
    } else {
      const err = await createRes.text()
      messages.value.push({ role: 'assistant', content: `Failed to create issue: ${err}` })
    }
  } catch (error) {
    messages.value.push({ role: 'assistant', content: `Error: ${String(error)}` })
  } finally {
    loading.value = false
  }
}

const applyQuickAction = (qa: QuickAction) => {
  pendingQuickAction.value = qa
}

const confirmQuickAction = async () => {
  if (!pendingQuickAction.value) return
  const { message, action } = pendingQuickAction.value
  pendingQuickAction.value = null
  if (action === 'wizard') {
    openRaiseWizard()
    return
  }
  input.value = message
  await sendMessage()
}

const declineQuickAction = () => {
  if (!pendingQuickAction.value) return
  const { message, action } = pendingQuickAction.value
  pendingQuickAction.value = null
  if (action === 'wizard') {
    // wizard has no prefill fallback — open it directly
    openRaiseWizard()
    return
  }
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
          <p class="model-meta">{{ settingsStore.llmEndpoint }} / {{ settingsStore.getCurrentModel() }}</p>
        </div>
        <div class="header-actions">
          <button
            class="icon-btn"
            @click="copyChat"
            :title="copyStatus || 'Copy chat to clipboard'"
            aria-label="Copy chat to clipboard"
          >
            <span aria-hidden="true">{{ copyStatus || '📋' }}</span>
            <span class="sr-only">Copy chat to clipboard</span>
          </button>
          <button class="close-btn" @click="closeModal" aria-label="Close contextual chat">×</button>
        </div>
      </header>

      <div v-if="quickActions.length" class="quick-actions">
        <button
          v-for="action in quickActions"
          :key="action.label"
          class="quick-action-btn"
          @click="applyQuickAction(action)"
        >
          {{ action.label }}
        </button>
      </div>

      <div v-if="pendingQuickAction" class="confirm-panel">
        <p class="confirm-label">{{ pendingQuickAction.label }}</p>
        <div class="confirm-actions">
          <button class="quick-action-btn confirm-yes" @click="confirmQuickAction">
            {{ pendingQuickAction.action === 'wizard' ? 'Open wizard' : 'Yes, run it' }}
          </button>
          <button
            v-if="pendingQuickAction.action !== 'wizard'"
            class="quick-action-btn"
            @click="declineQuickAction"
          >
            No, let me edit
          </button>
          <button class="quick-action-btn confirm-cancel" @click="pendingQuickAction = null">
            Cancel
          </button>
        </div>
      </div>

      <div v-if="raiseWizardOpen" class="wizard-panel">
        <h4>Issue Raise Wizard</h4>
        <p class="wizard-hint">Answer briefly so the issue is generic and reusable.</p>
        <div v-if="raiseWizardLoading" class="wizard-hint">Generating questions...</div>
        <div v-else>
          <div v-for="(question, index) in raiseWizardQuestions" :key="index" class="wizard-question">
            <label>{{ index + 1 }}. {{ question }}</label>
            <textarea v-model="raiseWizardAnswers[index]" rows="2"></textarea>
          </div>
          <div class="wizard-actions">
            <button class="quick-action-btn" @click="submitRaiseWizard">Create via Chat</button>
            <button class="quick-action-btn" @click="raiseWizardOpen = false">Cancel</button>
          </div>
        </div>
      </div>

      <div class="messages-area">
        <div v-if="!messages.length" class="empty-state">
          Ask a question about this {{ contextLabel.toLowerCase() }}.
        </div>
        <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
          <div class="bubble" v-html="renderMarkdown(message.content)"></div>
          <div v-if="message.role === 'assistant' && message.timing_ms" class="message-timing">
            {{ (message.timing_ms / 1000).toFixed(1) }}s
          </div>
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

.message-timing {
  margin-top: 4px;
  font-size: 0.75rem;
  opacity: 0.75;
}

.confirm-panel {
  border-bottom: 1px solid var(--border-color);
  padding: 10px 14px;
  background: var(--button-bg);
}

.confirm-label {
  margin: 0 0 8px;
  font-size: 0.9rem;
  font-weight: 600;
}

.confirm-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.confirm-yes {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.confirm-cancel {
  opacity: 0.7;
}

.wizard-panel {
  border-bottom: 1px solid var(--border-color);
  padding: 10px 14px;
}

.wizard-hint {
  margin: 4px 0 8px;
  font-size: 0.85rem;
  opacity: 0.8;
}

.wizard-question {
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.wizard-question textarea {
  width: 100%;
  border: 1px solid var(--border-color);
  background: var(--input-bg);
  color: var(--input-text);
  border-radius: 6px;
  padding: 8px;
  resize: vertical;
}

.wizard-actions {
  display: flex;
  gap: 8px;
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

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
</style>
