import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 10000,
  expect: {
    timeout: 5000,
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: 'html',
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || ((process.env.CI || process.env.TEST_TARGET === 'docker') ? 'http://localhost:8088' : 'http://localhost:5173'),
    trace: 'on-first-retry',
    httpCredentials: {
      username: process.env.ADMIN_USERNAME || 'testuser',
      password: process.env.ADMIN_PASSWORD || 'testpassword',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: process.env.TEST_TARGET === 'docker' ? undefined : (process.env.CI ? undefined : {
    command: 'yarnpkg dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  }),
});
