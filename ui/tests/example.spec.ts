import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Moirai/);
});

test('feeds column loads', async ({ page }) => {
  await page.goto('/');
  
  // Check if the Feeds header exists
  await expect(page.getByRole('heading', { name: 'Feeds' })).toBeVisible();
});
