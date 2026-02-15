import { test, expect } from '@playwright/test'

test.describe('Settings Page Version Display', () => {
  test('version information should load and display correctly', async ({ page }) => {
    // Navigate to settings page
    await page.goto('/#/settings')

    // Wait for the About Moirai section to be visible
    await expect(page.getByRole('heading', { name: 'About Moirai' })).toBeVisible({
      timeout: 10000,
    })

    // Check that version is displayed and not showing "Loading..."
    const versionText = page.locator('text=/Version:/')
    await expect(versionText).toBeVisible({ timeout: 10000 })

    // Get the full text of the version element
    const versionContent = await versionText.textContent()

    // Verify version is not "Loading..." anymore
    expect(versionContent).not.toContain('Loading...')

    // Verify it contains "Moirai v" which is the expected format
    expect(versionContent).toContain('Moirai v')

    // Optional: verify it has the version number pattern (e.g., "0.3.0")
    expect(versionContent).toMatch(/Moirai v\d+\.\d+\.\d+/)
  })
})
