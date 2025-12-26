<script setup lang="ts">
import FeedColumn from './FeedColumn.vue'
import ArticleColumn from './ArticleColumn.vue'
import EventColumn from './EventColumn.vue'
import TrendColumn from './TrendColumn.vue'

defineProps<{ msg: string }>()
</script>

<template>
  <div class="main-page">
    <h1>{{ msg }}</h1>
    <div class="columns-container">
      <div class="column">
        <FeedColumn />
      </div>
      <div class="column">
        <ArticleColumn />
      </div>
      <div class="column">
        <EventColumn />
      </div>
      <div class="column">
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
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>