<script setup lang="ts">
// The Stream page's side column (#376): one subject at a time, picked up from
// the flow. An article shows its summary; an issue (an event or a trend) its
// description and articles. Below either is the conversation about it.
import { computed, onMounted, ref, watch } from 'vue'
import SubjectChat from './SubjectChat.vue'
import { authFetch } from '../utils/authFetch'
import type { Article, IssueRef } from '../utils/article'
import { isValidUrl } from '../utils/formatters'
import type { SubjectRef } from '../utils/streamSubject'

interface Issue {
  _id: string
  logos?: string
  description?: string
  longevity?: string
  status?: string
  premises?: { type?: string; id?: string }[]
  // With ?expand=issues: the issues this one holds, e.g. the events of a trend.
  nested_issues?: { id: string; logos?: string; longevity?: string; article_links: string[] }[]
}

const props = defineProps<{
  subject: SubjectRef
  // The article of an article subject, as the stream shows it.
  article: Article | null
  // Stream articles by link, to name the articles of an issue.
  articlesByLink: Map<string, Article>
}>()

const emit = defineEmits<{
  close: []
  open: [subject: SubjectRef]
}>()

const closeButton = ref<HTMLButtonElement | null>(null)
const issue = ref<Issue | null>(null)
const issueState = ref<'idle' | 'loading' | 'missing' | 'error'>('idle')

let issueRequest = 0

const loadIssue = async () => {
  const mine = ++issueRequest
  if (props.subject.type !== 'issue') {
    issue.value = null
    issueState.value = 'idle'
    return
  }
  // A reload after the conversation used tools keeps the current view up.
  if (issue.value?._id !== props.subject.id) {
    issue.value = null
    issueState.value = 'loading'
  }
  try {
    const response = await authFetch(`/api/issues/${props.subject.id}?expand=issues`)
    if (mine !== issueRequest) return
    if (response.ok) {
      issue.value = await response.json()
      issueState.value = 'idle'
    } else {
      issue.value = null
      issueState.value = response.status === 404 ? 'missing' : 'error'
    }
  } catch (error) {
    if (mine !== issueRequest) return
    console.error('Failed to load the issue:', error)
    issue.value = null
    issueState.value = 'error'
  }
}

watch(
  () => (props.subject.type === 'issue' ? props.subject.id : null),
  () => void loadIssue(),
  { immediate: true }
)

const issueKind = computed(() => (issue.value?.longevity === 'transient' ? 'Event' : 'Trend'))

const heading = computed(() => {
  if (props.subject.type === 'article') return props.article?.title || 'Article'
  if (issue.value) return issue.value.logos || 'Untitled'
  return issueState.value === 'loading' ? 'Loading…' : 'Not available'
})

const kindLabel = computed(() => {
  if (props.subject.type === 'article') return 'Article'
  return issue.value ? issueKind.value : 'Event or trend'
})

const nestedIssues = computed(() => issue.value?.nested_issues || [])

// The issue's own articles and those of the issues it holds: a trend's
// articles are mostly those of its events. Premises are written by tool
// calls, so only an http(s) address becomes a link; anything else is text.
const issueArticles = computed(() => {
  const own = (issue.value?.premises || [])
    .filter((premise) => premise.type === 'message' && premise.id)
    .map((premise) => premise.id as string)
  const nested = nestedIssues.value.flatMap((child) => child.article_links)
  return [...new Set([...own, ...nested])].map((link) => ({
    link,
    title: props.articlesByLink.get(link)?.title || link,
    isLink: isValidUrl(link),
  }))
})

const articleIssues = computed<IssueRef[]>(() => props.article?.issueRefs || [])

const articleContext = computed<Record<string, unknown>>(() => {
  const article = props.article
  if (!article) return {}
  return {
    _id: article.link,
    title: article.title,
    link: article.link,
    summary: article.summary,
    published: article.published,
    feed_title: article.feed_title,
    feed_url: article.feed_url,
    issues: articleIssues.value.map((ref) => ({ id: ref.id, logos: ref.name })),
  }
})

const plainSummary = computed(() => {
  const doc = new DOMParser().parseFromString(props.article?.summary || '', 'text/html')
  return doc.body.textContent || ''
})

const formatTime = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

// Focus moves into the column when it opens; the page returns it on close.
onMounted(() => closeButton.value?.focus())
</script>

<template>
  <aside class="side-panel" aria-labelledby="side-panel-heading">
    <header class="side-header">
      <div class="side-heading">
        <span class="side-kind">{{ kindLabel }}</span>
        <h3 id="side-panel-heading">{{ heading }}</h3>
      </div>
      <button
        ref="closeButton"
        type="button"
        class="side-close"
        aria-label="Close the side column"
        title="Close (Esc)"
        @click="emit('close')"
      >
        ×
      </button>
    </header>

    <!-- An article of the stream -->
    <template v-if="subject.type === 'article' && article">
      <div class="side-body">
        <p class="side-meta">
          {{ article.feed_title }} · {{ formatTime(article.published) }} ·
          <a :href="article.link" target="_blank" rel="noopener">Open the article</a>
        </p>
        <p v-if="plainSummary" class="side-text">{{ plainSummary }}</p>
        <div v-if="articleIssues.length" class="side-refs">
          <span class="side-label">In</span>
          <template v-for="ref in articleIssues" :key="`${ref.kind}:${ref.id || ref.name}`">
            <button
              v-if="ref.id"
              type="button"
              class="ref-btn"
              :class="ref.kind"
              :title="`Open the ${ref.kind}`"
              @click="emit('open', { type: 'issue', id: ref.id })"
            >
              {{ ref.name }}
            </button>
            <span v-else class="ref-btn static" :class="ref.kind">{{ ref.name }}</span>
          </template>
        </div>
      </div>
      <SubjectChat
        context-type="article"
        :entity-id="article.link"
        :entity-data="articleContext"
        placeholder="Ask about this article…"
      />
    </template>

    <!-- An event or a trend -->
    <template v-else-if="subject.type === 'issue' && issue">
      <div class="side-body">
        <p v-if="issue.description" class="side-text">{{ issue.description }}</p>
        <p v-else class="side-text muted">No description yet.</p>
        <div v-if="nestedIssues.length" class="side-refs">
          <span class="side-label">Holds</span>
          <button
            v-for="child in nestedIssues"
            :key="child.id"
            type="button"
            class="ref-btn"
            :title="`Open ${child.logos || 'this issue'}`"
            @click="emit('open', { type: 'issue', id: child.id })"
          >
            {{ child.logos || 'Untitled' }}
          </button>
        </div>
        <div class="side-articles">
          <span class="side-label"
            >{{ issueArticles.length }} article{{ issueArticles.length === 1 ? '' : 's' }}</span
          >
          <ul v-if="issueArticles.length">
            <li v-for="item in issueArticles" :key="item.link">
              <a v-if="item.isLink" :href="item.link" target="_blank" rel="noopener">{{
                item.title
              }}</a>
              <span v-else>{{ item.title }}</span>
            </li>
          </ul>
        </div>
      </div>
      <SubjectChat
        context-type="issue"
        :entity-id="issue._id"
        :entity-data="issue as unknown as Record<string, unknown>"
        :placeholder="`Ask about this ${issueKind.toLowerCase()}, or say how to change it…`"
        @tools-used="loadIssue"
      />
    </template>

    <div v-else class="side-body">
      <p v-if="issueState === 'loading'" class="side-text muted">Loading…</p>
      <p v-else-if="issueState === 'missing'" class="side-text muted">
        This event or trend no longer exists.
      </p>
      <p v-else-if="issueState === 'error'" class="side-text muted">It could not be loaded.</p>
      <p v-else class="side-text muted">This article is no longer in the stream.</p>
    </div>
  </aside>
</template>

<style scoped>
.side-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding-inline-start: 20px;
  border-inline-start: 1px solid var(--border-color);
  color: var(--text-color);
  text-align: start;
}

/* The global link colour is too dark on the dark theme; underline instead. */
.side-panel a {
  color: inherit;
  text-decoration: underline;
}

.side-panel a:hover {
  color: var(--primary-hover);
}

.side-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--border-color);
}

.side-heading {
  min-width: 0;
}

.side-kind {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.7;
}

.side-header h3 {
  margin: 2px 0 0;
  font-size: 1.1rem;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.side-close {
  flex-shrink: 0;
  padding: 2px 10px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-color);
  font-size: 1.2rem;
  line-height: 1.2;
  box-shadow: none;
  cursor: pointer;
}

.side-close:hover {
  background: var(--button-bg);
  border-color: var(--primary-color);
}

.side-body {
  padding: 10px 0;
  max-height: 45%;
  overflow-y: auto;
  flex-shrink: 0;
}

.side-meta {
  margin: 0 0 8px;
  font-size: 0.8rem;
  opacity: 0.8;
}

.side-text {
  margin: 0 0 8px;
  font-size: 0.9rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.muted {
  font-style: italic;
  opacity: 0.7;
}

.side-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.7;
}

.side-refs {
  margin-bottom: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.ref-btn {
  padding: 2px 8px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: transparent;
  color: var(--text-color);
  font-size: 0.8rem;
  font-weight: 400;
  box-shadow: none;
}

button.ref-btn {
  cursor: pointer;
}

button.ref-btn:hover {
  background: var(--button-bg);
  border-color: var(--primary-color);
}

.side-articles ul {
  margin: 4px 0 0;
  padding-inline-start: 1.2em;
  font-size: 0.85rem;
}

.side-articles li {
  margin: 2px 0;
  overflow-wrap: anywhere;
}
</style>
