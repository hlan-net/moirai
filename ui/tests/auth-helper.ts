import { Page, expect } from '@playwright/test'

export async function authenticate(page: Page) {
  const email = `${process.env.ADMIN_USERNAME}@localhost.local`
  const password = process.env.ADMIN_PASSWORD || 'testpassword'

  // We can't easily use the login page if it has complex logic, 
  // so we use the API directly to get a token.
  const response = await page.request.post('/api/auth/login', {
    data: {
      email: email,
      password: password
    }
  })

  expect(response.ok()).toBeTruthy()
  const data = await response.json()
  const token = data.access_token

  // Set the token in localStorage
  await page.addInitScript((token) => {
    window.localStorage.setItem('token', token)
  }, token)
}
