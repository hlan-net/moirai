import { ref, watch } from 'vue'

const currentNamespace = ref('')
const namespaces = ref<string[]>([])

export function useNamespace() {
  const fetchNamespaces = async () => {
    try {
      const res = await fetch('/api/namespaces')
      if (res.ok) {
        namespaces.value = await res.json()
      }
    } catch (e) {
      console.error('Error fetching namespaces:', e)
    }
  }

  // Persist to local storage
  watch(currentNamespace, (newVal) => {
    if (newVal) {
        localStorage.setItem('moirai_namespace', newVal)
    } else {
        localStorage.removeItem('moirai_namespace')
    }
  })

  // Initialize from local storage
  const initNamespace = () => {
      const stored = localStorage.getItem('moirai_namespace')
      if (stored) {
          currentNamespace.value = stored
      }
      fetchNamespaces()
  }

  return {
    currentNamespace,
    namespaces,
    fetchNamespaces,
    initNamespace
  }
}
