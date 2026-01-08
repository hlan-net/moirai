<script setup lang="ts">
import { onMounted } from 'vue'
import FeedColumn from './FeedColumn.vue'
import ArticleColumn from './ArticleColumn.vue'
import EventColumn from './EventColumn.vue'
import TrendColumn from './TrendColumn.vue'
import { useNamespace } from '../composables/useNamespace'

defineProps<{ msg: string }>()

const { currentNamespace, namespaces, initNamespace } = useNamespace()

onMounted(() => {
  initNamespace()
})
</script>

<template>
  <div class="main-page">
    <h1>{{ msg }}</h1>
    
    <div class="controls">
      <label for="ns-select">Namespace Filter: </label>
      <select 
        id="ns-select" 
        v-model="currentNamespace" 
        class="ns-select"
      >
        <option value="">-- No Filter (Show All) --</option>
        <option v-for="ns in namespaces" :key="ns" :value="ns">
          {{ ns }}
        </option>
      </select>
      <span v-if="currentNamespace" class="active-badge">Filtered</span>
    </div>

    <div class="columns-container">
      <div class="column">
        <FeedColumn />
      </div>
      <div class="column">
        <ArticleColumn />
      </div>
      <div class="column">
        <EventColumn :namespace="currentNamespace" />
      </div>
      <div class="column">
        <TrendColumn :namespace="currentNamespace" />
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
}
.ns-select {
  padding: 8px;
  width: 350px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 1rem;
  background-color: white;
  color: #333;
}
.active-badge {
  background: #d83b01;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  margin-left: 10px;
  vertical-align: middle;
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