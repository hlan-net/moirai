import { test, expect } from '@playwright/test'

test.use({
  httpCredentials: {
    username: process.env.ADMIN_USERNAME || 'testuser',
    password: process.env.ADMIN_PASSWORD || 'testpassword',
  },
})

test.describe('Settings Model Catalog', () => {
  test('admin sees the model catalog editor with every purpose', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.goto('/#/settings')

    await page.getByRole('button', { name: 'System Settings' }).click()
    const section = page.getByTestId('model-catalog')
    await expect(section.getByRole('heading', { name: 'Model Catalog' })).toBeVisible()
    await expect(section.locator('.badge')).toBeVisible()

    for (const purpose of ['annotation', 'chat', 'event_synthesis', 'social_export']) {
      await expect(section.getByLabel(`Add a model to ${purpose}`)).toBeVisible()
    }
    // Nothing is edited yet, so there is nothing to save.
    await expect(section.getByRole('button', { name: 'Save catalog' })).toBeDisabled()
  })
})
