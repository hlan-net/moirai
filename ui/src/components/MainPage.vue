<script setup lang="ts">
import { onMounted, ref } from 'vue'
import FeedColumn from './FeedColumn.vue'
import ArticleColumn from './ArticleColumn.vue'
import EventColumn from './EventColumn.vue'

defineProps<{ msg: string }>()
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
    <h1>{{ msg }}</h1>
    <div class="columns-container">
      <div class="column">
        <FeedColumn :files="files" :feedsByFile="feedsByFile" />
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
