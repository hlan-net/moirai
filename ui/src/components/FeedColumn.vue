<script setup lang="ts">
import { onMounted, ref } from 'vue'

const files = ref<string[]>([])
const feedsByFile = ref<Record<string, any>>({})

onMounted(async () => {
  try {
    const responseFiles = await fetch('/api/feeds')
    // Example response: ['file1', 'file2', 'file3']
    const fileList = await responseFiles.json()
    files.value = fileList

    // Initialize each file's feed value so the UI renders immediately
    fileList.forEach((file: string) => {
      feedsByFile.value[file] = null
    })
  } catch (error) {
    console.error('Error fetching files:', error)
  }

  // For each file, fetch its corresponding feed 
  interface Feed {
    url: string;
    code?: number;
    status: string;
  }

  files.value.forEach(async (file: string, index: number) => {
    try {
      const responseFeed: Response = await fetch(`/api/feeds/${index}`)
      const feedData: Feed[] = await responseFeed.json()

      // Filter out feeds with status "failed"
      const filteredFeeds = Array.isArray(feedData)
        ? feedData.filter(feed => feed.status !== 'failed')
        : []

      feedsByFile.value[file] = filteredFeeds.length > 0 ? filteredFeeds : 'Empty'
    } catch (error) {
      console.error(`Error fetching feed for index ${index}:`, error)
      feedsByFile.value[file] = 'Empty'
    }
  })
})
</script>

<template>
  <div>
    <h2>Feeds</h2>
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