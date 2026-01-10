<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface Article {
  _id: string;
  title: string;
  summary: string;
  link: string;
  published: string;
  feed_url: string;
  events?: string[];
}

const articles = ref<Article[]>([])
const loading = ref(true)

const fetchArticles = async () => {
  try {
    const response = await fetch('/api/articles')
    if (response.ok) {
        const data = await response.json()
        articles.value = data.sort((a: Article, b: Article) => {
            return new Date(b.published).getTime() - new Date(a.published).getTime()
        })
    }
  } catch (error) {
    console.error('Error fetching articles:', error)
  } finally {
    loading.value = false
  }
}

const deleteArticle = async (id: string) => {
  if (!confirm("Delete this article?")) return;
  try {
    const res = await fetch(`/api/articles/${id}`, { method: 'DELETE' })
    if (res.ok) {
      articles.value = articles.value.filter(a => a._id !== id)
    } else {
      alert("Failed to delete article")
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  fetchArticles()
  setInterval(fetchArticles, 60000)
})

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleString()
  } catch (e) {
    return dateStr
  }
}

function stripHtml(html: string) {
   const doc = new DOMParser().parseFromString(html, 'text/html');
   return doc.body.textContent || "";
}
function getHostname(urlStr: string) {
  try {
    return new URL(urlStr).hostname
  } catch (e) {
    return urlStr
  }
}
</script>

<template>
  <div class="article-column">
    <h2>Articles ({{ articles.length }})</h2>
    <div v-if="loading">Loading articles...</div>
    <div v-else-if="articles.length" class="article-list">
      <div v-for="article in articles" :key="article._id" class="article-card">
        <div class="card-header">
           <h3><a :href="article.link" target="_blank">{{ article.title }}</a></h3>
           <button @click="deleteArticle(article._id)" class="delete-btn" title="Delete Article">×</button>
        </div>
        <p class="meta">{{ formatDate(article.published) }} | {{ getHostname(article.feed_url) }}</p>
        <p class="summary">{{ stripHtml(article.summary).substring(0, 200) }}...</p>
        <div v-if="article.events" class="event-tags">
          <span v-for="event in article.events" :key="event" class="tag">{{ event }}</span>
        </div>
      </div>
    </div>
    <div v-else>No articles found yet.</div>
  </div>
</template>

<style scoped>
.article-column {
  height: 100%;
  display: flex;
  flex-direction: column;
}
h2 {
  color: #007acc;
  margin-top: 0;
  position: sticky;
  top: 0;
  background: transparent;
  padding: 10px 0;
  z-index: 1;
}
.article-list {
  overflow-y: auto;
  flex: 1;
}
.article-card {
  border-bottom: 1px solid #eee;
  padding: 15px 0;
  text-align: left;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.article-card h3 {
  margin: 0 0 5px 0;
  font-size: 1.1rem;
}
.article-card a {
  color: #007acc;
  text-decoration: none;
}
.article-card a:hover {
  text-decoration: underline;
}
.meta {
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 8px;
}
.summary {
  font-size: 0.9rem;
  color: #333;
  line-height: 1.4;
}
.event-tags {
  margin-top: 10px;
}
.tag {
  display: inline-block;
  background: #eee;
  color: #333;
  padding: 2px 6px;
  border-radius: 4px;
  margin-right: 5px;
  font-size: 0.8rem;
}
.delete-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0 5px;
}
.delete-btn:hover {
  color: #cc0000;
}
</style>