import { defineStore } from 'pinia'

export const useFilterStore = defineStore('filter', {
  state: () => ({
    selectedFeedId: null as string | null,
    selectedIssueId: null as string | null,
    contextualFeedUrls: null as string[] | null,
    lastUpdated: null as Date | null,
    isRefreshing: false,
  }),
  getters: {
    selectedEventId: (state) => state.selectedIssueId,
    selectedTrendId: (state) => state.selectedIssueId,
  },
  actions: {
    setSelectedFeedId(id: string | null) {
      this.selectedFeedId = id
      this.contextualFeedUrls = null
      if (id) {
        // Clear issue selection if a feed is selected (assuming feed is top-level filter)
        this.selectedIssueId = null
      }
    },
    setSelectedIssueId(id: string | null) {
      this.selectedIssueId = id
      if (!id) {
        this.contextualFeedUrls = null
      }
    },
    setSelectedEventId(id: string | null) {
      this.selectedIssueId = id
      if (!id) {
        this.contextualFeedUrls = null
      }
    },
    setSelectedTrendId(id: string | null) {
      this.selectedIssueId = id
      if (!id) {
        this.contextualFeedUrls = null
      }
    },
    setContextualFeedUrls(urls: string[] | null) {
      this.contextualFeedUrls = urls
    },
    clearAllFilters() {
      this.selectedFeedId = null
      this.selectedIssueId = null
      this.contextualFeedUrls = null
    },
    markRefreshStart() {
      this.isRefreshing = true
    },
    markRefreshComplete() {
      this.isRefreshing = false
      this.lastUpdated = new Date()
    },
  },
})
