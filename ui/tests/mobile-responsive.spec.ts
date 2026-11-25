import { test, expect } from '@playwright/test'

test.describe('Mobile responsive layout', () => {
  test('navigation should be mobile-friendly', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/')

    // Check navigation links are visible
    await expect(page.getByRole('link', { name: 'Stream' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()

    // Verify navigation links are stacked vertically on mobile
    const nav = page.locator('.main-nav')
    const flexDirection = await nav.evaluate((el) => {
      return window.getComputedStyle(el).flexDirection
    })
    expect(flexDirection).toBe('column')
  })
})
