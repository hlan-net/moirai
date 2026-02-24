import { defineConfig, devices } from '@playwright/test';

const adminUsername = process.env.ADMIN_USERNAME || 'testuser';
const adminPassword = process.env.ADMIN_PASSWORD || 'testpassword';
const basicAuthToken = Buffer.from(`${adminUsername}:${adminPassword}`).toString('base64');

const defaultBaseURL = (process.env.CI || process.env.TEST_TARGET === 'docker') 
  ? 'http://localhost:8088' 
  : 'http://localhost:5173';

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
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || defaultBaseURL,
    trace: 'on-first-retry',
    httpCredentials: {
      username: adminUsername,
      password: adminPassword,
    },
    extraHTTPHeaders: {
      Authorization: `Basic ${basicAuthToken}`,
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
