<script setup lang="ts">
import { onMounted, ref, computed, watch, nextTick } from 'vue'
import { getHostname, isValidUrl } from '../utils/formatters'
import { useAuthStore } from '../stores/auth'
import { useFilterStore } from '../stores/filter' // Import the new filter store
import { useChatContextStore } from '../stores/chatContext'
import { authFetch } from '../utils/authFetch'

interface Feed {
  _id: string
  url: string
  title?: string
  category?: string
  favicon_url?: string
  last_fetch_error?: string
  last_fetch_at?: string
}

const feeds = ref<Feed[]>([])
const loading = ref(true)
const refreshing = ref(false)
const renamingFeedId = ref<string | null>(null)
const newFeedTitle = ref('')
const showBulkImportModal = ref(false)
const bulkImportText = ref('')
const bulkImporting = ref(false)
const bulkImportResults = ref<any>(null)
const notification = ref<{ message: string; type: 'error' | 'success' | 'warning' } | null>(null)
const searchQuery = ref('')
const bulkDeleteMode = ref(false)
const selectedFeedIds = ref<Set<string>>(new Set())

// Inject feed selection from parent (used in template) - NO LONGER USED, replaced by filterStore
// const selectedFeedUrl = inject<Ref<string | null>>('selectedFeedUrl', ref(null))
// const selectFeed = inject<(url: string | null) => void>('selectFeed', () => {})
// Prevent TS warnings - these are used in template
// void selectedFeedUrl
// void selectFeed

const authStore = useAuthStore()
const filterStore = useFilterStore() // Initialize the filter store
const chatContextStore = useChatContextStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

// Refs for modal accessibility
const modalContentRef = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const previousActiveElement = ref<HTMLElement | null>(null)

// Extract and validate URLs from text
const extractValidUrls = (text: string): string[] => {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && isValidUrl(line))
}

// Computed: Check if import button should be enabled
const canImport = computed(() => {
  if (!bulkImportText.value.trim()) return false
  const validUrls = extractValidUrls(bulkImportText.value)
  return validUrls.length > 0 && validUrls.length <= 50
})

// Computed: URL count for display
const urlCount = computed(() => {
  return extractValidUrls(bulkImportText.value).length
})

// Computed: Filtered feeds based on search query
const filteredFeeds = computed(() => {
  if (!searchQuery.value.trim()) return feeds.value

  const query = searchQuery.value.toLowerCase()

  const toSearchable = (value: unknown) => String(value ?? '').toLowerCase()

  return feeds.value.filter((feed) => {
    const title = toSearchable(feed.title)
    const url = toSearchable(feed.url)
    const category = toSearchable(feed.category)
    return title.includes(query) || url.includes(query) || category.includes(query)
  })
})

// Computed: Feeds filtered by contextual selection (articles from selected event)
const contextuallyFilteredFeeds = computed(() => {
  if (!filterStore.contextualFeedUrls) return filteredFeeds.value
  return filteredFeeds.value.filter(feed =>
    filterStore.contextualFeedUrls!.includes(feed.url)
  )
})

const showNotification = (message: string, type: 'error' | 'success' | 'warning') => {
  notification.value = { message, type }
  setTimeout(() => {
    notification.value = null
  }, 5000) // Auto-dismiss after 5 seconds
}

const fetchFeeds = async () => {
  try {
    const response = await authFetch('/api/feeds')
    if (response.ok) {
      const allFeeds = await response.json()
      // Filter out CouchDB design documents (internal structures)
      feeds.value = allFeeds.filter((f: Feed) => !f._id.startsWith('_design/'))
    }
  } catch (error) {
    console.error('Error fetching feeds:', error)
  } finally {
    loading.value = false
  }
}

const triggerRefresh = async () => {
  refreshing.value = true
  try {
    const res = await authFetch('/api/feeds/refresh', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      showNotification(`Started refreshing ${data.count} feeds.`, 'success')
    } else {
      showNotification('Failed to trigger refresh.', 'error')
    }
  } catch (e) {
    console.error(e)
    showNotification('Error triggering refresh.', 'error')
  } finally {
    refreshing.value = false
  }
}

const deleteFeed = async (id: string) => {
  if (!confirm('Are you sure you want to delete this feed?')) return

  try {
    const res = await authFetch(`/api/feeds/${id}`, { method: 'DELETE' })
    if (res.ok) {
      feeds.value = feeds.value.filter((f) => f._id !== id)
      // If the deleted feed was selected, clear the selection
      if (filterStore.selectedFeedId === id) {
        filterStore.setSelectedFeedId(null)
      }
      showNotification('Feed deleted successfully.', 'success')
    } else {
      showNotification('Failed to delete feed', 'error')
    }
  } catch (e) {
    console.error(e)
    showNotification('Error deleting feed', 'error')
  }
}

const toggleBulkDeleteMode = () => {
  bulkDeleteMode.value = !bulkDeleteMode.value
  if (!bulkDeleteMode.value) {
    selectedFeedIds.value.clear()
  }
}

const toggleFeedSelection = (feedId: string) => {
  if (selectedFeedIds.value.has(feedId)) {
    selectedFeedIds.value.delete(feedId)
  } else {
    selectedFeedIds.value.add(feedId)
  }
}

const selectAllFeeds = () => {
  contextuallyFilteredFeeds.value.forEach(feed => {
    selectedFeedIds.value.add(feed._id)
  })
}

const selectNoneFeeds = () => {
  selectedFeedIds.value.clear()
}

const bulkDeleteFeeds = async () => {
  const count = selectedFeedIds.value.size
  if (count === 0) {
    showNotification('No feeds selected', 'warning')
    return
  }

  const message = `Delete ${count} feed${count > 1 ? 's' : ''}?\n\n` +
    `Note: Articles from these feeds will remain in your collection. ` +
    `Only the feed subscriptions will be removed.`
  
  if (!confirm(message)) return

  let successCount = 0
  let failCount = 0

  for (const feedId of selectedFeedIds.value) {
    try {
      const res = await authFetch(`/api/feeds/${feedId}`, { method: 'DELETE' })
      if (res.ok) {
        successCount++
        feeds.value = feeds.value.filter((f) => f._id !== feedId)
        // If the deleted feed was selected, clear the selection
        if (filterStore.selectedFeedId === feedId) {
          filterStore.setSelectedFeedId(null)
        }
      } else {
        failCount++
      }
    } catch (e) {
      console.error(e)
      failCount++
    }
  }

  selectedFeedIds.value.clear()
  bulkDeleteMode.value = false

  if (failCount === 0) {
    showNotification(`Successfully deleted ${successCount} feed${successCount > 1 ? 's' : ''}`, 'success')
  } else {
    showNotification(
      `Deleted ${successCount} feed${successCount > 1 ? 's' : ''}, ${failCount} failed`,
      failCount > successCount ? 'error' : 'warning'
    )
  }
}

const startRename = (feed: Feed) => {
  renamingFeedId.value = feed._id
  newFeedTitle.value = feed.title || ''
}

const cancelRename = () => {
  renamingFeedId.value = null
  newFeedTitle.value = ''
}

const renameFeed = async (feed: Feed) => {
  try {
    const res = await authFetch(`/api/feeds/${feed._id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newFeedTitle.value }),
    })
    if (res.ok) {
      const updatedFeed = await res.json()
      const index = feeds.value.findIndex((f) => f._id === updatedFeed._id)
      if (index !== -1) {
        feeds.value[index] = updatedFeed
      }
      cancelRename()
      showNotification('Feed renamed successfully.', 'success')
    } else {
      showNotification('Failed to rename feed', 'error')
    }
  } catch (e) {
    console.error(e)
    showNotification('Error renaming feed', 'error')
  }
}

onMounted(() => {
  fetchFeeds()
})

const openFeedInNewTab = (url: string) => {
  globalThis.open(url, '_blank')
}

const openFeedChat = (feed: Feed) => {
  chatContextStore.open(
    'feed',
    feed._id,
    feed as unknown as Record<string, unknown>,
    'What has this feed been covering recently?'
  )
}

const handleFaviconError = (event: Event) => {
  // Hide the image if it fails to load
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
}

let bulkImportKeydownListenerAttached = false

const handleBulkImportKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' || event.key === 'Esc') {
    closeBulkImportModal()
  }
}

const openBulkImportModal = () => {
  // Store the currently focused element to restore later
  previousActiveElement.value = document.activeElement as HTMLElement
  showBulkImportModal.value = true
  bulkImportText.value = ''
  bulkImportResults.value = null

  if (!bulkImportKeydownListenerAttached) {
    globalThis.addEventListener('keydown', handleBulkImportKeydown)
    bulkImportKeydownListenerAttached = true
  }
}

const closeBulkImportModal = () => {
  showBulkImportModal.value = false
  bulkImportText.value = ''
  bulkImportResults.value = null

  // Remove keyboard event listener
  if (bulkImportKeydownListenerAttached) {
    globalThis.removeEventListener('keydown', handleBulkImportKeydown)
    bulkImportKeydownListenerAttached = false
  }

  // Restore focus to the element that opened the modal
  if (previousActiveElement.value) {
    previousActiveElement.value.focus()
  }
}

const parseOpmlFile = (xmlContent: string): string[] => {
  try {
    const parser = new DOMParser()
    const xmlDoc = parser.parseFromString(xmlContent, 'text/xml')

    // Check for parsing errors
    const parserError = xmlDoc.querySelector('parsererror')
    if (parserError) {
      throw new Error('Invalid OPML/XML format')
    }

    // Extract feed URLs from <outline> elements with xmlUrl attribute
    const outlines = xmlDoc.querySelectorAll('outline[xmlUrl]')
    const urls: string[] = []

    outlines.forEach((outline) => {
      const xmlUrl = outline.getAttribute('xmlUrl')
      if (xmlUrl && isValidUrl(xmlUrl)) {
        urls.push(xmlUrl)
      }
    })

    return urls
  } catch (error) {
    console.error('OPML parsing error:', error)
    throw new Error('Failed to parse OPML file. Please ensure it is a valid OPML format.')
  }
}

// Focus trap: handle Tab key to keep focus within modal
const handleModalKeydown = (event: KeyboardEvent) => {
  if (!modalContentRef.value) return

  // Close modal on Escape
  if (event.key === 'Escape') {
    closeBulkImportModal()
    return
  }

  // Focus trap: keep focus within modal when pressing Tab
  if (event.key === 'Tab') {
    const focusableElements = modalContentRef.value.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    const firstElement = focusableElements[0] as HTMLElement
    const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement

    if (event.shiftKey) {
      // Shift + Tab: if focus is on first element, move to last
      if (document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      }
    } else {
      // Tab: if focus is on last element, move to first
      if (document.activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }
  }
}

// Watch for modal open/close to manage focus
watch(showBulkImportModal, async (isOpen) => {
  if (isOpen) {
    await nextTick()
    // Move focus to the textarea as the primary interaction element
    if (textareaRef.value) {
      textareaRef.value.focus()
    }
  }
})

const handleFileUpload = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target?.result as string

    // Check if file is OPML based on extension
    if (file.name.toLowerCase().endsWith('.opml')) {
      try {
        const urls = parseOpmlFile(content)
        if (urls.length === 0) {
          showNotification('No valid feed URLs found in OPML file', 'warning')
        } else {
          bulkImportText.value = urls.join('\n')
          showNotification(
            `Found ${urls.length} feed URL${urls.length !== 1 ? 's' : ''} in OPML file`,
            'success'
          )
        }
      } catch (error) {
        showNotification(
          error instanceof Error ? error.message : 'Failed to parse OPML file',
          'error'
        )
        // Clear the file input
        input.value = ''
      }
    } else {
      // Plain text file - use as-is
      bulkImportText.value = content
    }
  }
  reader.readAsText(file)
}

const bulkImportFeeds = async () => {
  const urls = extractValidUrls(bulkImportText.value)

  if (urls.length === 0) {
    showNotification(
      'No valid URLs found. Please enter URLs starting with http:// or https://',
      'warning'
    )
    return
  }

  // Client-side validation: match server limit
  const MAX_BULK_IMPORT_SIZE = 100
  if (urls.length > MAX_BULK_IMPORT_SIZE) {
    showNotification(
      `Too many URLs! Maximum ${MAX_BULK_IMPORT_SIZE} URLs per import. You have ${urls.length} URLs. Please split into multiple imports.`,
      'warning'
    )
    return
  }

  bulkImporting.value = true
  try {
    const res = await authFetch('/api/feeds/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls }),
    })

    if (res.ok) {
      const results = await res.json()
      bulkImportResults.value = results

      // Show success notification
      if (results.success > 0) {
        showNotification(
          `Successfully imported ${results.success} feed${results.success > 1 ? 's' : ''}!`,
          'success'
        )
        await fetchFeeds()
      }

      // Show warning if some failed
      if (results.failed > 0 && results.success === 0) {
        showNotification(
          `Failed to import ${results.failed} feed${results.failed > 1 ? 's' : ''}. See details below.`,
          'error'
        )
      }
    } else {
      const errorText = await res.text()
      let errorMessage = 'Failed to import feeds'
      try {
        const errorJson = JSON.parse(errorText)
        errorMessage = errorJson.description || errorJson.error || errorMessage
      } catch {
        errorMessage = errorText || errorMessage
      }
      bulkImportResults.value = {
        total: urls.length,
        success: 0,
        failed: urls.length,
        skipped: 0,
        errors: [{ url: 'Request failed', error: errorMessage }],
      }
      showNotification(errorMessage, 'error')
    }
  } catch (e) {
    console.error(e)
    const errorMessage = e instanceof Error ? e.message : 'Network error occurred'
    bulkImportResults.value = {
      total: urls.length,
      success: 0,
      failed: urls.length,
      skipped: 0,
      errors: [{ url: 'Network error', error: errorMessage }],
    }
    showNotification(`Error importing feeds: ${errorMessage}`, 'error')
  } finally {
    bulkImporting.value = false
  }
}
</script>

<template>
  <div class="column-container">
    <div class="column-header">
      <h2>
        Feeds ({{ contextuallyFilteredFeeds.length
        }}<span v-if="filterStore.contextualFeedUrls && contextuallyFilteredFeeds.length !== filteredFeeds.length">
          &nbsp;/ {{ filteredFeeds.length }}</span>)
      </h2>
      <div class="header-actions" v-if="isAdmin">
        <button 
          @click="toggleBulkDeleteMode" 
          :class="['action-btn', { active: bulkDeleteMode }]" 
          title="Bulk Delete Feeds"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
          </svg>
          {{ bulkDeleteMode ? 'Cancel' : 'Delete' }}
        </button>
        <button @click="openBulkImportModal" class="action-btn" title="Bulk Import Feeds">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" />
          </svg>
          Import
        </button>
        <button
          @click="triggerRefresh"
          :disabled="refreshing"
          class="action-btn"
          title="Refresh All Feeds"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="currentColor"
            :class="{ spinning: refreshing }"
          >
            <path
              d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6 1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"
            />
          </svg>
          {{ refreshing ? 'Refreshing' : 'Refresh' }}
        </button>
      </div>
    </div>

    <!-- Search Input -->
    <div class="search-container">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search feeds by title, URL, or category..."
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

    <div v-if="filterStore.contextualFeedUrls" class="context-filter-hint">
      Showing feeds from selected event
    </div>

    <!-- Bulk Delete Controls -->
    <div v-if="bulkDeleteMode" class="bulk-delete-controls">
      <div class="bulk-select-actions">
        <button @click="selectAllFeeds" class="bulk-action-btn">Select All</button>
        <button @click="selectNoneFeeds" class="bulk-action-btn">Select None</button>
        <span class="selection-count">{{ selectedFeedIds.size }} selected</span>
      </div>
      <button 
        @click="bulkDeleteFeeds" 
        :disabled="selectedFeedIds.size === 0"
        class="bulk-delete-btn"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
        </svg>
        Delete {{ selectedFeedIds.size }} Feed{{ selectedFeedIds.size !== 1 ? 's' : '' }}
      </button>
    </div>

    <div v-if="loading">Loading...</div>
    <div v-else-if="!contextuallyFilteredFeeds.length && searchQuery" class="no-results">
      No feeds match "{{ searchQuery }}"
    </div>
    <ul v-else-if="contextuallyFilteredFeeds.length" class="feed-list">
      <li
        v-for="feed in contextuallyFilteredFeeds"
        :key="feed._id"
        class="feed-item"
        @click="
          bulkDeleteMode 
            ? toggleFeedSelection(feed._id)
            : filterStore.setSelectedFeedId(filterStore.selectedFeedId === feed._id ? null : feed._id)
        "
        :class="{ 'selected-feed': filterStore.selectedFeedId === feed._id }"
      >
        <div v-if="renamingFeedId === feed._id && isAdmin" class="feed-info">
          <input v-model="newFeedTitle" @keyup.enter="renameFeed(feed)" @keyup.esc="cancelRename" />
          <div class="rename-actions">
            <button @click="renameFeed(feed)">Save</button>
            <button @click="cancelRename">Cancel</button>
          </div>
        </div>
        <div v-else class="feed-info">
          <div class="feed-name-container">
            <input
              v-if="bulkDeleteMode"
              type="checkbox"
              :checked="selectedFeedIds.has(feed._id)"
              @click.stop="toggleFeedSelection(feed._id)"
              @change.stop
              class="feed-checkbox"
              :title="`Select ${feed.title || getHostname(feed.url)}`"
            />
            <img
              v-if="feed.favicon_url"
              :src="feed.favicon_url"
              class="feed-favicon"
              :alt="`${feed.title || getHostname(feed.url)} icon`"
              @error="handleFaviconError"
            />
            <span v-else class="feed-favicon-placeholder" aria-label="No icon">📰</span>
            <button
              class="feed-name-btn"
              @click.stop="
                filterStore.setSelectedFeedId(
                  filterStore.selectedFeedId === feed._id ? null : feed._id
                )
              "
              :title="feed.url"
            >
              {{ feed.title || getHostname(feed.url) }}
            </button>
            <a
              :href="feed.url"
              target="_blank"
              class="feed-link-icon"
              :title="`Open ${feed.url}`"
              @click.stop
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <path
                  d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"
                />
              </svg>
            </a>
          </div>
          <span v-if="feed.category" class="category-tag">{{ feed.category }}</span>
        </div>
        <div class="feed-actions" @click.stop>
          <div
            v-if="feed.last_fetch_error"
            class="warning-icon"
            :title="`Fetch error: ${feed.last_fetch_error}`"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
            </svg>
          </div>
          <button @click="openFeedInNewTab(feed.url)" class="icon-btn" title="Open Feed">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"
              />
            </svg>
          </button>
          <button
            v-if="authStore.isAuthenticated"
            @click="openFeedChat(feed)"
            class="icon-btn"
            title="Chat about feed"
          >
            💬
          </button>
          <button v-if="isAdmin" @click="startRename(feed)" class="icon-btn" title="Rename Feed">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"
              />
            </svg>
          </button>
          <button
            v-if="isAdmin"
            @click="deleteFeed(feed._id)"
            class="icon-btn delete"
            title="Delete Feed"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
              />
            </svg>
          </button>
        </div>
      </li>
    </ul>
    <div v-else>No feeds found.</div>

    <!-- Bulk Import Modal -->
    <div v-if="showBulkImportModal" class="modal-overlay" @click="closeBulkImportModal">
      <div
        ref="modalContentRef"
        class="modal-content"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        @click.stop
        @keydown="handleModalKeydown"
      >
        <div class="modal-header">
          <h3 id="modal-title">Bulk Import Feeds</h3>
          <button @click="closeBulkImportModal" class="modal-close" aria-label="Close">×</button>
        </div>

        <div v-if="!bulkImportResults" class="modal-body">
          <p>Paste feed URLs below (one per line) or upload a text file:</p>
          <p class="import-limit-notice">⚠️ Maximum 50 URLs per import (security limit)</p>

          <div class="file-upload-section">
            <input ref="fileInputRef" type="file" accept=".txt,.opml" @change="handleFileUpload" />
          </div>

          <textarea
            ref="textareaRef"
            v-model="bulkImportText"
            placeholder="https://example.com/feed.xml&#10;https://another.com/rss&#10;..."
            rows="10"
            class="bulk-import-textarea"
          ></textarea>

          <div v-if="bulkImportText.trim()" class="url-preview">
            <span v-if="urlCount > 0" class="url-count-valid">
              {{ urlCount }} valid URL{{ urlCount !== 1 ? 's' : '' }} found
            </span>
            <span v-else class="url-count-invalid"> No valid URLs found </span>
          </div>

          <div class="modal-actions">
            <button
              @click="bulkImportFeeds"
              :disabled="bulkImporting || !canImport"
              class="import-btn"
            >
              {{ bulkImporting ? 'Importing...' : 'Import Feeds' }}
            </button>
            <button @click="closeBulkImportModal" class="cancel-btn">Cancel</button>
          </div>
        </div>

        <div v-else class="modal-body">
          <h4>Import Results</h4>
          <div class="import-results">
            <p><strong>Total URLs:</strong> {{ bulkImportResults.total }}</p>
            <p class="success-text">
              <strong>Successfully imported:</strong> {{ bulkImportResults.success }}
            </p>
            <p v-if="bulkImportResults.skipped > 0" class="warning-text">
              <strong>Skipped (already exist):</strong> {{ bulkImportResults.skipped }}
            </p>
            <p v-if="bulkImportResults.failed > 0" class="error-text">
              <strong>Failed:</strong> {{ bulkImportResults.failed }}
            </p>

            <div
              v-if="bulkImportResults.errors && bulkImportResults.errors.length > 0"
              class="error-details"
            >
              <h5>Errors:</h5>
              <ul>
                <li v-for="(err, idx) in bulkImportResults.errors" :key="idx">
                  <strong>{{ err.url }}</strong
                  >: {{ err.error }}
                </li>
              </ul>
            </div>
          </div>

          <div class="modal-actions">
            <button @click="closeBulkImportModal" class="close-btn">Close</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast Notification -->
    <div v-if="notification" :class="['notification-toast', `notification-${notification.type}`]">
      {{ notification.message }}
    </div>
  </div>
</template>

<style scoped>
.column-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

h2 {
  margin: 0;
  color: #42b983;
}

.feed-list {
  list-style-type: none;
  padding: 0;
  overflow-y: auto;
  flex: 1;
}

.no-results {
  padding: 12px;
  color: var(--text-color);
  opacity: 0.8;
  font-style: italic;
}

.feed-item {
  margin: 10px 0;
  padding: 8px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition:
    background-color 0.2s,
    border-left 0.2s;
  border-left: 3px solid transparent;
}

.feed-item:hover {
  background-color: #3a3a3a;
}

.feed-item.selected-feed {
  background-color: #2d5a8f;
  border-left: 3px solid #4a7eb7;
}

.feed-item.selected-feed:hover {
  background-color: #3a6ba5;
}

.feed-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
}
.feed-name-container {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.feed-name-btn {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #42b983;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  padding: 0;
  font-size: inherit;
  font-family: inherit;
}
.feed-name-btn:hover {
  text-decoration: underline;
}

.feed-link-icon {
  color: #888;
  display: inline-flex;
  align-items: center;
  opacity: 0;
  transition: opacity 0.2s;
  text-decoration: none;
}

.feed-name-container:hover .feed-link-icon {
  opacity: 1;
}

.feed-link-icon:hover {
  color: #007bff;
}

.feed-favicon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  object-fit: contain;
}
.feed-favicon-placeholder {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  font-size: 14px;
  line-height: 16px;
  text-align: center;
}
.feed-link {
  color: #42b983;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.feed-link:hover {
  text-decoration: underline;
}
.category-tag {
  font-size: 0.75rem;
  background: var(--button-bg);
  color: var(--primary-color);
  border: 1px solid var(--border-color);
  padding: 2px 6px;
  border-radius: 4px;
  align-self: flex-start;
}
.feed-actions {
  display: flex;
  gap: 5px;
  align-items: center;
}
.icon-btn {
  background: transparent;
  border: none;
  color: var(--text-color);
  opacity: 0.7;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.icon-btn:hover {
  background: var(--button-bg);
  opacity: 1;
  color: var(--primary-color);
}
.icon-btn.delete:hover {
  color: #cc0000;
  background: rgba(204, 0, 0, 0.1);
}
.warning-icon {
  color: #ff9800;
  cursor: help;
  display: flex;
  align-items: center;
  padding: 4px;
}

.rename-actions {
  display: flex;
  gap: 5px;
  margin-top: 5px;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--bg-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  overflow: auto;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}
.modal-header h3 {
  margin: 0;
  color: #42b983;
}
.modal-close {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: var(--text-color);
  opacity: 0.5;
}
.modal-close:hover {
  opacity: 1;
}
.modal-body {
  padding: 20px;
}
.import-limit-notice {
  color: #ff9800;
  font-size: 0.9rem;
  margin: 5px 0 15px 0;
  padding: 8px;
  background: rgba(255, 152, 0, 0.1);
  border-left: 3px solid #ff9800;
  border-radius: 4px;
}
.file-upload-section {
  margin-bottom: 15px;
}
.bulk-import-textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--input-bg);
  color: var(--input-text);
  font-family: monospace;
  font-size: 0.9rem;
  resize: vertical;
  box-sizing: border-box;
}
.url-preview {
  margin-top: 10px;
  padding: 8px;
  border-radius: 4px;
  font-size: 0.9rem;
  font-weight: 500;
}
.url-count-valid {
  color: #42b983;
}
.url-count-invalid {
  color: #ff9800;
}
.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}
.import-btn,
.cancel-btn,
.close-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}
.import-btn {
  background: #42b983;
  color: white;
}
.import-btn:hover:not(:disabled) {
  background: #359268;
}
.import-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}
.cancel-btn {
  background: var(--button-bg);
  color: var(--text-color);
  border: 1px solid var(--border-color);
}
.cancel-btn:hover {
  background: var(--bg-color);
}
.close-btn {
  background: #42b983;
  color: white;
}
.close-btn:hover {
  background: #359268;
}
.import-results {
  background: var(--button-bg);
  padding: 15px;
  border-radius: 4px;
  margin-top: 15px;
}
.import-results p {
  margin: 5px 0;
}
.success-text {
  color: #42b983;
}
.warning-text {
  color: #ff9800;
}
.error-text {
  color: #cc0000;
}
.error-details {
  margin-top: 15px;
  padding: 10px;
  background: var(--bg-color);
  border-left: 3px solid #cc0000;
}
.error-details h5 {
  margin-top: 0;
  color: #cc0000;
}
.error-details ul {
  margin: 10px 0;
  padding-left: 20px;
}
.error-details li {
  margin: 5px 0;
  font-size: 0.9rem;
}

/* Notification Toast */
.notification-toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 15px 20px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-size: 0.95rem;
  font-weight: 500;
  z-index: 2000;
  animation: slideIn 0.3s ease-out;
  max-width: 400px;
}
@keyframes slideIn {
  from {
    transform: translateX(400px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
.notification-success {
  background: #d4edda;
  color: #155724;
  border-left: 4px solid #28a745;
}
.notification-error {
  background: #f8d7da;
  color: #721c24;
  border-left: 4px solid #dc3545;
}
.notification-warning {
  background: #fff3cd;
  color: #856404;
  border-left: 4px solid #ffc107;
}

.context-filter-hint {
  font-size: 0.75rem;
  opacity: 0.65;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border-color);
  font-style: italic;
}

/* Bulk Delete Styles */
.action-btn.active {
  background-color: #dc3545;
  border-color: #dc3545;
}

.action-btn.active:hover {
  background-color: #c82333;
  border-color: #bd2130;
}

.bulk-delete-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  background-color: rgba(220, 53, 69, 0.1);
  border: 1px solid #dc3545;
  border-radius: 4px;
  margin-bottom: 8px;
  gap: 8px;
}

.bulk-select-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.bulk-action-btn {
  padding: 4px 12px;
  background-color: #2c3e50;
  color: #fff;
  border: 1px solid #42b983;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background-color 0.2s;
}

.bulk-action-btn:hover {
  background-color: #34495e;
}

.selection-count {
  font-size: 0.85rem;
  color: var(--text-color);
  font-weight: bold;
}

.bulk-delete-btn {
  padding: 6px 16px;
  background-color: #dc3545;
  color: #fff;
  border: 1px solid #dc3545;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: background-color 0.2s;
  white-space: nowrap;
}

.bulk-delete-btn:hover:not(:disabled) {
  background-color: #c82333;
}

.bulk-delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.feed-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
  flex-shrink: 0;
}

.feed-item.selected-feed .feed-checkbox {
  /* Ensure checkbox is visible on selected items */
  filter: brightness(1.2);
}
</style>
