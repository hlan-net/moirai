import { test, expect } from '@playwright/test'

const rssXml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Moirai Aggregated Stream</title>
    <link>http://localhost</link>
    <description>Aggregated stream</description>
    <item>
      <title>First RSS Article</title>
      <link>https://example.com/articles/first</link>
      <description>First summary</description>
      <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
      <guid isPermaLink="true">https://example.com/articles/first</guid>
      <category domain="event">Launch</category>
      <source><title>Example Feed</title></source>
    </item>
    <item>
      <title>Second RSS Article</title>
      <link>https://example.com/articles/second</link>
      <description>Second summary</description>
      <pubDate>Mon, 01 Jan 2024 09:00:00 +0000</pubDate>
      <guid isPermaLink="true">https://example.com/articles/second</guid>
      <category domain="trend">Adoption</category>
      <source><title>Example Feed</title></source>
    </item>
  </channel>
</rss>`

test('stream page renders items from aggregated RSS feed', async ({ page }) => {
  await page.route('**/api/stream.rss*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/rss+xml',
      body: rssXml
    })
  })

  await page.goto('/#/stream')

  await expect(page.getByRole('heading', { name: 'Aggregated Stream' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 3, name: 'Example Feed' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'First RSS Article' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Second RSS Article' })).toBeVisible()
})
