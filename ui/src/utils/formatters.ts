/**
 * Shared formatting utilities for UI components
 */

/**
 * Formats an ISO date string into a local-aware readable string.
 */
export function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  try {
    return new Date(dateStr).toLocaleString()
  } catch (e) {
    return dateStr
  }
}

/**
 * Strips HTML tags from a string and returns plain text.
 */
export function stripHtml(html: string): string {
  if (!html) return ''
  const doc = new DOMParser().parseFromString(html, 'text/html')
  return doc.body.textContent || ''
}

/**
 * Extracts the hostname from a URL string.
 */
export function getHostname(urlStr: string): string {
  if (!urlStr) return ''
  try {
    return new URL(urlStr).hostname
  } catch (e) {
    return urlStr
  }
}

/**
 * Validates if a string is a valid HTTP/HTTPS URL.
 */
export function isValidUrl(urlString: string): boolean {
  try {
    const url = new URL(urlString)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

/**
 * Formats a duration in milliseconds into a short human-readable string.
 * Returns '—' for null/undefined.
 */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms}ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.round(seconds % 60)
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return `${hours}h ${remainingMinutes}m`
}
