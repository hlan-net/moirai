<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useTheme, type Theme } from '../composables/useTheme'

const appVersion = ref('Loading...')
const modelName = ref('llama3.1:latest')
const availableModels = ref<string[]>([])
const loadingModels = ref(false)
const allowPublicRead = ref(false)
const iterationInterval = ref(600)
const llmEndpoint = ref('ollama') // 'ollama' or 'openai'
const openaiApiKey = ref('')
const openaiModelName = ref('gpt-4-turbo')
const availableOpenAiModels = ref<string[]>([])
const geminiApiKey = ref('')
const geminiModelName = ref('gemini-1.5-pro')
const availableGeminiModels = ref<string[]>([])
const ollamaEndpointUrl = ref('http://host.docker.internal:11434/v1')
const collapsedSections = ref<Set<string>>(new Set(['general', 'ollama', 'openai', 'gemini']))

const { theme, setTheme } = useTheme()

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

const saveSettings = async () => {
  localStorage.setItem('moirai_model', modelName.value)
  localStorage.setItem('moirai_llm_endpoint', llmEndpoint.value)
  localStorage.setItem('moirai_openai_api_key', openaiApiKey.value)
  localStorage.setItem('moirai_openai_model', openaiModelName.value)
  localStorage.setItem('moirai_gemini_api_key', geminiApiKey.value)
  localStorage.setItem('moirai_gemini_model', geminiModelName.value)
  localStorage.setItem('moirai_ollama_endpoint_url', ollamaEndpointUrl.value)

  // Save server config
  try {
      const res = await fetch('/api/config', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
              allow_public_read: allowPublicRead.value,
              iteration_interval: iterationInterval.value
          })
      })
      if (!res.ok) {
          throw new Error("Failed to save config")
      }
  } catch (e) {
      console.error(e)
      alert("Failed to save server configuration.")
      return
  }

  alert('Settings saved!')
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

const fetchConfig = async () => {
    try {
        const res = await fetch('/api/config')
        if (res.ok) {
            const data = await res.json()
            allowPublicRead.value = data.allow_public_read
            iterationInterval.value = data.iteration_interval
            if (data.version) {
                appVersion.value = data.version
            }
        }
    } catch (e) {
        console.error("Error fetching config", e)
    }
}

onMounted(() => {
  const saved = localStorage.getItem('moirai_model')
  if (saved) {
    modelName.value = saved
  }
  const savedEndpoint = localStorage.getItem('moirai_llm_endpoint')
  if (savedEndpoint) {
    llmEndpoint.value = savedEndpoint
  }
  const savedApiKey = localStorage.getItem('moirai_openai_api_key')
  if (savedApiKey) {
    openaiApiKey.value = savedApiKey
  }
  const savedOpenaiModel = localStorage.getItem('moirai_openai_model')
  if (savedOpenaiModel) {
    openaiModelName.value = savedOpenaiModel
  }
  const savedGeminiApiKey = localStorage.getItem('moirai_gemini_api_key')
  if (savedGeminiApiKey) {
    geminiApiKey.value = savedGeminiApiKey
  }
  const savedGeminiModel = localStorage.getItem('moirai_gemini_model')
  if (savedGeminiModel) {
    geminiModelName.value = savedGeminiModel
  }
  const savedOllamaUrl = localStorage.getItem('moirai_ollama_endpoint_url')
  if (savedOllamaUrl) {
    ollamaEndpointUrl.value = savedOllamaUrl
  }

  if (llmEndpoint.value === 'ollama') {
    fetchOllamaModels()
  } else if (llmEndpoint.value === 'openai' && openaiApiKey.value) {
    fetchOpenAiModels()
  } else if (llmEndpoint.value === 'gemini' && geminiApiKey.value) {
    fetchGeminiModels()
  }
  fetchConfig()
})
</script>

<template>
  <div class="settings-page">
    <h1>Settings</h1>
    
    <div class="settings-section">
      <h2>About Moirai</h2>
      <div>
        <p><strong>Version:</strong> {{ appVersion }}</p>
        <p>Moirai is a GenAI-native press review platform powered by the Model Context Protocol (MCP).</p>
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
            <label for="model">LLM Model Name (Ollama):</label>
            <select v-if="availableModels.length" id="model" v-model="modelName">
              <option v-for="model in availableModels" :key="model" :value="model">
                {{ model }}
              </option>
            </select>
            <input v-else id="model" v-model="modelName" placeholder="e.g. gemma3:1b" />
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

    <div class="settings-section">
      <h2>
        General Settings
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
        <div class="form-group checkbox-group">
          <label for="public-read" class="checkbox-label">
            <input type="checkbox" id="public-read" v-model="allowPublicRead" />
            Allow Public Read Access (Stream Page)
          </label>
          <small>If enabled, the Stream page can be viewed without logging in.</small>
        </div>
        <div class="form-group">
          <label for="interval">Feed Refresh Interval (seconds):</label>
          <input type="number" id="interval" v-model="iterationInterval" min="0" step="60" />
          <small>How often the system checks for new articles. Set to 0 to disable automatic updates.</small>
        </div>
      </div>
    </div>

    <button @click="saveSettings">Save All Settings</button>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}
.settings-section {
  background: var(--card-bg);
  color: var(--text-color);
  padding: 20px;
  margin-bottom: 20px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
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
</style>
