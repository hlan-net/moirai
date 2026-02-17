import { test, expect } from '@playwright/test';

test.describe('Mobile Responsive Dashboard', () => {
  test('dashboard should be responsive on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
    await page.goto('/#/dashboard');
    
    // Wait for the page to load
    await expect(page.locator('h1')).toBeVisible();
    
    // Check that columns container exists
    const columnsContainer = page.locator('.columns-container');
    await expect(columnsContainer).toBeVisible();
    
    // Verify columns are stacked vertically (flex-direction: column)
    const flexDirection = await columnsContainer.evaluate((el) => {
      return window.getComputedStyle(el).flexDirection;
    });
    expect(flexDirection).toBe('column');
    
    // Verify all 4 columns are visible
    const columns = page.locator('.column');
    await expect(columns).toHaveCount(4);
    
    // Verify navigation is mobile-friendly (vertical layout)
    const nav = page.locator('.main-nav');
    const navFlexDirection = await nav.evaluate((el) => {
      return window.getComputedStyle(el).flexDirection;
    });
    expect(navFlexDirection).toBe('column');
  });

  test('dashboard should show 2-column layout on tablet viewport', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 }); // iPad
    await page.goto('/#/dashboard');
    
    // Wait for the page to load
    await expect(page.locator('h1')).toBeVisible();
    
    const columnsContainer = page.locator('.columns-container');
    await expect(columnsContainer).toBeVisible();
    
    // On tablet, columns should wrap in a row
    const flexDirection = await columnsContainer.evaluate((el) => {
      return window.getComputedStyle(el).flexDirection;
    });
    expect(flexDirection).toBe('row');
    
    // Navigation should be horizontal on tablet
    const nav = page.locator('.main-nav');
    const navFlexDirection = await nav.evaluate((el) => {
      return window.getComputedStyle(el).flexDirection;
    });
    expect(navFlexDirection).toBe('row');
  });

  test('dashboard should show 4-column layout on desktop viewport', async ({ page }) => {
    // Set desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/#/dashboard');
    
    // Wait for the page to load
    await expect(page.locator('h1')).toBeVisible();
    
    const columnsContainer = page.locator('.columns-container');
    await expect(columnsContainer).toBeVisible();
    
    // On desktop, columns should be in a row (no wrap)
    const flexDirection = await columnsContainer.evaluate((el) => {
      return window.getComputedStyle(el).flexDirection;
    });
    expect(flexDirection).toBe('row');
    
    // All 4 columns should be visible and in a horizontal row
    const columns = page.locator('.column');
    await expect(columns).toHaveCount(4);
    
    // Verify columns are positioned horizontally by checking their positions
    const firstColumn = columns.first();
    const lastColumn = columns.last();
    
    const firstBox = await firstColumn.boundingBox();
    const lastBox = await lastColumn.boundingBox();
    
    // Both bounding boxes should exist on desktop
    expect(firstBox).not.toBeNull();
    expect(lastBox).not.toBeNull();
    
    if (firstBox && lastBox) {
      // Last column should be to the right of the first column
      expect(lastBox.x).toBeGreaterThan(firstBox.x);
      // Both should be on roughly the same vertical level (allowing for small differences)
      expect(Math.abs(lastBox.y - firstBox.y)).toBeLessThan(50);
    }
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
    
    // Verify navigation links are stacked vertically on mobile
    const nav = page.locator('.main-nav');
    const flexDirection = await nav.evaluate((el) => {
      return window.getComputedStyle(el).flexDirection;
    });
    expect(flexDirection).toBe('column');
  });
});
