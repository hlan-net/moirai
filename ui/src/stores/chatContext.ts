import { defineStore } from 'pinia'

export type ChatContextType = 'article' | 'issue' | 'feed'

export interface ChatContextPayload {
  type: ChatContextType
  entity_id: string
  entity_data: Record<string, unknown>
}

interface ChatContextState {
  isOpen: boolean
  contextType: ChatContextType | null
  entityId: string | null
  entityData: Record<string, unknown> | null
  initialMessage: string | null
}

export const useChatContextStore = defineStore('chatContext', {
  state: (): ChatContextState => ({
    isOpen: false,
    contextType: null,
    entityId: null,
    entityData: null,
    initialMessage: null,
  }),
  getters: {
    contextPayload(state): ChatContextPayload | null {
      if (!state.contextType || !state.entityId || !state.entityData) {
        return null
      }
      return {
        type: state.contextType,
        entity_id: state.entityId,
        entity_data: state.entityData,
      }
    },
  },
  actions: {
    open(
      type: ChatContextType,
      entityId: string,
      entityData: Record<string, unknown>,
      initialMessage: string | null = null
    ) {
      this.contextType = type
      this.entityId = entityId
      this.entityData = entityData
      this.initialMessage = initialMessage
      this.isOpen = true
    },
    close() {
      this.isOpen = false
      this.contextType = null
      this.entityId = null
      this.entityData = null
      this.initialMessage = null
    },
  },
})
