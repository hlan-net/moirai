import { test, expect } from '@playwright/test'

type AuthCase = {
  name: string
  method: 'get' | 'put' | 'delete'
  url: string
  data?: Record<string, unknown>
  expectStatus?: number
  expectStatusIn?: number[]
  expectBodyRegex?: RegExp
}

const INVALID_CREDENTIALS = { username: 'invalid', password: 'invalid' }

const AUTH_CASES: AuthCase[] = [
  {
    name: 'GET /api/config requires authentication',
    method: 'get',
    url: '/api/config',
    expectStatus: 401,
    expectBodyRegex: /Authorization header is missing|Invalid Basic Auth credentials|login|Invalid Authorization scheme/,
  },
  {
    name: 'PUT /api/config requires authentication',
    method: 'put',
    url: '/api/config',
    data: { allow_public_read: true },
    expectStatus: 401,
  },
  {
    name: 'DELETE /api/feeds/:id requires authentication',
    method: 'delete',
    url: '/api/feeds/test-id',
    expectStatusIn: [401, 404],
  },
  {
    name: 'DELETE /api/articles/:id requires authentication',
    method: 'delete',
    url: '/api/articles/test-id',
    expectStatusIn: [401, 404],
  },
  {
    name: 'DELETE /api/issues/:id requires authentication',
    method: 'delete',
    url: '/api/issues/test-id',
    expectStatusIn: [401, 404],
  },
]

const PUBLIC_READ_CASES = [
  { name: 'GET /api/feeds allows public read when enabled', url: '/api/feeds' },
  { name: 'GET /api/articles allows public read when enabled', url: '/api/articles' },
]

async function withInvalidAuthContext<T>(
  playwright: any,
  baseURL: string | undefined,
  action: (context: any) => Promise<T>
): Promise<T> {
  const context = await playwright.request.newContext({
    baseURL: baseURL,
    httpCredentials: INVALID_CREDENTIALS,
    extraHTTPHeaders: {},
  })
  try {
    return await action(context)
  } finally {
    await context.dispose()
  }
}

async function requestWithMethod(
  context: any,
  method: AuthCase['method'],
  url: string,
  data?: Record<string, unknown>
) {
  switch (method) {
    case 'get':
      return context.get(url)
    case 'put':
      return context.put(url, { data: data })
    case 'delete':
      return context.delete(url)
    default:
      throw new Error(`Unsupported method: ${method}`)
  }
}

test.describe('API Authentication', () => {
  AUTH_CASES.forEach((caseInfo) => {
    test(caseInfo.name, async ({ playwright, baseURL }) => {
      const result = await withInvalidAuthContext(playwright, baseURL, async (context) => {
        const response = await requestWithMethod(
          context,
          caseInfo.method,
          caseInfo.url,
          caseInfo.data
        )
        const text = caseInfo.expectBodyRegex ? await response.text() : undefined
        return { status: response.status(), text }
      })

      if (caseInfo.expectStatusIn) {
        expect(caseInfo.expectStatusIn).toContain(result.status)
      } else {
        expect(result.status).toBe(caseInfo.expectStatus)
      }

      if (caseInfo.expectBodyRegex) {
        expect(result.text).toMatch(caseInfo.expectBodyRegex)
      }
    })
  })
})

test.describe('API Public Read Access', () => {
  PUBLIC_READ_CASES.forEach((caseInfo) => {
    test(caseInfo.name, async ({ request }) => {
      const response = await request.get(caseInfo.url)
      // Should return 200 when ALLOW_PUBLIC_READ=true
      expect(response.status()).toBe(200)
    })
  })
})
