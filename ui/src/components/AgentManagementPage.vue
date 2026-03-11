<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const logicModules = [
  'tasks.agent_logic.create_event_from_articles',
  'tasks.agent_logic.add_articles_to_event',
  'tasks.agent_logic.check_event_staleness',
]

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

const ownerHint = computed(() => {
  return authStore.user?._id || authStore.user?.id || ''
})

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
      <h2>Draft Agent Form</h2>
      <p class="muted">Draft only for now. Backend wiring comes next.</p>

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
</style>
