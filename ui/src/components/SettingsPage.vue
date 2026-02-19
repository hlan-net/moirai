<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { useTheme, type Theme } from '../composables/useTheme'

const authStore = useAuthStore()

const uiVersion = __APP_BUILD__ !== 'dev'
  ? `Moirai UI v${__APP_VERSION__} (build ${__APP_BUILD__})`
  : `Moirai UI v${__APP_VERSION__}`
const modelName = ref('llama3.1:latest')
const aboutDescription =
  'Moirai is a GenAI-native press review platform powered by the Model Context Protocol (MCP).'
const availableModels = ref([])
const loadingModels = ref(false)
const allowPublicRead = ref(false)
const iterationInterval = ref(600)
const schedulerEnabled = ref(true)
const showSchedulerLogs = ref(false)
const schedulerLogs = ref<SchedulerLogEntry[]>([])
const schedulerLogsLoading = ref(false)
const schedulerLogsError = ref('')
const llmEndpoint = ref('ollama') // 'ollama' or 'openai'
const openaiApiKey = ref('')
const openaiModelName = ref('gpt-4-turbo')
const availableOpenAiModels = ref([])
const geminiApiKey = ref('')
const geminiModelName = ref('gemini-3-flash')
const availableGeminiModels = ref([])
const ollamaEndpointUrl = ref('http://host.docker.internal:11434/v1')
const collapsedSections = ref(new Set(['general', 'ollama', 'openai', 'gemini', 'authentication']))
const activeTab = ref('user')

interface ComponentVersion {
  name: string
  version: string
}

interface SchedulerLogEntry {
  timestamp: string
  event: string
  message: string
  metadata?: Record<string, string>
}

const buildComponentVersions = (config?: {
  version?: string
  components?: Record<string, string>
}) => {
  const apiVersion = config?.components?.api ?? config?.version ?? 'unknown'
  const mcpVersion = config?.components?.mcp ?? 'unknown'
  const couchdbVersion = config?.components?.couchdb ?? 'unknown'

  return [
    { name: 'UI', version: uiVersion },
    { name: 'API', version: apiVersion },
    { name: 'MCP Server', version: mcpVersion },
    { name: 'CouchDB', version: couchdbVersion },
  ]
}

const componentVersions = ref<ComponentVersion[]>(buildComponentVersions())
const copyStatus = ref('')
const aboutCopyText = computed(() => {
  const lines: string[] = ['About Moirai']
  for (const component of componentVersions.value) {
    lines.push(component.name)
    lines.push(component.version)
  }
  lines.push(aboutDescription)
  return lines.join('\n')
})

// Auth Config
const googleClientId = ref('')
const entraClientId = ref('')
const entraTenantId = ref('')
const githubClientId = ref('')
const githubClientSecret = ref('')

const { theme, setTheme } = useTheme()

const copyAbout = async () => {
  const text = aboutCopyText.value
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.setAttribute('readonly', 'true')
      textarea.style.position = 'absolute'
      textarea.style.left = '-9999px'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    copyStatus.value = 'Copied'
  } catch (error) {
    console.error('Failed to copy about info', error)
    copyStatus.value = 'Copy failed'
  } finally {
    window.setTimeout(() => {
      copyStatus.value = ''
    }, 2000)
  }
}

watch(llmEndpoint, (newEndpoint) => {
  if (newEndpoint === 'openai' && availableOpenAiModels.value.length === 0 && openaiApiKey.value) {
    fetchOpenAiModels()
  } else if (newEndpoint === 'ollama' && availableModels.value.length === 0) {
    fetchOllamaModels()
  } else if (newEndpoint === 'gemini' && availableGeminiModels.value.length === 0 && geminiApiKey.value) {
    fetchGeminiModels()
  }
})

watch(openaiApiKey, (newKey) => {
  if (!newKey) {
    availableOpenAiModels.value = []
  }
})

watch(geminiApiKey, (newKey) => {
  if (!newKey) {
    availableGeminiModels.value = []
  }
})

const toggleSection = (section: string) => {
  if (collapsedSections.value.has(section)) {
    collapsedSections.value.delete(section)
  } else {
    collapsedSections.value.add(section)
  }
}

const fetchSchedulerLogs = async () => {
  schedulerLogsLoading.value = true
  schedulerLogsError.value = ''

  try {
    const res = await axios.get('/api/scheduler/logs', { params: { limit: 50 } })
    schedulerLogs.value = Array.isArray(res.data?.logs) ? res.data.logs : []
  } catch (e) {
    console.error('Error fetching scheduler logs', e)
    schedulerLogsError.value = 'Failed to load scheduler logs.'
    schedulerLogs.value = []
  } finally {
    schedulerLogsLoading.value = false
  }
}

const openSchedulerLogs = async () => {
  showSchedulerLogs.value = true
  await fetchSchedulerLogs()
}

const closeSchedulerLogs = () => {
  showSchedulerLogs.value = false
}

const formatLogTimestamp = (timestamp: string) => {
  const parsed = new Date(timestamp)
  if (Number.isNaN(parsed.valueOf())) {
    return timestamp
  }
  return parsed.toLocaleString()
}
const saveSettings = async () => {
  // Save User Settings
  try {
      await axios.put('/api/auth/me/settings', {
          moirai_model: modelName.value,
          moirai_llm_endpoint: llmEndpoint.value,
          moirai_openai_api_key: openaiApiKey.value,
          moirai_openai_model: openaiModelName.value,
          moirai_gemini_api_key: geminiApiKey.value,
          moirai_gemini_model: geminiModelName.value,
          moirai_ollama_endpoint_url: ollamaEndpointUrl.value,
          moirai_theme: theme.value
      })
      
      // Save System Config (Admin only or if allowed)
      const configRes = await fetch('/api/config', {
          method: 'PUT',
          headers: authStore.token ? { 
              'Authorization': `Bearer ${authStore.token}`,
              'Content-Type': 'application/json'
          } : { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
               allow_public_read: allowPublicRead.value,
               iteration_interval: schedulerEnabled.value ? iterationInterval.value : 0,
              google_client_id: googleClientId.value,
              entra_client_id: entraClientId.value,
              entra_tenant_id: entraTenantId.value,
              github_client_id: githubClientId.value,
              github_client_secret: githubClientSecret.value
          })
      })
      
      if (!configRes.ok) {
           if (configRes.status === 403) {
               console.warn("User does not have permission to update system config.")
           } else {
               throw new Error("Failed to save config")
           }
      }
      
      alert('Settings saved!')
  } catch (e) {
      console.error(e)
      alert("Failed to save settings.")
  }
}

const fetchOllamaModels = async () => {
  loadingModels.value = true
  try {
    const res = await fetch('/api/models')
    if (res.ok) {
      availableModels.value = await res.json()
    }
  } catch (e) {
    console.error('Error fetching models:', e)
  } finally {
    loadingModels.value = false
  }
}

const fetchOpenAiModels = async () => {
  if (!openaiApiKey.value) {
    alert('Please provide an OpenAI API key.')
    return
  }
  loadingModels.value = true
  try {
    const res = await fetch('/api/models?llm_endpoint=openai', {
      headers: {
        'x-openai-api-key': openaiApiKey.value
      }
    })
    if (res.ok) {
      availableOpenAiModels.value = await res.json()
    }
  } catch (e) {
    console.error('Error fetching models:', e)
  } finally {
    loadingModels.value = false
  }
}

const fetchGeminiModels = async () => {
  if (!geminiApiKey.value) {
    alert('Please provide a Gemini API key.')
    return
  }
  loadingModels.value = true
  try {
    const res = await fetch('/api/models?llm_endpoint=gemini', {
      headers: {
        'x-gemini-api-key': geminiApiKey.value
      }
    })
    if (res.ok) {
      availableGeminiModels.value = await res.json()
    }
  } catch (e) {
    console.error('Error fetching models:', e)
  } finally {
    loadingModels.value = false
  }
}

const fetchUserProfile = async () => {
    try {
        const res = await axios.get('/api/auth/me')
        if (res.data) {
            const settings = res.data.settings || {}
            // Load User Settings
            if (settings.moirai_model) modelName.value = settings.moirai_model
            if (settings.moirai_llm_endpoint) llmEndpoint.value = settings.moirai_llm_endpoint
            if (settings.moirai_openai_api_key) openaiApiKey.value = settings.moirai_openai_api_key
            if (settings.moirai_openai_model) openaiModelName.value = settings.moirai_openai_model
            if (settings.moirai_gemini_api_key) geminiApiKey.value = settings.moirai_gemini_api_key
            if (settings.moirai_gemini_model) geminiModelName.value = settings.moirai_gemini_model
            if (settings.moirai_ollama_endpoint_url) ollamaEndpointUrl.value = settings.moirai_ollama_endpoint_url
            if (settings.moirai_theme) setTheme(settings.moirai_theme as Theme)
            
            // Refresh models based on loaded settings
            if (llmEndpoint.value === 'ollama') fetchOllamaModels()
            else if (llmEndpoint.value === 'openai' && openaiApiKey.value) fetchOpenAiModels()
            else if (llmEndpoint.value === 'gemini' && geminiApiKey.value) fetchGeminiModels()
        }
    } catch (e) {
        console.error("Error fetching user profile", e)
    }
}

const fileInput = ref<HTMLInputElement | null>(null)

const exportSettings = async () => {
  // 1. Fetch server config
  let serverConfig = {}
  try {
      const res = await fetch('/api/config')
      if (res.ok) {
          serverConfig = await res.json()
      }
  } catch (e) {
      console.error("Error fetching config for export", e)
  }

  // 2. Gather local storage
  const clientSettings: Record<string, string | null> = {
      'moirai_model': localStorage.getItem('moirai_model'),
      'moirai_llm_endpoint': localStorage.getItem('moirai_llm_endpoint'),
      'moirai_openai_api_key': localStorage.getItem('moirai_openai_api_key'),
      'moirai_openai_model': localStorage.getItem('moirai_openai_model'),
      'moirai_gemini_api_key': localStorage.getItem('moirai_gemini_api_key'),
      'moirai_gemini_model': localStorage.getItem('moirai_gemini_model'),
      'moirai_ollama_endpoint_url': localStorage.getItem('moirai_ollama_endpoint_url'),
      'moirai_theme': localStorage.getItem('moirai_theme'),
  }

  // 3. Construct JSON
  const exportData = {
      version: 1,
      timestamp: new Date().toISOString(),
      client_settings: clientSettings,
      server_config: serverConfig
  }

  // 4. Download file
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportData, null, 2));
  const downloadAnchorNode = document.createElement('a');
  downloadAnchorNode.setAttribute("href", dataStr);
  downloadAnchorNode.setAttribute("download", "moirai-settings.json");
  document.body.appendChild(downloadAnchorNode); // required for firefox
  downloadAnchorNode.click();
  downloadAnchorNode.remove();
}

const triggerImport = () => {
  fileInput.value?.click()
}

const importSettings = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return

  const file = target.files[0]
  const reader = new FileReader()

  reader.onload = async (e) => {
    try {
      if (!e.target?.result) return
      const content = e.target.result as string
      const data = JSON.parse(content)

      // Validate basic structure
      if (!data.client_settings || !data.server_config) {
          alert("Invalid settings file format.")
          return
      }

      if (!confirm("This will overwrite your current settings and reload the page. Continue?")) {
          return
      }

      // Restore client settings
      Object.entries(data.client_settings).forEach(([key, value]) => {
          if (value !== null && typeof value === 'string') {
              localStorage.setItem(key, value)
          }
      })

      // Restore server config
      try {
          const res = await fetch('/api/config', {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(data.server_config)
          })
          if (!res.ok) {
              console.error("Failed to restore server config during import")
              alert("Settings imported, but server configuration failed to update.")
          }
      } catch (err) {
          console.error("Error updating server config:", err)
      }

      alert("Settings imported successfully! Reloading...")
      location.reload()

    } catch (err) {
      console.error("Error parsing settings file:", err)
      alert("Failed to parse settings file.")
    }
  }

  reader.readAsText(file)
  // Reset input so same file can be selected again
  target.value = ''
}

const fetchConfig = async () => {
    try {
        const res = await axios.get('/api/config')
        if (res.data) {
            const config = res.data
            console.log("Config loaded via axios:", config)
            componentVersions.value = buildComponentVersions(config)
            if (config.allow_public_read !== undefined) allowPublicRead.value = config.allow_public_read
            if (config.iteration_interval !== undefined) {
              const intervalValue = Number(config.iteration_interval)
              schedulerEnabled.value = intervalValue > 0
              if (intervalValue > 0) {
                iterationInterval.value = intervalValue
              }
            }
            if (config.google_client_id) googleClientId.value = config.google_client_id
            if (config.entra_client_id) entraClientId.value = config.entra_client_id
            if (config.entra_tenant_id) entraTenantId.value = config.entra_tenant_id
            if (config.github_client_id) githubClientId.value = config.github_client_id
            if (config.github_client_secret) githubClientSecret.value = config.github_client_secret
        }
    } catch (e) {
        console.error("Error fetching system config via axios", e)
        componentVersions.value = buildComponentVersions()
    }
}

onMounted(() => {
  fetchUserProfile()
  // Still fetch system config for version and system-wide settings
  fetchConfig()
})
</script>

<template>
  <div class="settings-page">

    <h1>Settings</h1>
    
    <div class="settings-section">
      <h2 class="about-header">
        <span>About Moirai</span>
        <span class="about-actions">
          <button class="secondary copy-btn" @click="copyAbout">Copy details</button>
          <span v-if="copyStatus" class="copy-status">{{ copyStatus }}</span>
        </span>
      </h2>
      <div>
        <div class="version-list">
          <div v-for="component in componentVersions" :key="component.name" class="version-row">
            <span class="version-name">{{ component.name }}</span>
            <span class="version-value">{{ component.version }}</span>
          </div>
        </div>
        <p class="about-description">{{ aboutDescription }}</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button 
        :class="['tab-btn', { active: activeTab === 'user' }]" 
        @click="activeTab = 'user'"
      >
        User Settings
      </button>
      <button 
        :class="['tab-btn', { active: activeTab === 'system' }]" 
        @click="activeTab = 'system'"
      >
        System Settings
      </button>
    </div>

    <!-- User Settings Tab -->
    <div v-show="activeTab === 'user'" class="tab-content">
      <div class="settings-section">
        <h2>
          General (User)
        </h2>
        <div>
          <div class="form-group">
            <label for="theme">Theme:</label>
            <select id="theme" :value="theme" @change="setTheme(($event.target as HTMLSelectElement).value as Theme)">
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="auto">Auto (System)</option>
            </select>
          </div>
        </div>
      </div>

    <div class="settings-section">
      <h2>
        LLM Endpoint Configuration
      </h2>
      <div class="form-group">
        <div class="radio-group">
          <label>
            <input type="radio" value="ollama" v-model="llmEndpoint">
            Ollama
          </label>
          <label>
            <input type="radio" value="openai" v-model="llmEndpoint">
            OpenAI
          </label>
          <label>
            <input type="radio" value="gemini" v-model="llmEndpoint">
            Gemini
          </label>
        </div>
      </div>
      <div class="sub-section">
        <h3 @click="toggleSection('ollama')">
          Ollama
          <span class="toggle-icon">{{ collapsedSections.has('ollama') ? '▶' : '▼' }}</span>
        </h3>
        <div v-if="!collapsedSections.has('ollama')">
          <div class="form-group">
            <label for="ollama-url">Ollama Endpoint URL:</label>
            <input type="text" id="ollama-url" v-model="ollamaEndpointUrl" />
          </div>
          <div class="form-group">
            <label for="ollama-model">LLM Model Name (Ollama):</label>
            <select v-if="availableModels.length" id="ollama-model" v-model="modelName">
              <option v-for="model in availableModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <input v-else v-model="modelName" placeholder="e.g. gemma3:1b" />
            <small v-if="loadingModels">Loading available models...</small>
            <small v-else-if="availableModels.length">Select a model provided by your Ollama instance.</small>
            <small v-else>Ensure this model is pulled in your Ollama instance. (Could not fetch list)</small>
          </div>
        </div>
      </div>
      <div class="sub-section">
        <h3 @click="toggleSection('openai')">
          OpenAI
          <span class="toggle-icon">{{ collapsedSections.has('openai') ? '▶' : '▼' }}</span>
        </h3>
        <div v-if="!collapsedSections.has('openai')">
          <div class="form-group">
            <label for="openai-api-key">OpenAI API Key:</label>
            <input type="password" id="openai-api-key" v-model="openaiApiKey" />
          </div>
          <div class="form-group">
            <label for="openai-model">OpenAI Model Name:</label>
            <button @click="fetchOpenAiModels" :disabled="!openaiApiKey || loadingModels">
              {{ loadingModels ? 'Loading...' : 'Fetch Models' }}
            </button>
            <select v-if="availableOpenAiModels.length" id="openai-model" v-model="openaiModelName">
              <option v-for="model in availableOpenAiModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <small v-if="loadingModels">Loading available models...</small>
            <small v-if="!openaiApiKey">Provide an API key and click "Fetch Models" to see a list of available models.</small>
          </div>
        </div>
      </div>

      <div class="sub-section">
        <h3 @click="toggleSection('gemini')">
          Gemini
          <span class="toggle-icon">{{ collapsedSections.has('gemini') ? '▶' : '▼' }}</span>
        </h3>
        <div v-if="!collapsedSections.has('gemini')">
          <div class="form-group">
            <label for="gemini-api-key">Gemini API Key:</label>
            <input type="password" id="gemini-api-key" v-model="geminiApiKey" />
          </div>
          <div class="form-group">
            <label for="gemini-model">Gemini Model Name:</label>
            <button @click="fetchGeminiModels" :disabled="!geminiApiKey || loadingModels">
              {{ loadingModels ? 'Loading...' : 'Fetch Models' }}
            </button>
            <select v-if="availableGeminiModels.length" id="gemini-model" v-model="geminiModelName">
              <option v-for="model in availableGeminiModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <small v-if="loadingModels">Loading available models...</small>
            <small v-if="!geminiApiKey">Provide an API key and click "Fetch Models" to see a list of available models.</small>
          </div>
        </div>
      </div>
    </div>

    </div> <!-- End User Tab -->

    <!-- System Settings Tab -->
    <div v-show="activeTab === 'system'" class="tab-content">
    <div class="settings-section">
      <h2>
        System Configuration
      </h2>
      <div>
        <div class="form-group checkbox-group">
          <label for="public-read" class="checkbox-label">
            <input type="checkbox" id="public-read" v-model="allowPublicRead" />
            Allow Public Read Access (Stream Page)
          </label>
          <small>If enabled, the Stream page can be viewed without logging in.</small>
        </div>
        <div class="form-group checkbox-group">
          <label for="scheduler-enabled" class="checkbox-label">
            <input type="checkbox" id="scheduler-enabled" v-model="schedulerEnabled" />
            Enable Scheduler (Automatic Feed Refresh)
          </label>
          <small v-if="schedulerEnabled">Feeds will refresh on the interval below.</small>
          <small v-else>Scheduler is paused. Turn this on to resume automatic updates.</small>
        </div>
        <div class="form-group">
          <label for="interval">Feed Refresh Interval (seconds):</label>
          <input type="number" id="interval" v-model="iterationInterval" min="60" step="60" :disabled="!schedulerEnabled" />
          <small>How often the system checks for new articles.</small>
        </div>
        <div class="button-group">
          <button class="secondary" @click="openSchedulerLogs">View Scheduler Logs</button>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <h2 @click="toggleSection('authentication')">
        Authentication Provider Configuration
        <span class="toggle-icon">{{ collapsedSections.has('authentication') ? '▶' : '▼' }}</span>
      </h2>
      <div v-if="!collapsedSections.has('authentication')">
         <p class="section-desc">Configure trusted 3rd party authentication providers. <br/>These settings can also be set via environment variables (which take precedence).</p>
         
         <div class="form-group">
            <label for="google-client-id">Google Client ID:</label>
            <input type="text" id="google-client-id" v-model="googleClientId" placeholder="e.g. 123...apps.googleusercontent.com" />
         </div>
         
         <div class="form-group">
            <label for="entra-client-id">Microsoft Entra Client ID (Application ID):</label>
            <input type="text" id="entra-client-id" v-model="entraClientId" placeholder="e.g. 00000000-0000-0000-0000-000000000000" />
         </div>
         
         <div class="form-group">
            <label for="entra-tenant-id">Microsoft Entra Tenant ID:</label>
            <input type="text" id="entra-tenant-id" v-model="entraTenantId" placeholder="e.g. common, organizations, or UUID" />
         </div>
      </div>
    </div>

    <div class="settings-section">
      <h2>Backup & Restore</h2>
      <div>
        <p>Export your settings to a JSON file or restore from a backup. Note: Export includes your API keys.</p>
        <div class="button-group">
            <button class="secondary" @click="exportSettings">Export Settings</button>
            <button class="secondary" @click="triggerImport">Import Settings</button>
            <input 
                type="file" 
                ref="fileInput" 
                style="display: none" 
                accept=".json" 
                @change="importSettings" 
            />
        </div>
      </div>
    </div>
    </div> <!-- End System Tab -->

    <div class="actions-bar">
      <button @click="saveSettings" class="save-all-btn">Save All Settings</button>
    </div>

    <div v-if="showSchedulerLogs" class="modal-backdrop" @click.self="closeSchedulerLogs">
      <div class="modal-panel">
        <div class="modal-header">
          <h3>Scheduler Logs</h3>
          <button class="secondary" @click="closeSchedulerLogs">Close</button>
        </div>
        <div class="modal-body">
          <div v-if="schedulerLogsLoading" class="modal-state">Loading logs...</div>
          <div v-else-if="schedulerLogsError" class="modal-state">{{ schedulerLogsError }}</div>
          <div v-else-if="!schedulerLogs.length" class="modal-state">No scheduler logs yet.</div>
          <ul v-else class="scheduler-logs">
            <li v-for="(log, index) in schedulerLogs" :key="`${log.timestamp}-${index}`" class="scheduler-log">
              <div class="log-line">
                <span class="log-time">{{ formatLogTimestamp(log.timestamp) }}</span>
                <span class="log-event">{{ log.event }}</span>
              </div>
              <div class="log-message">{{ log.message }}</div>
              <div v-if="log.metadata" class="log-meta">
                <span v-for="(value, key) in log.metadata" :key="key">{{ key }}={{ value }}</span>
              </div>
            </li>
          </ul>
        </div>
        <div class="modal-footer">
          <button class="secondary" :disabled="schedulerLogsLoading" @click="fetchSchedulerLogs">Refresh</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 80px; /* Space for fixed bottom bar if needed, currently inline */
}

/* Tabs */
.tabs {
  display: flex;
  margin-bottom: 20px;
  border-bottom: 2px solid var(--border-color);
}

.tab-btn {
  background: transparent;
  color: var(--text-color);
  border: none;
  border-bottom: 3px solid transparent;
  padding: 10px 20px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  border-radius: 0;
  opacity: 0.7;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: var(--button-bg);
  opacity: 1;
}

.tab-btn.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  opacity: 1;
  font-weight: bold;
}

.settings-section {
  background: var(--card-bg);
  color: var(--text-color);
  padding: 20px;
  margin-bottom: 20px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.version-list {
  display: grid;
  gap: 6px;
  margin-bottom: 16px;
}

.version-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-color);
  border-bottom-color: color-mix(in srgb, var(--border-color) 40%, transparent);
}

.version-row:last-child {
  border-bottom: none;
}

.version-name {
  font-weight: 500;
  font-size: 0.95rem;
  letter-spacing: 0.01em;
}

.version-value {
  color: var(--text-color);
  opacity: 0.8;
  text-align: right;
  font-size: 0.98rem;
  font-variant-numeric: tabular-nums;
}

.about-description {
  margin: 10px 0 0;
  font-size: 1.15rem;
  line-height: 1.65;
  max-width: 62ch;
}
.about-header {
  align-items: center;
  gap: 12px;
}
.about-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.copy-btn {
  white-space: nowrap;
}
.copy-status {
  font-size: 0.85rem;
  color: var(--text-color);
  opacity: 0.7;
}
h2 {
  margin-top: 0;
  color: var(--text-color);
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 10px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
}
.sub-section {
  margin-left: 20px;
  border-left: 2px solid var(--border-color);
  padding-left: 20px;
  margin-top: 20px;
}
.sub-section.disabled {
  opacity: 0.5;
  pointer-events: none;
}
h3 {
  cursor: pointer;
  display: flex;
  justify-content: space-between;
}
.toggle-icon {
  transition: transform 0.2s;
}
.form-group {
  margin-bottom: 15px;
}
.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}
.checkbox-group {
    margin: 20px 0;
}
.checkbox-label {
    display: flex !important;
    align-items: center;
    font-weight: normal !important;
    cursor: pointer;
}
.checkbox-label input {
    width: auto !important;
    margin-right: 10px;
}
.form-group input, .form-group select {
  padding: 8px;
  width: 100%;
  max-width: 300px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--input-bg);
  color: var(--input-text);
}
.form-group small {
  display: block;
  margin-top: 5px;
  color: var(--text-color);
  opacity: 0.7;
}

.radio-group {
  display: flex;
  gap: 15px;
}

.radio-group label {
  font-weight: normal;
}

button {
  background: var(--primary-color);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}
button:hover {
  background: var(--primary-hover);
}

.button-group {
    display: flex;
    gap: 15px;
    margin-top: 15px;
}

button.secondary {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    color: var(--text-color);
}

button.secondary:hover {
    background: var(--input-bg);
}

.save-all-btn {
  width: 100%;
  padding: 15px;
  font-size: 1.1rem;
  margin-top: 20px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(12, 14, 18, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 200;
}

.modal-panel {
  background: var(--card-bg);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  width: min(90vw, 720px);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.25);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
}

.modal-body {
  padding: 16px 18px;
  overflow: auto;
}

.modal-footer {
  padding: 12px 18px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}

.modal-state {
  color: var(--text-color);
  opacity: 0.8;
}

.scheduler-logs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.scheduler-log {
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: color-mix(in srgb, var(--card-bg) 80%, var(--input-bg));
}

.log-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.9rem;
  opacity: 0.8;
}

.log-event {
  text-transform: capitalize;
  font-weight: 600;
}

.log-message {
  margin-top: 6px;
}

.log-meta {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 0.85rem;
  opacity: 0.75;
}

.log-meta span {
  background: var(--input-bg);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
}
</style>
