import { test, expect } from '@playwright/test'

test('anonymous users are redirected when stream is private', async ({ browser }) => {
  const adminUser = process.env.ADMIN_USERNAME || 'username'
  const adminPassword = process.env.ADMIN_PASSWORD || 'password'
  const baseURL =
    process.env.PLAYWRIGHT_TEST_BASE_URL ||
    (process.env.TEST_TARGET === 'docker' ? 'http://localhost:8088' : 'http://localhost:5173')

  const adminContext = await browser.newContext({
    httpCredentials: {
      username: adminUser,
      password: adminPassword
    }
  })

  const configRes = await adminContext.request.put(`${baseURL}/api/config`, {
    data: {
      allow_public_read: false
    }
  })

  expect(configRes.ok()).toBeTruthy()

  const anonymousContext = await browser.newContext({
    httpCredentials: {
      username: 'invalid',
      password: 'invalid'
    }
  })
  const rssRes = await anonymousContext.request.get(`${baseURL}/api/stream.rss`)
  expect(rssRes.status()).toBe(401)
  const authChallenge = rssRes.headers()['www-authenticate'] || ''
  expect(authChallenge.toLowerCase()).toContain('basic')

  const page = await anonymousContext.newPage()
  await page.goto(`${baseURL}/#/stream`)
  await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible()

  await adminContext.close()
  await anonymousContext.close()
})
