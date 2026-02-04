<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'

interface Feed {
  _id: string;
  url: string;
  title?: string;
  category?: string;
  favicon_url?: string;
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

// URL validation function
const isValidUrl = (urlString: string): boolean => {
  try {
    const url = new URL(urlString)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

// Extract and validate URLs from text
const extractValidUrls = (text: string): string[] => {
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && isValidUrl(line))
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

const showNotification = (message: string, type: 'error' | 'success' | 'warning') => {
  notification.value = { message, type }
  setTimeout(() => {
    notification.value = null
  }, 5000) // Auto-dismiss after 5 seconds
}

const fetchFeeds = async () => {
  try {
    const response = await fetch('/api/feeds')
    if (response.ok) {
        feeds.value = await response.json()
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
        const res = await fetch('/api/feeds/refresh', { method: 'POST' })
        if (res.ok) {
            const data = await res.json()
            alert(`Started refreshing ${data.count} feeds.`)
        } else {
            alert("Failed to trigger refresh.")
        }
    } catch (e) {
        console.error(e)
        alert("Error triggering refresh.")
    } finally {
        refreshing.value = false
    }
}

const deleteFeed = async (id: string) => {
  if (!confirm("Are you sure you want to delete this feed?")) return;
  
  try {
    const res = await fetch(`/api/feeds/${id}`, { method: 'DELETE' })
    if (res.ok) {
      feeds.value = feeds.value.filter(f => f._id !== id)
    } else {
      alert("Failed to delete feed")
    }
  } catch (e) {
    console.error(e)
    alert("Error deleting feed")
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
    const res = await fetch(`/api/feeds/${feed._id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newFeedTitle.value })
    })
    if (res.ok) {
      const updatedFeed = await res.json()
      const index = feeds.value.findIndex(f => f._id === updatedFeed._id)
      if (index !== -1) {
        feeds.value[index] = updatedFeed
      }
      cancelRename()
    } else {
      alert("Failed to rename feed")
    }
  } catch (e) {
    console.error(e)
    alert("Error renaming feed")
  }
}

onMounted(() => {
  fetchFeeds()
})

function getHostname(urlStr: string) {
  try {
    return new URL(urlStr).hostname
  } catch (e) {
    return urlStr
  }
}

const openFeedInNewTab = (url: string) => {
  window.open(url, '_blank')
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
  showBulkImportModal.value = true
  bulkImportText.value = ''
  bulkImportResults.value = null

  if (!bulkImportKeydownListenerAttached) {
    window.addEventListener('keydown', handleBulkImportKeydown)
    bulkImportKeydownListenerAttached = true
  }
}

const closeBulkImportModal = () => {
  showBulkImportModal.value = false
  bulkImportText.value = ''
  bulkImportResults.value = null

  if (bulkImportKeydownListenerAttached) {
    window.removeEventListener('keydown', handleBulkImportKeydown)
    bulkImportKeydownListenerAttached = false
  }
}

const handleFileUpload = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  
  const reader = new FileReader()
  reader.onload = (e) => {
    bulkImportText.value = e.target?.result as string
  }
  reader.readAsText(file)
}

const bulkImportFeeds = async () => {
  const urls = extractValidUrls(bulkImportText.value)
  
  if (urls.length === 0) {
    showNotification('No valid URLs found. Please enter URLs starting with http:// or https://', 'warning')
    return
  }
  
  // Client-side validation: match server limit
  const MAX_BULK_IMPORT_SIZE = 100
  if (urls.length > MAX_BULK_IMPORT_SIZE) {
    showNotification(`Too many URLs! Maximum ${MAX_BULK_IMPORT_SIZE} URLs per import. You have ${urls.length} URLs. Please split into multiple imports.`, 'warning')
    return
  }
  
  bulkImporting.value = true
  try {
    const res = await fetch('/api/feeds/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls })
    })
    
    if (res.ok) {
      const results = await res.json()
      bulkImportResults.value = results
      
      // Show success notification
      if (results.success > 0) {
        showNotification(`Successfully imported ${results.success} feed${results.success > 1 ? 's' : ''}!`, 'success')
        await fetchFeeds()
      }
      
      // Show warning if some failed
      if (results.failed > 0 && results.success === 0) {
        showNotification(`Failed to import ${results.failed} feed${results.failed > 1 ? 's' : ''}. See details below.`, 'error')
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
        errors: [{ url: 'Request failed', error: errorMessage }]
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
      errors: [{ url: 'Network error', error: errorMessage }]
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
        <h2>Feeds ({{ feeds.length }})</h2>
        <div class="header-actions">
          <button @click="openBulkImportModal" class="bulk-import-btn" title="Bulk Import Feeds">📥</button>
          <button @click="triggerRefresh" :disabled="refreshing" class="refresh-btn" title="Refresh All Feeds">
              {{ refreshing ? '...' : '↻' }}
          </button>
        </div>
    </div>

    <div v-if="loading">Loading...</div>
    <ul v-else-if="feeds.length" class="feed-list">
      <li v-for="feed in feeds" :key="feed._id" class="feed-item">
        <div v-if="renamingFeedId === feed._id" class="feed-info">
          <input v-model="newFeedTitle" @keyup.enter="renameFeed(feed)" @keyup.esc="cancelRename" />
          <div class="rename-actions">
            <button @click="renameFeed(feed)">Save</button>
            <button @click="cancelRename">Cancel</button>
          </div>
        </div>
        <div v-else class="feed-info">
          <div class="feed-name-container">
            <img v-if="feed.favicon_url" :src="feed.favicon_url" class="feed-favicon" :alt="`${feed.title || getHostname(feed.url)} icon`" @error="handleFaviconError" />
            <span v-else class="feed-favicon-placeholder" role="img" :aria-label="`${feed.title || getHostname(feed.url)} icon`">📰</span>
            <a :href="feed.url" target="_blank" class="feed-link" :title="feed.url">{{ feed.title || getHostname(feed.url) }}</a>
          </div>
          <span v-if="feed.category" class="category-tag">{{ feed.category }}</span>
        </div>
        <div class="feed-actions">
          <button @click="openFeedInNewTab(feed.url)" class="open-link-btn" title="Open Feed">🔗</button>
          <button @click="startRename(feed)" class="rename-btn" title="Rename Feed">✏️</button>
          <button @click="deleteFeed(feed._id)" class="delete-btn" title="Delete Feed">×</button>
        </div>
      </li>
    </ul>
    <div v-else>No feeds found.</div>
    
    <!-- Bulk Import Modal -->
    <div v-if="showBulkImportModal" class="modal-overlay" @click="closeBulkImportModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Bulk Import Feeds</h3>
          <button @click="closeBulkImportModal" class="modal-close">×</button>
        </div>
        
        <div v-if="!bulkImportResults" class="modal-body">
          <p>Paste feed URLs below (one per line) or upload a text file:</p>
          <p class="import-limit-notice">⚠️ Maximum 50 URLs per import (security limit)</p>
          
          <div class="file-upload-section">
            <input type="file" accept=".txt,.opml" @change="handleFileUpload" />
          </div>
          
          <textarea 
            v-model="bulkImportText" 
            placeholder="https://example.com/feed.xml&#10;https://another.com/rss&#10;..."
            rows="10"
            class="bulk-import-textarea"
          ></textarea>
          
          <div v-if="bulkImportText.trim()" class="url-preview">
            <span v-if="urlCount > 0" class="url-count-valid">
              {{ urlCount }} valid URL{{ urlCount !== 1 ? 's' : '' }} found
            </span>
            <span v-else class="url-count-invalid">
              No valid URLs found
            </span>
          </div>
          
          <div class="modal-actions">
            <button @click="bulkImportFeeds" :disabled="bulkImporting || !canImport" class="import-btn">
              {{ bulkImporting ? 'Importing...' : 'Import Feeds' }}
            </button>
            <button @click="closeBulkImportModal" class="cancel-btn">Cancel</button>
          </div>
        </div>
        
        <div v-else class="modal-body">
          <h4>Import Results</h4>
          <div class="import-results">
            <p><strong>Total URLs:</strong> {{ bulkImportResults.total }}</p>
            <p class="success-text"><strong>Successfully imported:</strong> {{ bulkImportResults.success }}</p>
            <p v-if="bulkImportResults.skipped > 0" class="warning-text"><strong>Skipped (already exist):</strong> {{ bulkImportResults.skipped }}</p>
            <p v-if="bulkImportResults.failed > 0" class="error-text"><strong>Failed:</strong> {{ bulkImportResults.failed }}</p>
            
            <div v-if="bulkImportResults.errors && bulkImportResults.errors.length > 0" class="error-details">
              <h5>Errors:</h5>
              <ul>
                <li v-for="(err, idx) in bulkImportResults.errors" :key="idx">
                  <strong>{{ err.url }}</strong>: {{ err.error }}
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
  height: 100%;
  display: flex;
  flex-direction: column;
}
.column-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #eee;
    padding-bottom: 10px;
    margin-bottom: 10px;
    margin-top: 0;
}
h2 {
  margin: 0;
  color: #42b983;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.bulk-import-btn, .refresh-btn {
    background: none;
    border: 1px solid #ccc;
    padding: 2px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1.2rem;
    color: var(--text-color);
}
.bulk-import-btn:hover, .refresh-btn:hover:not(:disabled) {
    background: var(--button-bg);
    color: var(--primary-color);
    border-color: var(--primary-color);
}
.refresh-btn:disabled {
    opacity: 0.5;
    cursor: wait;
}
.feed-list {
  list-style-type: none;
  padding: 0;
  overflow-y: auto;
  flex: 1;
}
.feed-item {
  margin: 10px 0;
  padding: 8px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
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
  background: #eef;
  color: #669;
  padding: 2px 6px;
  border-radius: 4px;
  align-self: flex-start;
}
.feed-actions {
  display: flex;
  gap: 5px;
}
.open-link-btn, .rename-btn, .delete-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0 5px;
}
.open-link-btn {
  color: #999;
}
.open-link-btn:hover {
  color: #000;
}
.rename-btn {
  color: #999;
}
.rename-btn:hover {
  color: #000;
}
.delete-btn {
  color: #cc0000;
}
.delete-btn:hover {
  color: #ff0000;
  font-weight: bold;
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
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  overflow: auto;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
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
  color: #999;
}
.modal-close:hover {
  color: #000;
}
.modal-body {
  padding: 20px;
}
.import-limit-notice {
  color: #ff9800;
  font-size: 0.9rem;
  margin: 5px 0 15px 0;
  padding: 8px;
  background: #fff3e0;
  border-left: 3px solid #ff9800;
  border-radius: 4px;
}
.file-upload-section {
  margin-bottom: 15px;
}
.bulk-import-textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
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
.import-btn, .cancel-btn, .close-btn {
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
  background: #f5f5f5;
  color: #333;
}
.cancel-btn:hover {
  background: #e0e0e0;
}
.close-btn {
  background: #42b983;
  color: white;
}
.close-btn:hover {
  background: #359268;
}
.import-results {
  background: #f9f9f9;
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
  background: #fff;
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
</style>