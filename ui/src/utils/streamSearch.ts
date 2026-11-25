// Stream search (#377): the query lives in the page's `q` parameter, like the
// section choice (#344) and the open subject (#376).

export const SEARCH_LIMIT = 200
export const SEARCH_MAX_LENGTH = 200

/** The search text of the `q` query parameter, or '' when there is none. */
export const parseSearchQuery = (value: unknown): string =>
  typeof value === 'string' ? value.trim().slice(0, SEARCH_MAX_LENGTH) : ''

/** The request that answers a search with the items of the stream. */
export const searchUrl = (query: string): string =>
  `/api/articles/search?format=rss&limit=${SEARCH_LIMIT}&q=${encodeURIComponent(query)}`
