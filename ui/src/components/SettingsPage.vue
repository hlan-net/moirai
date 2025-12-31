<script setup lang="ts">
import { ref, onMounted } from 'vue'

const appVersion = ref('0.1.0-alpha')
const modelName = ref('llama3.1')
const availableModels = ref<string[]>([])
const loadingModels = ref(false)

const saveSettings = () => {
  localStorage.setItem('moirai_model', modelName.value)
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

onMounted(() => {
  const saved = localStorage.getItem('moirai_model')
  if (saved) {
    modelName.value = saved
  }
  fetchModels()
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
  background: #fff;
  color: #333;
  padding: 20px;
  margin-bottom: 20px;
  border-radius: 8px;
  border: 1px solid #ddd;
}
h2 {
  margin-top: 0;
  color: #333;
  border-bottom: 1px solid #eee;
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
.form-group input, .form-group select {
  padding: 8px;
  width: 100%;
  max-width: 300px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: white;
  color: #333;
}
.form-group small {
  display: block;
  margin-top: 5px;
  color: #666;
}
button {
  background: #007acc;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}
button:hover {
  background: #005f9e;
}
</style>
