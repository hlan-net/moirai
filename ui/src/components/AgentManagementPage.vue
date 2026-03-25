<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import { authFetch } from '../utils/authFetch'
import { ALLOWED_LOGIC_MODULES, LOGIC_MODULE_INFO, TRIGGER_TYPE_INFO } from '../utils/agentConstants'

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
const userspaces = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const loadingUserspaces = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const showAdvanced = ref(false)

const ownerHint = computed(() => {
  return authStore.user?._id || authStore.user?.id || ''
})

const userspaceReady = computed(() => draftAgent.value.userspace.trim().length > 0)

const selectedModuleInfo = computed(() => {
  return LOGIC_MODULE_INFO[draftAgent.value.logic_module] || null
})

const selectedTriggerInfo = computed(() => {
  return TRIGGER_TYPE_INFO[draftAgent.value.trigger_type] || null
})

const setTemplate = (template: 'stale' | 'discover' | 'enrich') => {
  if (template === 'stale') {
    draftAgent.value.name = 'Daily Staleness Sweep'
    draftAgent.value.trigger_type = 'scheduled'
    draftAgent.value.schedule_interval = '1d'
    draftAgent.value.target_db = 'issues'
    draftAgent.value.logic_module = 'tasks.agent_logic.check_event_staleness'
    draftAgent.value.parameters = '{\n  "staleness_threshold_days": 30\n}'
    return
  }

  if (template === 'discover') {
    draftAgent.value.name = 'Event Discovery Agent'
    draftAgent.value.trigger_type = 'on_new_article'
    draftAgent.value.schedule_interval = ''
    draftAgent.value.target_db = 'articles'
    draftAgent.value.logic_module = 'tasks.agent_logic.create_event_from_articles'
    draftAgent.value.parameters = '{\n  "topic": "your topic here"\n}'
    return
  }

  draftAgent.value.name = 'Event Enrichment Agent'
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

const loadUserspaces = async () => {
  loadingUserspaces.value = true
  try {
    const response = await authFetch('/api/userspaces')
    if (response.ok) {
      userspaces.value = await response.json()
      // Auto-select first userspace if available and none selected
      if (userspaces.value.length > 0 && !draftAgent.value.userspace) {
        draftAgent.value.userspace = userspaces.value[0]
      }
    }
  } catch (error) {
    console.error('Failed to load userspaces:', error)
  } finally {
    loadingUserspaces.value = false
  }
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

    successMessage.value = 'Agent summoned successfully!'
    draftAgent.value.name = ''
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

    successMessage.value = 'Agent dismissed'
    await loadAgents()
  } catch (error) {
    errorMessage.value = `Delete failed: ${String(error)}`
  }
}

const getModuleDisplayName = (module: string) => {
  return LOGIC_MODULE_INFO[module]?.name || module.split('.').pop() || module
}

const getStatusClass = (status: string) => {
  if (status === 'active') return 'status-active'
  if (status === 'paused') return 'status-paused'
  if (status === 'error') return 'status-error'
  return ''
}

// Auto-load agents when userspace changes
watch(() => draftAgent.value.userspace, () => {
  if (userspaceReady.value) {
    loadAgents()
  }
})

onMounted(async () => {
  if (ownerHint.value) {
    draftAgent.value.owner_user_id = ownerHint.value
  }
  await loadUserspaces()
})
</script>

<template>
  <div class="agent-management-page">
    <!-- Hero Section with Mythology Framing -->
    <section class="hero card">
      <div class="hero-icon">👁️</div>
      <h1>Give Your Issues Awareness</h1>
      <p class="hero-subtitle">
        In Moirai, an <strong>Issue is a Zeitgeist</strong> — the spirit of a story unfolding in the world.
        An <strong>Agent</strong> is not a separate worker; it is the Zeitgeist's own awareness — its eyes
        looking outward to ask: <em>"What articles are about me? Is my story still being told?"</em>
      </p>
    </section>

    <!-- Getting Started Guide -->
    <section class="card guide-section">
      <h2>How Issues Perceive Themselves</h2>
      <div class="guide-grid">
        <div class="guide-item">
          <div class="guide-icon">🌅</div>
          <h3>Awakening</h3>
          <p>A new Zeitgeist recognizes itself in the flow of articles — a story emerges from the noise.</p>
        </div>
        <div class="guide-item">
          <div class="guide-icon">👁️</div>
          <h3>Observing</h3>
          <p>The Zeitgeist watches itself — matching new articles, measuring its own relevance.</p>
        </div>
        <div class="guide-item">
          <div class="guide-icon">🌑</div>
          <h3>Fading</h3>
          <p>The Zeitgeist senses when its story is no longer told — and acknowledges its time has passed.</p>
        </div>
      </div>
    </section>

    <!-- Quick Start Templates -->
    <section class="card">
      <h2>Quick Start — Choose an Awareness Type</h2>
      <p class="muted">Select a template to pre-fill the form below. Each gives your issues a different kind of perception.</p>
      <div class="template-grid">
        <button class="template" @click="setTemplate('discover')">
          <div class="template-icon">🌅</div>
          <div class="template-content">
            <strong>Awakening</strong>
            <span>Recognize new Zeitgeists in the article flow</span>
          </div>
        </button>
        <button class="template" @click="setTemplate('enrich')">
          <div class="template-icon">👁️</div>
          <div class="template-content">
            <strong>Observation</strong>
            <span>Match articles to existing Zeitgeists</span>
          </div>
        </button>
        <button class="template" @click="setTemplate('stale')">
          <div class="template-icon">🌑</div>
          <div class="template-content">
            <strong>Staleness Sweep</strong>
            <span>Daily cleanup of inactive Events</span>
          </div>
        </button>
      </div>
    </section>

    <!-- Create Agent Form -->
    <section class="card">
      <h2>Configure Your Agent</h2>

      <!-- Userspace Selection (Primary) -->
      <div class="userspace-section">
        <label>
          <span class="label-text">Kingdom (Userspace)</span>
          <span class="label-hint">The realm where this agent will serve</span>
          <select v-model="draftAgent.userspace" :disabled="loadingUserspaces">
            <option value="" disabled>{{ loadingUserspaces ? 'Loading...' : 'Select a userspace' }}</option>
            <option v-for="us in userspaces" :key="us" :value="us">{{ us }}</option>
          </select>
        </label>
      </div>

      <!-- Main Form -->
      <div class="form-section" :class="{ disabled: !userspaceReady }">
        <div class="form-grid">
          <label>
            <span class="label-text">Agent Name</span>
            <span class="label-hint">A memorable name for this mortal</span>
            <input v-model="draftAgent.name" type="text" placeholder="e.g., Climate News Watcher" :disabled="!userspaceReady" />
          </label>

          <label>
            <span class="label-text">Quest Type (Logic Module)</span>
            <span class="label-hint">What task will this agent perform?</span>
            <select v-model="draftAgent.logic_module" :disabled="!userspaceReady">
              <option v-for="logic in logicModules" :key="logic" :value="logic">
                {{ getModuleDisplayName(logic) }}
              </option>
            </select>
          </label>
        </div>

        <!-- Module Info Box -->
        <div v-if="selectedModuleInfo" class="info-box">
          <strong>{{ selectedModuleInfo.name }}</strong>
          <p>{{ selectedModuleInfo.description }}</p>
          <p class="use-case">{{ selectedModuleInfo.useCase }}</p>
        </div>

        <div class="form-grid">
          <label>
            <span class="label-text">Trigger</span>
            <span class="label-hint">When should the agent act?</span>
            <select v-model="draftAgent.trigger_type" :disabled="!userspaceReady">
              <option v-for="trigger in triggerTypes" :key="trigger" :value="trigger">
                {{ TRIGGER_TYPE_INFO[trigger]?.name || trigger }}
              </option>
            </select>
          </label>

          <label v-if="draftAgent.trigger_type === 'scheduled'">
            <span class="label-text">Schedule Interval</span>
            <span class="label-hint">How often? (e.g., 1h, 6h, 1d)</span>
            <input
              v-model="draftAgent.schedule_interval"
              type="text"
              placeholder="1d"
              :disabled="!userspaceReady"
            />
          </label>

          <label>
            <span class="label-text">Status</span>
            <span class="label-hint">Active agents run; paused agents wait</span>
            <select v-model="draftAgent.status" :disabled="!userspaceReady">
              <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
            </select>
          </label>
        </div>

        <!-- Trigger Info -->
        <div v-if="selectedTriggerInfo" class="info-box subtle">
          <p>{{ selectedTriggerInfo.description }}</p>
        </div>

        <!-- Advanced Settings Toggle -->
        <button type="button" class="toggle-advanced" @click="showAdvanced = !showAdvanced">
          {{ showAdvanced ? '▼ Hide Advanced Settings' : '▶ Show Advanced Settings' }}
        </button>

        <!-- Advanced Settings -->
        <div v-if="showAdvanced" class="advanced-section">
          <div class="form-grid">
            <label>
              <span class="label-text">Target Database</span>
              <input v-model="draftAgent.target_db" type="text" :disabled="!userspaceReady" />
            </label>

            <label>
              <span class="label-text">Linked Entity ID</span>
              <span class="label-hint">Optional: Link to a specific Event/Issue</span>
              <input v-model="draftAgent.linked_entity_id" type="text" placeholder="Event/Issue UUID" :disabled="!userspaceReady" />
            </label>

            <label>
              <span class="label-text">Owner User ID</span>
              <input
                v-model="draftAgent.owner_user_id"
                type="text"
                :placeholder="ownerHint || 'Auto-filled from your account'"
                :disabled="!userspaceReady"
              />
            </label>
          </div>

          <label class="full-width">
            <span class="label-text">Parameters (JSON)</span>
            <span class="label-hint">Custom configuration for the logic module</span>
            <textarea v-model="draftAgent.parameters" rows="6" :disabled="!userspaceReady" />
          </label>
        </div>
      </div>

      <!-- Actions -->
      <div class="actions">
        <button
          type="button"
          class="primary"
          @click="createAgent"
          :disabled="saving || !userspaceReady || !draftAgent.name.trim()"
        >
          {{ saving ? 'Summoning...' : 'Summon Agent' }}
        </button>
      </div>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
    </section>

    <!-- Existing Agents -->
    <section class="card">
      <h2>Your Mortal Servants</h2>
      <p class="muted">Agents currently serving in {{ draftAgent.userspace || 'your kingdom' }}.</p>

      <div v-if="!userspaceReady" class="empty-state">
        <p>Select a userspace above to see your agents.</p>
      </div>
      <div v-else-if="loading" class="empty-state">
        <p>Consulting the roster...</p>
      </div>
      <div v-else-if="!agents.length" class="empty-state">
        <p>No agents yet. Summon your first mortal above!</p>
      </div>
      <div v-else class="agent-list">
        <article v-for="agent in agents" :key="agent._id" class="agent-item">
          <div class="agent-info">
            <div class="agent-header">
              <strong>{{ agent.name }}</strong>
              <span class="status-badge" :class="getStatusClass(agent.status)">{{ agent.status }}</span>
            </div>
            <div class="agent-meta">
              <span class="meta-item">
                <span class="meta-label">Quest:</span>
                {{ getModuleDisplayName(agent.logic_module) }}
              </span>
              <span class="meta-item">
                <span class="meta-label">Trigger:</span>
                {{ TRIGGER_TYPE_INFO[agent.trigger_type]?.name || agent.trigger_type }}
              </span>
              <span v-if="agent.schedule_interval" class="meta-item">
                <span class="meta-label">Every:</span>
                {{ agent.schedule_interval }}
              </span>
            </div>
          </div>
          <button class="danger" type="button" @click="deleteAgent(agent._id)" title="Dismiss this agent">
            Dismiss
          </button>
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
  max-width: 900px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.card {
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  border-radius: 12px;
  padding: 20px;
}

/* Hero Section */
.hero {
  text-align: center;
  padding: 32px 24px;
  background: linear-gradient(145deg, color-mix(in srgb, var(--card-bg) 85%, #4a90a4), var(--card-bg));
  border-top: 3px solid #4a90a4;
}

.hero-icon {
  font-size: 3rem;
  margin-bottom: 12px;
}

.hero h1 {
  margin: 0 0 12px;
  font-size: 1.8rem;
}

.hero-subtitle {
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.7;
  opacity: 0.9;
}

/* Guide Section */
.guide-section h2 {
  margin: 0 0 16px;
}

.guide-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.guide-item {
  padding: 16px;
  background: var(--input-bg);
  border-radius: 8px;
  text-align: center;
}

.guide-icon {
  font-size: 2rem;
  margin-bottom: 8px;
}

.guide-item h3 {
  margin: 0 0 8px;
  font-size: 1rem;
}

.guide-item p {
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.8;
  line-height: 1.5;
}

/* Templates */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.template {
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--input-bg);
  color: var(--input-text);
  padding: 14px;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.1s;
}

.template:hover {
  border-color: var(--primary-color);
  transform: translateY(-1px);
}

.template-icon {
  font-size: 1.8rem;
}

.template-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-content strong {
  font-size: 0.95rem;
}

.template-content span {
  font-size: 0.8rem;
  opacity: 0.7;
}

/* Form Sections */
h2 {
  margin: 0 0 12px;
}

p {
  margin: 0 0 12px;
}

.muted {
  opacity: 0.7;
}

.userspace-section {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
}

.form-section {
  transition: opacity 0.2s;
}

.form-section.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label-text {
  font-weight: 600;
  font-size: 0.9rem;
}

.label-hint {
  font-size: 0.75rem;
  opacity: 0.6;
  font-weight: normal;
}

input,
select,
textarea {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--input-bg);
  color: var(--input-text);
  font: inherit;
  font-size: 0.9rem;
}

input:focus,
select:focus,
textarea:focus {
  outline: none;
  border-color: var(--primary-color);
}

textarea {
  resize: vertical;
  font-family: monospace;
  font-size: 0.85rem;
}

.full-width {
  grid-column: 1 / -1;
}

/* Info Box */
.info-box {
  background: color-mix(in srgb, var(--primary-color) 10%, var(--card-bg));
  border: 1px solid color-mix(in srgb, var(--primary-color) 30%, var(--border-color));
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.info-box.subtle {
  background: var(--input-bg);
  border-color: var(--border-color);
}

.info-box strong {
  display: block;
  margin-bottom: 4px;
}

.info-box p {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.info-box .use-case {
  margin-top: 8px;
  font-style: italic;
  opacity: 0.8;
}

/* Advanced Toggle */
.toggle-advanced {
  background: transparent;
  border: none;
  color: var(--text-color);
  opacity: 0.7;
  cursor: pointer;
  padding: 8px 0;
  font-size: 0.85rem;
}

.toggle-advanced:hover {
  opacity: 1;
}

.advanced-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--border-color);
}

/* Actions */
.actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

button {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 20px;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  transition: all 0.2s;
}

button.primary {
  background: var(--primary-color);
  color: var(--bg-color);
  border-color: var(--primary-color);
}

button.primary:hover:not(:disabled) {
  filter: brightness(1.1);
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

button.danger {
  background: transparent;
  color: #d9534f;
  border-color: #d9534f;
  padding: 6px 12px;
  font-size: 0.85rem;
}

button.danger:hover {
  background: #d9534f;
  color: white;
}

.error-text {
  margin-top: 12px;
  color: #d9534f;
  font-size: 0.9rem;
}

.success-text {
  margin-top: 12px;
  color: #2d8a5f;
  font-size: 0.9rem;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 32px;
  opacity: 0.6;
}

/* Agent List */
.agent-list {
  display: grid;
  gap: 12px;
}

.agent-item {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  background: var(--input-bg);
}

.agent-info {
  flex: 1;
  min-width: 0;
}

.agent-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.agent-header strong {
  font-size: 1rem;
}

.status-badge {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.status-active {
  background: #166534;
  color: white;
}

.status-paused {
  background: #6c757d;
  color: white;
}

.status-error {
  background: #d9534f;
  color: white;
}

.agent-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.85rem;
  opacity: 0.8;
}

.meta-item {
  display: flex;
  gap: 4px;
}

.meta-label {
  opacity: 0.6;
}
</style>
