import { test, expect, type Page, type Route } from '@playwright/test'

// Feeds column section dropdown (#266): a section change sends only the
// category, and a failed save puts the stored value back in the dropdown.

const feed = {
  _id: 'feed-1',
  url: 'https://example.com/rss',
  title: 'Arts &amp; Culture',
  category: 'general',
}

const mockDashboard = async (page: Page, onPut: (route: Route) => Promise<void>) => {
  await page.addInitScript(() => window.localStorage.setItem('token', 'test-token'))
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    if (url.pathname === '/api/auth/me') {
      return route.fulfill({
        json: { id: 'u1', email: 'admin@localhost.local', role: 'admin' },
      })
    }
    if (url.pathname === '/api/feeds/feed-1' && method === 'PUT') return onPut(route)
    if (url.pathname === '/api/feeds') return route.fulfill({ json: [feed] })
    return route.fulfill({ json: [] })
  })
}

test('changing a feed section sends only the category', async ({ page }) => {
  let body: Record<string, unknown> | null = null
  await mockDashboard(page, async (route) => {
    body = route.request().postDataJSON()
    await route.fulfill({ json: { ...feed, category: 'culture' } })
  })

  await page.goto('/#/dashboard')
  const select = page.locator('.section-select').first()
  await expect(select).toHaveValue('general')

  await select.selectOption('culture')

  await expect.poll(() => body).toEqual({ category: 'culture' })
  await expect(select).toHaveValue('culture')
})

test('a failed section save reverts the dropdown', async ({ page }) => {
  await mockDashboard(page, (route) => route.fulfill({ status: 500, json: {} }))

  await page.goto('/#/dashboard')
  const select = page.locator('.section-select').first()
  await expect(select).toHaveValue('general')

  await select.selectOption('sports')

  await expect(page.getByText('Failed to update feed section')).toBeVisible()
  await expect(select).toHaveValue('general')
})
