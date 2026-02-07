<script setup lang="ts">
import { ref, provide } from 'vue'
import FeedColumn from './FeedColumn.vue'
import ArticleColumn from './ArticleColumn.vue'
import EventColumn from './EventColumn.vue'
import TrendColumn from './TrendColumn.vue'

defineProps<{ msg: string }>()

const focusedColumn = ref<string | null>(null)
const selectedFeedUrl = ref<string | null>(null)

const setFocus = (column: string | null) => {
  focusedColumn.value = column
}

const selectFeed = (feedUrl: string | null) => {
  selectedFeedUrl.value = feedUrl
}

// Provide selectedFeedUrl to child components
provide('selectedFeedUrl', selectedFeedUrl)
provide('selectFeed', selectFeed)
</script>

<template>
  <div class="main-page">
    <div class="header-container">
      <div class="title-wrapper">
        <h1>{{ msg }}</h1>
        <div class="header-controls">
          <button v-if="focusedColumn" @click="setFocus(null)" class="clear-focus-btn">Clear Focus</button>
          <button v-if="selectedFeedUrl" @click="selectFeed(null)" class="clear-filter-btn">Clear Feed Filter</button>
        </div>
      </div>
    </div>

    <div class="columns-container">
      <div 
        :class="['column', { focused: focusedColumn === 'feeds', unfocused: focusedColumn && focusedColumn !== 'feeds' }]"
        @click="setFocus('feeds')"
      >
        <FeedColumn />
      </div>
      <div 
        :class="['column', { focused: focusedColumn === 'articles', unfocused: focusedColumn && focusedColumn !== 'articles' }]"
        @click="setFocus('articles')"
      >
        <ArticleColumn />
      </div>
      <div 
        :class="['column', { focused: focusedColumn === 'events', unfocused: focusedColumn && focusedColumn !== 'events' }]"
        @click="setFocus('events')"
      >
        <EventColumn />
      </div>
      <div 
        :class="['column', { focused: focusedColumn === 'trends', unfocused: focusedColumn && focusedColumn !== 'trends' }]"
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
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 10px;
  box-sizing: border-box;
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
  font-size: 1.5rem;
}

.header-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 300px;
}

.clear-focus-btn, .clear-filter-btn {
  padding: 8px 16px;
  background: #2c3e50;
  color: #42b983;
  border: 1px solid #42b983;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  width: 100%;
}

.clear-focus-btn:hover, .clear-filter-btn:hover {
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
  min-height: 300px;
  max-height: 500px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.column.focused {
  min-height: 400px;
  max-height: 600px;
}

.column.unfocused {
  opacity: 0.7;
  min-height: 200px;
  max-height: 300px;
}

/* Tablet: 2-column layout */
@media (min-width: 768px) {
  .main-page {
    padding: 15px;
  }

  h1 {
    font-size: 1.8rem;
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

  .clear-focus-btn, .clear-filter-btn {
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
    max-height: none;
    overflow: hidden;
  }

  .column.focused {
    flex: 1 1 60%;
    max-height: none;
  }

  .column.unfocused {
    flex: 1 1 calc(40% - 15px);
    max-height: none;
  }
}

/* Desktop: 4-column layout */
@media (min-width: 1200px) {
  .main-page {
    padding: 20px;
  }

  h1 {
    font-size: 2rem;
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