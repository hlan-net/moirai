<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useTheme, type Theme } from '../composables/useTheme'

const appVersion = ref('0.1.0-alpha')
const modelName = ref('llama3.1:latest')
const availableModels = ref<string[]>([])
const loadingModels = ref(false)
const allowPublicRead = ref(false)
const iterationInterval = ref(600)

const { theme, setTheme } = useTheme()

const saveSettings = async () => {
  localStorage.setItem('moirai_model', modelName.value)
  
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

const fetchModels = async () => {
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

const fetchConfig = async () => {
    try {
        const res = await fetch('/api/config')
        if (res.ok) {
            const data = await res.json()
            allowPublicRead.value = data.allow_public_read
            iterationInterval.value = data.iteration_interval
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
  fetchModels()
  fetchConfig()
})
</script>

<template>
  <div class="settings-page">
    <h1>Settings</h1>
    
    <div class="settings-section">
      <h2>About Moirai</h2>
      <p><strong>Version:</strong> {{ appVersion }}</p>
      <p>Moirai is a GenAI-native press review platform powered by the Model Context Protocol (MCP).</p>
    </div>

    <div class="settings-section">
      <h2>Configuration</h2>
      
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
              Allow Public Read Access (History Page)
          </label>
          <small>If enabled, the History page can be viewed without logging in.</small>
      </div>

      <div class="form-group">
          <label for="interval">Feed Refresh Interval (seconds):</label>
          <input type="number" id="interval" v-model="iterationInterval" min="0" step="60" />
          <small>How often the system checks for new articles. Set to 0 to disable automatic updates.</small>
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
      <button @click="saveSettings">Save</button>
    </div>
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
