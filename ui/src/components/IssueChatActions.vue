<script setup lang="ts">
import { ref } from 'vue'
import { useChatContextStore } from '../stores/chatContext'
import { authFetch } from '../utils/authFetch'

interface IssueLike {
  _id: string
  [key: string]: unknown
}

const props = defineProps<{
  issue: IssueLike
}>()

const chatContextStore = useChatContextStore()

const shareState = ref<'idle' | 'loading' | 'done' | 'error'>('idle')
const shareUrl = ref<string | null>(null)
const shareError = ref<string | null>(null)

const openIssueChat = () => {
  chatContextStore.open('issue', props.issue._id, props.issue as Record<string, unknown>)
}

const openRefineIssueChat = () => {
  chatContextStore.open(
    'issue',
    props.issue._id,
    props.issue as Record<string, unknown>,
    'Help me refine the description of this Issue based on its linked articles'
  )
}

const shareToBluesky = async () => {
  shareState.value = 'loading'
  shareError.value = null
  shareUrl.value = null
  try {
    const res = await authFetch(`/api/issues/${props.issue._id}/share`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: 'bluesky' }),
    })
    const data = await res.json()
    if (!res.ok) {
      shareState.value = 'error'
      shareError.value = data.error || 'Share failed'
    } else {
      shareState.value = 'done'
      shareUrl.value = data.url || null
    }
  } catch (err) {
    console.error('Share to Bluesky failed:', err)
    shareState.value = 'error'
    shareError.value = 'Network error'
  }
}
</script>

<template>
  <div class="card-actions" @click.stop>
    <button class="mini-action" @click="openIssueChat">💬 Chat</button>
    <button class="mini-action" @click="openRefineIssueChat">✏️ Refine</button>
    <button
      class="mini-action bluesky-btn"
      :disabled="shareState === 'loading'"
      @click="shareToBluesky"
      title="Share to Bluesky"
    >
      {{ shareState === 'loading' ? '…' : '🦋 Share' }}
    </button>
    <a
      v-if="shareState === 'done' && shareUrl"
      :href="shareUrl"
      target="_blank"
      rel="noopener noreferrer"
      class="share-link"
      title="View on Bluesky"
    >
      View post ↗
    </a>
    <span v-if="shareState === 'error'" class="share-error" :title="shareError || ''">
      ⚠ Failed
    </span>
  </div>
</template>

<style scoped>
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  align-items: center;
}

.mini-action {
  border: 1px solid var(--border-color);
  background: var(--button-bg);
  color: var(--text-color);
  border-radius: 6px;
  font-size: 0.8rem;
  padding: 4px 8px;
  cursor: pointer;
}

.mini-action:disabled {
  opacity: 0.5;
  cursor: default;
}

.bluesky-btn {
  border-color: #0085ff;
}

.share-link {
  font-size: 0.75rem;
  color: #0085ff;
  text-decoration: none;
}

.share-link:hover {
  text-decoration: underline;
}

.share-error {
  font-size: 0.75rem;
  color: var(--error-color, #e74c3c);
}
</style>
