<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { authFetch } from '../utils/authFetch'

interface CatalogEntry {
  provider: string
  endpoint?: string
  model?: string
  capabilities?: string[]
  languages?: string[]
  apiKeyEnv?: string
}

interface PurposeInfo {
  id: string
  needs: string
  description: string
}

interface CatalogPayload {
  source: 'database' | 'file' | 'none'
  catalog: Record<string, CatalogEntry>
  purposes: Record<string, string[]>
  updated_at: string | null
  updated_by: string | null
  skipped: string[]
  purpose_info: PurposeInfo[]
  providers: string[]
  capabilities: string[]
}

// Rows carry a local key so an entry can be renamed without losing the
// purposes that point at it.
interface EntryRow {
  key: number
  name: string
  provider: string
  endpoint: string
  model: string
  capabilities: string[]
  languages: string
  apiKeyEnv: string
}

const DEFAULT_CAPABILITIES = ['chat', 'json']
const KEYED_PROVIDERS = ['openai', 'gemini']

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const errors = ref<string[]>([])
const notice = ref('')
const source = ref<CatalogPayload['source']>('none')
const updatedAt = ref<string | null>(null)
const updatedBy = ref<string | null>(null)
const skipped = ref<string[]>([])
const purposeInfo = ref<PurposeInfo[]>([])
const providers = ref<string[]>([])
const capabilities = ref<string[]>([])
const rows = ref<EntryRow[]>([])
const purposeKeys = ref<Record<string, number[]>>({})
const pendingAdd = ref<Record<string, string>>({})
const dirty = ref(false)
let nextKey = 1

const sourceLabel = computed(() => {
  if (source.value === 'database') return 'Edited in the admin UI'
  if (source.value === 'file') return 'From Helm values (llm.catalog)'
  return 'Not configured: legacy settings apply'
})

const rowByKey = (key: number) => rows.value.find((r) => r.key === key)

const effectiveCapabilities = (row: EntryRow) =>
  row.capabilities.length ? row.capabilities : DEFAULT_CAPABILITIES

const candidatesFor = (purpose: PurposeInfo) =>
  rows.value.filter(
    (r) =>
      r.name.trim() &&
      effectiveCapabilities(r).includes(purpose.needs) &&
      !(purposeKeys.value[purpose.id] || []).includes(r.key)
  )

const applyPayload = (data: CatalogPayload) => {
  source.value = data.source
  updatedAt.value = data.updated_at
  updatedBy.value = data.updated_by
  skipped.value = data.skipped || []
  purposeInfo.value = data.purpose_info
  providers.value = data.providers
  capabilities.value = data.capabilities
  const keyByName: Record<string, number> = {}
  rows.value = Object.entries(data.catalog || {}).map(([name, entry]) => {
    const key = nextKey++
    keyByName[name] = key
    return {
      key,
      name,
      provider: entry.provider || 'ollama',
      endpoint: entry.endpoint || '',
      model: entry.model || '',
      capabilities: [...(entry.capabilities || [])],
      languages: (entry.languages || []).join(', '),
      apiKeyEnv: entry.apiKeyEnv || '',
    }
  })
  const keys: Record<string, number[]> = {}
  for (const info of data.purpose_info) {
    keys[info.id] = (data.purposes?.[info.id] || [])
      .map((name) => keyByName[name])
      .filter((key): key is number => key !== undefined)
  }
  purposeKeys.value = keys
  pendingAdd.value = Object.fromEntries(data.purpose_info.map((info) => [info.id, '']))
  dirty.value = false
}

const load = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const res = await authFetch('/api/llm/catalog')
    if (!res.ok) {
      loadError.value =
        res.status === 403 ? 'Only admins can edit the model catalog.' : `Error ${res.status}`
      return
    }
    applyPayload((await res.json()) as CatalogPayload)
  } catch (e) {
    loadError.value = String(e)
  } finally {
    loading.value = false
  }
}

const markDirty = () => {
  dirty.value = true
  notice.value = ''
}

const addEntry = () => {
  rows.value.push({
    key: nextKey++,
    name: '',
    provider: 'ollama',
    endpoint: '',
    model: '',
    capabilities: [],
    languages: '',
    apiKeyEnv: '',
  })
  markDirty()
}

const removeEntry = (key: number) => {
  rows.value = rows.value.filter((r) => r.key !== key)
  for (const id of Object.keys(purposeKeys.value)) {
    purposeKeys.value[id] = (purposeKeys.value[id] || []).filter((k) => k !== key)
  }
  markDirty()
}

const toggleCapability = (row: EntryRow, capability: string) => {
  const current = new Set(effectiveCapabilities(row))
  if (current.has(capability)) current.delete(capability)
  else current.add(capability)
  row.capabilities = capabilities.value.filter((c) => current.has(c))
  markDirty()
}

const addToPurpose = (purpose: string) => {
  const key = Number(pendingAdd.value[purpose])
  if (!key) return
  purposeKeys.value[purpose] = [...(purposeKeys.value[purpose] || []), key]
  pendingAdd.value[purpose] = ''
  markDirty()
}

const movePurposeEntry = (purpose: string, index: number, delta: number) => {
  const list = [...(purposeKeys.value[purpose] || [])]
  const target = index + delta
  if (target < 0 || target >= list.length) return
  const moved = list[index] as number
  list[index] = list[target] as number
  list[target] = moved
  purposeKeys.value[purpose] = list
  markDirty()
}

const removeFromPurpose = (purpose: string, index: number) => {
  purposeKeys.value[purpose] = (purposeKeys.value[purpose] || []).filter((_, i) => i !== index)
  markDirty()
}

const buildBody = () => {
  const catalog: Record<string, CatalogEntry> = {}
  for (const row of rows.value) {
    const entry: CatalogEntry = { provider: row.provider }
    if (row.endpoint.trim()) entry.endpoint = row.endpoint.trim()
    if (row.model.trim()) entry.model = row.model.trim()
    if (row.capabilities.length) entry.capabilities = [...row.capabilities]
    const languages = row.languages
      .split(',')
      .map((l) => l.trim())
      .filter(Boolean)
    if (languages.length) entry.languages = languages
    if (KEYED_PROVIDERS.includes(row.provider) && row.apiKeyEnv.trim()) {
      entry.apiKeyEnv = row.apiKeyEnv.trim()
    }
    catalog[row.name.trim()] = entry
  }
  const purposes: Record<string, string[]> = {}
  for (const [id, keys] of Object.entries(purposeKeys.value)) {
    const names = keys.map((k) => rowByKey(k)?.name.trim() || '').filter(Boolean)
    if (names.length) purposes[id] = names
  }
  return { catalog, purposes }
}

const localErrors = () => {
  const found: string[] = []
  const names = rows.value.map((r) => r.name.trim())
  if (names.some((n) => !n)) found.push('Every model needs a name.')
  const duplicates = names.filter((n, i) => n && names.indexOf(n) !== i)
  if (duplicates.length) found.push(`Duplicate names: ${[...new Set(duplicates)].join(', ')}`)
  return found
}

const save = async () => {
  errors.value = localErrors()
  notice.value = ''
  if (errors.value.length) return
  saving.value = true
  try {
    const res = await authFetch('/api/llm/catalog', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildBody()),
    })
    const data = await res.json()
    if (!res.ok) {
      errors.value = data.details || [data.error || data.message || `Error ${res.status}`]
      return
    }
    applyPayload(data as CatalogPayload)
    notice.value = 'Saved. Every service picks up the change within about 30 seconds.'
  } catch (e) {
    errors.value = [String(e)]
  } finally {
    saving.value = false
  }
}

const resetToHelm = async () => {
  if (!confirm('Discard the catalog edited here and use the Helm values (llm.catalog) again?')) {
    return
  }
  saving.value = true
  errors.value = []
  try {
    const res = await authFetch('/api/llm/catalog', { method: 'DELETE' })
    const data = await res.json()
    if (!res.ok) {
      errors.value = [data.error || data.message || `Error ${res.status}`]
      return
    }
    applyPayload(data as CatalogPayload)
    notice.value = 'Reverted to the Helm values.'
  } catch (e) {
    errors.value = [String(e)]
  } finally {
    saving.value = false
  }
}

const formatTime = (value: string | null) => (value ? new Date(value).toLocaleString() : '')

onMounted(load)
</script>

<template>
  <div class="settings-section model-catalog" data-testid="model-catalog">
    <h2>Model Catalog</h2>
    <p class="section-desc">
      Named models and which jobs use them. Each purpose tries its models in order and falls through
      to the next on failure. API keys stay in the environment; an entry only names the variable.
    </p>

    <div v-if="loading" class="state">Loading catalog...</div>
    <div v-else-if="loadError" class="state error">{{ loadError }}</div>
    <template v-else>
      <div class="source-line">
        <span :class="['badge', `badge-${source}`]">{{ sourceLabel }}</span>
        <span v-if="source === 'database' && updatedAt" class="meta">
          Last saved {{ formatTime(updatedAt) }}<span v-if="updatedBy"> by {{ updatedBy }}</span>
        </span>
        <span v-if="source === 'file'" class="meta">Saving here overrides the Helm values.</span>
      </div>

      <div v-if="skipped.length" class="warning">
        Ignored by the running services: {{ skipped.join(', ') }}. An AISA entry without a model
        needs a default model in the AISA Secret.
      </div>

      <h3 class="static">Models</h3>
      <div v-if="!rows.length" class="state">No models yet.</div>
      <div v-for="row in rows" :key="row.key" class="entry-card">
        <div class="entry-grid">
          <label>
            Name
            <input v-model="row.name" type="text" placeholder="e.g. npu-qwen" @input="markDirty" />
          </label>
          <label>
            Provider
            <select v-model="row.provider" @change="markDirty">
              <option v-for="p in providers" :key="p" :value="p">{{ p }}</option>
            </select>
          </label>
          <label>
            Model
            <input
              v-model="row.model"
              type="text"
              :placeholder="row.provider === 'aisa' ? 'AISA default model' : 'e.g. llama3.2:3b'"
              @input="markDirty"
            />
          </label>
          <label v-if="row.provider === 'ollama'">
            Endpoint
            <input
              v-model="row.endpoint"
              type="text"
              placeholder="http://host:11434/v1"
              @input="markDirty"
            />
          </label>
          <label v-if="KEYED_PROVIDERS.includes(row.provider)">
            API key env var
            <input
              v-model="row.apiKeyEnv"
              type="text"
              :placeholder="`${row.provider.toUpperCase()}_API_KEY`"
              @input="markDirty"
            />
          </label>
          <label>
            Languages
            <input
              v-model="row.languages"
              type="text"
              placeholder="any (e.g. en, fi)"
              @input="markDirty"
            />
          </label>
        </div>
        <div class="entry-footer">
          <div class="capabilities">
            <label v-for="c in capabilities" :key="c" class="checkbox-label">
              <input
                type="checkbox"
                :checked="effectiveCapabilities(row).includes(c)"
                @change="toggleCapability(row, c)"
              />
              {{ c }}
            </label>
          </div>
          <button class="secondary small" @click="removeEntry(row.key)">Remove</button>
        </div>
      </div>
      <div class="button-group">
        <button class="secondary" @click="addEntry">Add model</button>
      </div>

      <h3 class="static">Purposes</h3>
      <div v-for="purpose in purposeInfo" :key="purpose.id" class="purpose-row">
        <div class="purpose-head">
          <strong>{{ purpose.id }}</strong>
          <span class="meta">{{ purpose.description }} · needs {{ purpose.needs }}</span>
        </div>
        <ol v-if="(purposeKeys[purpose.id] || []).length" class="purpose-list">
          <li v-for="(key, index) in purposeKeys[purpose.id]" :key="key">
            <span class="purpose-index">{{ index + 1 }}.</span>
            <span class="purpose-name">{{ rowByKey(key)?.name || '(unnamed)' }}</span>
            <button
              class="secondary small"
              :disabled="index === 0"
              aria-label="Move up"
              @click="movePurposeEntry(purpose.id, index, -1)"
            >
              ↑
            </button>
            <button
              class="secondary small"
              :disabled="index === (purposeKeys[purpose.id] || []).length - 1"
              aria-label="Move down"
              @click="movePurposeEntry(purpose.id, index, 1)"
            >
              ↓
            </button>
            <button
              class="secondary small"
              aria-label="Remove"
              @click="removeFromPurpose(purpose.id, index)"
            >
              ✕
            </button>
          </li>
        </ol>
        <p v-else class="meta">Not set: the legacy configuration applies.</p>
        <div class="purpose-add">
          <select v-model="pendingAdd[purpose.id]" :aria-label="`Add a model to ${purpose.id}`">
            <option value="">Add a model…</option>
            <option v-for="row in candidatesFor(purpose)" :key="row.key" :value="String(row.key)">
              {{ row.name }}
            </option>
          </select>
          <button
            class="secondary small"
            :disabled="!pendingAdd[purpose.id]"
            @click="addToPurpose(purpose.id)"
          >
            Add
          </button>
        </div>
      </div>

      <ul v-if="errors.length" class="errors">
        <li v-for="(e, i) in errors" :key="i">{{ e }}</li>
      </ul>
      <p v-if="notice" class="notice">{{ notice }}</p>

      <div class="button-group">
        <button :disabled="saving || !dirty" @click="save">Save catalog</button>
        <button class="secondary" :disabled="saving || !dirty" @click="load">
          Discard changes
        </button>
        <button
          v-if="source === 'database'"
          class="secondary"
          :disabled="saving"
          @click="resetToHelm"
        >
          Reset to Helm values
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.settings-section {
  text-align: left;
  background: var(--card-bg);
  color: var(--text-color);
  padding: 20px;
  margin-bottom: 20px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}
h2 {
  margin-top: 0;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 10px;
}
h3.static {
  margin: 24px 0 10px;
}
.section-desc,
.meta {
  opacity: 0.75;
  font-size: 0.9rem;
}
.state {
  padding: 8px 0;
  opacity: 0.8;
}
.error,
.errors {
  color: #e5534b;
}
.errors {
  margin: 12px 0 0;
  padding-left: 20px;
}
.notice {
  margin: 12px 0 0;
  color: var(--primary-color);
}
.warning {
  margin: 12px 0;
  padding: 10px 12px;
  border: 1px solid #d29922;
  border-radius: 6px;
  font-size: 0.9rem;
}
.source-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.badge {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.85rem;
  border: 1px solid var(--border-color);
}
.badge-database {
  border-color: var(--primary-color);
  color: var(--primary-color);
}
.entry-card {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 10px;
}
.entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.entry-grid label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.85rem;
  font-weight: bold;
}
input[type='text'],
select {
  padding: 7px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--input-bg);
  color: var(--input-text);
  font-weight: normal;
}
.entry-footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}
.capabilities {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.9rem;
  cursor: pointer;
}
.purpose-row {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}
.purpose-head {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: baseline;
}
.purpose-list {
  margin: 8px 0;
  padding-left: 0;
  list-style: none;
}
.purpose-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.purpose-index {
  width: 18px;
  opacity: 0.7;
}
.purpose-name {
  min-width: 140px;
}
.purpose-add {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
button {
  background: var(--primary-color);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}
button:hover:not(:disabled) {
  background: var(--primary-hover);
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
button.secondary {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  color: var(--text-color);
}
button.small {
  padding: 4px 10px;
}
.button-group {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 15px;
}
</style>
