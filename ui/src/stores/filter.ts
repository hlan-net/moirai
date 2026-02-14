import { defineStore } from 'pinia'

export const useFilterStore = defineStore('filter', {
  state: () => ({
    selectedFeedId: null as string | null,
    selectedEventId: null as string | null,
    selectedTrendId: null as string | null,
  }),
  actions: {
    setSelectedFeedId(id: string | null) {
      this.selectedFeedId = id
      if (id) {
        // Clear event/trend selection if a feed is selected (assuming feed is top-level filter)
        this.selectedEventId = null
        this.selectedTrendId = null
      }
    },
    setSelectedEventId(id: string | null) {
      this.selectedEventId = id
      if (id) {
        // Clear trend selection if an event is selected
        this.selectedTrendId = null
      }
    },
    setSelectedTrendId(id: string | null) {
      this.selectedTrendId = id
    },
    clearAllFilters() {
      this.selectedFeedId = null
      this.selectedEventId = null
      this.selectedTrendId = null
    },
  },
})
