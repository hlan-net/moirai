import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

/**
 * Centralized reactive settings store
 * Replaces scattered localStorage access with single source of truth
 */
export const useSettingsStore = defineStore('settings', () => {
  // Model & Provider Settings
  const llmEndpoint = ref<string>(localStorage.getItem('moirai_llm_endpoint') || 'ollama')
  const ollamaModel = ref<string>(localStorage.getItem('moirai_model') || 'llama3.2:3b')
  const openaiModel = ref<string>(localStorage.getItem('moirai_openai_model') || 'gpt-4-turbo')
  const geminiModel = ref<string>(localStorage.getItem('moirai_gemini_model') || 'gemini-1.5-pro')
  
  // API Keys
  const openaiApiKey = ref<string>(localStorage.getItem('moirai_openai_api_key') || '')
  const geminiApiKey = ref<string>(localStorage.getItem('moirai_gemini_api_key') || '')
  
  // Endpoints
  // Ollama runs locally over plain HTTP by design — NOSONAR (typescript:S5332)
  const ollamaEndpointUrl = ref<string>(localStorage.getItem('moirai_ollama_endpoint_url') || 'http://host.docker.internal:11434/v1') // NOSONAR
  
  // Theme
  const theme = ref<string>(localStorage.getItem('moirai_theme') || 'dark')

  // Computed: Current model based on provider
  const getCurrentModel = () => {
    switch (llmEndpoint.value) {
      case 'openai':
        return openaiModel.value
      case 'gemini':
        return geminiModel.value
      default:
        return ollamaModel.value
    }
  }

  // Computed: Current model key for storage
  const getCurrentModelKey = () => {
    switch (llmEndpoint.value) {
      case 'openai':
        return 'moirai_openai_model'
      case 'gemini':
        return 'moirai_gemini_model'
      default:
        return 'moirai_model'
    }
  }

  // Update current model based on provider
  const setCurrentModel = (model: string) => {
    switch (llmEndpoint.value) {
      case 'openai':
        openaiModel.value = model
        break
      case 'gemini':
        geminiModel.value = model
        break
      default:
        ollamaModel.value = model
    }
  }

  // Watch all settings and persist to localStorage
  watch(llmEndpoint, (value) => {
    localStorage.setItem('moirai_llm_endpoint', value)
  })
  
  watch(ollamaModel, (value) => {
    localStorage.setItem('moirai_model', value)
  })
  
  watch(openaiModel, (value) => {
    localStorage.setItem('moirai_openai_model', value)
  })
  
  watch(geminiModel, (value) => {
    localStorage.setItem('moirai_gemini_model', value)
  })
  
  watch(openaiApiKey, (value) => {
    if (value) localStorage.setItem('moirai_openai_api_key', value)
    else localStorage.removeItem('moirai_openai_api_key')
  })
  
  watch(geminiApiKey, (value) => {
    if (value) localStorage.setItem('moirai_gemini_api_key', value)
    else localStorage.removeItem('moirai_gemini_api_key')
  })
  
  watch(ollamaEndpointUrl, (value) => {
    localStorage.setItem('moirai_ollama_endpoint_url', value)
  })
  
  watch(theme, (value) => {
    localStorage.setItem('moirai_theme', value)
  })

  // Load settings from backend
  const loadFromBackend = async (settings: Record<string, any>) => {
    if (settings.moirai_llm_endpoint) llmEndpoint.value = settings.moirai_llm_endpoint
    if (settings.moirai_model) ollamaModel.value = settings.moirai_model
    if (settings.moirai_openai_model) openaiModel.value = settings.moirai_openai_model
    if (settings.moirai_gemini_model) geminiModel.value = settings.moirai_gemini_model
    if (settings.moirai_openai_api_key) openaiApiKey.value = settings.moirai_openai_api_key
    if (settings.moirai_gemini_api_key) geminiApiKey.value = settings.moirai_gemini_api_key
    if (settings.moirai_ollama_endpoint_url) ollamaEndpointUrl.value = settings.moirai_ollama_endpoint_url
    if (settings.moirai_theme) theme.value = settings.moirai_theme
  }

  // Save all settings to backend
  const saveToBackend = async () => {
    const settingsPayload = {
      moirai_llm_endpoint: llmEndpoint.value,
      moirai_model: ollamaModel.value,
      moirai_openai_model: openaiModel.value,
      moirai_gemini_model: geminiModel.value,
      moirai_openai_api_key: openaiApiKey.value,
      moirai_gemini_api_key: geminiApiKey.value,
      moirai_ollama_endpoint_url: ollamaEndpointUrl.value,
      moirai_theme: theme.value,
    }
    
    return settingsPayload
  }

  // Reset to defaults
  const resetToDefaults = () => {
    llmEndpoint.value = 'ollama'
    ollamaModel.value = 'llama3.2:3b'
    openaiModel.value = 'gpt-4-turbo'
    geminiModel.value = 'gemini-1.5-pro'
    openaiApiKey.value = ''
    geminiApiKey.value = ''
    ollamaEndpointUrl.value = 'http://host.docker.internal:11434/v1' // NOSONAR
    theme.value = 'dark'
  }

  return {
    // State
    llmEndpoint,
    ollamaModel,
    openaiModel,
    geminiModel,
    openaiApiKey,
    geminiApiKey,
    ollamaEndpointUrl,
    theme,
    
    // Getters
    getCurrentModel,
    getCurrentModelKey,
    
    // Actions
    setCurrentModel,
    loadFromBackend,
    saveToBackend,
    resetToDefaults,
  }
})
