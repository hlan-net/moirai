<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, useTemplateRef } from 'vue'
import { type Article } from '../utils/articleCache'
import { authFetch } from '../utils/authFetch'
import { useTheme } from '../composables/useTheme'
import { useAuthStore } from '../stores/auth'

interface ArticleGroup {
  title: string
  favicon?: string
  articles: Article[]
}

type GroupMode = 'feed' | 'time'

const articles = ref<Article[]>([])
const loading = ref(true)
const fetchingUpdates = ref(false)
const totalCount = ref(0)
const expandedArticles = ref<Set<string>>(new Set())
const isHighDensity = ref(true)
const groupMode = ref<GroupMode>('feed')
const newArticleCount = ref(0)
const streamContainer = useTemplateRef<HTMLElement>('streamContainer')
const { resolveTheme, setTheme } = useTheme()
const authStore = useAuthStore()
const isAuthenticated = computed(() => authStore.isAuthenticated)

let refreshInterval: number | null = null

const RSS_LIMIT = 200
const RSS_REFRESH_MS = 120000

// Feed-grouped: sequential feed grouping (existing behavior)
const feedGroupedArticles = computed(() => {
  const firstArticle = articles.value[0]
  if (!firstArticle) {
    return []
  }

  const groups: ArticleGroup[] = []
  let currentGroup: ArticleGroup = {
    title: firstArticle.feed_title || getHostname(firstArticle.feed_url),
    favicon: firstArticle.feed_favicon,
    articles: [firstArticle]
  }

  for (let i = 1; i < articles.value.length; i++) {
    const article = articles.value[i]
    if (!article) continue
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

const timeGroupedArticles = computed(() => {
  if (articles.value.length === 0) {
    return []
  }

  const now = new Date()
  const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000)
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterdayStart = new Date(todayStart.getTime() - 24 * 60 * 60 * 1000)

  const lastHour: Article[] = []
  const earlierToday: Article[] = []
  const yesterday: Article[] = []
  const older: Article[] = []

  for (const article of articles.value) {
    const pubDate = new Date(article.published)
    if (pubDate >= oneHourAgo) {
      lastHour.push(article)
    } else if (pubDate >= todayStart) {
      earlierToday.push(article)
    } else if (pubDate >= yesterdayStart) {
      yesterday.push(article)
    } else {
      older.push(article)
    }
  }

  const groups: ArticleGroup[] = [
    { title: 'Last Hour', favicon: undefined, articles: lastHour },
    { title: 'Earlier Today', favicon: undefined, articles: earlierToday },
    { title: 'Yesterday', favicon: undefined, articles: yesterday },
    { title: 'Older', favicon: undefined, articles: older },
  ]

  return groups.filter((group) => group.articles.length > 0)
})

// Unified accessor for the template
const groupedArticles = computed(() => {
  return groupMode.value === 'feed' ? feedGroupedArticles.value : timeGroupedArticles.value
})

const resolvedTheme = computed(() => resolveTheme())
const themeLabel = computed(() => (resolvedTheme.value === 'dark' ? 'Dark' : 'Light'))
const themeTitle = computed(() =>
  resolvedTheme.value === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'
)

const _extractCategories = (item: Element) => {
  const events: string[] = []
  const trends: string[] = []
  const topics: string[] = []
  let priority: 'low' | 'medium' | 'high' | undefined
  let sentiment: 'positive' | 'neutral' | 'negative' | undefined

  for (const category of Array.from(item.querySelectorAll('category'))) {
    const label = category.textContent?.trim()
    if (!label) continue
    const domain = category.getAttribute('domain')
    if (domain === 'event') {
      events.push(label)
    } else if (domain === 'trend') {
      trends.push(label)
    } else if (domain === 'topic') {
      topics.push(label)
    } else if (domain === 'priority') {
      priority = label as 'low' | 'medium' | 'high'
    } else if (domain === 'sentiment') {
      sentiment = label as 'positive' | 'neutral' | 'negative'
    }
  }
  return { events, trends, topics, priority, sentiment }
}

const _parseFeedItem = (item: Element, index: number): Article => {
  const title = item.querySelector('title')?.textContent?.trim() || 'Untitled'
  const link = item.querySelector('link')?.textContent?.trim() || ''
  const summary = item.querySelector('description')?.textContent?.trim() || ''
  const pubDate = item.querySelector('pubDate')?.textContent?.trim() || ''
  const guid = item.querySelector('guid')?.textContent?.trim() || link || `${title}-${index}`
  const sourceTitle =
    item.querySelector('source > title')?.textContent?.trim() ||
    item.querySelector('source')?.textContent?.trim() ||
    ''

  let published = ''
  if (pubDate) {
    const parsed = new Date(pubDate)
    if (!Number.isNaN(parsed.getTime())) {
      published = parsed.toISOString()
    }
  }

  let feedUrl = link
  try {
    feedUrl = new URL(link).origin
  } catch (error) {
    feedUrl = link
  }

  const { events, trends, topics, priority, sentiment } = _extractCategories(item)

  const annotations =
    topics.length || priority || sentiment
      ? {
          topics,
          priority: priority || 'low',
          sentiment: sentiment || 'neutral',
        }
      : undefined

  return {
    _id: guid,
    title,
    summary,
    link,
    published: published || new Date().toISOString(),
    feed_url: feedUrl,
    feed_title: sourceTitle || getHostname(feedUrl),
    events: events.length ? events : undefined,
    trends: trends.length ? trends : undefined,
    annotations,
  }
}

const parseRssFeed = (xmlText: string): Article[] => {
  const doc = new DOMParser().parseFromString(xmlText, 'application/xml')
  if (doc.querySelector('parsererror')) {
    throw new Error('Invalid RSS feed')
  }

  return Array.from(doc.querySelectorAll('item')).map((item, index) => _parseFeedItem(item, index))
}

const fetchStream = async (isManual = false) => {
  if (articles.value.length === 0) {
    loading.value = true
  }
  fetchingUpdates.value = true
  try {
    const response = await authFetch(`/api/stream.rss?limit=${RSS_LIMIT}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch RSS: ${response.status}`)
    }
    const xmlText = await response.text()
    const parsed = parseRssFeed(xmlText)

    if (articles.value.length === 0 || isManual) {
      // Initial load or manual refresh: replace entirely
      articles.value = parsed
      totalCount.value = parsed.length
    } else {
      // Auto-refresh: count new articles silently without changing the display
      const existingIds = new Set(articles.value.map((a) => a._id))
      const newItems = parsed.filter((a) => !existingIds.has(a._id))

      if (newItems.length > 0) {
        newArticleCount.value += newItems.length
      }
    }
  } catch (error) {
    console.error('Error fetching RSS stream:', error)
  } finally {
    fetchingUpdates.value = false
    loading.value = false
  }
}

const refreshAndReset = () => {
  newArticleCount.value = 0
  fetchStream(true)
}

onMounted(async () => {
  await fetchStream(true)
  refreshInterval = globalThis.setInterval(() => fetchStream(false), RSS_REFRESH_MS)
})

onUnmounted(() => {
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

const toggleTheme = () => {
  const nextTheme = resolvedTheme.value === 'dark' ? 'light' : 'dark'
  setTheme(nextTheme, { persist: false })
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
            <button @click="isHighDensity = !isHighDensity" class="density-btn" :title="isHighDensity ? 'Switch to Expanded View' : 'Switch to High Density View'">
                <svg v-if="isHighDensity" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M3 4h18v2H3V4zm0 7h18v2H3v-2zm0 7h18v2H3v-2z"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M3 4h18v4H3V4zm0 7h18v4H3v-4zm0 7h18v4H3v-4z"/>
                </svg>
                {{ isHighDensity ? 'Compact' : 'Expanded' }}
            </button>

            <button @click="groupMode = groupMode === 'feed' ? 'time' : 'feed'" class="density-btn" :title="groupMode === 'feed' ? 'Switch to Time-Blocked' : 'Switch to Feed-Grouped'">
                <svg v-if="groupMode === 'feed'" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14zM7 10h2v7H7zm4-3h2v10h-2zm4 6h2v4h-2z"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/>
                </svg>
                {{ groupMode === 'feed' ? 'By Feed' : 'By Time' }}
            </button>

            <button v-if="!isAuthenticated" @click="toggleTheme" class="theme-btn" :title="themeTitle">
                <svg v-if="resolvedTheme === 'dark'" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M21.64 13.65a9 9 0 0 1-11.29-11.3A9 9 0 1 0 21.64 13.65z" />
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 4.5a1 1 0 0 1 1 1V7a1 1 0 0 1-2 0V5.5a1 1 0 0 1 1-1zm0 10a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zm0 5.5a1 1 0 0 1 1 1V22a1 1 0 1 1-2 0v-1.5a1 1 0 0 1 1-1zm7.5-7.5a1 1 0 0 1-1-1h-1.5a1 1 0 1 1 0-2H18.5a1 1 0 0 1 1 1zm-14 0a1 1 0 0 1-1-1h-1.5a1 1 0 1 1 0-2H4.5a1 1 0 0 1 1 1zm11.86-5.86a1 1 0 0 1 0-1.41l1.06-1.06a1 1 0 1 1 1.41 1.41l-1.06 1.06a1 1 0 0 1-1.41 0zm-11.31 0a1 1 0 0 1-1.41 0L3.58 5.23a1 1 0 1 1 1.41-1.41l1.06 1.06a1 1 0 0 1 0 1.41zm11.31 11.31a1 1 0 0 1 1.41 0l1.06 1.06a1 1 0 1 1-1.41 1.41l-1.06-1.06a1 1 0 0 1 0-1.41zm-11.31 0a1 1 0 0 1 0 1.41L5 20.27a1 1 0 1 1-1.41-1.41l1.06-1.06a1 1 0 0 1 1.41 0z" />
                </svg>
                {{ themeLabel }}
            </button>

            <a href="/api/stream.rss" class="rss-link" title="Subscribe to RSS feed" target="_blank">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19 7.38 20 6.18 20A2.18 2.18 0 0 1 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/>
                </svg>
                RSS
            </a>
            <button @click="refreshAndReset" :disabled="fetchingUpdates" class="refresh-btn" :class="{ 'has-new': newArticleCount > 0 }" title="Refresh stream">
                {{ fetchingUpdates ? 'Checking...' : '↻ Refresh' }}
                <span v-if="newArticleCount > 0" class="new-count-badge">{{ newArticleCount }}</span>
            </button>
        </div>
    </header>

    <div v-if="loading" class="loading">Loading stream...</div>
    
    <div v-else-if="articles.length" ref="streamContainer" class="stream-container" :class="{ 'high-density': isHighDensity }">
      <div v-for="(group, index) in groupedArticles" :key="group.title + '-' + index" class="feed-group">
        <h3 class="group-title">
          <template v-if="groupMode === 'feed'">
            <img v-if="group.favicon" :src="group.favicon" class="group-favicon" :alt="`${group.title} icon`" @error="handleFaviconError" />
            <img v-else class="group-favicon-placeholder" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ctext y='20' font-size='20'%3E📰%3C/text%3E%3C/svg%3E" alt="Default news icon" />
          </template>
          {{ group.title }}
          <span v-if="groupMode === 'time'" class="group-count">({{ group.articles.length }})</span>
        </h3>
        
        <div v-for="article in group.articles" :key="article._id" 
             :class="['stream-item', { 'compact-item': isHighDensity }]">
          
          <!-- High Density (River) View -->
          <template v-if="isHighDensity">
            <div class="compact-row">
              <span class="compact-time">{{ new Date(article.published).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}</span>
              <!-- Inline source tag for time-blocked mode -->
              <span v-if="groupMode === 'time'" class="inline-source" :title="article.feed_title || getHostname(article.feed_url)">
                <img v-if="article.feed_favicon" :src="article.feed_favicon" class="inline-favicon" alt="Feed icon" @error="handleFaviconError" />
                {{ article.feed_title || getHostname(article.feed_url) }}
              </span>
              <h4 class="item-title compact-title">
                <a :href="article.link" target="_blank">{{ article.title }}</a>
              </h4>
              <div class="compact-tags">
                <span v-if="article.annotations?.priority === 'high'" class="dot-tag priority-high-dot" title="High Priority"></span>
                <span v-if="article.annotations?.priority === 'medium'" class="dot-tag priority-medium-dot" title="Medium Priority"></span>
                <span v-if="article.annotations?.sentiment === 'positive'" class="dot-tag sentiment-positive-dot" title="Positive Sentiment"></span>
                <span v-if="article.annotations?.sentiment === 'negative'" class="dot-tag sentiment-negative-dot" title="Negative Sentiment"></span>
                <span v-if="article.events?.length" class="dot-tag event-dot" title="Has Events"></span>
                <span v-if="article.trends?.length" class="dot-tag trend-dot" title="Has Trends"></span>
              </div>
            </div>
          </template>

          <!-- Expanded View -->
          <template v-else>
            <!-- Inline source for time-blocked expanded view -->
            <div v-if="groupMode === 'time'" class="inline-source-expanded">
              <img v-if="article.feed_favicon" :src="article.feed_favicon" class="inline-favicon" alt="Feed icon" @error="handleFaviconError" />
              <span>{{ article.feed_title || getHostname(article.feed_url) }}</span>
            </div>
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
            <div v-if="article.events || article.trends || article.annotations" class="item-tags">
              <div v-if="article.events && article.events.length > 0" class="tag-group">
                <span v-for="event in article.events" :key="event" class="tag tag-event">{{ event }}</span>
              </div>
              <div v-if="article.trends && article.trends.length > 0" class="tag-group">
                <span v-for="trend in article.trends" :key="trend" class="tag tag-trend">{{ trend }}</span>
              </div>
              <div v-if="article.annotations" class="tag-group">
                <span v-for="topic in article.annotations.topics" :key="topic" class="tag tag-topic">{{ topic }}</span>
                <span :class="['tag', 'tag-priority', `tag-priority-${article.annotations.priority}`]">{{ article.annotations.priority }}</span>
                <span :class="['tag', 'tag-sentiment', `tag-sentiment-${article.annotations.sentiment}`]">{{ article.annotations.sentiment }}</span>
              </div>
            </div>
            <div class="item-meta">
                <span class="date">{{ formatDate(article.published) }}</span>
            </div>
          </template>
        </div>
        <hr v-if="index < groupedArticles.length - 1 && !isHighDensity" class="group-divider">
      </div>

    </div>
    
    <div v-else class="empty-state">No articles found in the stream.</div>
    
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
    color: var(--text-color);
    opacity: 0.8;
    font-size: 0.9rem;
}

.update-badge {
  font-size: 0.9rem;
  color: var(--primary-color);
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
    position: relative;
}

.refresh-btn.has-new {
    font-weight: 700;
    border-color: var(--primary-color);
    color: var(--primary-color);
}

.new-count-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--primary-color);
    color: white;
    font-size: 0.7rem;
    font-weight: 700;
    min-width: 18px;
    height: 18px;
    border-radius: 9px;
    padding: 0 5px;
    margin-left: 4px;
    line-height: 1;
}

.refresh-btn:hover:not(:disabled) {
    background: var(--button-bg);
    border-color: var(--primary-color);
    color: white;
}

.refresh-btn:disabled {
    opacity: 0.6;
    cursor: wait;
}

.density-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
}

.density-btn:hover,
.theme-btn:hover {
    background: var(--button-bg);
    border-color: var(--primary-color);
}

.theme-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
}


.stream-container {
    overflow-y: auto;
    flex: 1;
    padding-right: 10px; /* For scrollbar */
}

.feed-group {
  margin-bottom: 20px;
}

.high-density .feed-group {
  margin-bottom: 10px;
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

.high-density .group-title {
  font-size: 1rem;
  margin-bottom: 8px;
  padding-bottom: 5px;
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
    background: transparent;
    padding: 14px 0;
    margin-bottom: 0;
    border-bottom: none;
    text-align: left; /* Ensure stream items are left-aligned */
}

.compact-item {
    padding: 6px 0;
    margin-bottom: 0;
}

.feed-group .stream-item:last-child {
    border-bottom: none;
}

.compact-row {
    display: flex;
    align-items: baseline;
    gap: 12px;
}

.compact-time {
    font-size: 0.8rem;
    color: var(--text-color);
    opacity: 0.7;
    min-width: 60px;
    flex-shrink: 0;
}

.compact-title {
    margin: 0 !important;
    font-size: 1rem !important;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
}

.compact-tags {
    display: flex;
    gap: 4px;
    margin-left: auto;
}

.dot-tag {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.event-dot { background-color: #1565c0; }
.trend-dot { background-color: #7b1fa2; }

/* Annotation dots (compact view) */
.priority-high-dot { background-color: #c62828; }
.priority-medium-dot { background-color: #ef6c00; }
.sentiment-positive-dot { background-color: #2e7d32; }
.sentiment-negative-dot { background-color: #d32f2f; }

.item-meta {
    font-size: 0.8rem;
    color: var(--text-color);
    opacity: 0.7;
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
    color: #af9fc5;
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

/* AI annotation tags (expanded view) */
.tag-topic {
  background-color: #e8f5e9;
  color: #2e7d32;
  border: 1px solid #81c784;
}

.tag-priority {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.5px;
}

.tag-priority-high {
  background-color: #ffebee;
  color: #c62828;
  border: 1px solid #ef9a9a;
}

.tag-priority-medium {
  background-color: #fff3e0;
  color: #ef6c00;
  border: 1px solid #ffcc80;
}

.tag-priority-low {
  background-color: #f5f5f5;
  color: #757575;
  border: 1px solid #e0e0e0;
}

.tag-sentiment {
  font-size: 0.7rem;
  font-weight: 500;
}

.tag-sentiment-positive {
  background-color: #e8f5e9;
  color: #2e7d32;
  border: 1px solid #81c784;
}

.tag-sentiment-neutral {
  background-color: #f5f5f5;
  color: #757575;
  border: 1px solid #e0e0e0;
}

.tag-sentiment-negative {
  background-color: #ffebee;
  color: #c62828;
  border: 1px solid #ef9a9a;
}

.group-divider {
  border: 0;
  border-top: 1px solid var(--border-color);
  margin: 20px 0;
}

.loading, .empty-state {
    text-align: center;
    padding: 40px;
    color: var(--text-color);
    opacity: 0.8;
    font-size: 1.2rem;
}

/* Group count for time-blocked headers */
.group-count {
    font-size: 0.85rem;
    font-weight: 400;
    opacity: 0.85;
}

/* Inline source tag (compact / time-blocked) */
.inline-source {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.75rem;
    color: var(--text-color);
    opacity: 0.8;
    background: rgba(255, 255, 255, 0.06);
    padding: 1px 6px;
    border-radius: 3px;
    white-space: nowrap;
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 0;
}

.inline-source-expanded {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.8rem;
    color: var(--text-color);
    opacity: 0.8;
    margin-bottom: 4px;
}

.inline-favicon {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
    object-fit: contain;
}

/* Mobile responsiveness */
@media (max-width: 767px) {
  .stream-page {
    padding: 12px;
  }

  .page-header {
    flex-wrap: wrap;
    gap: 8px;
    align-items: flex-start;
  }

  .page-header h2 {
    font-size: 1.4rem;
  }

  .header-actions {
    flex-wrap: wrap;
    gap: 6px;
    width: 100%;
  }

  .density-btn,
  .theme-btn,
  .refresh-btn,
  .rss-link {
    font-size: 0.8rem;
    padding: 5px 8px;
  }

  .inline-source {
    flex-shrink: 1;
    max-width: min(140px, 30vw);
  }
}
</style>
