import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

test.describe('OPML Import Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:8088/#/dashboard');
    await page.waitForTimeout(1000);
  });

  test('should parse OPML file and extract feed URLs', async ({ page }) => {
    // Create a test OPML file
    const opmlContent = `<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>Test Feed List</title>
  </head>
  <body>
    <outline text="Tech News" title="Tech News">
      <outline type="rss" text="Hacker News" title="Hacker News" xmlUrl="https://news.ycombinator.com/rss" htmlUrl="https://news.ycombinator.com/"/>
      <outline type="rss" text="Ars Technica" title="Ars Technica" xmlUrl="https://feeds.arstechnica.com/arstechnica/index" htmlUrl="https://arstechnica.com/"/>
    </outline>
    <outline text="Development" title="Development">
      <outline type="rss" text="CSS-Tricks" title="CSS-Tricks" xmlUrl="https://css-tricks.com/feed/" htmlUrl="https://css-tricks.com/"/>
      <outline type="rss" text="Smashing Magazine" title="Smashing Magazine" xmlUrl="https://www.smashingmagazine.com/feed/" htmlUrl="https://www.smashingmagazine.com/"/>
    </outline>
  </body>
</opml>`;

    const testOpmlPath = path.join('/tmp', 'test_feeds.opml');
    fs.writeFileSync(testOpmlPath, opmlContent);

    // Open bulk import modal
    await page.click('button[title="Bulk Import Feeds"]');
    await page.waitForSelector('.modal-overlay', { state: 'visible' });

    // Upload OPML file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testOpmlPath);

    // Wait a bit for the file to be processed
    await page.waitForTimeout(500);

    // Check if the textarea was populated with URLs
    const textareaValue = await page.locator('.bulk-import-textarea').inputValue();
    
    // Verify all 4 feed URLs are present
    expect(textareaValue).toContain('https://news.ycombinator.com/rss');
    expect(textareaValue).toContain('https://feeds.arstechnica.com/arstechnica/index');
    expect(textareaValue).toContain('https://css-tricks.com/feed/');
    expect(textareaValue).toContain('https://www.smashingmagazine.com/feed/');

    // Verify notification appears (using correct class)
    const notification = page.locator('.notification-toast.notification-success');
    await expect(notification).toBeVisible({ timeout: 3000 });
    await expect(notification).toContainText('Found 4 feed URL');

    // Clean up
    fs.unlinkSync(testOpmlPath);
  });

  test('should handle plain text file upload', async ({ page }) => {
    // Create a test text file
    const textContent = `https://example.com/feed1.xml
https://example.com/feed2.xml
https://example.com/feed3.xml`;

    const testTextPath = path.join('/tmp', 'test_feeds.txt');
    fs.writeFileSync(testTextPath, textContent);

    // Open bulk import modal
    await page.click('button[title="Bulk Import Feeds"]');
    await page.waitForSelector('.modal-overlay', { state: 'visible' });

    // Upload text file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testTextPath);

    // Wait a bit for the file to be processed
    await page.waitForTimeout(500);

    // Check if the textarea was populated
    const textareaValue = await page.locator('.bulk-import-textarea').inputValue();
    expect(textareaValue).toBe(textContent);

    // Clean up
    fs.unlinkSync(testTextPath);
  });

  test('should show error for invalid OPML file', async ({ page }) => {
    // Create an invalid OPML file
    const invalidContent = `This is not valid XML`;

    const testInvalidPath = path.join('/tmp', 'invalid.opml');
    fs.writeFileSync(testInvalidPath, invalidContent);

    // Open bulk import modal
    await page.click('button[title="Bulk Import Feeds"]');
    await page.waitForSelector('.modal-overlay', { state: 'visible' });

    // Upload invalid file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testInvalidPath);

    // Wait a bit for the file to be processed
    await page.waitForTimeout(500);

    // Verify error notification appears (using correct class)
    const notification = page.locator('.notification-toast.notification-error');
    await expect(notification).toBeVisible({ timeout: 3000 });
    await expect(notification).toContainText('Failed to parse OPML file');

    // Clean up
    fs.unlinkSync(testInvalidPath);
  });

  test('should show warning for OPML file with no valid URLs', async ({ page }) => {
    // Create an OPML file with no xmlUrl attributes
    const emptyOpmlContent = `<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>Empty Feed List</title>
  </head>
  <body>
    <outline text="Category" title="Category">
      <outline text="No URL" title="No URL" htmlUrl="https://example.com/"/>
    </outline>
  </body>
</opml>`;

    const testEmptyPath = path.join('/tmp', 'empty_feeds.opml');
    fs.writeFileSync(testEmptyPath, emptyOpmlContent);

    // Open bulk import modal
    await page.click('button[title="Bulk Import Feeds"]');
    await page.waitForSelector('.modal-overlay', { state: 'visible' });

    // Upload OPML file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testEmptyPath);

    // Wait a bit for the file to be processed
    await page.waitForTimeout(500);

    // Verify warning notification appears (using correct class)
    const notification = page.locator('.notification-toast.notification-warning');
    await expect(notification).toBeVisible({ timeout: 3000 });
    await expect(notification).toContainText('No valid feed URLs found in OPML file');

    // Clean up
    fs.unlinkSync(testEmptyPath);
  });
});
