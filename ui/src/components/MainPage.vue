<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import FeedColumn from './FeedColumn.vue'
import ArticleColumn from './ArticleColumn.vue'
import EventColumn from './EventColumn.vue'
import TrendColumn from './TrendColumn.vue'
import { useFilterStore } from '../stores/filter' // Import the new filter store
import { TIME_DISPLAY_UPDATE_INTERVAL } from '../config/polling'

defineProps<{ msg: string }>()

const focusedColumn = ref<string | null>(null)
// const selectedFeedUrl = ref<string | null>(null) // NO LONGER USED, replaced by filterStore

const filterStore = useFilterStore() // Initialize the filter store

const setFocus = (column: string | null) => {
  focusedColumn.value = column
}

// const selectFeed = (feedUrl: string | null) => { // NO LONGER USED, replaced by filterStore
//   selectedFeedUrl.value = feedUrl
// }

// Provide selectedFeedUrl to child components - NO LONGER NEEDED
// provide('selectedFeedUrl', selectedFeedUrl)
// provide('selectFeed', selectFeed)

const hasActiveFilters = computed(() => {
  return (
    filterStore.selectedFeedId !== null ||
    filterStore.selectedIssueId !== null
  )
})

// Time display formatting
const timeAgoDisplay = ref('')
let timeUpdateInterval: number | null = null

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  
  if (seconds < 10) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

function updateTimeDisplay() {
  if (filterStore.lastUpdated) {
    timeAgoDisplay.value = formatTimeAgo(filterStore.lastUpdated)
  }
}

onMounted(() => {
  timeUpdateInterval = window.setInterval(() => {
    updateTimeDisplay()
  }, TIME_DISPLAY_UPDATE_INTERVAL)
})

onUnmounted(() => {
  if (timeUpdateInterval) {
    clearInterval(timeUpdateInterval)
  }
})
</script>

<template>
  <div class="main-page">
    <div class="dashboard-status">
      <div v-if="filterStore.isRefreshing" class="status-indicator refreshing">
        <span class="spinner"></span>
        Refreshing data...
      </div>
      <div v-else-if="filterStore.lastUpdated" class="status-indicator">
        <span class="check-icon">✓</span>
        Updated {{ timeAgoDisplay }}
      </div>
    </div>

    <div class="header-container">
      <div class="title-wrapper">
        <h1>{{ msg }}</h1>
        <div class="header-controls">
          <button v-if="focusedColumn" @click="setFocus(null)" class="clear-focus-btn">
            Clear Focus
          </button>
          <button
            v-if="hasActiveFilters"
            @click="filterStore.clearAllFilters()"
            class="clear-filter-btn"
          >
            Clear All Filters
          </button>
        </div>
      </div>
    </div>

    <div class="columns-container">
      <div
        :class="[
          'column',
          {
            focused: focusedColumn === 'feeds',
            unfocused: focusedColumn && focusedColumn !== 'feeds',
          },
        ]"
        @click="setFocus('feeds')"
      >
        <FeedColumn />
      </div>
      <div
        :class="[
          'column',
          {
            focused: focusedColumn === 'articles',
            unfocused: focusedColumn && focusedColumn !== 'articles',
          },
        ]"
        @click="setFocus('articles')"
      >
        <ArticleColumn />
      </div>
      <div
        :class="[
          'column',
          {
            focused: focusedColumn === 'events',
            unfocused: focusedColumn && focusedColumn !== 'events',
          },
        ]"
        @click="setFocus('events')"
      >
        <EventColumn />
      </div>
      <div
        :class="[
          'column',
          {
            focused: focusedColumn === 'trends',
            unfocused: focusedColumn && focusedColumn !== 'trends',
          },
        ]"
        @click="setFocus('trends')"
      >
        <TrendColumn />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Mobile-first approach: Base styles for mobile devices */
.main-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 10px;
  box-sizing: border-box;
}

.dashboard-status {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
  padding: 0.5rem 1rem;
  display: flex;
  justify-content: flex-end;
  margin: -10px -10px 10px -10px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--color-text);
  opacity: 0.7;
}

.status-indicator.refreshing {
  color: var(--color-heading);
  opacity: 1;
}

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.check-icon {
  color: #42b983;
  font-weight: bold;
}

.header-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 15px;
  gap: 10px;
}

.title-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

h1 {
  margin: 0;
  text-align: center;
}

.header-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 300px;
}

.clear-focus-btn,
.clear-filter-btn {
  padding: 8px 16px;
  background: #2c3e50;
  color: #42b983;
  border: 1px solid #42b983;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  width: 100%;
}

.clear-focus-btn:hover,
.clear-filter-btn:hover {
  background: #34495e;
}

.clear-filter-btn {
  background: #2d5a8f;
  color: #fff;
  border-color: #4a7eb7;
}

.clear-filter-btn:hover {
  background: #3a6ba5;
}

/* Mobile: Stack columns vertically */
.columns-container {
  display: flex;
  flex-direction: column;
  gap: 15px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.column {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--card-bg);
  display: flex;
  flex-direction: column;
  min-height: 200px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.column.focused {
  min-height: 300px;
}

.column.unfocused {
  opacity: 0.7;
  min-height: 150px;
}

/* Tablet: 2-column layout */
@media (min-width: 768px) {
  .main-page {
    padding: 15px;
  }

  .header-container {
    flex-direction: row;
    justify-content: space-between;
    margin-bottom: 20px;
  }

  .title-wrapper {
    flex-direction: row;
    width: auto;
  }

  .header-controls {
    flex-direction: row;
    gap: 10px;
    width: auto;
  }

  .clear-focus-btn,
  .clear-filter-btn {
    width: auto;
  }

  .columns-container {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 15px;
    overflow: hidden;
  }

  .column {
    flex: 1 1 calc(50% - 10px);
    min-width: 0;
  }

  .column.focused {
    flex: 1 1 60%;
  }

  .column.unfocused {
    flex: 1 1 calc(40% - 15px);
  }
}

/* Desktop: 4-column layout */
@media (min-width: 1200px) {
  .main-page {
    padding: 20px;
  }

  .dashboard-status {
    margin: -20px -20px 15px -20px;
  }

  .header-container {
    justify-content: center;
  }

  .title-wrapper {
    position: relative;
  }

  .header-controls {
    position: absolute;
    left: 100%;
    margin-left: 20px;
    white-space: nowrap;
  }

  .columns-container {
    flex-wrap: nowrap;
    gap: 20px;
  }

  .column {
    flex: 1;
    min-height: 0;
  }

  .column.focused {
    flex-grow: 2;
  }

  .column.unfocused {
    flex-grow: 0.5;
    opacity: 0.5;
  }
}
</style>
