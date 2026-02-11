import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: process.env.CI ? 'http://localhost:8088' : 'http://localhost:5173',
    trace: 'on-first-retry',
    httpCredentials: {
      username: process.env.API_USERNAME || 'testuser',
      password: process.env.API_PASSWORD || 'testpassword',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: process.env.CI ? undefined : {
    command: 'yarnpkg dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
});
