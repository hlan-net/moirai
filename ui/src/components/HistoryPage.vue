<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

interface Article {
  _id: string;
  title: string;
  summary: string;
  link: string;
  published: string;
  feed_url: string;
  feed_title?: string;
}

const articles = ref<Article[]>([])
const loading = ref(true)
const refreshing = ref(false)
const expandedArticles = ref<Set<string>>(new Set())
let intervalId: number | undefined

const fetchArticles = async (isManual = false) => {
  if (isManual) refreshing.value = true
  try {
    const response = await fetch('/api/articles')
    if (response.ok) {
        const data = await response.json()
        articles.value = data.sort((a: Article, b: Article) => {
            return new Date(b.published).getTime() - new Date(a.published).getTime()
        })
    } else {
      console.error("Failed to fetch articles", response.status)
    }
  } catch (error) {
    console.error('Error fetching articles:', error)
  } finally {
    loading.value = false
    if (isManual) refreshing.value = false
  }
}

onMounted(() => {
  fetchArticles()
  intervalId = setInterval(fetchArticles, 60000)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
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

function getHostname(urlStr:string) {
  try {
    return new URL(urlStr).hostname
  } catch (e) {
    return urlStr
  }
}

const toggleExpand = (id: string) => {
  if (expandedArticles.value.has(id)) {
    expandedArticles.value.delete(id)
  } else {
    expandedArticles.value.add(id)
  }
}
</script>

<template>
  <div class="history-page">
    <header class="page-header">
        <div class="header-left">
            <h2>History Stream</h2>
            <span class="count">{{ articles.length }} Articles</span>
        </div>
        <button @click="fetchArticles(true)" :disabled="refreshing" class="refresh-btn" title="Check for updates">
            {{ refreshing ? 'Checking...' : '↻ Refresh' }}
        </button>
    </header>

    <div v-if="loading" class="loading">Loading stream...</div>
    
    <div v-else-if="articles.length" class="stream-container">
      <div v-for="article in articles" :key="article._id" class="stream-item">
        <div class="item-meta">
            <span class="source">{{ article.feed_title || getHostname(article.feed_url) }}</span>
            <span class="date">{{ formatDate(article.published) }}</span>
        </div>
        <h3 class="item-title">
            <a :href="article.link" target="_blank">{{ article.title }}</a>
        </h3>
        <div class="item-summary">
          <span v-if="!expandedArticles.has(article._id)">
            {{ stripHtml(article.summary).substring(0, 300) }}
            <button 
              v-if="stripHtml(article.summary).length > 300" 
              @click="toggleExpand(article._id)"
              class="read-more-btn"
            >
              ... Read More
            </button>
          </span>
          <span v-else>
            {{ stripHtml(article.summary) }}
            <button @click="toggleExpand(article._id)" class="read-more-btn">
              Show Less
            </button>
          </span>
        </div>
      </div>
    </div>
    
    <div v-else class="empty-state">No articles found in the stream.</div>
  </div>
</template>

<style scoped>
.history-page {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #eee;
    margin-bottom: 20px;
    padding-bottom: 10px;
}

.header-left {
    display: flex;
    align-items: baseline;
    gap: 15px;
}

.page-header h2 {
    margin: 0;
    color: var(--text-color);
}

.count {
    color: #7f8c8d;
    font-size: 0.9rem;
}

.refresh-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
    background: var(--button-bg);
    border-color: var(--primary-color);
    color: var(--primary-color);
}

.refresh-btn:disabled {
    opacity: 0.6;
    cursor: wait;
}

.stream-container {
    overflow-y: auto;
    flex: 1;
    padding-right: 10px; /* For scrollbar */
}

.stream-item {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
    transition: box-shadow 0.2s;
}

.stream-item:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.item-meta {
    font-size: 0.85rem;
    color: #95a5a6;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
}

.source {
    font-weight: 600;
    color: var(--text-color);
    opacity: 0.8;
}

.item-title {
    margin: 0 0 10px 0;
    font-size: 1.4rem;
    line-height: 1.3;
}

.item-title a {
    color: var(--primary-color);
    text-decoration: none;
}

.item-title a:hover {
    text-decoration: underline;
    color: var(--primary-hover);
}

.item-summary {
    color: var(--text-color);
    opacity: 0.9;
    line-height: 1.6;
    font-size: 1rem;
}

.read-more-btn {
  background: none;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0;
  margin-left: 5px;
}

.read-more-btn:hover {
  text-decoration: underline;
}

.loading, .empty-state {
    text-align: center;
    padding: 40px;
    color: #7f8c8d;
    font-size: 1.2rem;
}
</style>
