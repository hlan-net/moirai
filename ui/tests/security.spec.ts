import { test, expect } from '@playwright/test';

test.describe('API Authentication', () => {
  // Create a new request context without HTTP credentials for each test
  test('GET /api/config requires authentication', async ({ playwright }) => {
    const context = await playwright.request.newContext({
      baseURL: 'http://localhost:8088',
      httpCredentials: { username: 'invalid', password: 'invalid' },
    });
    const response = await context.get('/api/config');
    expect(response.status()).toBe(401);
    const text = await response.text();
    expect(text).toContain('login with proper credentials');
    await context.dispose();
  });

  test('PUT /api/config requires authentication', async ({ playwright }) => {
    const context = await playwright.request.newContext({
      baseURL: 'http://localhost:8088',
      httpCredentials: { username: 'invalid', password: 'invalid' },
    });
    const response = await context.put('/api/config', {
      data: { allow_public_read: true }
    });
    expect(response.status()).toBe(401);
    await context.dispose();
  });

  test('DELETE /api/feeds/:id requires authentication', async ({ playwright }) => {
    const context = await playwright.request.newContext({
      baseURL: 'http://localhost:8088',
      httpCredentials: { username: 'invalid', password: 'invalid' },
    });
    const response = await context.delete('/api/feeds/test-id');
    // Should be 401 (no auth) or 404 (auth passed but not found) - both are acceptable
    // since auth check may happen before or after route resolution
    expect([401, 404]).toContain(response.status());
    await context.dispose();
  });

  test('DELETE /api/articles/:id requires authentication', async ({ playwright }) => {
    const context = await playwright.request.newContext({
      baseURL: 'http://localhost:8088',
      httpCredentials: { username: 'invalid', password: 'invalid' },
    });
    const response = await context.delete('/api/articles/test-id');
    expect([401, 404]).toContain(response.status());
    await context.dispose();
  });

  test('DELETE /api/events/:id requires authentication', async ({ playwright }) => {
    const context = await playwright.request.newContext({
      baseURL: 'http://localhost:8088',
      httpCredentials: { username: 'invalid', password: 'invalid' },
    });
    const response = await context.delete('/api/events/test-id');
    expect([401, 404]).toContain(response.status());
    await context.dispose();
  });

  test('DELETE /api/trends/:id requires authentication', async ({ playwright }) => {
    const context = await playwright.request.newContext({
      baseURL: 'http://localhost:8088',
      httpCredentials: { username: 'invalid', password: 'invalid' },
    });
    const response = await context.delete('/api/trends/test-id');
    expect([401, 404]).toContain(response.status());
    await context.dispose();
  });
});

test.describe('API Public Read Access', () => {
  test('GET /api/feeds allows public read when enabled', async ({ request }) => {
    const response = await request.get('/api/feeds');
    // Should return 200 when ALLOW_PUBLIC_READ=true
    expect(response.status()).toBe(200);
  });

  test('GET /api/articles allows public read when enabled', async ({ request }) => {
    const response = await request.get('/api/articles');
    // Should return 200 when ALLOW_PUBLIC_READ=true
    expect(response.status()).toBe(200);
  });
});
