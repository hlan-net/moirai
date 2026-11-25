/**
 * Shared formatting utilities for UI components
 */

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
