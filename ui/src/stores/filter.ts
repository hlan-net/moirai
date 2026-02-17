import { defineStore } from 'pinia'

export const useFilterStore = defineStore('filter', {
  state: () => ({
    selectedFeedId: null as string | null,
    selectedIssueId: null as string | null,
  }),
  getters: {
    selectedEventId: (state) => state.selectedIssueId,
    selectedTrendId: (state) => state.selectedIssueId,
  },
  actions: {
    setSelectedFeedId(id: string | null) {
      this.selectedFeedId = id
      if (id) {
        // Clear issue selection if a feed is selected (assuming feed is top-level filter)
        this.selectedIssueId = null
      }
    },
    setSelectedIssueId(id: string | null) {
      this.selectedIssueId = id
    },
    setSelectedEventId(id: string | null) {
      this.selectedIssueId = id
    },
    setSelectedTrendId(id: string | null) {
      this.selectedIssueId = id
    },
    clearAllFilters() {
      this.selectedFeedId = null
      this.selectedIssueId = null
    },
  },
})
