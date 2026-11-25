import { test, expect, type Page } from '@playwright/test'

// The UI is the Stream page, Login and Settings (#375): the navigation offers
// nothing else, and the paths of the removed views lead to the stream.

const emptyStream = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Moirai Aggregated Stream</title><link>http://localhost</link><description>x</description></channel></rss>`

const mockApi = async (page: Page, { loggedIn }: { loggedIn: boolean }) => {
  if (loggedIn) {
    await page.addInitScript(() => window.localStorage.setItem('token', 'test-token'))
  }
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/stream.rss') {
      return route.fulfill({ status: 200, contentType: 'application/rss+xml', body: emptyStream })
    }
    if (url.pathname === '/api/auth/me') {
      return loggedIn
        ? route.fulfill({ json: { id: 'u1', email: 'admin@localhost.local', role: 'admin' } })
        : route.fulfill({ status: 401, json: { message: 'Unauthorized' } })
    }
    return route.fulfill({ json: [] })
  })
}

const navLinks = (page: Page) => page.locator('.main-nav .links .nav-link')

test('a logged-in user sees Stream, Settings and Logout only', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Aggregated Stream' })).toBeVisible()
  await expect(navLinks(page)).toHaveText(['Stream', 'Settings', 'Logout'])
})

test('a visitor sees Stream and Login only', async ({ page }) => {
  await mockApi(page, { loggedIn: false })
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Aggregated Stream' })).toBeVisible()
  await expect(navLinks(page)).toHaveText(['Stream', 'Login'])
})

for (const path of [
  'dashboard',
  'lifespan',
  'chat',
  'agents',
  'sessions',
  'sessions/abc123',
  'mythology',
  'no-such-page',
]) {
  test(`/${path} leads to the stream`, async ({ page }) => {
    await mockApi(page, { loggedIn: true })
    await page.goto(`/#/${path}`)

    await expect(page.getByRole('heading', { name: 'Aggregated Stream' })).toBeVisible()
    await expect(page).toHaveURL(/#\/$/)
  })
}

test('feeds are managed in Settings', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.route('**/api/feeds', (route) =>
    route.fulfill({
      json: [{ _id: 'f1', url: 'https://example.com/rss', title: 'Example', category: 'sports' }],
    })
  )
  await page.goto('/#/settings')
  await page.getByRole('button', { name: 'Feeds', exact: true }).click()

  await expect(page.getByRole('heading', { name: 'Feeds (1)' })).toBeVisible()
  await expect(page.getByText('Example', { exact: true })).toBeVisible()
  await expect(page.locator('.section-select')).toHaveValue('sports')
  await expect(page.locator('button[title="Bulk Import Feeds"]')).toBeVisible()
})
