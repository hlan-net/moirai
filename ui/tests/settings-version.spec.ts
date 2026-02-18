import { test, expect } from '@playwright/test'

test.use({
  httpCredentials: {
    username: process.env.API_USERNAME || 'testuser',
    password: process.env.API_PASSWORD || 'testpassword',
  },
})

test.describe('Settings Page Version Display', () => {
  test('version information should load and display correctly', async ({ page }) => {
    // Navigate to root to ensure we are logged in (via httpCredentials)
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Navigate to settings page
    await page.goto('/#/settings')

    // Wait for the About Moirai section to be visible
    await expect(page.getByRole('heading', { name: 'About Moirai' })).toBeVisible()

    const aboutSection = page.getByRole('heading', { name: 'About Moirai' }).locator('..')

    const uiRow = aboutSection.getByText('UI', { exact: true }).locator('..')
    await expect(uiRow).toBeVisible()
    await expect(uiRow.locator('.version-value')).toContainText('Moirai UI v')

    const apiRow = aboutSection.getByText('API', { exact: true }).locator('..')
    await expect(apiRow).toBeVisible()
    await expect(apiRow.locator('.version-value')).toContainText('Moirai v')
  })
})
