<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { articleCache, type Article } from '../utils/articleCache'
import { useAuthStore } from '../stores/auth'
import LoginModal from './LoginModal.vue'

interface ArticleGroup {
  title: string;
  favicon?: string;
  articles: Article[];
}

const articles = ref<Article[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const fetchingUpdates = ref(false)
const hasMore = ref(true)
const totalCount = ref(0)
const sentinelEl = ref<HTMLElement | null>(null)
const expandedArticles = ref<Set<string>>(new Set())
const showLoginModal = ref(false)

const authStore = useAuthStore()
const isAuthenticated = computed(() => authStore.isAuthenticated)

let observer: IntersectionObserver | null = null
let refreshInterval: number | null = null

const PAGE_SIZE = 50

const groupedArticles = computed(() => {
  if (articles.value.length === 0) {
    return []
  }

  const groups: ArticleGroup[] = []
  let currentGroup: ArticleGroup = {
    title: articles.value[0].feed_title || getHostname(articles.value[0].feed_url),
    favicon: articles.value[0].feed_favicon,
    articles: [articles.value[0]]
  }

  for (let i = 1; i < articles.value.length; i++) {
    const article = articles.value[i]
    const articleFeedTitle = article.feed_title || getHostname(article.feed_url)
    if (articleFeedTitle === currentGroup.title) {
      currentGroup.articles.push(article)
    } else {
      groups.push(currentGroup)
      currentGroup = {
        title: articleFeedTitle,
        favicon: article.feed_favicon,
        articles: [article]
      }
    }
  }
  groups.push(currentGroup)

  return groups
})

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
      const existingIds = new Set(articles.value.map((a: Article) => a._id))
      const newArticles = result.articles.filter((a: Article) => !existingIds.has(a._id))
      
      if (newArticles.length > 0) {
        articles.value = [...newArticles, ...articles.value]
        await articleCache.saveArticles(result.articles)
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
  
  // Periodic refresh (every 2 minutes)
  refreshInterval = globalThis.setInterval(fetchLatestUpdates, 120000)
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

const handleFaviconError = (event: Event) => {
  // Hide the image if it fails to load
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
}
</script>

<template>
  <div class="stream-page">
    <header class="page-header">
        <div class="header-left">
            <h2>Aggregated Stream</h2>
            <span class="count">
              <span v-if="totalCount > 0">{{ articles.length }}/{{ totalCount }}</span>
              <span v-else-if="!loading">{{ articles.length }}</span>
              Articles
            </span>
            <span v-if="fetchingUpdates" class="update-badge">↻</span>
        </div>
        <div class="header-actions">
            <!-- Login Button for Public View -->
            <button v-if="!isAuthenticated" @click="showLoginModal = true" class="login-btn">
                Sign In
            </button>

            <a href="/api/stream.rss" class="rss-link" title="Subscribe to RSS feed" target="_blank">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19 7.38 20 6.18 20A2.18 2.18 0 0 1 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/>
                </svg>
                RSS
            </a>
            <button @click="fetchLatestUpdates" :disabled="fetchingUpdates" class="refresh-btn" title="Check for updates">
                {{ fetchingUpdates ? 'Checking...' : '↻ Refresh' }}
            </button>
        </div>
    </header>

    <div v-if="loading" class="loading">Loading stream...</div>
    
    <div v-else-if="articles.length" class="stream-container">
      <div v-for="(group, index) in groupedArticles" :key="index" class="feed-group">
        <h3 class="group-title">
          <img v-if="group.favicon" :src="group.favicon" class="group-favicon" :alt="`${group.title} icon`" @error="handleFaviconError" />
          <span v-else class="group-favicon-placeholder" role="img" :aria-label="`${group.title} icon`">📰</span>
          {{ group.title }}
        </h3>
        <div v-for="article in group.articles" :key="article._id" class="stream-item">
          <h4 class="item-title">
              <a :href="article.link" target="_blank">{{ article.title }}</a>
          </h4>
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
          <div v-if="article.events || article.trends" class="item-tags">
            <div v-if="article.events && article.events.length > 0" class="tag-group">
              <span class="tag-label">Events:</span>
              <span v-for="event in article.events" :key="event" class="tag tag-event">{{ event }}</span>
            </div>
            <div v-if="article.trends && article.trends.length > 0" class="tag-group">
              <span class="tag-label">Trends:</span>
              <span v-for="trend in article.trends" :key="trend" class="tag tag-trend">{{ trend }}</span>
            </div>
          </div>
          <div class="item-meta">
              <span class="date">{{ formatDate(article.published) }}</span>
          </div>
        </div>
        <hr v-if="index < groupedArticles.length - 1" class="group-divider">
      </div>
      
      <!-- Sentinel element for infinite scroll -->
      <div ref="sentinelEl" class="sentinel">
        <div v-if="loadingMore" class="loading-more">Loading more articles...</div>
        <div v-else-if="!hasMore" class="end-message">No more articles</div>
      </div>
    </div>
    
    <div v-else class="empty-state">No articles found in the stream.</div>
    
    <LoginModal v-if="showLoginModal" @close="showLoginModal = false" @success="fetchLatestUpdates" />
  </div>
</template>

<style scoped>
.stream-page {
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

.header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
}

.rss-link {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    text-decoration: none;
    font-size: 0.9rem;
    transition: all 0.2s;
}

.rss-link:hover {
    background: var(--button-bg);
    border-color: #ee802f;
    color: #ee802f;
}

.rss-link svg {
    vertical-align: middle;
}

.page-header h2 {
    margin: 0;
    color: var(--text-color);
}

.count {
    color: #7f8c8d;
    font-size: 0.9rem;
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

.login-btn {
    background: var(--primary-color);
    color: white;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
}
.login-btn:hover {
    background: var(--primary-hover);
}

.stream-container {
    overflow-y: auto;
    flex: 1;
    padding-right: 10px; /* For scrollbar */
}

.feed-group {
  margin-bottom: 20px;
}

.group-title {
  font-size: 1.2rem;
  color: var(--text-color);
  font-weight: 600;
  padding-bottom: 10px;
  margin-bottom: 20px;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 10px;
}

.group-favicon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  object-fit: contain;
}

.group-favicon-placeholder {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  font-size: 18px;
  line-height: 20px;
  text-align: center;
}

.stream-item {
    background: var(--card-bg);
    padding: 10px 0;
    margin-bottom: 10px;
    text-align: left; /* Ensure stream items are left-aligned */
}

.item-meta {
    font-size: 0.8rem;
    color: #95a5a6;
    margin-top: 10px;
    text-align: right;
}

.source {
    font-weight: 600;
    color: var(--text-color);
    opacity: 0.8;
}

.item-title {
    margin: 0 0 10px 0;
    font-size: 1.2rem;
    line-height: 1.3;
    text-align: left;
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
    text-align: justify;
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

.item-tags {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tag-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.tag-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-color);
  opacity: 0.7;
}

.tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 500;
}

.tag-event {
  background-color: #e3f2fd;
  color: #1565c0;
  border: 1px solid #90caf9;
}

.tag-trend {
  background-color: #f3e5f5;
  color: #7b1fa2;
  border: 1px solid #ce93d8;
}

.group-divider {
  border: 0;
  border-top: 1px solid var(--border-color);
  margin: 20px 0;
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

.loading, .empty-state {
    text-align: center;
    padding: 40px;
    color: #7f8c8d;
    font-size: 1.2rem;
}
</style>
