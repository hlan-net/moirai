import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authFetch } from '../utils/authFetch'

export interface SessionDoc {
  session_id: string
  session_type: 'scheduled_agent' | 'on_new_article' | 'chat'
  userspace: string
  agent_config_id: string | null
  agent_name: string | null
  trigger: string | null
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  status: 'running' | 'success' | 'error' | 'cancelled'
  error: string | null
  resolved_llm: Record<string, unknown>
  llm_calls: number
  tool_calls: number
  articles_processed: number
  step_count?: number
}

export interface SessionStep {
  step_id: string
  step_type: 'tool_call' | 'llm_call'
  tool_name?: string
  input_summary?: string
  output_summary?: string
  status: 'success' | 'error' | 'retried' | 'pending_approval' | 'denied'
  latency_ms?: number
  correlation_id?: string
  attempt?: number
  risk_level?: 'normal' | 'destructive'
  timestamp?: string
  error_message?: string
  error_code?: string
}

const USERSPACE_STORAGE_KEY = 'moirai_sessions_userspace'

export const useSessionsStore = defineStore('sessions', () => {
  const userspaces = ref<string[]>([])
  const currentUserspace = ref<string>(localStorage.getItem(USERSPACE_STORAGE_KEY) || '')
  const sessions = ref<SessionDoc[]>([])
  const loading = ref(false)
  const loadingUserspaces = ref(false)
  const error = ref<string>('')

  const setCurrentUserspace = (userspace: string) => {
    currentUserspace.value = userspace
    if (userspace) {
      localStorage.setItem(USERSPACE_STORAGE_KEY, userspace)
    } else {
      localStorage.removeItem(USERSPACE_STORAGE_KEY)
    }
  }

  const loadUserspaces = async () => {
    loadingUserspaces.value = true
    error.value = ''
    try {
      const response = await authFetch('/api/userspaces')
      if (!response.ok) {
        throw new Error(`Failed to load userspaces (${response.status})`)
      }
      userspaces.value = await response.json()
      if (userspaces.value.length > 0 && !userspaces.value.includes(currentUserspace.value)) {
        setCurrentUserspace(userspaces.value[0])
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      loadingUserspaces.value = false
    }
  }

  const loadSessions = async (limit = 50, offset = 0) => {
    if (!currentUserspace.value) {
      sessions.value = []
      return
    }
    loading.value = true
    error.value = ''
    try {
      const params = new URLSearchParams({
        userspace: currentUserspace.value,
        limit: String(limit),
        offset: String(offset),
      })
      const response = await authFetch(`/api/sessions?${params.toString()}`)
      if (!response.ok) {
        throw new Error(`Failed to load sessions (${response.status})`)
      }
      sessions.value = await response.json()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      sessions.value = []
    } finally {
      loading.value = false
    }
  }

  const fetchSession = async (sessionId: string): Promise<SessionDoc | null> => {
    try {
      const response = await authFetch(`/api/sessions/${sessionId}`)
      if (!response.ok) {
        throw new Error(`Failed to load session (${response.status})`)
      }
      return await response.json()
    } catch {
      return null
    }
  }

  const fetchSteps = async (sessionId: string): Promise<SessionStep[]> => {
    try {
      const response = await authFetch(`/api/sessions/${sessionId}/steps`)
      if (!response.ok) {
        throw new Error(`Failed to load steps (${response.status})`)
      }
      return await response.json()
    } catch {
      return []
    }
  }

  const cancelSession = async (sessionId: string): Promise<boolean> => {
    try {
      const response = await authFetch(`/api/sessions/${sessionId}/cancel`, { method: 'POST' })
      return response.ok
    } catch {
      return false
    }
  }

  return {
    userspaces,
    currentUserspace,
    sessions,
    loading,
    loadingUserspaces,
    error,
    setCurrentUserspace,
    loadUserspaces,
    loadSessions,
    fetchSession,
    fetchSteps,
    cancelSession,
  }
})
