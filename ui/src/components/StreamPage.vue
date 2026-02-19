<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { type Article } from '../utils/articleCache'

interface ArticleGroup {
  title: string
  favicon?: string
  articles: Article[]
}

const articles = ref<Article[]>([])
const loading = ref(true)
const fetchingUpdates = ref(false)
const totalCount = ref(0)
const expandedArticles = ref<Set<string>>(new Set())
const isHighDensity = ref(true)

let refreshInterval: number | null = null

const RSS_LIMIT = 200
const RSS_REFRESH_MS = 120000

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

const parseRssFeed = (xmlText: string): Article[] => {
  const doc = new DOMParser().parseFromString(xmlText, 'application/xml')
  if (doc.querySelector('parsererror')) {
    throw new Error('Invalid RSS feed')
  }

  return Array.from(doc.querySelectorAll('item')).map((item, index) => {
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

    const events: string[] = []
    const trends: string[] = []
    for (const category of Array.from(item.querySelectorAll('category'))) {
      const label = category.textContent?.trim()
      if (!label) continue
      const domain = category.getAttribute('domain')
      if (domain === 'event') {
        events.push(label)
      } else if (domain === 'trend') {
        trends.push(label)
      }
    }

    return {
      _id: guid,
      title,
      summary,
      link,
      published: published || new Date().toISOString(),
      feed_url: feedUrl,
      feed_title: sourceTitle || getHostname(feedUrl),
      events: events.length ? events : undefined,
      trends: trends.length ? trends : undefined
    }
  })
}

const fetchStream = async () => {
  if (articles.value.length === 0) {
    loading.value = true
  }
  fetchingUpdates.value = true
  try {
    const response = await fetch(`/api/stream.rss?limit=${RSS_LIMIT}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch RSS: ${response.status}`)
    }
    const xmlText = await response.text()
    const parsed = parseRssFeed(xmlText)
    articles.value = parsed
    totalCount.value = parsed.length
  } catch (error) {
    console.error('Error fetching RSS stream:', error)
  } finally {
    fetchingUpdates.value = false
    loading.value = false
  }
}

onMounted(async () => {
  await fetchStream()
  refreshInterval = globalThis.setInterval(fetchStream, RSS_REFRESH_MS)
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

            <a href="/api/stream.rss" class="rss-link" title="Subscribe to RSS feed" target="_blank">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19 7.38 20 6.18 20A2.18 2.18 0 0 1 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/>
                </svg>
                RSS
            </a>
            <button @click="fetchStream" :disabled="fetchingUpdates" class="refresh-btn" title="Refresh stream">
                {{ fetchingUpdates ? 'Checking...' : '↻ Refresh' }}
            </button>
        </div>
    </header>

    <div v-if="loading" class="loading">Loading stream...</div>
    
    <div v-else-if="articles.length" class="stream-container" :class="{ 'high-density': isHighDensity }">
      <div v-for="(group, index) in groupedArticles" :key="index" class="feed-group">
        <h3 class="group-title">
          <img v-if="group.favicon" :src="group.favicon" class="group-favicon" :alt="`${group.title} icon`" @error="handleFaviconError" />
          <span v-else class="group-favicon-placeholder" role="img" :aria-label="`${group.title} icon`">📰</span>
          {{ group.title }}
        </h3>
        
        <div v-for="article in group.articles" :key="article._id" 
             :class="['stream-item', { 'compact-item': isHighDensity }]">
          
          <!-- High Density (River) View -->
          <template v-if="isHighDensity">
            <div class="compact-row">
              <span class="compact-time">{{ new Date(article.published).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}</span>
              <h4 class="item-title compact-title">
                <a :href="article.link" target="_blank">{{ article.title }}</a>
              </h4>
              <div class="compact-tags">
                <span v-if="article.events?.length" class="dot-tag event-dot" title="Has Events"></span>
                <span v-if="article.trends?.length" class="dot-tag trend-dot" title="Has Trends"></span>
              </div>
            </div>
          </template>

          <!-- Expanded View -->
          <template v-else>
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
                <span v-for="event in article.events" :key="event" class="tag tag-event">{{ event }}</span>
              </div>
              <div v-if="article.trends && article.trends.length > 0" class="tag-group">
                <span v-for="trend in article.trends" :key="trend" class="tag tag-trend">{{ trend }}</span>
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

.density-btn:hover {
    background: var(--button-bg);
    border-color: var(--primary-color);
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
    border-bottom: 1px solid var(--border-color);
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
    color: #95a5a6;
    min-width: 60px;
    flex-shrink: 0;
}

.compact-title {
    margin: 0 !important;
    font-size: 1rem !important;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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

.loading, .empty-state {
    text-align: center;
    padding: 40px;
    color: #7f8c8d;
    font-size: 1.2rem;
}
</style>
