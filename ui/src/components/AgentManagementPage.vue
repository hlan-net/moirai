<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { authFetch } from '../utils/authFetch'
import { ALLOWED_LOGIC_MODULES } from '../utils/agentConstants'

const authStore = useAuthStore()

// Single source of truth: mirrors api/validation.py::ALLOWED_LOGIC_MODULES
const logicModules = ALLOWED_LOGIC_MODULES

const triggerTypes = ['on_new_article', 'scheduled']
const statuses = ['active', 'paused']
const targetDbs = ['articles', 'issues']

const draftAgent = ref({
  name: '',
  userspace: '',
  owner_user_id: '',
  status: 'active',
  trigger_type: 'scheduled',
  schedule_interval: '1d',
  target_db: 'issues',
  logic_module: 'tasks.agent_logic.check_event_staleness',
  linked_entity_id: '',
  parameters: '{\n  "staleness_threshold_days": 30\n}',
})

type AgentDoc = {
  _id: string
  name: string
  userspace: string
  owner_user_id: string
  status: string
  trigger_type: string
  target_db: string
  logic_module: string
  schedule_interval?: string
  linked_entity_id?: string
}

const agents = ref<AgentDoc[]>([])
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const ownerHint = computed(() => {
  return authStore.user?._id || authStore.user?.id || ''
})

const userspaceReady = computed(() => draftAgent.value.userspace.trim().length > 0)

const setTemplate = (template: 'stale' | 'discover' | 'enrich') => {
  if (template === 'stale') {
    draftAgent.value.trigger_type = 'scheduled'
    draftAgent.value.schedule_interval = '1d'
    draftAgent.value.target_db = 'issues'
    draftAgent.value.logic_module = 'tasks.agent_logic.check_event_staleness'
    draftAgent.value.parameters = '{\n  "staleness_threshold_days": 30\n}'
    return
  }

  if (template === 'discover') {
    draftAgent.value.trigger_type = 'on_new_article'
    draftAgent.value.schedule_interval = ''
    draftAgent.value.target_db = 'articles'
    draftAgent.value.logic_module = 'tasks.agent_logic.create_event_from_articles'
    draftAgent.value.parameters = '{\n  "topic": "energy transition"\n}'
    return
  }

  draftAgent.value.trigger_type = 'on_new_article'
  draftAgent.value.schedule_interval = ''
  draftAgent.value.target_db = 'articles'
  draftAgent.value.logic_module = 'tasks.agent_logic.add_articles_to_event'
  draftAgent.value.parameters = '{\n  "min_relevance": 0.7\n}'
}

const resetFeedback = () => {
  errorMessage.value = ''
  successMessage.value = ''
}

const loadAgents = async () => {
  resetFeedback()
  if (!userspaceReady.value) {
    agents.value = []
    return
  }

  loading.value = true
  try {
    const response = await authFetch(
      `/api/agents?userspace=${encodeURIComponent(draftAgent.value.userspace)}&owner_only=true`
    )
    if (!response.ok) {
      const msg = await response.text()
      throw new Error(msg || 'Failed to load agents')
    }
    agents.value = await response.json()
  } catch (error) {
    errorMessage.value = `Load failed: ${String(error)}`
  } finally {
    loading.value = false
  }
}

const createAgent = async () => {
  resetFeedback()
  saving.value = true
  try {
    const ownerUserId = draftAgent.value.owner_user_id.trim() || ownerHint.value
    const parsedParameters = draftAgent.value.parameters.trim()
      ? JSON.parse(draftAgent.value.parameters)
      : {}

    const payload = {
      name: draftAgent.value.name,
      userspace: draftAgent.value.userspace,
      owner_user_id: ownerUserId,
      status: draftAgent.value.status,
      trigger_type: draftAgent.value.trigger_type,
      schedule_interval:
        draftAgent.value.trigger_type === 'scheduled'
          ? draftAgent.value.schedule_interval
          : undefined,
      target_db: draftAgent.value.target_db,
      logic_module: draftAgent.value.logic_module,
      linked_entity_id: draftAgent.value.linked_entity_id || undefined,
      parameters: parsedParameters,
    }

    const response = await authFetch('/api/agents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const msg = await response.text()
      throw new Error(msg || 'Failed to create agent')
    }

    successMessage.value = 'Agent created'
    await loadAgents()
  } catch (error) {
    errorMessage.value = `Create failed: ${String(error)}`
  } finally {
    saving.value = false
  }
}

const deleteAgent = async (agentId: string) => {
  resetFeedback()
  try {
    const response = await authFetch(
      `/api/agents/${encodeURIComponent(agentId)}?userspace=${encodeURIComponent(draftAgent.value.userspace)}`,
      { method: 'DELETE' }
    )
    if (!response.ok) {
      const msg = await response.text()
      throw new Error(msg || 'Failed to delete agent')
    }

    successMessage.value = 'Agent deleted'
    await loadAgents()
  } catch (error) {
    errorMessage.value = `Delete failed: ${String(error)}`
  }
}

onMounted(() => {
  if (ownerHint.value) {
    draftAgent.value.owner_user_id = ownerHint.value
  }
})
</script>

<template>
  <div class="agent-management-page">
    <section class="hero card">
      <h1>Agents</h1>
      <p>
        Agents are background automations scoped to a single <strong>userspace</strong>.
        They run with the owning user&apos;s model credentials and never cross userspace boundaries.
      </p>
      <ul>
        <li>Trigger types: <code>on_new_article</code>, <code>scheduled</code></li>
        <li>Agent status: <code>active</code>, <code>paused</code>, <code>error</code></li>
        <li>Allowed logic modules are pre-whitelisted for safety</li>
      </ul>
    </section>

    <section class="card">
      <h2>Suggested Templates</h2>
      <div class="template-grid">
        <button class="template" @click="setTemplate('stale')">
          <strong>Daily Staleness Sweep</strong>
          <span>scheduled · issues · check_event_staleness</span>
        </button>
        <button class="template" @click="setTemplate('discover')">
          <strong>Event Discovery</strong>
          <span>on_new_article · articles · create_event_from_articles</span>
        </button>
        <button class="template" @click="setTemplate('enrich')">
          <strong>Event Enrichment</strong>
          <span>on_new_article · articles · add_articles_to_event</span>
        </button>
      </div>
    </section>

    <section class="card">
      <h2>Create Agent</h2>
      <p class="muted">Userspace-scoped config with owner-bound credentials.</p>

      <div class="form-grid">
        <label>
          Name
          <input v-model="draftAgent.name" type="text" placeholder="Quarterly policy monitor" />
        </label>

        <label>
          Userspace (UUID)
          <input v-model="draftAgent.userspace" type="text" placeholder="00000000-0000-0000-0000-000000000000" />
        </label>

        <label>
          Owner User ID (UUID)
          <input
            v-model="draftAgent.owner_user_id"
            type="text"
            :placeholder="ownerHint || 'User UUID that owns API keys'"
          />
        </label>

        <label>
          Status
          <select v-model="draftAgent.status">
            <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>

        <label>
          Trigger
          <select v-model="draftAgent.trigger_type">
            <option v-for="trigger in triggerTypes" :key="trigger" :value="trigger">{{ trigger }}</option>
          </select>
        </label>

        <label>
          Schedule Interval
          <input
            v-model="draftAgent.schedule_interval"
            type="text"
            placeholder="1h, 6h, 1d"
            :disabled="draftAgent.trigger_type !== 'scheduled'"
          />
        </label>

        <label>
          Target DB
          <select v-model="draftAgent.target_db">
            <option v-for="targetDb in targetDbs" :key="targetDb" :value="targetDb">{{ targetDb }}</option>
          </select>
        </label>

        <label>
          Logic Module
          <select v-model="draftAgent.logic_module">
            <option v-for="logic in logicModules" :key="logic" :value="logic">{{ logic }}</option>
          </select>
        </label>

        <label>
          Linked Entity ID (optional)
          <input v-model="draftAgent.linked_entity_id" type="text" placeholder="Event/Issue UUID" />
        </label>
      </div>

      <label class="full-width">
        Parameters JSON
        <textarea v-model="draftAgent.parameters" rows="8" />
      </label>

      <div class="actions">
        <button class="secondary" type="button" @click="loadAgents" :disabled="loading || !userspaceReady">
          {{ loading ? 'Loading...' : 'Refresh List' }}
        </button>
        <button type="button" @click="createAgent" :disabled="saving || !userspaceReady || !draftAgent.name.trim()">
          {{ saving ? 'Creating...' : 'Create Agent' }}
        </button>
      </div>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
    </section>

    <section class="card">
      <h2>Existing Agents (This Userspace)</h2>
      <div v-if="!userspaceReady" class="muted">Enter a userspace UUID to load agents.</div>
      <div v-else-if="loading" class="muted">Loading agents...</div>
      <div v-else-if="!agents.length" class="muted">No agents found in this userspace.</div>
      <div v-else class="agent-list">
        <article v-for="agent in agents" :key="agent._id" class="agent-item">
          <div>
            <strong>{{ agent.name }}</strong>
            <div class="agent-meta">
              <span>{{ agent.status }}</span>
              <span>{{ agent.trigger_type }}</span>
              <span>{{ agent.target_db }}</span>
            </div>
            <code>{{ agent.logic_module }}</code>
          </div>
          <button class="danger" type="button" @click="deleteAgent(agent._id)">Delete</button>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.agent-management-page {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
  max-width: 960px;
  margin: 0 auto;
  display: grid;
  gap: 16px;
}

.card {
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  border-radius: 10px;
  padding: 16px;
}

.hero {
  background: linear-gradient(145deg, color-mix(in srgb, var(--card-bg) 90%, transparent), var(--card-bg));
}

h1,
h2 {
  margin: 0 0 10px;
}

p {
  margin: 0 0 10px;
}

.muted {
  opacity: 0.75;
}

ul {
  margin: 0;
  padding-left: 18px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.template {
  text-align: left;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--input-bg);
  color: var(--input-text);
  padding: 10px;
  cursor: pointer;
  display: grid;
  gap: 5px;
}

.template:hover {
  border-color: var(--primary-color);
}

.template span {
  font-size: 0.85rem;
  opacity: 0.75;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 600;
}

input,
select,
textarea {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 8px;
  background: var(--input-bg);
  color: var(--input-text);
  font: inherit;
}

textarea {
  resize: vertical;
}

.full-width {
  margin-top: 12px;
}

.actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}

button {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 8px 12px;
  background: var(--primary-color);
  color: var(--bg-color);
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.secondary {
  background: transparent;
  color: var(--text-color);
}

.danger {
  background: transparent;
  color: #d9534f;
}

.error-text {
  margin-top: 10px;
  color: #d9534f;
}

.success-text {
  margin-top: 10px;
  color: #2d8a5f;
}

.agent-list {
  display: grid;
  gap: 10px;
}

.agent-item {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.agent-meta {
  display: flex;
  gap: 10px;
  opacity: 0.8;
  font-size: 0.9rem;
  margin: 4px 0;
}
</style>
