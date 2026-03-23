/**
 * Polling configuration for dashboard components.
 * 
 * All dashboard columns should use these synchronized intervals
 * to prevent erratic update behavior.
 */

/**
 * Synchronized refresh interval for all dashboard columns.
 * Backend fetches new data every 30 seconds.
 */
export const SYNC_REFRESH_INTERVAL = 30000 // 30 seconds

/**
 * Fast refresh interval for critical updates (future use).
 */
export const FAST_REFRESH_INTERVAL = 10000 // 10 seconds

/**
 * Time format update interval for "X seconds ago" displays.
 */
export const TIME_DISPLAY_UPDATE_INTERVAL = 10000 // 10 seconds
