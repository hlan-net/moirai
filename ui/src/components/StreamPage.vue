<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { type Article, type IssueRef } from '../utils/article'
import { authFetch } from '../utils/authFetch'
import { useTheme } from '../composables/useTheme'
import { useAuthStore } from '../stores/auth'
import StreamViewMenu from './StreamViewMenu.vue'
import StreamSidePanel from './StreamSidePanel.vue'
import { type SubjectRef, formatSubject, parseSubject, sameSubject } from '../utils/streamSubject'
import { SEARCH_LIMIT, SEARCH_MAX_LENGTH, parseSearchQuery, searchUrl } from '../utils/streamSearch'
import {
  DEFAULT_SECTIONS,
  SECTIONS,
  type SectionKey,
  formatSectionsValue,
  isWholeStream,
  parseSectionsValue,
  readStoredSections,
  sectionsParam,
  sectionsSummary,
  storeSections,
} from '../utils/streamSections'

interface ArticleGroup {
  title: string
  favicon?: string
  articles: Article[]
}

type GroupMode = 'feed' | 'time'

// Stream sections (#266, #344): one or several at once, chosen in the menu.
// The choice comes from the page's URL (?sections=sports,culture or =all),
// else from the browser, else Top stories; every change is written to both,
// so it survives a reload and a view can be shared as a link.
const route = useRoute()
const router = useRouter()

const selectedSections = ref<SectionKey[]>(
  parseSectionsValue(route.query.sections) ?? readStoredSections() ?? [...DEFAULT_SECTIONS]
)
const sectionSummary = computed(() => sectionsSummary(selectedSections.value))
const selectedSectionsModel = computed({
  get: () => selectedSections.value,
  set: (keys: SectionKey[]) => selectSections(keys),
})

const authStore = useAuthStore()
const isAuthenticated = computed(() => authStore.isAuthenticated)

// Search (#377): the `q` query parameter replaces the list with the articles
// that mention it, from every section and beyond the newest of the stream.
// Logged-in users only, like every request other than the stream's (#376).
// The stream stays loaded underneath, so clearing the search shows it as it
// was, without a request.
const searchQuery = computed(() => (isAuthenticated.value ? parseSearchQuery(route.query.q) : ''))
const searchInput = ref(searchQuery.value)
const searchResults = ref<Article[]>([])
const searchLoading = ref(false)
const searchError = ref('')

const streamArticles = ref<Article[]>([])
const articles = computed(() => (searchQuery.value ? searchResults.value : streamArticles.value))
const loading = ref(true)
const viewLoading = computed(() => (searchQuery.value ? searchLoading.value : loading.value))
const fetchingUpdates = ref(false)
const totalCount = ref(0)
const expandedArticles = ref<Set<string>>(new Set())
const isHighDensity = ref(true)
const groupMode = ref<GroupMode>('feed')
const newArticleCount = ref(0)
const { resolveTheme, setTheme } = useTheme()

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
    articles: [firstArticle],
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
        articles: [article],
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

// Namespace of the feed's own attributes (MOIRAI_RSS_NS in api/rss_ops.py).
const MOIRAI_RSS_NS = 'https://github.com/hlan-net/moirai/ns/rss'

const _extractCategories = (item: Element) => {
  const events: string[] = []
  const trends: string[] = []
  const issueRefs: IssueRef[] = []
  const topics: string[] = []
  let priority: 'low' | 'medium' | 'high' | undefined
  let sentiment: 'positive' | 'neutral' | 'negative' | undefined
  let section: string | undefined

  for (const category of Array.from(item.querySelectorAll('category'))) {
    const label = category.textContent?.trim()
    if (!label) continue
    const domain = category.getAttribute('domain')
    if (domain === 'section') {
      section = label
    } else if (domain === 'event' || domain === 'trend') {
      ;(domain === 'event' ? events : trends).push(label)
      const id = category.getAttributeNS(MOIRAI_RSS_NS, 'id') || undefined
      issueRefs.push({ kind: domain, name: label, id })
    } else if (domain === 'topic') {
      topics.push(label)
    } else if (domain === 'priority') {
      priority = label as 'low' | 'medium' | 'high'
    } else if (domain === 'sentiment') {
      sentiment = label as 'positive' | 'neutral' | 'negative'
    }
  }
  return { events, trends, issueRefs, topics, priority, sentiment, section }
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

  const { events, trends, issueRefs, topics, priority, sentiment, section } =
    _extractCategories(item)

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
    issueRefs: issueRefs.length ? issueRefs : undefined,
    annotations,
    section,
  }
}

const parseRssFeed = (xmlText: string): Article[] => {
  const doc = new DOMParser().parseFromString(xmlText, 'application/xml')
  if (doc.querySelector('parsererror')) {
    throw new Error('Invalid RSS feed')
  }

  return Array.from(doc.querySelectorAll('item')).map((item, index) => _parseFeedItem(item, index))
}

const sectionQuery = computed(() => {
  const param = sectionsParam(selectedSections.value)
  return param ? `section=${encodeURIComponent(param)}` : ''
})
const streamUrl = computed(() =>
  sectionQuery.value
    ? `/api/stream.rss?limit=${RSS_LIMIT}&${sectionQuery.value}`
    : `/api/stream.rss?limit=${RSS_LIMIT}`
)
const rssSubscribeUrl = computed(() =>
  sectionQuery.value ? `/api/stream.rss?${sectionQuery.value}` : '/api/stream.rss'
)
const emptyMessage = computed(() => {
  if (searchQuery.value) {
    return searchError.value || `No articles mention “${searchQuery.value}”.`
  }
  if (isWholeStream(selectedSections.value)) return 'No articles found in the stream.'
  return selectedSections.value.length === 1
    ? 'No articles in this section yet.'
    : 'No articles in these sections yet.'
})

// Every fetch takes a sequence number; only the latest one may write the
// list or clear the loading flags, so a superseded request (e.g. after a tab
// switch, including A -> B -> A) can neither show stale data nor end the
// current request's loading state early.
let latestRequest = 0

const fetchStream = async (isManual = false) => {
  const requestId = ++latestRequest
  const isCurrent = () => requestId === latestRequest
  // Only a first load or a tab switch shows the loading state: a background
  // poll of an empty section must not flash it over the empty-state message.
  if (isManual && streamArticles.value.length === 0) {
    loading.value = true
  }
  fetchingUpdates.value = true
  try {
    const response = await authFetch(streamUrl.value)
    if (!response.ok) {
      throw new Error(`Failed to fetch RSS: ${response.status}`)
    }
    const xmlText = await response.text()
    if (!isCurrent()) return
    const parsed = parseRssFeed(xmlText)

    if (streamArticles.value.length === 0 || isManual) {
      // Initial load or manual refresh: replace entirely
      streamArticles.value = parsed
      totalCount.value = parsed.length
    } else {
      // Auto-refresh: count new articles silently without changing the display
      const existingIds = new Set(streamArticles.value.map((a) => a._id))
      const newItems = parsed.filter((a) => !existingIds.has(a._id))

      if (newItems.length > 0) {
        newArticleCount.value += newItems.length
      }
    }
  } catch (error) {
    if (isCurrent()) console.error('Error fetching RSS stream:', error)
  } finally {
    if (isCurrent()) {
      fetchingUpdates.value = false
      loading.value = false
    }
  }
}

// The side column (#376): one subject, an article or an issue, named by the
// `open` query parameter. Logged-in users only: without a login the page
// makes no request other than the stream's, and the parameter is ignored.
const openSubject = computed<SubjectRef | null>(() =>
  isAuthenticated.value ? parseSubject(route.query.open) : null
)
// The stream and the search results together: an open article stays known
// when the list under it changes from one to the other.
const articlesByLink = computed(
  () => new Map([...streamArticles.value, ...searchResults.value].map((a) => [a.link, a]))
)
const subjectArticle = computed(() => {
  const subject = openSubject.value
  return subject?.type === 'article' ? (articlesByLink.value.get(subject.link) ?? null) : null
})
// An article subject waits for the first load, so that a shared link does
// not flash "no longer in the stream" before the stream has arrived.
const showSidePanel = computed(
  () => openSubject.value !== null && !(openSubject.value.type === 'article' && viewLoading.value)
)

// The control of the stream that last opened the column gets the focus back
// when it closes. The column's own controls come without an event, so moving
// on inside the column keeps the row it was opened from.
let subjectOpener: HTMLElement | null = null

const openSubjectRef = (subject: SubjectRef, event?: Event) => {
  if (!isAuthenticated.value) return
  if (event?.currentTarget instanceof HTMLElement) {
    subjectOpener = event.currentTarget
  }
  hideDotDetails()
  if (sameSubject(subject, openSubject.value)) return
  void router.push({ query: { ...route.query, open: formatSubject(subject) } })
}

const closeSubject = () => {
  if (!openSubject.value) return
  const query = { ...route.query }
  delete query.open
  void router.push({ query })
}

// However the column closes (its button, Escape, or the browser's Back),
// the control that opened it gets the focus back.
watch(openSubject, async (now, before) => {
  if (now || !before) return
  await nextTick()
  if (subjectOpener?.isConnected) subjectOpener.focus()
  subjectOpener = null
})

const onEscape = (event: KeyboardEvent) => {
  // The menu handles its own Escape first.
  if (event.defaultPrevented || !openSubject.value) return
  event.preventDefault()
  closeSubject()
}

// A dot of an event or a trend: straight to the issue when the article has
// exactly one of that kind, otherwise to the article, which lists them.
const openFromDot = (article: Article, kind: IssueRef['kind'], event: Event) => {
  const refs = (article.issueRefs || []).filter((ref) => ref.kind === kind)
  const only = refs.length === 1 ? refs[0] : undefined
  openSubjectRef(
    only?.id ? { type: 'issue', id: only.id } : { type: 'article', link: article.link },
    event
  )
}

// Like the stream's requests, only the latest search may write its result.
let latestSearch = 0

const runSearch = async () => {
  const query = searchQuery.value
  const requestId = ++latestSearch
  const isCurrent = () => requestId === latestSearch
  searchError.value = ''
  if (!query) {
    searchResults.value = []
    searchLoading.value = false
    return
  }
  searchLoading.value = true
  try {
    const response = await authFetch(searchUrl(query))
    if (!response.ok) {
      throw new Error(`Search failed: ${response.status}`)
    }
    const xmlText = await response.text()
    if (!isCurrent()) return
    searchResults.value = parseRssFeed(xmlText)
  } catch (error) {
    if (!isCurrent()) return
    console.error('Error searching articles:', error)
    searchResults.value = []
    searchError.value = 'The search failed. Try again in a moment.'
  } finally {
    if (isCurrent()) searchLoading.value = false
  }
}

// The URL is the state: the field, Back and a shared link all end up here.
watch(searchQuery, (query) => {
  searchInput.value = query
  expandedArticles.value = new Set()
  hideDotDetails()
  void runSearch()
})

const submitSearch = () => {
  const query = parseSearchQuery(searchInput.value)
  if (query === searchQuery.value) {
    // The same search again is a refresh of its results.
    if (query) void runSearch()
    return
  }
  const rest = { ...route.query }
  delete rest.q
  void router.push({ query: query ? { ...rest, q: query } : rest })
}

const clearSearch = () => {
  searchInput.value = ''
  submitSearch()
}

// "12 results · Search: “derby”"; a full page of results may not be all of them.
const searchSummary = computed(() => {
  const name = `Search: “${searchQuery.value}”`
  if (searchLoading.value) return name
  const count = searchResults.value.length
  const more = count >= SEARCH_LIMIT ? '+' : ''
  return `${count}${more} ${count === 1 ? 'result' : 'results'} · ${name}`
})

const sectionLabel = (article: Article) =>
  SECTIONS.find((section) => section.key === article.section)?.label

const refreshAndReset = () => {
  if (searchQuery.value) {
    void runSearch()
    return
  }
  newArticleCount.value = 0
  void fetchStream(true)
}

const selectSections = (keys: SectionKey[]) => {
  if (sectionsParam(keys) === sectionsParam(selectedSections.value)) {
    // Same stream (e.g. all ticked vs. none ticked): keep the ticks, no refetch.
    selectedSections.value = keys
    return
  }
  selectedSections.value = keys
  const value = formatSectionsValue(keys)
  storeSections(keys)
  void router.replace({ query: { ...route.query, sections: value } })
  streamArticles.value = []
  totalCount.value = 0
  newArticleCount.value = 0
  expandedArticles.value = new Set()
  hideDotDetails()
  void fetchStream(true)
}

onMounted(async () => {
  if (searchQuery.value) void runSearch()
  await fetchStream(true)
  refreshInterval = globalThis.setInterval(() => {
    // The background check and its badge pause while search results are shown.
    if (searchQuery.value) return
    // Skip a tick while a fetch is in flight rather than supersede it.
    if (!fetchingUpdates.value) void fetchStream(false)
  }, RSS_REFRESH_MS)
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
  const doc = new DOMParser().parseFromString(html, 'text/html')
  return doc.body.textContent || ''
}

function getHostname(urlStr: string) {
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

// Dot-details popover (compact view). Teleported to <body> with fixed positioning so
// the scrolling .stream-container can't clip it.
const DOT_POPOVER_GAP = 6
const hoveredArticle = ref<Article | null>(null)
const popoverPos = ref({ top: 0, right: 0, placeAbove: false })

const ISSUE_KINDS = ['event', 'trend'] as const

const hasDots = (article: Article) =>
  article.annotations?.priority === 'high' ||
  article.annotations?.priority === 'medium' ||
  article.annotations?.sentiment === 'positive' ||
  article.annotations?.sentiment === 'negative' ||
  !!article.events?.length ||
  !!article.trends?.length

const showDotDetails = (article: Article, event: Event) => {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const placeAbove = rect.bottom > window.innerHeight * 0.6
  popoverPos.value = {
    top: placeAbove ? rect.top - DOT_POPOVER_GAP : rect.bottom + DOT_POPOVER_GAP,
    right: Math.max(8, window.innerWidth - rect.right),
    placeAbove,
  }
  hoveredArticle.value = article
}

const hideDotDetails = () => {
  hoveredArticle.value = null
}

const toggleTheme = () => {
  const nextTheme = resolvedTheme.value === 'dark' ? 'light' : 'dark'
  setTheme(nextTheme, { persist: false })
}
</script>

<template>
  <div class="stream-layout" :class="{ 'has-panel': showSidePanel }" @keydown.esc="onEscape">
    <div class="stream-page">
      <header class="page-header">
        <div class="header-left">
          <h2>Aggregated Stream</h2>
          <span v-if="searchQuery" class="count" data-testid="search-summary">{{
            searchSummary
          }}</span>
          <span v-else class="count">
            <span v-if="totalCount > 0">{{ articles.length }}/{{ totalCount }}</span>
            <span v-else-if="!loading">{{ articles.length }}</span>
            Articles
            <span class="section-summary" data-testid="section-summary"
              >· {{ sectionSummary }}</span
            >
          </span>
          <span v-if="fetchingUpdates || searchLoading" class="update-badge">↻</span>
        </div>
        <div class="header-actions">
          <form
            v-if="isAuthenticated"
            class="search-form"
            role="search"
            @submit.prevent="submitSearch"
          >
            <input
              v-model="searchInput"
              type="search"
              class="search-input"
              placeholder="Search articles"
              aria-label="Search articles"
              :maxlength="SEARCH_MAX_LENGTH"
            />
            <button
              v-if="searchQuery"
              type="button"
              class="search-clear"
              aria-label="Clear the search"
              title="Clear the search"
              @click="clearSearch"
            >
              ×
            </button>
          </form>
          <button
            @click="refreshAndReset"
            :disabled="fetchingUpdates || searchLoading"
            class="refresh-btn"
            :class="{ 'has-new': newArticleCount > 0 }"
            title="Refresh stream"
          >
            {{ fetchingUpdates ? 'Checking...' : '↻ Refresh' }}
            <span v-if="newArticleCount > 0" class="new-count-badge">{{ newArticleCount }}</span>
          </button>
          <StreamViewMenu
            v-model:sections="selectedSectionsModel"
            v-model:high-density="isHighDensity"
            v-model:group-mode="groupMode"
            :show-theme="!isAuthenticated"
            :theme-label="themeLabel"
            :rss-url="rssSubscribeUrl"
            @toggle-theme="toggleTheme"
          />
        </div>
      </header>

      <div v-if="viewLoading" class="loading">
        {{ searchQuery ? 'Searching...' : 'Loading stream...' }}
      </div>

      <div
        v-else-if="articles.length"
        ref="streamContainer"
        class="stream-container"
        :class="{ 'high-density': isHighDensity }"
        @scroll.passive="hideDotDetails"
      >
        <div
          v-for="(group, index) in groupedArticles"
          :key="group.title + '-' + index"
          class="feed-group"
        >
          <h3 class="group-title">
            <template v-if="groupMode === 'feed'">
              <img
                v-if="group.favicon"
                :src="group.favicon"
                class="group-favicon"
                :alt="`${group.title} icon`"
                @error="handleFaviconError"
              />
              <img
                v-else
                class="group-favicon-placeholder"
                src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ctext y='20' font-size='20'%3E📰%3C/text%3E%3C/svg%3E"
                alt="Default news icon"
              />
            </template>
            {{ group.title }}
            <span v-if="groupMode === 'time'" class="group-count"
              >({{ group.articles.length }})</span
            >
          </h3>

          <div
            v-for="article in group.articles"
            :key="article._id"
            :class="['stream-item', { 'compact-item': isHighDensity }]"
          >
            <!-- High Density (River) View -->
            <template v-if="isHighDensity">
              <div class="compact-row">
                <span class="compact-time">{{
                  new Date(article.published).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })
                }}</span>
                <!-- Inline source tag for time-blocked mode -->
                <span
                  v-if="groupMode === 'time'"
                  class="inline-source"
                  :title="article.feed_title || getHostname(article.feed_url)"
                >
                  <img
                    v-if="article.feed_favicon"
                    :src="article.feed_favicon"
                    class="inline-favicon"
                    alt="Feed icon"
                    @error="handleFaviconError"
                  />
                  {{ article.feed_title || getHostname(article.feed_url) }}
                </span>
                <!-- A search covers every section, so each result names its own. -->
                <span
                  v-if="searchQuery && sectionLabel(article)"
                  class="inline-source row-section"
                  >{{ sectionLabel(article) }}</span
                >
                <h4 class="item-title compact-title">
                  <a :href="article.link" target="_blank">{{ article.title }}</a>
                </h4>
                <div
                  v-if="hasDots(article)"
                  class="compact-tags"
                  tabindex="0"
                  aria-describedby="dot-details-popover"
                  @mouseenter="showDotDetails(article, $event)"
                  @mouseleave="hideDotDetails"
                  @focus="showDotDetails(article, $event)"
                  @blur="hideDotDetails"
                >
                  <span
                    v-if="article.annotations?.priority === 'high'"
                    class="dot-tag priority-high-dot"
                  ></span>
                  <span
                    v-if="article.annotations?.priority === 'medium'"
                    class="dot-tag priority-medium-dot"
                  ></span>
                  <span
                    v-if="article.annotations?.sentiment === 'positive'"
                    class="dot-tag sentiment-positive-dot"
                  ></span>
                  <span
                    v-if="article.annotations?.sentiment === 'negative'"
                    class="dot-tag sentiment-negative-dot"
                  ></span>
                  <template v-for="kind in ISSUE_KINDS" :key="kind">
                    <template v-if="article[`${kind}s`]?.length">
                      <button
                        v-if="isAuthenticated"
                        type="button"
                        class="dot-tag dot-btn"
                        :class="`${kind}-dot`"
                        :aria-label="`Open the ${kind} of ${article.title}`"
                        @click.stop="openFromDot(article, kind, $event)"
                      ></button>
                      <span v-else class="dot-tag" :class="`${kind}-dot`"></span>
                    </template>
                  </template>
                </div>
                <button
                  v-if="isAuthenticated"
                  type="button"
                  class="discuss-btn"
                  :class="{ 'no-dots': !hasDots(article) }"
                  :aria-label="`Discuss ${article.title}`"
                  title="Discuss"
                  @click="openSubjectRef({ type: 'article', link: article.link }, $event)"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm0 14H5.17L4 17.17V4h16v12z"
                    />
                  </svg>
                </button>
              </div>
            </template>

            <!-- Expanded View -->
            <template v-else>
              <!-- Inline source for time-blocked expanded view -->
              <div v-if="groupMode === 'time'" class="inline-source-expanded">
                <img
                  v-if="article.feed_favicon"
                  :src="article.feed_favicon"
                  class="inline-favicon"
                  alt="Feed icon"
                  @error="handleFaviconError"
                />
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
                  <span v-for="event in article.events" :key="event" class="tag tag-event">{{
                    event
                  }}</span>
                </div>
                <div v-if="article.trends && article.trends.length > 0" class="tag-group">
                  <span v-for="trend in article.trends" :key="trend" class="tag tag-trend">{{
                    trend
                  }}</span>
                </div>
                <div v-if="article.annotations" class="tag-group">
                  <span
                    v-for="topic in article.annotations.topics"
                    :key="topic"
                    class="tag tag-topic"
                    >{{ topic }}</span
                  >
                  <span
                    :class="['tag', 'tag-priority', `tag-priority-${article.annotations.priority}`]"
                    >{{ article.annotations.priority }}</span
                  >
                  <span
                    :class="[
                      'tag',
                      'tag-sentiment',
                      `tag-sentiment-${article.annotations.sentiment}`,
                    ]"
                    >{{ article.annotations.sentiment }}</span
                  >
                </div>
              </div>
              <div class="item-meta">
                <span class="date">{{ formatDate(article.published) }}</span>
                <span v-if="searchQuery && sectionLabel(article)" class="row-section">{{
                  sectionLabel(article)
                }}</span>
                <button
                  v-if="isAuthenticated"
                  type="button"
                  class="read-more-btn"
                  @click="openSubjectRef({ type: 'article', link: article.link }, $event)"
                >
                  Discuss
                </button>
              </div>
            </template>
          </div>
          <hr v-if="index < groupedArticles.length - 1 && !isHighDensity" class="group-divider" />
        </div>
      </div>

      <div v-else class="empty-state" :role="searchError ? 'alert' : undefined">
        {{ emptyMessage }}
      </div>

      <Teleport to="body">
        <div
          v-if="hoveredArticle"
          id="dot-details-popover"
          role="tooltip"
          class="dot-popover"
          :class="{ 'place-above': popoverPos.placeAbove }"
          :style="{ top: `${popoverPos.top}px`, right: `${popoverPos.right}px` }"
        >
          <div v-if="hoveredArticle.annotations?.priority === 'high'" class="dot-popover-row">
            <span class="dot-tag priority-high-dot"></span>
            <span>High priority</span>
          </div>
          <div
            v-else-if="hoveredArticle.annotations?.priority === 'medium'"
            class="dot-popover-row"
          >
            <span class="dot-tag priority-medium-dot"></span>
            <span>Medium priority</span>
          </div>
          <div v-if="hoveredArticle.annotations?.sentiment === 'positive'" class="dot-popover-row">
            <span class="dot-tag sentiment-positive-dot"></span>
            <span>Positive sentiment</span>
          </div>
          <div
            v-else-if="hoveredArticle.annotations?.sentiment === 'negative'"
            class="dot-popover-row"
          >
            <span class="dot-tag sentiment-negative-dot"></span>
            <span>Negative sentiment</span>
          </div>
          <div v-if="hoveredArticle.events?.length" class="dot-popover-row">
            <span class="dot-tag event-dot"></span>
            <span class="dot-popover-label">Events</span>
            <span class="dot-popover-tags">
              <span v-for="event in hoveredArticle.events" :key="event" class="tag tag-event">{{
                event
              }}</span>
            </span>
          </div>
          <div v-if="hoveredArticle.trends?.length" class="dot-popover-row">
            <span class="dot-tag trend-dot"></span>
            <span class="dot-popover-label">Trends</span>
            <span class="dot-popover-tags">
              <span v-for="trend in hoveredArticle.trends" :key="trend" class="tag tag-trend">{{
                trend
              }}</span>
            </span>
          </div>
          <div v-if="hoveredArticle.annotations?.topics?.length" class="dot-popover-row">
            <span class="dot-tag dot-placeholder"></span>
            <span class="dot-popover-label">Topics</span>
            <span class="dot-popover-tags">
              <span
                v-for="topic in hoveredArticle.annotations.topics"
                :key="topic"
                class="tag tag-topic"
                >{{ topic }}</span
              >
            </span>
          </div>
        </div>
      </Teleport>
    </div>
    <StreamSidePanel
      v-if="showSidePanel && openSubject"
      class="stream-side"
      :subject="openSubject"
      :article="subjectArticle"
      :articles-by-link="articlesByLink"
      @close="closeSubject"
      @open="openSubjectRef"
    />
  </div>
</template>

<style scoped>
/* The stream, and beside it the side column when one is open (#376). */
.stream-layout {
  display: flex;
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  height: 100%;
  min-height: 0;
}

.stream-layout.has-panel {
  max-width: 1400px;
}

.stream-page {
  padding: 20px;
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.stream-side {
  flex: 0 0 clamp(320px, 38%, 480px);
  padding-block: 20px;
  padding-inline-end: 20px;
}

/* No room for two columns: the side column covers the stream. */
@media (max-width: 899px) {
  .stream-side {
    position: fixed;
    inset: 0;
    z-index: 1800;
    padding: 16px;
    border: none;
    background: var(--bg-color);
  }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border-bottom: 2px solid #eee;
  margin-bottom: 20px;
  padding-bottom: 10px;
}

.header-left {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 15px;
  min-width: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
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

.section-summary {
  margin-left: 4px;
}

.search-form {
  position: relative;
  display: flex;
  align-items: center;
}

.search-input {
  width: 180px;
  padding: 6px 26px 6px 10px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-color);
  font-size: 0.9rem;
}

.search-input:focus-visible {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary-color) 35%, transparent);
}

/* The page has its own clear button, which also ends the search. */
.search-input::-webkit-search-cancel-button {
  appearance: none;
}

.search-clear {
  position: absolute;
  inset-inline-end: 2px;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  box-shadow: none;
  color: var(--text-color);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0.7;
}

.search-clear:hover,
.search-clear:focus-visible {
  opacity: 1;
}

.row-section {
  font-size: 0.75rem;
  opacity: 0.8;
}

.update-badge {
  font-size: 0.9rem;
  color: var(--primary-color);
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
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

.event-dot {
  background-color: #1565c0;
}
.trend-dot {
  background-color: #7b1fa2;
}

/* Annotation dots (compact view) */
.priority-high-dot {
  background-color: #c62828;
}
.priority-medium-dot {
  background-color: #ef6c00;
}
.sentiment-positive-dot {
  background-color: #2e7d32;
}
.sentiment-negative-dot {
  background-color: #d32f2f;
}

.dot-btn {
  padding: 0;
  border: none;
  box-shadow: none;
  cursor: pointer;
  position: relative;
}

/* A hit area larger than the 8px dot. */
.dot-btn::after {
  content: '';
  position: absolute;
  inset: -6px -3px;
}

.dot-btn:hover,
.dot-btn:focus-visible {
  box-shadow: none;
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.discuss-btn {
  align-self: center;
  display: inline-flex;
  padding: 2px 4px;
  background: transparent;
  border: none;
  border-radius: 4px;
  box-shadow: none;
  color: var(--text-color);
  opacity: 0.45;
  cursor: pointer;
}

.discuss-btn.no-dots {
  margin-left: auto;
}

.discuss-btn:hover,
.discuss-btn:focus-visible {
  background: var(--button-bg);
  box-shadow: none;
  opacity: 1;
}

.compact-tags:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
  border-radius: 4px;
}

/* Dot-details popover (teleported to body, fixed position) */
.dot-popover {
  position: fixed;
  z-index: 2000;
  max-width: 320px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--card-bg);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  font-size: 0.85rem;
  text-align: left;
  pointer-events: none;
}

.dot-popover.place-above {
  transform: translateY(-100%);
}

.dot-popover-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.dot-popover-row .dot-tag {
  flex-shrink: 0;
}

.dot-placeholder {
  visibility: hidden;
}

.dot-popover-label {
  font-weight: 600;
  opacity: 0.8;
  flex-shrink: 0;
}

.dot-popover-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.dot-popover-tags .tag {
  padding: 1px 8px;
  font-size: 0.75rem;
}

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

.loading,
.empty-state {
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
    justify-content: flex-end;
    gap: 6px;
    width: 100%;
  }

  .refresh-btn {
    font-size: 0.8rem;
    padding: 5px 8px;
  }

  .search-form {
    flex: 1;
    min-width: 0;
  }

  .search-input {
    width: 100%;
  }

  .inline-source {
    flex-shrink: 1;
    max-width: min(140px, 30vw);
  }
}
</style>
