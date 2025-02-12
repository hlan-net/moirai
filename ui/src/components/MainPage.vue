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
        // Example response: ['file1', 'file2', 'file3']
        files.value = await responseFiles.json()
      } catch (error) {
        console.error('Error fetching files:', error)
      }

      // For each file, try to fetch its corresponding feed using the index.
      interface Feed {
        url: string;
        code?: number;
        status: string;
      }

      files.value.forEach(async (file: string, index: number) => {
        try {
          const responseFeed: Response = await fetch(`/api/feeds/${index}`);
          // Example response: [{"code":404,"status":"failed","url":"https://www.example.org/feed/"},{"status":"success","url":"https://sitename.com/atom.xml"}]
          const feedData: Feed[] = await responseFeed.json();

          // Filter out feeds with status "failed"
          const filteredFeeds = Array.isArray(feedData)
            ? feedData.filter(feed => feed.status !== 'failed')
            : [];

          feedsByFile.value[file] = filteredFeeds.length > 0 ? filteredFeeds : 'Empty';
        } catch (error) {
          console.error(`Error fetching feed for index ${index}:`, error);
          feedsByFile.value[file] = 'Empty';
        }
      });
    });

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
