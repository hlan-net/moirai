import { test, expect } from '@playwright/test';

test('stream page loads at root path', async ({ page }) => {
  await page.goto('/');
  
  // Check if the Stream header exists
  await expect(page.getByRole('heading', { name: 'Aggregated Stream' })).toBeVisible();
});

test('stream page loads when clicking Stream menu item', async ({ page }) => {
  await page.goto('/');
  
  // Wait for initial page load
  await expect(page.getByRole('heading', { name: 'Aggregated Stream' })).toBeVisible();
  
  // Click on the Stream navigation link
  await page.getByRole('link', { name: 'Stream' }).click();
  
  // Check that the Stream page is still visible (not empty)
  await expect(page.getByRole('heading', { name: 'Aggregated Stream' })).toBeVisible();
});

test('stream page loads via direct navigation to /#/stream', async ({ page }) => {
  await page.goto('/#/stream');
  
  // Check if the Stream header exists
  await expect(page.getByRole('heading', { name: 'Aggregated Stream' })).toBeVisible();
});
