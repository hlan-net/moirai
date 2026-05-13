<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionsStore, type SessionDoc, type SessionStep } from '../stores/sessions'
import { formatDate, formatDuration } from '../utils/formatters'

const route = useRoute()
const router = useRouter()
const sessionsStore = useSessionsStore()

const sessionId = computed(() => route.params.id as string)
const session = ref<SessionDoc | null>(null)
const steps = ref<SessionStep[]>([])
const loading = ref(true)
const error = ref('')
const cancelling = ref(false)
const cancelError = ref('')

let pollTimer: ReturnType<typeof setTimeout> | null = null

const SESSION_TYPE_LABELS: Record<SessionDoc['session_type'], string> = {
  scheduled_agent: 'Scheduled',
  on_new_article: 'On New Article',
  chat: 'Chat',
}

const STATUS_LABELS: Record<SessionDoc['status'], string> = {
  running: 'Running',
  success: 'Success',
  error: 'Error',
  cancelled: 'Cancelled',
}

const STEP_STATUS_LABELS: Record<SessionStep['status'], string> = {
  success: 'OK',
  error: 'Error',
  retried: 'Retried',
  pending_approval: 'Pending',
  denied: 'Denied',
}

const isRunning = computed(() => session.value?.status === 'running')

const load = async () => {
  loading.value = true
  error.value = ''
  const [sessionData, stepsData] = await Promise.all([
    sessionsStore.fetchSession(sessionId.value),
    sessionsStore.fetchSteps(sessionId.value),
  ])
  if (!sessionData) {
    error.value = 'Session not found.'
  } else {
    session.value = sessionData
    steps.value = stepsData
  }
  loading.value = false
}

const poll = async () => {
  if (!isRunning.value) return
  const [sessionData, stepsData] = await Promise.all([
    sessionsStore.fetchSession(sessionId.value),
    sessionsStore.fetchSteps(sessionId.value),
  ])
  if (sessionData) {
    session.value = sessionData
    steps.value = stepsData
  }
  if (isRunning.value) {
    pollTimer = setTimeout(poll, 3000)
  }
}

const cancel = async () => {
  cancelling.value = true
  cancelError.value = ''
  const ok = await sessionsStore.cancelSession(sessionId.value)
  if (!ok) {
    cancelError.value = 'Cancel request failed. Try again.'
  } else {
    await load()
  }
  cancelling.value = false
}

onMounted(async () => {
  await load()
  if (isRunning.value) {
    pollTimer = setTimeout(poll, 3000)
  }
})

onUnmounted(() => {
  if (pollTimer !== null) clearTimeout(pollTimer)
})
</script>

<template>
  <div class="detail-page">
    <div class="back-row">
      <button type="button" class="back-btn" @click="router.push('/sessions')">← Sessions</button>
    </div>

    <div v-if="loading" class="empty-state">Loading…</div>
    <div v-else-if="error" class="error-message">{{ error }}</div>

    <template v-else-if="session">
      <section class="card meta-card">
        <header class="meta-header">
          <div>
            <h1 class="session-title">
              {{ SESSION_TYPE_LABELS[session.session_type] }}
              <span v-if="session.agent_name" class="agent-name">— {{ session.agent_name }}</span>
            </h1>
            <p class="muted">{{ formatDate(session.started_at) }}</p>
          </div>
          <div class="header-right">
            <span class="status-pill" :class="`status-${session.status}`">
              {{ STATUS_LABELS[session.status] }}
            </span>
            <button
              v-if="isRunning"
              type="button"
              class="cancel-btn"
              :disabled="cancelling"
              @click="cancel"
            >
              {{ cancelling ? 'Cancelling…' : 'Cancel Session' }}
            </button>
          </div>
        </header>

        <div v-if="cancelError" class="cancel-error">{{ cancelError }}</div>

        <dl class="meta-grid">
          <div class="meta-item">
            <dt>Duration</dt>
            <dd>{{ formatDuration(session.duration_ms) }}</dd>
          </div>
          <div class="meta-item">
            <dt>Steps</dt>
            <dd>{{ session.step_count ?? steps.length }}</dd>
          </div>
          <div class="meta-item">
            <dt>Tool calls</dt>
            <dd>{{ session.tool_calls }}</dd>
          </div>
          <div class="meta-item">
            <dt>LLM calls</dt>
            <dd>{{ session.llm_calls }}</dd>
          </div>
          <div class="meta-item">
            <dt>Articles</dt>
            <dd>{{ session.articles_processed }}</dd>
          </div>
          <div v-if="session.error" class="meta-item meta-error-row">
            <dt>Error</dt>
            <dd class="error-text">{{ session.error }}</dd>
          </div>
        </dl>
      </section>

      <section class="card steps-card">
        <h2 class="steps-heading">Step Timeline</h2>

        <div v-if="steps.length === 0" class="empty-state">No steps recorded for this session.</div>

        <ol v-else class="step-list">
          <li v-for="(step, idx) in steps" :key="step.step_id || idx" class="step-item">
            <div class="step-connector" aria-hidden="true">
              <span class="step-dot" :class="`dot-${step.status}`"></span>
              <span v-if="idx < steps.length - 1" class="step-line"></span>
            </div>

            <div class="step-body">
              <div class="step-top">
                <span class="tool-name">{{ step.tool_name || step.step_type }}</span>
                <span class="step-badges">
                  <span
                    v-if="step.risk_level === 'destructive'"
                    class="badge badge-destructive"
                    title="Destructive tool"
                  >!</span>
                  <span v-if="(step.attempt ?? 1) > 1" class="badge badge-attempt">
                    attempt {{ step.attempt }}
                  </span>
                  <span class="step-status" :class="`step-status-${step.status}`">
                    {{ STEP_STATUS_LABELS[step.status] }}
                  </span>
                  <span v-if="step.latency_ms !== undefined" class="step-latency">
                    {{ formatDuration(step.latency_ms) }}
                  </span>
                </span>
              </div>

              <div v-if="step.input_summary" class="step-summary">
                <span class="summary-label">In</span>
                <code class="summary-text">{{ step.input_summary }}</code>
              </div>

              <div v-if="step.output_summary" class="step-summary">
                <span class="summary-label">Out</span>
                <code class="summary-text">{{ step.output_summary }}</code>
              </div>

              <div v-if="step.error_message" class="step-error">{{ step.error_message }}</div>
            </div>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.back-row {
  display: flex;
  align-items: center;
}

.back-btn {
  background: none;
  border: none;
  color: var(--accent-color, #4a90e2);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0;
}

.back-btn:hover {
  text-decoration: underline;
}

.meta-card,
.steps-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.meta-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.session-title {
  margin: 0 0 4px 0;
  font-size: 1.2rem;
}

.agent-name {
  font-weight: 400;
  color: var(--text-muted, #888);
}

.muted {
  color: var(--text-muted, #888);
  margin: 0;
  font-size: 0.85rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.status-pill {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.status-pill.status-running {
  background-color: #1e5fa8;
  color: white;
}

.status-pill.status-success {
  background-color: #166534;
  color: white;
}

.status-pill.status-error {
  background-color: #d9534f;
  color: white;
}

.status-pill.status-cancelled {
  background-color: #6c757d;
  color: white;
}

.cancel-btn {
  padding: 6px 14px;
  background-color: #d9534f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
}

.cancel-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cancel-error {
  padding: 8px 12px;
  background-color: #d9534f;
  border: 1px solid #b94440;
  border-radius: 4px;
  color: white;
  font-size: 0.85rem;
}

.meta-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 32px;
  margin: 0;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 80px;
}

.meta-item dt {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #888);
}

.meta-item dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
}

.meta-error-row {
  flex-basis: 100%;
}

.error-text {
  color: #d9534f;
  word-break: break-word;
}

.steps-heading {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.step-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.step-item {
  display: flex;
  gap: 12px;
}

.step-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 16px;
  flex-shrink: 0;
  padding-top: 3px;
}

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-success {
  background-color: #166534;
}

.dot-error {
  background-color: #d9534f;
}

.dot-retried {
  background-color: #b45309;
}

.dot-pending_approval {
  background-color: #1e5fa8;
}

.dot-denied {
  background-color: #6c757d;
}

.step-line {
  width: 2px;
  flex: 1;
  background-color: var(--border-color, rgba(255, 255, 255, 0.12));
  margin-top: 4px;
  min-height: 12px;
}

.step-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 16px;
}

.step-top {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}

.tool-name {
  font-weight: 600;
  font-size: 0.9rem;
  word-break: break-word;
}

.step-badges {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 700;
}

.badge-destructive {
  background-color: #7c2d12;
  color: #fef2f2;
}

.badge-attempt {
  background-color: rgba(255, 255, 255, 0.1);
  color: var(--text-muted, #888);
}

.step-status {
  font-size: 0.75rem;
  font-weight: 600;
}

.step-status-success {
  color: #4ade80;
}

.step-status-error {
  color: #f87171;
}

.step-status-retried {
  color: #fbbf24;
}

.step-status-pending_approval {
  color: #60a5fa;
}

.step-status-denied {
  color: #9ca3af;
}

.step-latency {
  font-size: 0.75rem;
  color: var(--text-muted, #888);
  font-variant-numeric: tabular-nums;
}

.step-summary {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.summary-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--text-muted, #888);
  padding-top: 2px;
  flex-shrink: 0;
  width: 22px;
}

.summary-text {
  font-size: 0.8rem;
  color: var(--text-muted, #aaa);
  word-break: break-all;
  white-space: pre-wrap;
  font-family: monospace;
}

.step-error {
  font-size: 0.8rem;
  color: #f87171;
  word-break: break-word;
}

.error-message {
  padding: 10px 14px;
  background-color: #d9534f;
  border: 1px solid #b94440;
  border-radius: 4px;
  color: white;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted, #888);
}
</style>
