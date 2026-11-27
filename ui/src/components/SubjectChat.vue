<script setup lang="ts">
// The conversation about one subject of the Stream page's side column (#376):
// an article or an issue. The subject is the chat's context, so the reader
// never names it. The conversation is stored in the chat history and found
// again by its subject, so opening the same subject continues it.
import { nextTick, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { authFetch } from '../utils/authFetch'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  tool_calls?: unknown[]
  tool_execution_errors?: number
  timing_ms?: number
}

const props = defineProps<{
  contextType: 'article' | 'issue'
  entityId: string
  entityData: Record<string, unknown>
  placeholder: string
}>()

// The assistant used tools in its last answer; the subject may have changed.
const emit = defineEmits<{ toolsUsed: [] }>()

const messages = ref<ChatMessage[]>([])
const input = ref('')
const loading = ref(false)
const restoring = ref(false)
const sessionId = ref<string | null>(null)
// The scrolling area: the subject's own text (the slot) and the messages.
const scroller = ref<HTMLElement | null>(null)

// Every load and send belongs to the subject it started on. If the reader
// has moved to another subject meanwhile, its result is dropped.
let generation = 0

const contextPayload = () => ({
  type: props.contextType,
  entity_id: props.entityId,
  entity_data: props.entityData,
})

const stripInternalReminders = (content: string) =>
  content.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/gi, '').trim()

const renderMarkdown = (content: string) =>
  DOMPurify.sanitize(marked.parse(content || '') as string)

const scrollToEnd = async () => {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

// A new subject starts from its own text, at the top.
const scrollToStart = () => {
  if (scroller.value) scroller.value.scrollTop = 0
}

const restore = async () => {
  const mine = ++generation
  messages.value = []
  sessionId.value = null
  input.value = ''
  loading.value = false
  restoring.value = true
  scrollToStart()
  try {
    const params = new URLSearchParams({
      context_type: props.contextType,
      entity_id: props.entityId,
    })
    const response = await authFetch(`/api/chat/history?${params.toString()}`)
    if (mine !== generation || !response.ok) return
    const sessions = await response.json()
    const latest = Array.isArray(sessions) ? sessions[0] : null
    if (!latest) return
    sessionId.value = latest._id
    messages.value = (Array.isArray(latest.messages) ? latest.messages : []).filter(
      (m: ChatMessage) => (m.role === 'user' || m.role === 'assistant') && m.content
    )
    void scrollToEnd()
  } catch (error) {
    if (mine === generation) console.error('Failed to load the conversation:', error)
  } finally {
    if (mine === generation) restoring.value = false
  }
}

const ensureSession = async (firstMessage: string, context: object, mine: number) => {
  if (sessionId.value) return
  const response = await authFetch('/api/chat/history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: firstMessage.slice(0, 60), context }),
  })
  if (!response.ok) return
  const created = await response.json()
  // The session belongs to the subject it was created for.
  if (mine === generation) sessionId.value = created._id
}

const persist = async (context: object) => {
  if (!sessionId.value) return
  try {
    await authFetch(`/api/chat/history/${sessionId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: messages.value, context }),
    })
  } catch (error) {
    console.error('Failed to save the conversation:', error)
  }
}

const send = async () => {
  const text = input.value.trim()
  if (!text || loading.value || restoring.value) return
  // The subject of this message is fixed here: every request below uses this
  // context, and stops if the reader has moved to another subject meanwhile.
  const mine = generation
  const context = contextPayload()
  const history = messages.value.map(({ role, content }) => ({ role, content }))
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  void scrollToEnd()

  let usedTools = false
  try {
    await ensureSession(text, context, mine)
    if (mine !== generation) return
    // No model or provider is sent: the server uses the deployment's chat model.
    const response = await authFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history, context }),
    })
    if (mine !== generation) return
    if (response.ok) {
      const payload = await response.json()
      const toolCalls = Array.isArray(payload.tool_calls) ? payload.tool_calls : []
      usedTools = toolCalls.length > 0
      messages.value.push({
        role: 'assistant',
        content: stripInternalReminders(payload.response || ''),
        tool_calls: toolCalls,
        tool_execution_errors: Number(payload.tool_execution_errors || 0),
        timing_ms: Number(payload.timing_ms || 0),
      })
    } else {
      const body = await response.text()
      messages.value.push({ role: 'assistant', content: `Error: ${body || response.statusText}` })
    }
  } catch (error) {
    if (mine !== generation) return
    messages.value.push({ role: 'assistant', content: `Error: ${String(error)}` })
  } finally {
    if (mine === generation) {
      loading.value = false
      await persist(context)
      void scrollToEnd()
      if (usedTools) emit('toolsUsed')
    }
  }
}

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void send()
  }
}

watch(() => `${props.contextType}:${props.entityId}`, restore, { immediate: true })
</script>

<template>
  <section class="subject-chat" aria-label="Conversation">
    <!-- One scrolling area from the header down: what the subject is, then
         the conversation about it. Only the conversation is a live region. -->
    <div ref="scroller" class="chat-scroll">
      <slot />
      <div class="chat-log" role="log" aria-live="polite">
        <p v-if="restoring" class="chat-hint">Loading the conversation…</p>
        <p v-else-if="messages.length === 0" class="chat-hint">{{ placeholder }}</p>
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="chat-message"
          :class="message.role"
        >
          <div class="chat-role">{{ message.role === 'user' ? 'You' : 'Moirai' }}</div>
          <div v-if="message.role === 'user'" class="chat-text">{{ message.content }}</div>
          <div v-else class="chat-text markdown" v-html="renderMarkdown(message.content)"></div>
          <div v-if="message.tool_calls?.length" class="chat-meta">
            {{ message.tool_calls.length }} tool call{{ message.tool_calls.length === 1 ? '' : 's'
            }}<span v-if="message.tool_execution_errors">
              , {{ message.tool_execution_errors }} failed</span
            >
          </div>
        </div>
        <p v-if="loading" class="chat-hint">Thinking…</p>
      </div>
    </div>

    <form class="chat-form" @submit.prevent="send">
      <textarea
        v-model="input"
        class="chat-input"
        rows="2"
        aria-label="Message"
        :placeholder="placeholder"
        :disabled="restoring"
        @keydown="onKeydown"
      ></textarea>
      <button type="submit" class="chat-send" :disabled="loading || restoring || !input.trim()">
        Send
      </button>
    </form>
  </section>
</template>

<style scoped>
.subject-chat {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.chat-scroll {
  flex: 1;
  min-height: 80px;
  overflow-y: auto;
  padding-inline-end: 6px;
}

.chat-log {
  padding: 4px 2px;
}

.chat-hint {
  margin: 8px 0;
  font-size: 0.85rem;
  font-style: italic;
  opacity: 0.7;
}

.chat-message {
  margin: 0 0 12px;
}

.chat-role {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.7;
}

.chat-text {
  font-size: 0.9rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.chat-message.user .chat-text {
  white-space: pre-wrap;
}

.chat-text.markdown :deep(p) {
  margin: 0.3em 0;
}

/* An answer's headings stay the size of the column's own text. */
.chat-text.markdown :deep(h1),
.chat-text.markdown :deep(h2),
.chat-text.markdown :deep(h3),
.chat-text.markdown :deep(h4) {
  margin: 0.8em 0 0.3em;
  font-size: 1rem;
  line-height: 1.3;
}

.chat-text.markdown :deep(ul),
.chat-text.markdown :deep(ol) {
  margin: 0.3em 0;
  padding-inline-start: 1.3em;
}

.chat-text.markdown :deep(pre) {
  overflow-x: auto;
  padding: 8px;
  border-radius: 4px;
  background: var(--button-bg);
  font-size: 0.8rem;
}

.chat-meta {
  margin-top: 2px;
  font-size: 0.75rem;
  opacity: 0.65;
}

.chat-form {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}

.chat-input {
  flex: 1;
  resize: vertical;
  min-height: 2.6em;
  padding: 6px 8px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--input-bg);
  color: var(--input-text);
  font: inherit;
  font-size: 0.9rem;
}

.chat-send {
  padding: 8px 14px;
  font-size: 0.9rem;
}

.chat-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
