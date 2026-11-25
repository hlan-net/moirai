import { test, expect } from '@playwright/test'

test('has title', async ({ page }) => {
  await page.goto('/')

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Moirai/)
})

test('feeds load in Settings', async ({ page }) => {
  await page.goto('/#/settings')
  await page.getByRole('button', { name: 'Feeds', exact: true }).click()

  // Check if the Feeds header exists (with count)
  await expect(page.getByRole('heading', { name: /Feeds \(\d+\)/ })).toBeVisible()
})
