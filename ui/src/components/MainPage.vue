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
  if (feedUrl) {
    console.log('Feed selected:', feedUrl)
  }
}

// Provide selectedFeedUrl to child components
provide('selectedFeedUrl', selectedFeedUrl)
provide('selectFeed', selectFeed)
</script>

<template>
  <div class="main-page">
    <h1>{{ msg }}</h1>
    
    <div v-if="focusedColumn || selectedFeedUrl" class="controls">
      <button v-if="focusedColumn" @click="setFocus(null)" class="clear-focus-btn">Clear Focus</button>
      <button v-if="selectedFeedUrl" @click="selectFeed(null)" class="clear-filter-btn">Clear Feed Filter</button>
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
.main-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 20px;
  box-sizing: border-box;
}
h1 {
  margin-bottom: 20px;
  text-align: center;
}
.controls {
  margin-bottom: 20px;
  text-align: center;
  display: flex;
  gap: 10px;
  justify-content: center;
}

.clear-focus-btn, .clear-filter-btn {
  padding: 8px 16px;
  background: #2c3e50;
  color: #42b983;
  border: 1px solid #42b983;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
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

.columns-container {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  flex: 1;
  overflow: hidden; /* Prevent full page scroll, allow columns to scroll */
}
.column {
  flex: 1;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--card-bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s ease;
}
.column.focused {
  flex-grow: 2;
}
.column.unfocused {
  flex-grow: 0.5;
  opacity: 0.5;
}
</style>