<script setup lang="ts">
import { defineProps } from 'vue'

defineProps<{
  files: string[]
  feedsByFile: Record<string, any>
}>()
</script>

<template>
  <div>
    <!-- Dynamic Feeds by File -->
    <section v-for="file in files" :key="file">
      <h2>{{ file }}</h2>
      <ul
        v-if="feedsByFile[file] && feedsByFile[file] !== 'Empty' && feedsByFile[file].length"
      >
        <li v-for="(feed, i) in feedsByFile[file]" :key="i">
          <a :href="feed.url" target="_blank">{{ feed.url }}</a>
        </li>
      </ul>
      <div v-else>
        <!-- Show loading status if feedsByFile[file] is still null -->
        <span v-if="feedsByFile[file] === null">Loading...</span>
        <span v-else>Empty</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
section {
  margin-bottom: 20px;
}
h2 {
  margin-top: 30px;
  color: #42b983;
}
ul {
  list-style-type: none;
  padding: 0;
}
li {
  display: inline-block;
  margin: 0 10px;
}
a {
  color: #42b983;
  text-decoration: none;
}
</style>