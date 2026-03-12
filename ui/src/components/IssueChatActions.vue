<script setup lang="ts">
import { useChatContextStore } from '../stores/chatContext'

interface IssueLike {
  _id: string
  [key: string]: unknown
}

const props = defineProps<{
  issue: IssueLike
}>()

const chatContextStore = useChatContextStore()

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
</script>

<template>
  <div class="card-actions" @click.stop>
    <button class="mini-action" @click="openIssueChat">💬 Chat</button>
    <button class="mini-action" @click="openRefineIssueChat">✏️ Refine</button>
  </div>
</template>

<style scoped>
.card-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
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
</style>
