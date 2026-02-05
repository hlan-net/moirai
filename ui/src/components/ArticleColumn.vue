<script setup lang="ts">
import { onMounted, ref, onUnmounted } from 'vue'
import { articleCache, type Article } from '../utils/articleCache'

const articles = ref<Article[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const fetchingUpdates = ref(false)
const hasMore = ref(true)
const totalCount = ref(0)
const sentinelEl = ref<HTMLElement | null>(null)

let observer: IntersectionObserver | null = null
let refreshInterval: number | null = null

const PAGE_SIZE = 50

const fetchArticles = async (skip = 0, since?: string) => {
  try {
    const params = new URLSearchParams({
      limit: PAGE_SIZE.toString(),
      skip: skip.toString()
    })
    if (since) {
      params.append('since', since)
    }

    const response = await fetch(`/api/articles?${params}`)
    if (response.ok) {
      const data = await response.json()
      return {
        articles: data.articles || [],
        hasMore: data.has_more || false,
        totalCount: data.total_count || 0
      }
    }
  } catch (error) {
    console.error('Error fetching articles:', error)
  }
  return { articles: [], hasMore: false, totalCount: 0 }
}

const loadFromCache = async () => {
  try {
    const cached = await articleCache.getArticles()
    if (cached.length > 0) {
      articles.value = cached
      loading.value = false
      console.log(`Loaded ${cached.length} articles from cache`)
    }
  } catch (error) {
    console.error('Error loading from cache:', error)
  }
}

const fetchLatestUpdates = async () => {
  fetchingUpdates.value = true
  try {
    const newestTimestamp = await articleCache.getNewestTimestamp()
    const result = await fetchArticles(0, newestTimestamp || undefined)
    
    if (result.articles.length > 0) {
      // Merge new articles with existing (deduplicate by _id)
      const existingIds = new Set(articles.value.map((a: Article) => a._id))
      const newArticles = result.articles.filter((a: Article) => !existingIds.has(a._id))
      
      if (newArticles.length > 0) {
        articles.value = [...newArticles, ...articles.value]
        await articleCache.saveArticles(result.articles)
        console.log(`Fetched ${newArticles.length} new articles`)
      }
    }
    
    totalCount.value = result.totalCount
  } catch (error) {
    console.error('Error fetching updates:', error)
  } finally {
    fetchingUpdates.value = false
  }
}

const loadMore = async () => {
  if (loadingMore.value || !hasMore.value) return
  
  loadingMore.value = true
  try {
    const result = await fetchArticles(articles.value.length)
    
    if (result.articles.length > 0) {
      articles.value = [...articles.value, ...result.articles]
      await articleCache.saveArticles(result.articles)
    }
    
    hasMore.value = result.hasMore
    totalCount.value = result.totalCount
  } catch (error) {
    console.error('Error loading more articles:', error)
  } finally {
    loadingMore.value = false
  }
}

const deleteArticle = async (id: string) => {
  if (!confirm("Delete this article?")) return;
  try {
    const res = await fetch(`/api/articles/${id}`, { method: 'DELETE' })
    if (res.ok) {
      articles.value = articles.value.filter(a => a._id !== id)
      // Note: We don't remove from cache as it will auto-expire
    } else {
      alert("Failed to delete article")
    }
  } catch (e) {
    console.error(e)
  }
}

const setupIntersectionObserver = () => {
  if (!sentinelEl.value) return
  
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !loadingMore.value) {
        loadMore()
      }
    },
    { rootMargin: '200px' }
  )
  
  observer.observe(sentinelEl.value)
}

onMounted(async () => {
  // 1. Load cached articles immediately
  await loadFromCache()
  
  // 2. Fetch latest updates
  await fetchLatestUpdates()
  
  // 3. If no cached articles, do initial fetch
  if (articles.value.length === 0) {
    const result = await fetchArticles(0)
    articles.value = result.articles
    hasMore.value = result.hasMore
    totalCount.value = result.totalCount
    await articleCache.saveArticles(result.articles)
  }
  
  loading.value = false
  
  // 4. Set up infinite scroll
  setupIntersectionObserver()
  
  // 5. Clean old cache
  articleCache.clearOldArticles().catch(console.error)
  
  // 6. Periodic refresh (every 2 minutes)
  refreshInterval = window.setInterval(fetchLatestUpdates, 120000)
})

onUnmounted(() => {
  if (observer) {
    observer.disconnect()
  }
  if (refreshInterval !== null) {
    clearInterval(refreshInterval)
  }
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
    <h2>
      Articles 
      <span v-if="totalCount > 0">({{ articles.length }}/{{ totalCount }})</span>
      <span v-else-if="!loading">({{ articles.length }})</span>
      <span v-if="fetchingUpdates" class="update-badge">↻</span>
    </h2>
    <div v-if="loading" class="loading-state">Loading cached articles...</div>
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
      
      <!-- Sentinel element for infinite scroll -->
      <div ref="sentinelEl" class="sentinel">
        <div v-if="loadingMore" class="loading-more">Loading more articles...</div>
        <div v-else-if="!hasMore" class="end-message">No more articles</div>
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
  display: flex;
  align-items: center;
  gap: 8px;
}
.update-badge {
  font-size: 0.9rem;
  color: #666;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.loading-state {
  text-align: center;
  padding: 20px;
  color: var(--text-color);
  opacity: 0.7;
}
.article-list {
  overflow-y: auto;
  flex: 1;
}
.article-card {
  border-bottom: 1px solid var(--border-color);
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
  color: var(--text-color);
  opacity: 0.6;
  margin-bottom: 8px;
}
.summary {
  font-size: 0.9rem;
  color: var(--text-color);
  opacity: 0.9;
  line-height: 1.4;
}
.event-tags {
  margin-top: 10px;
}
.tag {
  display: inline-block;
  background: var(--button-bg);
  color: var(--primary-color);
  border: 1px solid var(--border-color);
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
.sentinel {
  padding: 20px;
  text-align: center;
}
.loading-more {
  color: #666;
  font-style: italic;
}
.end-message {
  color: #999;
  font-size: 0.9rem;
}
</style>