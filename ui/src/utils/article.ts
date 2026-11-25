// An article as the Stream page shows it, parsed from /api/stream.rss.

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
  /** Stream section (#266): main | sports | culture | business */
  section?: string
  cached_at?: string
}
