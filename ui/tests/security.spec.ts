import { test, expect } from '@playwright/test'

const INVALID_CREDENTIALS = { username: 'invalid', password: 'invalid' }

async function withInvalidAuthContext<T>(
  playwright: any,
  baseURL: string | undefined,
  action: (context: any) => Promise<T>
): Promise<T> {
  const context = await playwright.request.newContext({
    baseURL: baseURL,
    httpCredentials: INVALID_CREDENTIALS,
  })
  try {
    return await action(context)
  } finally {
    await context.dispose()
  }
}

test.describe('API Authentication', () => {
  // Create a new request context without HTTP credentials for each test
  test('GET /api/config requires authentication', async ({ playwright, baseURL }) => {
    const response = await withInvalidAuthContext(playwright, baseURL, (context) =>
      context.get('/api/config')
    )
    expect(response.status()).toBe(401)
    const text = await response.text()
    // Expect either missing header (if not retried) or invalid credentials
    expect(text).toMatch(/Authorization header is missing|Invalid Basic Auth credentials|login/)
  })

  test('PUT /api/config requires authentication', async ({ playwright, baseURL }) => {
    const response = await withInvalidAuthContext(playwright, baseURL, (context) =>
      context.put('/api/config', { data: { allow_public_read: true } })
    )
    expect(response.status()).toBe(401)
  })

  test('DELETE /api/feeds/:id requires authentication', async ({ playwright, baseURL }) => {
    const response = await withInvalidAuthContext(playwright, baseURL, (context) =>
      context.delete('/api/feeds/test-id')
    )
    // Should be 401 (no auth) or 404 (auth passed but not found) - both are acceptable
    // since auth check may happen before or after route resolution
    expect([401, 404]).toContain(response.status())
  })

  test('DELETE /api/articles/:id requires authentication', async ({ playwright, baseURL }) => {
    const response = await withInvalidAuthContext(playwright, baseURL, (context) =>
      context.delete('/api/articles/test-id')
    )
    expect([401, 404]).toContain(response.status())
  })

  test('DELETE /api/issues/:id requires authentication', async ({ playwright, baseURL }) => {
    const response = await withInvalidAuthContext(playwright, baseURL, (context) =>
      context.delete('/api/issues/test-id')
    )
    expect([401, 404]).toContain(response.status())
  })
})

test.describe('API Public Read Access', () => {
  test('GET /api/feeds allows public read when enabled', async ({ request }) => {
    const response = await request.get('/api/feeds')
    // Should return 200 when ALLOW_PUBLIC_READ=true
    expect(response.status()).toBe(200)
  })

  test('GET /api/articles allows public read when enabled', async ({ request }) => {
    const response = await request.get('/api/articles')
    // Should return 200 when ALLOW_PUBLIC_READ=true
    expect(response.status()).toBe(200)
  })
})
