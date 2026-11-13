import { test, expect, type Page } from '@playwright/test'

// Stream sections (#266): the page opens on Top stories; each tab loads its
// own section of the RSS stream; an article appears in exactly one tab.

const item = (title: string, slug: string, section: string) => `
    <item>
      <title>${title}</title>
      <link>https://example.com/${slug}</link>
      <description>${title} summary</description>
      <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
      <guid isPermaLink="true">https://example.com/${slug}</guid>
      <category domain="section">${section}</category>
      <source><title>Example Feed</title></source>
    </item>`

const channel = (items: string) => `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Moirai Aggregated Stream</title>
    <link>http://localhost</link>
    <description>Aggregated stream</description>${items}
  </channel>
</rss>`

const bySection: Record<string, string> = {
  main: channel(item('Parliament Vote', 'politics/vote', 'main')),
  sports: channel(item('Derby Result', 'urheilu/derby', 'sports')),
  culture: channel(item('Opera Premiere', 'kulttuuri/opera', 'culture')),
  business: channel(''),
}

const mockStream = async (page: Page, requested: string[]) => {
  await page.route('**/api/stream.rss*', async (route) => {
    const section = new URL(route.request().url()).searchParams.get('section') ?? ''
    requested.push(section)
    await route.fulfill({
      status: 200,
      contentType: 'application/rss+xml',
      body: bySection[section] ?? channel(''),
    })
  })
}

test('stream opens on Top stories and requests that section', async ({ page }) => {
  const requested: string[] = []
  await mockStream(page, requested)

  await page.goto('/#/stream')

  const tabs = page.getByRole('tab')
  await expect(tabs).toHaveText(['Top stories', 'Sports', 'Culture', 'Business'])
  await expect(page.getByRole('tab', { name: 'Top stories' })).toHaveAttribute(
    'aria-selected',
    'true'
  )
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  expect(requested[0]).toBe('main')
})

test('switching tabs changes the list and keeps sections disjoint', async ({ page }) => {
  const requested: string[] = []
  await mockStream(page, requested)

  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Derby Result' })).toHaveCount(0)

  await page.getByRole('tab', { name: 'Sports' }).click()

  await expect(page.getByRole('tab', { name: 'Sports' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('link', { name: 'Derby Result' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toHaveCount(0)
  expect(requested).toContain('sports')

  await page.getByRole('tab', { name: 'Business' }).click()
  await expect(page.getByText('No articles in this section yet.')).toBeVisible()

  const rssLink = page.getByRole('link', { name: /RSS/ })
  await expect(rssLink).toHaveAttribute('href', '/api/stream.rss?section=business')
})
