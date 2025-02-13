<script setup lang="ts">
import FeedColumn from './FeedColumn.vue'
import ArticleColumn from './ArticleColumn.vue'
import EventColumn from './EventColumn.vue'

defineProps<{ msg: string }>()
</script>

<template>
  <div>
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
    </div>
  </div>
</template>

<style scoped>
h1 {
  margin-bottom: 20px;
}
.columns-container {
  display: flex;
  justify-content: space-between;
  gap: 20px;
}
.column {
  flex: 1;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
</style>
