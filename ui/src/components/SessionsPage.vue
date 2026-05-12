<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useSessionsStore, type SessionDoc } from '../stores/sessions'
import { formatDate, formatDuration } from '../utils/formatters'

const router = useRouter()
const sessionsStore = useSessionsStore()
const { userspaces, currentUserspace, sessions, loading, loadingUserspaces, error } =
  storeToRefs(sessionsStore)

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

const hasSessions = computed(() => sessions.value.length > 0)

const onUserspaceChange = async () => {
  await sessionsStore.loadSessions()
}

const refresh = () => sessionsStore.loadSessions()

const openSession = (sessionId: string) => {
  router.push(`/sessions/${sessionId}`)
}

const sessionTypeLabel = (type: SessionDoc['session_type']) => SESSION_TYPE_LABELS[type] || type

const statusLabel = (status: SessionDoc['status']) => STATUS_LABELS[status] || status

const statusClass = (status: SessionDoc['status']) => `status-${status}`

onMounted(async () => {
  await sessionsStore.loadUserspaces()
  await sessionsStore.loadSessions()
})
</script>

<template>
  <div class="sessions-page">
    <section class="card">
      <header class="header">
        <div class="title-block">
          <h1>Sessions</h1>
          <p class="muted">Agent runs and chat turns from the last 7 days.</p>
        </div>
        <div class="controls">
          <label class="userspace-picker">
            <span class="label-text">Userspace</span>
            <select
              :value="currentUserspace"
              :disabled="loadingUserspaces"
              @change="
                (e) => {
                  sessionsStore.setCurrentUserspace((e.target as HTMLSelectElement).value)
                  onUserspaceChange()
                }
              "
            >
              <option value="" disabled>
                {{ loadingUserspaces ? 'Loading…' : 'Select a userspace' }}
              </option>
              <option v-for="us in userspaces" :key="us" :value="us">{{ us }}</option>
            </select>
          </label>
          <button type="button" class="refresh-btn" :disabled="loading" @click="refresh">
            {{ loading ? 'Loading…' : 'Refresh' }}
          </button>
        </div>
      </header>

      <div v-if="error" class="error-message">{{ error }}</div>

      <div v-if="!currentUserspace && !loadingUserspaces" class="empty-state">
        Select a userspace to see its sessions.
      </div>

      <div v-else-if="loading && !hasSessions" class="empty-state">Loading sessions…</div>

      <div v-else-if="!hasSessions" class="empty-state">
        No sessions in the last 7 days for this userspace.
      </div>

      <table v-else class="sessions-table">
        <thead>
          <tr>
            <th>Started</th>
            <th>Type</th>
            <th>Agent</th>
            <th>Status</th>
            <th class="numeric">Duration</th>
            <th class="numeric">Steps</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="session in sessions"
            :key="session.session_id"
            class="row"
            @click="openSession(session.session_id)"
          >
            <td>{{ formatDate(session.started_at) }}</td>
            <td>{{ sessionTypeLabel(session.session_type) }}</td>
            <td class="agent-cell">{{ session.agent_name || '—' }}</td>
            <td>
              <span class="status-pill" :class="statusClass(session.status)">
                {{ statusLabel(session.status) }}
              </span>
            </td>
            <td class="numeric">{{ formatDuration(session.duration_ms) }}</td>
            <td class="numeric">{{ session.step_count ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.sessions-page {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
  box-sizing: border-box;
}

.header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.title-block h1 {
  margin: 0 0 4px 0;
}

.muted {
  color: var(--text-muted, #888);
  margin: 0;
  font-size: 0.9rem;
}

.controls {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}

.userspace-picker {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label-text {
  font-size: 0.8rem;
  color: var(--text-muted, #888);
}

.userspace-picker select {
  min-width: 240px;
  padding: 6px 10px;
  background-color: var(--card-bg);
  color: var(--text-color);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.15));
  border-radius: 4px;
}

.refresh-btn {
  padding: 8px 16px;
  background-color: var(--accent-color, #4a90e2);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  padding: 10px 14px;
  margin: 12px 0;
  background-color: rgba(220, 53, 69, 0.15);
  border: 1px solid rgba(220, 53, 69, 0.4);
  border-radius: 4px;
  color: #f5c2c7;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted, #888);
}

.sessions-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}

.sessions-table th,
.sessions-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
}

.sessions-table th {
  font-weight: 600;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted, #888);
}

.sessions-table .numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.sessions-table .agent-cell {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row {
  cursor: pointer;
  transition: background-color 0.15s;
}

.row:hover {
  background-color: rgba(255, 255, 255, 0.04);
}

.status-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.status-pill.status-running {
  background-color: rgba(74, 144, 226, 0.2);
  color: #6bb0ff;
}

.status-pill.status-success {
  background-color: rgba(40, 167, 69, 0.2);
  color: #6fd28a;
}

.status-pill.status-error {
  background-color: rgba(220, 53, 69, 0.2);
  color: #f5c2c7;
}

.status-pill.status-cancelled {
  background-color: rgba(255, 255, 255, 0.1);
  color: var(--text-muted, #888);
}
</style>
