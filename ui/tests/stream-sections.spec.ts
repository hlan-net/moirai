import { test, expect, type Page } from '@playwright/test'

// Stream sections (#266, #344): the page opens on Top stories; the menu next
// to Refresh chooses one or several sections (none ticked = whole stream),
// the view and the RSS link; the choice is named next to the count, kept in
// the URL and in the browser.

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

const ITEMS: Record<string, string> = {
  main: item('Parliament Vote', 'politics/vote', 'main'),
  sports: item('Derby Result', 'urheilu/derby', 'sports'),
  culture: item('Opera Premiere', 'kulttuuri/opera', 'culture'),
  business: '',
}

// The union of the requested sections, as the API serves it; no `section` is
// the whole stream. Returns the raw `section` value ('' for none).
const sectionOf = (url: string) => new URL(url).searchParams.get('section') ?? ''

const bodyFor = (section: string) => {
  const keys = section ? section.split(',') : Object.keys(ITEMS)
  return channel(keys.map((key) => ITEMS[key] ?? '').join(''))
}

const mockStream = async (
  page: Page,
  requested: string[],
  delayMs: Record<string, number> = {}
) => {
  await page.route('**/api/stream.rss*', async (route) => {
    const section = sectionOf(route.request().url())
    requested.push(section)
    await new Promise((resolve) => setTimeout(resolve, delayMs[section] ?? 0))
    await route
      .fulfill({ status: 200, contentType: 'application/rss+xml', body: bodyFor(section) })
      .catch(() => {})
  })
}

const menuButton = (page: Page) => page.getByRole('button', { name: 'Stream options' })
const menu = (page: Page) => page.getByRole('menu', { name: 'Stream options' })
const sectionItem = (page: Page, name: string) =>
  page.getByRole('menuitemcheckbox', { name, exact: true })
const summary = (page: Page) => page.getByTestId('section-summary')

test('opens on Top stories, with the menu in place of the tabs', async ({ page }) => {
  const requested: string[] = []
  await mockStream(page, requested)

  await page.goto('/#/stream')

  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  await expect(summary(page)).toHaveText('· Top stories')
  await expect(page.getByRole('tab')).toHaveCount(0)
  expect(requested[0]).toBe('main')

  await expect(menuButton(page)).toHaveAttribute('aria-expanded', 'false')
  await menuButton(page).click()
  await expect(menuButton(page)).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('menuitemcheckbox')).toHaveText([
    /Top stories/,
    /Sports/,
    /Culture/,
    /Business/,
  ])
  await expect(sectionItem(page, 'Top stories')).toHaveAttribute('aria-checked', 'true')
  await expect(sectionItem(page, 'Sports')).toHaveAttribute('aria-checked', 'false')
})

test('several sections are read together and named next to the count', async ({ page }) => {
  const requested: string[] = []
  await mockStream(page, requested)

  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()

  await menuButton(page).click()
  await sectionItem(page, 'Sports').click()

  await expect(page.getByRole('link', { name: 'Derby Result' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  await expect(summary(page)).toHaveText('· Top stories, Sports')
  expect(requested).toContain('main,sports')
  await expect(page).toHaveURL(/sections=main%2Csports|sections=main,sports/)

  // The menu stays open for further choices; the RSS link follows them.
  await expect(menu(page)).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'RSS for this view' })).toHaveAttribute(
    'href',
    '/api/stream.rss?section=main%2Csports'
  )

  // Only Sports left: Top stories drops out of the list.
  await sectionItem(page, 'Top stories').click()
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toHaveCount(0)
  await expect(summary(page)).toHaveText('· Sports')
})

test('unticking the last section shows the whole stream', async ({ page }) => {
  const requested: string[] = []
  await mockStream(page, requested)

  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()

  await menuButton(page).click()
  await sectionItem(page, 'Top stories').click()

  await expect(summary(page)).toHaveText('· All sections')
  await expect(page.getByRole('link', { name: 'Derby Result' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Opera Premiere' })).toBeVisible()
  expect(requested.at(-1)).toBe('')
  await expect(page.getByRole('menuitem', { name: 'RSS for this view' })).toHaveAttribute(
    'href',
    '/api/stream.rss'
  )
})

test('an empty choice of one section says so', async ({ page }) => {
  await mockStream(page, [])

  await page.goto('/#/stream?sections=business')

  await expect(summary(page)).toHaveText('· Business')
  await expect(page.getByText('No articles in this section yet.')).toBeVisible()
})

test('the choice is read from the URL and survives a reload', async ({ page }) => {
  const requested: string[] = []
  await mockStream(page, requested)

  await page.goto('/#/stream?sections=sports,culture')
  await expect(summary(page)).toHaveText('· Sports, Culture')
  await expect(page.getByRole('link', { name: 'Opera Premiere' })).toBeVisible()
  expect(requested[0]).toBe('sports,culture')

  // Change it in the menu, then come back without the query: the browser kept it.
  await menuButton(page).click()
  await sectionItem(page, 'Sports').click()
  await expect(summary(page)).toHaveText('· Culture')

  await page.goto('/#/stream')
  await expect(summary(page)).toHaveText('· Culture')
  expect(requested.at(-1)).toBe('culture')
})

test('an unknown section in the URL falls back to the default', async ({ page }) => {
  const requested: string[] = []
  await mockStream(page, requested)

  await page.goto('/#/stream?sections=weather')

  await expect(summary(page)).toHaveText('· Top stories')
  expect(requested[0]).toBe('main')
})

test('the menu works from the keyboard and closes on Escape or outside', async ({ page }) => {
  await mockStream(page, [])

  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()

  await menuButton(page).focus()
  await page.keyboard.press('ArrowDown')
  await expect(menu(page)).toBeVisible()
  await expect(sectionItem(page, 'Top stories')).toBeFocused()

  await page.keyboard.press('ArrowDown')
  await expect(sectionItem(page, 'Sports')).toBeFocused()
  await page.keyboard.press('Space')
  await expect(sectionItem(page, 'Sports')).toHaveAttribute('aria-checked', 'true')
  await expect(summary(page)).toHaveText('· Top stories, Sports')

  await page.keyboard.press('End')
  await expect(page.getByRole('menuitem', { name: 'RSS for this view' })).toBeFocused()
  await page.keyboard.press('ArrowDown')
  await expect(sectionItem(page, 'Top stories')).toBeFocused()

  await page.keyboard.press('Escape')
  await expect(menu(page)).toBeHidden()
  await expect(menuButton(page)).toBeFocused()
  await expect(menuButton(page)).toHaveAttribute('aria-expanded', 'false')

  await menuButton(page).click()
  await expect(menu(page)).toBeVisible()
  await page.getByRole('heading', { name: 'Aggregated Stream' }).click()
  await expect(menu(page)).toBeHidden()
})

test('density and grouping are chosen in the menu', async ({ page }) => {
  await mockStream(page, [])

  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  await expect(page.locator('.stream-container')).toHaveClass(/high-density/)

  await menuButton(page).click()
  await page.getByRole('menuitemradio', { name: 'Expanded' }).click()
  await expect(page.locator('.stream-container')).not.toHaveClass(/high-density/)
  await expect(page.getByRole('menuitemradio', { name: 'Expanded' })).toHaveAttribute(
    'aria-checked',
    'true'
  )

  await page.getByRole('menuitemradio', { name: 'By time' }).click()
  await expect(page.getByRole('heading', { level: 3, name: /Older/ })).toBeVisible()
})

test('a superseded request does not end the current loading state', async ({ page }) => {
  // Top stories + Sports answers quickly, + Culture slowly: the slow, newer
  // request must keep "Loading" up, never show the faster, older result.
  await mockStream(page, [], { 'main,sports': 300, 'main,sports,culture': 2000 })

  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()

  await menuButton(page).click()
  await sectionItem(page, 'Sports').click()
  await sectionItem(page, 'Culture').click()

  // The first has answered by now; the second has not.
  await page.waitForTimeout(800)
  await expect(page.getByText('Loading stream...')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Derby Result' })).toHaveCount(0)

  await expect(page.getByRole('link', { name: 'Opera Premiere' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Derby Result' })).toBeVisible()
  await expect(summary(page)).toHaveText('· Top stories, Sports, Culture')
})
