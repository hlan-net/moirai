<script setup lang="ts">
import { onMounted, ref, onUnmounted, computed, inject, watch, type Ref } from 'vue'
import { articleCache, type Article } from '../utils/articleCache'
import { formatDate, stripHtml, getHostname } from '../utils/formatters'
import { useAuthStore } from '../stores/auth'
import { useFilterStore } from '../stores/filter' // Import the new filter store

const articles = ref<Article[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const fetchingUpdates = ref(false)
const hasMore = ref(true)
const totalCount = ref(0)
const sentinelEl = ref<HTMLElement | null>(null)
const searchQuery = ref('')

// Inject selected feed from parent - NO LONGER USED DIRECTLY FOR FILTERING
// const selectedFeedUrl = inject<Ref<string | null>>('selectedFeedUrl', ref(null))

const authStore = useAuthStore()
const filterStore = useFilterStore() // Initialize the filter store
const isAdmin = computed(() => authStore.user?.role === 'admin')

let observer: IntersectionObserver | null = null
let refreshInterval: number | null = null

const PAGE_SIZE = 50

const fetchArticles = async (
  skip = 0,
  since?: string,
  feedId: string | null = null,
  eventId: string | null = null,
  trendId: string | null = null
) => {
  try {
    const params = new URLSearchParams({
      limit: PAGE_SIZE.toString(),
      skip: skip.toString(),
    })
    if (since) {
      params.append('since', since)
    }
    if (feedId) {
      params.append('feed_id', feedId)
    }
    if (eventId) {
      params.append('event_id', eventId)
    }
    if (trendId) {
      params.append('trend_id', trendId)
    }

    const response = await fetch(`/api/articles?${params}`)
    if (response.ok) {
      const data = await response.json()
      return {
        articles: data.articles || [],
        hasMore: data.has_more || false,
        totalCount: data.total_count || 0,
      }
    }
  } catch (error) {
    console.error('Error fetching articles:', error)
  }
  return { articles: [], hasMore: false, totalCount: 0 }
}

const loadFromCache = async () => {
  // Clear cache if any filter is active
  if (filterStore.selectedFeedId || filterStore.selectedEventId || filterStore.selectedTrendId) {
    articles.value = []
    loading.value = false
    return // Don't load from cache if filtered, fetch fresh
  }
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
  // Skip fetching updates if any filter is active, as we re-fetch completely
  if (filterStore.selectedFeedId || filterStore.selectedEventId || filterStore.selectedTrendId) {
    fetchingUpdates.value = false
    return
  }

  fetchingUpdates.value = true
  try {
    const newestTimestamp = await articleCache.getNewestTimestamp()
    const result = await fetchArticles(
      0,
      newestTimestamp || undefined,
      filterStore.selectedFeedId,
      filterStore.selectedEventId,
      filterStore.selectedTrendId
    )

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
    const result = await fetchArticles(
      articles.value.length,
      undefined,
      filterStore.selectedFeedId,
      filterStore.selectedEventId,
      filterStore.selectedTrendId
    )

    if (result.articles.length > 0) {
      articles.value = [...articles.value, ...result.articles]
      // Only cache if no filters are active
      if (
        !filterStore.selectedFeedId &&
        !filterStore.selectedEventId &&
        !filterStore.selectedTrendId
      ) {
        await articleCache.saveArticles(result.articles)
      }
    }

    hasMore.value = result.hasMore
    totalCount.value = result.totalCount
  } catch (error) {
    console.error('Error loading more articles:', error)
  } finally {
    loadingMore.value = false
  }
}

// Watch for changes in filter store and re-fetch articles
watch(
  [
    () => filterStore.selectedFeedId,
    () => filterStore.selectedEventId,
    () => filterStore.selectedTrendId,
  ],
  async () => {
    loading.value = true
    articles.value = [] // Clear current articles
    hasMore.value = true
    totalCount.value = 0
    if (observer) {
      observer.disconnect() // Disconnect old observer
    }
    await loadFromCache() // Try to load from cache first if no filters
    await fetchArticlesAndCache(0) // Fetch fresh based on new filters
    loading.value = false
    setupIntersectionObserver() // Re-setup observer
  }
)

const fetchArticlesAndCache = async (skip = 0) => {
  const result = await fetchArticles(
    skip,
    undefined,
    filterStore.selectedFeedId,
    filterStore.selectedEventId,
    filterStore.selectedTrendId
  )
  if (skip === 0) {
    // Initial load
    articles.value = result.articles
  } else {
    // Load more
    articles.value = [...articles.value, ...result.articles]
  }
  hasMore.value = result.hasMore
  totalCount.value = result.totalCount
  // Only cache if no filters are active
  if (!filterStore.selectedFeedId && !filterStore.selectedEventId && !filterStore.selectedTrendId) {
    await articleCache.saveArticles(result.articles)
  }
}

// Computed: Filtered articles based on search query
const filteredArticles = computed(() => {
  let filtered = articles.value

  // No longer filtering by selectedFeedUrl here, as it's handled by API now
  // if (selectedFeedUrl.value) {
  //   filtered = filtered.filter(article => article.feed_url === selectedFeedUrl.value)
  // }

  // Filter by search query (local client-side filter)
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter((article) => {
      const title = (article.title || '').toLowerCase()
      const summary = (article.summary || '').toLowerCase()
      const feedTitle = (article.feed_title || '').toLowerCase()
      return title.includes(query) || summary.includes(query) || feedTitle.includes(query)
    })
  }

  return filtered
})

const deleteArticle = async (id: string) => {
  if (!confirm('Delete this article?')) return
  try {
    const res = await fetch(`/api/articles/${id}`, { method: 'DELETE' })
    if (res.ok) {
      articles.value = articles.value.filter((a) => a._id !== id)
      // Note: We don't remove from cache as it will auto-expire
    } else {
      alert('Failed to delete article')
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
  // 1. Load cached articles immediately (only if no filters initially active)
  await loadFromCache()

  // 2. Fetch initial articles (might include latest updates or filtered)
  await fetchArticlesAndCache(0)

  loading.value = false

  // 3. Set up infinite scroll
  setupIntersectionObserver()

  // 4. Clean old cache
  articleCache.clearOldArticles().catch(console.error)

  // 5. Periodic refresh (every 2 minutes) - only if no filters are active
  refreshInterval = globalThis.setInterval(() => {
    if (
      !filterStore.selectedFeedId &&
      !filterStore.selectedEventId &&
      !filterStore.selectedTrendId
    ) {
      fetchLatestUpdates()
    }
  }, 120000)
})

onUnmounted(() => {
  if (observer) {
    observer.disconnect()
  }
  if (refreshInterval !== null) {
    clearInterval(refreshInterval)
  }
})

const refreshingFeed = ref(false)

const handleRefresh = async () => {
  refreshingFeed.value = true

  try {
    // Determine which feed to refresh based on filter store
    const feedToRefresh = filterStore.selectedFeedId
      ? articles.value.find((a) => a._id === filterStore.selectedFeedId)?.feed_url
      : null

    if (feedToRefresh) {
      // Refresh specific feed
      const encodedUrl = encodeURIComponent(feedToRefresh)
      const response = await fetch(`/api/feeds/refresh/${encodedUrl}`, { method: 'POST' })

      if (response.ok) {
        // Wait a bit for the feed to be fetched
        setTimeout(async () => {
          await fetchArticlesAndCache(0) // Re-fetch all based on current filters
          refreshingFeed.value = false
        }, 2000)
      } else {
        console.error('Failed to refresh feed')
        refreshingFeed.value = false
      }
    } else {
      // If no specific feed is selected, or if feedToRefresh is null, just fetch latest updates
      // This will respect current filters
      await fetchArticlesAndCache(0) // Re-fetch all based on current filters
      refreshingFeed.value = false
    }
  } catch (error) {
    console.error('Error refreshing:', error)
    refreshingFeed.value = false
  }
}
</script>

<template>
  <div class="article-column">
    <div class="column-header">
      <h2>
        Articles
        <span v-if="totalCount > 0">({{ filteredArticles.length }}/{{ totalCount }})</span>
        <span v-else-if="!loading">({{ filteredArticles.length }})</span>
        <span v-if="fetchingUpdates" class="update-badge">↻</span>
      </h2>
      <div class="header-actions" v-if="isAdmin">
        <button
          @click="handleRefresh"
          :disabled="refreshingFeed"
          class="action-btn"
          :title="
            refreshingFeed
              ? 'Refreshing...'
              : filterStore.selectedFeedId
                ? 'Refresh selected feed'
                : 'Check for updates'
          "
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="currentColor"
            :class="{ spinning: refreshingFeed }"
          >
            <path
              d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14 .69 4.22 1.78L13 11h7V4l-2.35 2.35z"
            />
          </svg>
          {{ refreshingFeed ? 'Refreshing' : 'Refresh' }}
        </button>
      </div>
    </div>

    <!-- Search Input -->
    <div class="search-container">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search articles by title, description, or source..."
        class="search-input"
      />
      <button
        v-if="searchQuery"
        @click="searchQuery = ''"
        class="clear-search-btn"
        title="Clear search"
      >
        ×
      </button>
    </div>

    <div v-if="loading" class="loading-state">Loading articles...</div>
    <div v-else-if="!filteredArticles.length" class="no-results">
      <span v-if="searchQuery">No articles match "{{ searchQuery }}"</span>
      <span v-else>No articles found yet for the current filters.</span>
    </div>
    <div v-else class="article-list">
      <div v-for="article in filteredArticles" :key="article._id" class="article-card">
        <div class="card-header">
          <h3>
            <a :href="article.link" target="_blank">{{ article.title }}</a>
          </h3>
          <button
            v-if="isAdmin"
            @click="deleteArticle(article._id)"
            class="delete-btn"
            title="Delete Article"
          >
            ×
          </button>
        </div>
        <p class="meta">
          {{ formatDate(article.published) }} | {{ getHostname(article.feed_url) }}
        </p>
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
  </div>
</template>

<style scoped>
.article-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

h2 {
  color: #007acc;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
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
