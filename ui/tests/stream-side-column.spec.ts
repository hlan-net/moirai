import { test, expect, type Page } from '@playwright/test'

// The Stream page's side column (#376): opens beside the stream on an article
// or on an event/trend, holds the conversation about it, changes subject and
// closes without a reload or a refetch of the stream. Logged-in users only.

const NS = 'https://github.com/hlan-net/moirai/ns/rss'

const item = (title: string, slug: string, categories = '') => `
    <item>
      <title>${title}</title>
      <link>https://example.com/${slug}</link>
      <description>${title} summary</description>
      <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
      <guid isPermaLink="true">https://example.com/${slug}</guid>
      <category domain="section">main</category>${categories}
      <source><title>Example Feed</title></source>
    </item>`

const STREAM = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:moirai="${NS}">
  <channel>
    <title>Moirai Aggregated Stream</title>
    <link>http://localhost</link>
    <description>Aggregated stream</description>
    ${item(
      'Derby Result',
      'derby',
      `
      <category domain="event" moirai:id="ev-1">Derby aftermath</category>
      <category domain="trend" moirai:id="tr-1">League finances</category>`
    )}
    ${item('Opera Premiere', 'opera')}
    ${item(
      'Budget Vote',
      'budget',
      `
      <category domain="event" moirai:id="ev-2">Budget talks</category>
      <category domain="event" moirai:id="ev-3">Coalition row</category>`
    )}
  </channel>
</rss>`

const ISSUES: Record<string, object> = {
  'ev-1': {
    _id: 'ev-1',
    logos: 'Derby aftermath',
    description: 'What followed the derby.',
    longevity: 'transient',
    status: 'active',
    premises: [
      { type: 'message', id: 'https://example.com/derby' },
      { type: 'message', id: 'https://elsewhere.example/report' },
    ],
  },
  'tr-1': {
    _id: 'tr-1',
    logos: 'League finances',
    description: '',
    longevity: 'temporal',
    status: 'active',
    premises: [],
  },
}

interface Calls {
  stream: number
  api: string[]
  chatBodies: Record<string, unknown>[]
  saved: Record<string, unknown>[]
}

const mockApi = async (
  page: Page,
  { loggedIn = true, stored = [] as object[] }: { loggedIn?: boolean; stored?: object[] } = {}
): Promise<Calls> => {
  const calls: Calls = { stream: 0, api: [], chatBodies: [], saved: [] }
  if (loggedIn) {
    await page.addInitScript(() => window.localStorage.setItem('token', 'test-token'))
  }
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method()
    if (url.pathname === '/api/stream.rss') {
      calls.stream += 1
      return route.fulfill({ status: 200, contentType: 'application/rss+xml', body: STREAM })
    }
    calls.api.push(`${method} ${url.pathname}${url.search}`)
    if (url.pathname === '/api/auth/me') {
      return loggedIn
        ? route.fulfill({ json: { id: 'u1', email: 'user@localhost.local', role: 'user' } })
        : route.fulfill({ status: 401, json: { message: 'Unauthorized' } })
    }
    if (url.pathname.startsWith('/api/issues/')) {
      const issue = ISSUES[url.pathname.split('/').pop() as string]
      return issue ? route.fulfill({ json: issue }) : route.fulfill({ status: 404, json: {} })
    }
    if (url.pathname === '/api/chat/history' && method === 'GET') {
      return route.fulfill({ json: stored })
    }
    if (url.pathname === '/api/chat/history' && method === 'POST') {
      return route.fulfill({ json: { _id: 'session-1', messages: [] } })
    }
    if (url.pathname.startsWith('/api/chat/history/') && method === 'PUT') {
      calls.saved.push(request.postDataJSON())
      return route.fulfill({ json: { _id: 'session-1' } })
    }
    if (url.pathname === '/api/chat' && method === 'POST') {
      calls.chatBodies.push(request.postDataJSON())
      return route.fulfill({
        json: { response: 'It ended **two–one**.', tool_calls: [], timing_ms: 12 },
      })
    }
    return route.fulfill({ json: [] })
  })
  return calls
}

const panel = (page: Page) => page.getByRole('complementary')
const discuss = (page: Page, title: string) =>
  page.getByRole('button', { name: `Discuss ${title}`, exact: true })

test('opens on an article beside the stream and closes without refetching', async ({ page }) => {
  const calls = await mockApi(page)
  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Derby Result' })).toBeVisible()
  await expect(panel(page)).toHaveCount(0)

  await discuss(page, 'Derby Result').click()

  await expect(panel(page)).toBeVisible()
  await expect(panel(page).getByRole('heading', { name: 'Derby Result' })).toBeVisible()
  await expect(panel(page).getByText('Derby Result summary')).toBeVisible()
  await expect(page).toHaveURL(/open=article/)
  // The stream is still there, beside the column.
  await expect(page.getByRole('link', { name: 'Opera Premiere' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Close the side column' })).toBeFocused()

  await page.getByRole('button', { name: 'Close the side column' }).click()

  await expect(panel(page)).toHaveCount(0)
  await expect(page).not.toHaveURL(/open=/)
  await expect(discuss(page, 'Derby Result')).toBeFocused()
  expect(calls.stream).toBe(1)
})

test('a conversation is sent with its subject, shown and saved', async ({ page }) => {
  const calls = await mockApi(page)
  await page.goto('/#/stream')
  await discuss(page, 'Derby Result').click()

  await panel(page).getByRole('textbox', { name: 'Message' }).fill('How did it end?')
  await panel(page).getByRole('button', { name: 'Send' }).click()

  await expect(panel(page).getByText('How did it end?')).toBeVisible()
  await expect(panel(page).getByText('It ended two–one.')).toBeVisible()
  await expect(panel(page).locator('.markdown strong')).toHaveText('two–one')

  const body = calls.chatBodies[0] as { message: string; context: Record<string, any> }
  expect(body.message).toBe('How did it end?')
  expect(body.context.type).toBe('article')
  expect(body.context.entity_id).toBe('https://example.com/derby')
  expect(body.context.entity_data.title).toBe('Derby Result')
  // The server picks the model: the page sends none.
  expect(body).not.toHaveProperty('model')
  expect(body).not.toHaveProperty('llm_endpoint')

  await expect.poll(() => calls.saved.length).toBe(1)
  expect(calls.saved[0].messages as unknown[]).toHaveLength(2)
})

test('an earlier conversation about the same subject continues', async ({ page }) => {
  const calls = await mockApi(page, {
    stored: [
      {
        _id: 'session-9',
        messages: [
          { role: 'user', content: 'Who scored?' },
          { role: 'assistant', content: 'The captain.' },
        ],
      },
    ],
  })
  await page.goto('/#/stream')
  await discuss(page, 'Derby Result').click()

  await expect(panel(page).getByText('Who scored?')).toBeVisible()
  await expect(panel(page).getByText('The captain.')).toBeVisible()
  expect(
    calls.api.some(
      (c) =>
        c.startsWith('GET /api/chat/history?') &&
        c.includes('context_type=article') &&
        c.includes('entity_id=https%3A%2F%2Fexample.com%2Fderby')
    )
  ).toBe(true)

  await panel(page).getByRole('textbox', { name: 'Message' }).fill('And then?')
  await panel(page).getByRole('textbox', { name: 'Message' }).press('Enter')
  await expect(panel(page).getByText('It ended two–one.')).toBeVisible()

  const body = calls.chatBodies[0] as { history: unknown[] }
  expect(body.history).toHaveLength(2)
  // Continued in the stored session: no new one is created.
  expect(calls.api.some((c) => c === 'POST /api/chat/history')).toBe(false)
})

test('an event opens from its dot, and from the article that lists it', async ({ page }) => {
  await mockApi(page)
  await page.goto('/#/stream')
  await expect(page.getByRole('link', { name: 'Derby Result' })).toBeVisible()

  // One event on the article: its dot goes straight to the event.
  await page.getByRole('button', { name: 'Open the event of Derby Result' }).click()

  await expect(panel(page).getByRole('heading', { name: 'Derby aftermath' })).toBeVisible()
  await expect(panel(page).getByText('What followed the derby.')).toBeVisible()
  await expect(panel(page).getByText('2 articles')).toBeVisible()
  // An article of the stream is named; another is shown by its address.
  await expect(panel(page).getByRole('link', { name: 'Derby Result' })).toBeVisible()
  await expect(
    panel(page).getByRole('link', { name: 'https://elsewhere.example/report' })
  ).toBeVisible()
  await expect(page).toHaveURL(/open=issue:ev-1/)

  // Two events on the article: the dot opens the article, which lists both.
  await page.getByRole('button', { name: 'Open the event of Budget Vote' }).click()
  await expect(panel(page).getByRole('heading', { name: 'Budget Vote' })).toBeVisible()
  await expect(panel(page).getByRole('button', { name: 'Budget talks' })).toBeVisible()
  await expect(panel(page).getByRole('button', { name: 'Coalition row' })).toBeVisible()

  // From an article to its trend, in the same column.
  await discuss(page, 'Derby Result').click()
  await panel(page).getByRole('button', { name: 'League finances' }).click()
  await expect(panel(page).getByRole('heading', { name: 'League finances' })).toBeVisible()
  await expect(panel(page).getByText('Trend', { exact: true })).toBeVisible()
  await expect(panel(page).getByText('No description yet.')).toBeVisible()
})

test('the subject is read from the URL, and Back and Escape close the column', async ({ page }) => {
  const calls = await mockApi(page)
  await page.goto('/#/stream?open=issue:ev-1')

  await expect(panel(page).getByRole('heading', { name: 'Derby aftermath' })).toBeVisible()

  await discuss(page, 'Opera Premiere').click()
  await expect(panel(page).getByRole('heading', { name: 'Opera Premiere' })).toBeVisible()

  await page.goBack()
  await expect(panel(page).getByRole('heading', { name: 'Derby aftermath' })).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(panel(page)).toHaveCount(0)
  expect(calls.stream).toBe(1)

  // A shared link to an article of the stream.
  await page.goto('/#/stream?open=article:https://example.com/opera')
  await expect(panel(page).getByRole('heading', { name: 'Opera Premiere' })).toBeVisible()
})

test('a missing issue says so', async ({ page }) => {
  await mockApi(page)
  await page.goto('/#/stream?open=issue:gone')

  await expect(panel(page).getByText('This event or trend no longer exists.')).toBeVisible()
})

test('without a login there is no column and no request beyond the stream', async ({ page }) => {
  const calls = await mockApi(page, { loggedIn: false })
  await page.goto('/#/stream?open=issue:ev-1')

  await expect(page.getByRole('link', { name: 'Derby Result' })).toBeVisible()
  await expect(panel(page)).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^Discuss / })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^Open the event/ })).toHaveCount(0)
  expect(calls.api.filter((c) => !c.includes('/api/auth/'))).toEqual([])
})

test('on a narrow screen the column covers the stream and closes back to it', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 })
  await mockApi(page)
  await page.goto('/#/stream')
  await discuss(page, 'Derby Result').click()

  const box = await panel(page).boundingBox()
  expect(box?.x).toBe(0)
  expect(box?.width).toBe(390)

  await page.getByRole('button', { name: 'Close the side column' }).click()
  await expect(panel(page)).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Derby Result' })).toBeVisible()
})

test('in right-to-left text the column is on the left', async ({ page }) => {
  await mockApi(page)
  await page.goto('/#/stream')
  await page.evaluate(() => document.documentElement.setAttribute('dir', 'rtl'))
  await discuss(page, 'Derby Result').click()

  const column = await panel(page).boundingBox()
  const stream = await page.locator('.stream-page').boundingBox()
  expect(column!.x).toBeLessThan(stream!.x)
})
