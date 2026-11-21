import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useFilterStore } from '../stores/filter'
import { authFetch } from '../utils/authFetch'

export interface Premise {
  type: 'message' | 'issue'
  id: string
}

export type LongevityTier = 'transient' | 'temporal' | 'epic'

export interface Issue {
  _id: string
  logos: string
  description: string
  premises: Premise[]
  longevity: LongevityTier
  status: 'active' | 'eternal'
  public?: boolean
}

export interface IssueListOptions {
  /** Longevity tier to request; omit to list every issue. */
  longevity?: LongevityTier
  /** Milliseconds between background refreshes. */
  refreshMs: number
  /** Report background refreshes to the filter store (the sync indicator). */
  trackRefresh?: boolean
  /** The wording that differs between the views. */
  text: {
    fetchError: string
    confirmDelete: string
    confirmRemovePremise: string
  }
}

/**
 * The issue list behind the Events and Trends columns and the Lifespan view:
 * loading, periodic refresh, refetch on feed filter change, text search,
 * selection, expansion, delete and premise removal.
 */
export function useIssueList(options: IssueListOptions) {
  const filterStore = useFilterStore()

  const issues = ref<Issue[]>([])
  const loading = ref(true)
  const refreshing = ref(false)
  const expandedIssues = ref<Set<string>>(new Set())
  const searchQuery = ref('')
  let refreshInterval: number | null = null

  const filteredIssues = computed(() => {
    if (!searchQuery.value.trim()) return issues.value
    const query = searchQuery.value.toLowerCase()
    return issues.value.filter(
      (issue) =>
        issue.logos.toLowerCase().includes(query) || issue.description.toLowerCase().includes(query)
    )
  })

  const fetchIssues = async (isRefresh = false) => {
    if (isRefresh) {
      if (options.trackRefresh) filterStore.markRefreshStart()
      refreshing.value = true
    } else {
      loading.value = true
    }

    try {
      const params = new URLSearchParams()
      if (options.longevity) {
        params.append('longevity', options.longevity)
      }
      if (filterStore.selectedFeedId) {
        params.append('feed_url', filterStore.selectedFeedId)
      }

      const queryString = params.toString() ? `?${params.toString()}` : ''
      const response = await authFetch(`/api/issues${queryString}`)

      if (response.ok) {
        const data = await response.json()
        issues.value = Array.isArray(data)
          ? data.filter((i: Issue) => !i._id.startsWith('_design/'))
          : []
      } else if (!isRefresh) {
        issues.value = []
      }
    } catch (error) {
      console.error(options.text.fetchError, error)
      if (!isRefresh) {
        issues.value = []
      }
    } finally {
      loading.value = false
      refreshing.value = false
      if (isRefresh && options.trackRefresh) {
        filterStore.markRefreshComplete()
      }
    }
  }

  const selectIssue = (issueId: string) => {
    filterStore.setSelectedIssueId(filterStore.selectedIssueId === issueId ? null : issueId)
  }

  /** Put an issue returned by the API in place of its stale copy. */
  const replaceIssue = (updated: Issue) => {
    const index = issues.value.findIndex((i) => i._id === updated._id)
    if (index !== -1) {
      issues.value[index] = updated
    }
  }

  const deleteIssue = async (id: string) => {
    if (!confirm(options.text.confirmDelete)) return
    try {
      const res = await authFetch(`/api/issues/${id}`, { method: 'DELETE' })
      if (res.ok) {
        issues.value = issues.value.filter((i) => i._id !== id)
        expandedIssues.value.delete(id)
        if (filterStore.selectedIssueId === id) {
          filterStore.setSelectedIssueId(null)
        }
      }
    } catch (error) {
      console.error(error)
    }
  }

  const removePremise = async (issueId: string, premiseId: string) => {
    if (!confirm(options.text.confirmRemovePremise)) return
    try {
      const res = await authFetch(`/api/issues/${issueId}/premises`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: premiseId }),
      })
      if (res.ok) {
        replaceIssue(await res.json())
      }
    } catch (error) {
      console.error(error)
    }
  }

  const toggleExpand = (id: string) => {
    if (expandedIssues.value.has(id)) {
      expandedIssues.value.delete(id)
    } else {
      expandedIssues.value.add(id)
    }
  }

  watch(
    () => filterStore.selectedFeedId,
    () => {
      void fetchIssues()
    }
  )

  onMounted(() => {
    void fetchIssues()
    refreshInterval = globalThis.setInterval(() => void fetchIssues(true), options.refreshMs)
  })

  onUnmounted(() => {
    if (refreshInterval !== null) {
      clearInterval(refreshInterval)
    }
  })

  return {
    issues,
    loading,
    refreshing,
    expandedIssues,
    searchQuery,
    filteredIssues,
    fetchIssues,
    selectIssue,
    replaceIssue,
    deleteIssue,
    removePremise,
    toggleExpand,
  }
}
