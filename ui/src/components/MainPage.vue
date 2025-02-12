<template>
  <div class="main">
    <h1>{{ msg }}</h1>

    <!-- Dynamic Feeds by File -->
    <section v-for="file in files" :key="file">
      <h2>{{ file }}</h2>
      <ul v-if="feedsByFile[file] !== 'Empty' && feedsByFile[file].length">
        <li v-for="(feed, i) in feedsByFile[file]" :key="i">
          <a :href="feed.url" target="_blank">{{ feed.url }}</a>
        </li>
      </ul>
      <div v-else>
        Empty
      </div>
    </section>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue'

export default defineComponent({
  name: 'MainPage',
  props: {
    msg: String
  },
  setup() {
    const files = ref<string[]>([])
    const feedsByFile = ref<Record<string, any>>({})

    onMounted(async () => {
      try {
        const responseFiles = await fetch('/api/feeds')
        files.value = await responseFiles.json()
      } catch (error) {
        console.error('Error fetching files:', error)
      }

      // For each file, try to fetch its corresponding feed.
      for (const file of files.value) {
        try {
          const responseFeed = await fetch(`/api/feeds/${encodeURIComponent(file)}`)
          const feedData = await responseFeed.json()
          feedsByFile.value[file] =
            Array.isArray(feedData) && feedData.length > 0 ? feedData : "Empty"
        } catch (error) {
          console.error(`Error fetching feed for ${file}:`, error)
          feedsByFile.value[file] = "Empty"
        }
      }
    })

    return { files, feedsByFile }
  }
})
</script>

<style scoped>
h1 {
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
section {
  margin-bottom: 20px;
}
</style>
