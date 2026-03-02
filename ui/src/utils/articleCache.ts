/**
 * IndexedDB cache for articles
 * Provides instant page loads by caching articles locally
 */

const DB_NAME = 'moirai-cache'
const STORE_NAME = 'articles'
const DB_VERSION = 1
const CACHE_MAX_AGE_DAYS = 1

export interface Article {
  _id: string
  title: string
  summary: string
  link: string
  published: string
  feed_url: string
  issues?: {
    id: string
    logos: string
    longevity: string
    status: string
  }[]
  events?: string[]
  trends?: string[]
  annotations?: {
    topics: string[]
    priority: 'low' | 'medium' | 'high'
    sentiment: 'positive' | 'neutral' | 'negative'
  }
  feed_title?: string
  feed_favicon?: string
  cached_at?: string
}

class ArticleCache {
  private db: IDBDatabase | null = null

  /**
   * Initialize the IndexedDB database
   */
  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION)

      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        this.db = request.result
        resolve()
      }

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        
        // Create object store if it doesn't exist
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: '_id' })
          store.createIndex('published', 'published', { unique: false })
          store.createIndex('cached_at', 'cached_at', { unique: false })
        }
      }
    })
  }

  /**
   * Save articles to cache
   */
  async saveArticles(articles: Article[]): Promise<void> {
    if (!this.db) await this.init()
    if (!this.db) throw new Error('Database not initialized')

    const transaction = this.db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const now = new Date().toISOString()

    for (const article of articles) {
      const cachedArticle = { ...article, cached_at: now }
      store.put(cachedArticle)
    }

    return new Promise((resolve, reject) => {
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
    })
  }

  /**
   * Get all cached articles sorted by published date (newest first)
   */
  async getArticles(limit?: number): Promise<Article[]> {
    if (!this.db) await this.init()
    if (!this.db) throw new Error('Database not initialized')

    const transaction = this.db.transaction([STORE_NAME], 'readonly')
    const store = transaction.objectStore(STORE_NAME)

    return new Promise((resolve, reject) => {
      const request = store.getAll()
      
      request.onsuccess = () => {
        const articles = request.result as Article[]
        // Sort by published date descending
        articles.sort((a, b) => {
          return new Date(b.published).getTime() - new Date(a.published).getTime()
        })
        
        resolve(limit ? articles.slice(0, limit) : articles)
      }
      
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Get the timestamp of the newest cached article
   */
  async getNewestTimestamp(): Promise<string | null> {
    const articles = await this.getArticles(1)
    return articles[0]?.published ?? null
  }

  /**
   * Clear articles older than CACHE_MAX_AGE_DAYS
   */
  async clearOldArticles(): Promise<number> {
    if (!this.db) await this.init()
    if (!this.db) throw new Error('Database not initialized')

    const cutoffDate = new Date()
    cutoffDate.setDate(cutoffDate.getDate() - CACHE_MAX_AGE_DAYS)
    const cutoffISO = cutoffDate.toISOString()

    const transaction = this.db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const index = store.index('cached_at')
    
    let deletedCount = 0

    return new Promise((resolve, reject) => {
      const request = index.openCursor()
      
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest).result
        if (cursor) {
          const article = cursor.value as Article
          if (article.cached_at && article.cached_at < cutoffISO) {
            cursor.delete()
            deletedCount++
          }
          cursor.continue()
        }
      }
      
      transaction.oncomplete = () => resolve(deletedCount)
      transaction.onerror = () => reject(transaction.error)
    })
  }

  /**
   * Clear all cached articles
   */
  async clearAll(): Promise<void> {
    if (!this.db) await this.init()
    if (!this.db) throw new Error('Database not initialized')

    const transaction = this.db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    
    return new Promise((resolve, reject) => {
      const request = store.clear()
      request.onsuccess = () => resolve()
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Get cache statistics
   */
  async getStats(): Promise<{ count: number; oldestDate: string | null; newestDate: string | null }> {
    const articles = await this.getArticles()
    const newestArticle = articles[0]
    const oldestArticle = articles.length > 0 ? articles[articles.length - 1] : undefined
    
    return {
      count: articles.length,
      newestDate: newestArticle?.published ?? null,
      oldestDate: oldestArticle?.published ?? null
    }
  }
}

// Export singleton instance
export const articleCache = new ArticleCache()
