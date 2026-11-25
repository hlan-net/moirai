import { test, expect, type Page } from '@playwright/test'

// Stream search (#377): a logged-in reader's query replaces the list with the
// articles that mention it, as the same rows; the query is kept in the URL;
// clearing it shows the stream as it was, without a reload or a refetch.

const NS = 'https://github.com/hlan-net/moirai/ns/rss'

const item = (title: string, slug: string, section = 'main', categories = '') => `
    <item>
      <title>${title}</title>
      <link>https://example.com/${slug}</link>
      <description>${title} summary</description>
      <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
      <guid isPermaLink="true">https://example.com/${slug}</guid>
      <category domain="section">${section}</category>${categories}
      <source><title>Example Feed</title></source>
    </item>`

const channel = (items: string) => `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:moirai="${NS}">
  <channel>
    <title>Moirai</title>
    <link>http://localhost</link>
    <description>Articles</description>${items}
  </channel>
</rss>`

const STREAM = channel(item('Parliament Vote', 'vote') + item('Opera Premiere', 'opera'))

// What the search finds, by query; anything else finds nothing.
const RESULTS: Record<string, string> = {
  derby: channel(
    item(
      'Old Derby Report',
      'old-derby',
      'sports',
      `
      <category domain="event" moirai:id="ev-1">Derby aftermath</category>`
    ) + item('Derby Preview', 'derby-preview', 'sports')
  ),
  opera: channel(item('Opera Review', 'opera-review', 'culture')),
}

interface Calls {
  stream: number
  searches: string[]
  api: string[]
}

const mockApi = async (
  page: Page,
  {
    loggedIn = true,
    delayMs = {} as Record<string, number>,
    failing = [] as string[],
  }: { loggedIn?: boolean; delayMs?: Record<string, number>; failing?: string[] } = {}
): Promise<Calls> => {
  const calls: Calls = { stream: 0, searches: [], api: [] }
  if (loggedIn) {
    await page.addInitScript(() => window.localStorage.setItem('token', 'test-token'))
  }
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/stream.rss') {
      calls.stream += 1
      return route.fulfill({ status: 200, contentType: 'application/rss+xml', body: STREAM })
    }
    calls.api.push(`${route.request().method()} ${url.pathname}${url.search}`)
    if (url.pathname === '/api/auth/me') {
      return loggedIn
        ? route.fulfill({ json: { id: 'u1', email: 'user@localhost.local', role: 'user' } })
        : route.fulfill({ status: 401, json: { message: 'Unauthorized' } })
    }
    if (url.pathname === '/api/articles/search') {
      const query = url.searchParams.get('q') ?? ''
      calls.searches.push(url.search)
      await new Promise((resolve) => setTimeout(resolve, delayMs[query] ?? 0))
      if (failing.includes(query)) {
        return route
          .fulfill({ status: 429, json: { message: 'Too many requests' } })
          .catch(() => {})
      }
      return route
        .fulfill({
          status: 200,
          contentType: 'application/rss+xml',
          body: RESULTS[query] ?? channel(''),
        })
        .catch(() => {})
    }
    return route.fulfill({ json: [] })
  })
  return calls
}

const field = (page: Page) => page.getByRole('searchbox', { name: 'Search articles' })
const summary = (page: Page) => page.getByTestId('search-summary')
const clear = (page: Page) => page.getByRole('button', { name: 'Clear the search' })

test('a query replaces the list with its results and names itself', async ({ page }) => {
  const calls = await mockApi(page)
  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()

  await field(page).fill('derby')
  await field(page).press('Enter')

  await expect(page.getByRole('link', { name: 'Old Derby Report' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Derby Preview' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toHaveCount(0)
  await expect(summary(page)).toHaveText('2 results · Search: “derby”')
  await expect(page.getByTestId('section-summary')).toHaveCount(0)
  await expect(page).toHaveURL(/[?&]q=derby/)
  expect(calls.searches).toEqual(['?format=rss&limit=200&q=derby'])

  // A result is a stream row: its section is named, and its event opens.
  await expect(page.locator('.row-section').first()).toHaveText('Sports')
  await page.getByRole('button', { name: 'Open the event of Old Derby Report' }).click()
  await expect(page).toHaveURL(/open=issue:ev-1/)
  await expect(page).toHaveURL(/[?&]q=derby/)
})

test('clearing the search shows the stream as it was, without a request', async ({ page }) => {
  const calls = await mockApi(page)
  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  await expect(clear(page)).toHaveCount(0)

  await field(page).fill('derby')
  await field(page).press('Enter')
  await expect(page.getByRole('link', { name: 'Derby Preview' })).toBeVisible()
  const streamRequests = calls.stream
  await page.evaluate(() => ((window as unknown as { __kept: boolean }).__kept = true))

  await clear(page).click()

  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Derby Preview' })).toHaveCount(0)
  await expect(page.getByTestId('section-summary')).toHaveText('· Top stories')
  await expect(field(page)).toHaveValue('')
  await expect(page).not.toHaveURL(/[?&]q=/)
  expect(calls.stream).toBe(streamRequests)
  expect(await page.evaluate(() => (window as unknown as { __kept?: boolean }).__kept)).toBe(true)

  // Submitting an empty field ends a search as well, and Back returns to it.
  await page.goBack()
  await expect(page.getByRole('link', { name: 'Derby Preview' })).toBeVisible()
  await expect(field(page)).toHaveValue('derby')
  await field(page).fill('  ')
  await field(page).press('Enter')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
})

test('the query is read from the URL', async ({ page }) => {
  const calls = await mockApi(page)
  await page.goto('/#/stream?q=opera')

  await expect(page.getByRole('link', { name: 'Opera Review' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Opera Premiere' })).toHaveCount(0)
  await expect(field(page)).toHaveValue('opera')
  await expect(summary(page)).toHaveText('1 result · Search: “opera”')
  expect(calls.searches).toHaveLength(1)
})

test('a search without results says so', async ({ page }) => {
  await mockApi(page)
  await page.goto('/#/stream?q=zeppelin')

  await expect(page.getByText('No articles mention “zeppelin”.')).toBeVisible()
  await expect(summary(page)).toHaveText('0 results · Search: “zeppelin”')
})

test('a failed search says so, and Refresh tries again', async ({ page }) => {
  const calls = await mockApi(page, { failing: ['derby'] })
  await page.goto('/#/stream?q=derby')

  await expect(page.getByRole('alert')).toHaveText('The search failed. Try again in a moment.')

  await page.getByRole('button', { name: /Refresh/ }).click()
  await expect.poll(() => calls.searches.length).toBe(2)
})

test('a slower, older search does not replace a newer one', async ({ page }) => {
  await mockApi(page, { delayMs: { derby: 1500 } })
  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()

  await field(page).fill('derby')
  await field(page).press('Enter')
  await field(page).fill('opera')
  await field(page).press('Enter')

  await expect(page.getByRole('link', { name: 'Opera Review' })).toBeVisible()
  await page.waitForTimeout(1800)
  await expect(page.getByRole('link', { name: 'Opera Review' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Derby Preview' })).toHaveCount(0)
})

test('without a login there is no search field and the query is ignored', async ({ page }) => {
  const calls = await mockApi(page, { loggedIn: false })
  await page.goto('/#/stream?q=derby')

  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  await expect(field(page)).toHaveCount(0)
  await expect(summary(page)).toHaveCount(0)
  expect(calls.searches).toEqual([])
})

// The side column (#376) beside search results.
const panel = (page: Page) => page.getByRole('complementary')
const draft = (page: Page) => panel(page).getByRole('textbox', { name: 'Message' })

test('an article opened from the results stays open when the search is cleared', async ({
  page,
}) => {
  await mockApi(page)
  await page.goto('/#/stream?q=derby')
  await page.getByRole('button', { name: 'Discuss Old Derby Report', exact: true }).click()
  await expect(panel(page).getByRole('heading', { name: 'Old Derby Report' })).toBeVisible()

  // The article is not among the stream's own, only among the results.
  await clear(page).click()
  await expect(page.getByRole('link', { name: 'Parliament Vote' })).toBeVisible()
  await expect(panel(page).getByRole('heading', { name: 'Old Derby Report' })).toBeVisible()
  await expect(panel(page).getByText('no longer in the stream')).toHaveCount(0)
})

test('a new search or Refresh keeps the open column and the message in it', async ({ page }) => {
  await mockApi(page, { delayMs: { opera: 200, derby: 200 } })
  await page.goto('/#/stream?q=derby')
  await page.getByRole('button', { name: 'Discuss Old Derby Report', exact: true }).click()
  await draft(page).fill('Half a thought')

  await page.getByRole('button', { name: /Refresh/ }).click()
  await expect(draft(page)).toHaveValue('Half a thought')
  await expect(summary(page)).toContainText('2 results')
  await expect(draft(page)).toHaveValue('Half a thought')

  await field(page).fill('opera')
  await field(page).press('Enter')
  await expect(draft(page)).toHaveValue('Half a thought')
  await expect(summary(page)).toContainText('1 result')
  await expect(draft(page)).toHaveValue('Half a thought')
  await expect(panel(page).getByRole('heading', { name: 'Old Derby Report' })).toBeVisible()
})
