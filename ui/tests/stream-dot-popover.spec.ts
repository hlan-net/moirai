import { test, expect } from '@playwright/test'

const rssXml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Moirai Aggregated Stream</title>
    <link>http://localhost</link>
    <description>Aggregated stream</description>
    <item>
      <title>Annotated Article</title>
      <link>https://example.com/articles/annotated</link>
      <description>Annotated summary</description>
      <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
      <guid isPermaLink="true">https://example.com/articles/annotated</guid>
      <category domain="event">Launch</category>
      <category domain="trend">Adoption</category>
      <category domain="topic">space</category>
      <category domain="priority">high</category>
      <category domain="sentiment">negative</category>
      <source><title>Example Feed</title></source>
    </item>
    <item>
      <title>Plain Article</title>
      <link>https://example.com/articles/plain</link>
      <description>Plain summary</description>
      <pubDate>Mon, 01 Jan 2024 09:00:00 +0000</pubDate>
      <guid isPermaLink="true">https://example.com/articles/plain</guid>
      <source><title>Example Feed</title></source>
    </item>
  </channel>
</rss>`

test('hovering compact-view dots shows annotation details', async ({ page }) => {
  await page.route('**/api/stream.rss*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/rss+xml', body: rssXml })
  })

  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Annotated Article' })).toBeVisible()

  // Only the annotated row gets a dot cluster
  const dots = page.locator('.compact-tags')
  await expect(dots).toHaveCount(1)

  const popover = page.getByRole('tooltip')
  await expect(popover).toHaveCount(0)

  await dots.hover()
  await expect(popover).toBeVisible()
  await expect(popover).toContainText('High priority')
  await expect(popover).toContainText('Negative sentiment')
  await expect(popover).toContainText('Launch')
  await expect(popover).toContainText('Adoption')
  await expect(popover).toContainText('space')

  await page.getByRole('heading', { name: 'Aggregated Stream' }).hover()
  await expect(popover).toHaveCount(0)

  // Keyboard focus shows it too
  await dots.focus()
  await expect(popover).toBeVisible()
})
