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

    // The version might take a moment to load via API
    const versionText = page.locator('p:has-text("Version:")')
    
    // Wait for "Loading..." to disappear and be replaced by actual version
    await expect(versionText).not.toContainText('Loading...', { timeout: 10000 })
    
    // Get the full text of the version element
    const versionContent = await versionText.textContent() || ""

    // Verify it contains "Moirai v" which is the expected format
    expect(versionContent).toContain('Moirai v')

    // Optional: verify it has the version number pattern (e.g., "0.3.1")
    expect(versionContent).toMatch(/Moirai v\d+\.\d+\.\d+/)
  })
})
