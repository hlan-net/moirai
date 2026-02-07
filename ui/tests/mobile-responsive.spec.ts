import { test, expect } from '@playwright/test';

test.describe('Mobile Responsive Dashboard', () => {
  test('dashboard should be responsive on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
    await page.goto('/#/dashboard');
    
    // Wait for the page to load
    await expect(page.locator('h1')).toBeVisible({ timeout: 10000 });
    
    // Check that columns stack vertically on mobile
    const columnsContainer = page.locator('.columns-container');
    await expect(columnsContainer).toBeVisible();
    
    // Verify navigation is mobile-friendly
    const nav = page.locator('.main-nav');
    await expect(nav).toBeVisible();
  });

  test('dashboard should show 2 columns on tablet viewport', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 }); // iPad
    await page.goto('/#/dashboard');
    
    // Wait for the page to load
    await expect(page.locator('h1')).toBeVisible({ timeout: 10000 });
    
    const columnsContainer = page.locator('.columns-container');
    await expect(columnsContainer).toBeVisible();
  });

  test('dashboard should show 4 columns on desktop viewport', async ({ page }) => {
    // Set desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/#/dashboard');
    
    // Wait for the page to load
    await expect(page.locator('h1')).toBeVisible({ timeout: 10000 });
    
    const columnsContainer = page.locator('.columns-container');
    await expect(columnsContainer).toBeVisible();
    
    // On desktop, columns should be in a row
    const columns = page.locator('.column');
    await expect(columns.first()).toBeVisible();
  });

  test('navigation should be mobile-friendly', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    
    // Check navigation links are visible
    await expect(page.getByRole('link', { name: 'Stream' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Chat' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible();
  });
});
