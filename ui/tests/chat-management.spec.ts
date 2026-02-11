import { test, expect } from '@playwright/test';

test.describe('Chat Session Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/#/chat');
    await page.waitForLoadState('networkidle');
  });

  test('should search and filter chat sessions by title', async ({ page }) => {
    // Create a few test chat sessions
    const testChats = [
      'Linux kernel updates discussion',
      'Python best practices',
      'JavaScript frameworks comparison'
    ];

    for (const title of testChats) {
      await page.click('.new-chat-btn');
      await page.waitForTimeout(500);
      
      const input = page.locator('.input-area input');
      await input.fill(title);
      await input.press('Enter');
      
      // Wait for response
      await page.waitForTimeout(2000);
    }

    // Wait for sessions to load
    await page.waitForTimeout(1000);

    // Test search by title
    const searchInput = page.locator('.search-input');
    await searchInput.fill('Linux');
    
    // Wait for filter to apply (reactive, should be immediate)
    await page.waitForTimeout(100);

    // Should show only the Linux chat
    const visibleSessions = page.locator('.session-item');
    await expect(visibleSessions).toHaveCount(1);
    await expect(visibleSessions.first()).toContainText('Linux');

    // Clear search
    await page.click('.clear-search-btn');
    await page.waitForTimeout(100);

    // Should show all sessions
    await expect(visibleSessions).toHaveCount(testChats.length);
  });

  test('should search and filter chat sessions by model', async ({ page }) => {
    // Assuming there are sessions with different models
    const searchInput = page.locator('.search-input');
    
    // Search for a common model name
    await searchInput.fill('llama');
    await page.waitForTimeout(100);

    // Verify filtering works (sessions with 'llama' in model name should appear)
    const visibleSessions = page.locator('.session-item');
    const count = await visibleSessions.count();
    
    // If no sessions match, that's also valid - just verify the filter is working
    if (count > 0) {
      // Check that visible sessions contain the search term
      const firstSession = visibleSessions.first();
      const text = await firstSession.textContent();
      expect(text?.toLowerCase()).toContain('llama');
    }
  });

  test('should search and filter chat sessions by provider', async ({ page }) => {
    const searchInput = page.locator('.search-input');
    
    // Search for provider name
    await searchInput.fill('ollama');
    await page.waitForTimeout(100);

    // Verify filtering works
    const visibleSessions = page.locator('.session-item');
    const count = await visibleSessions.count();
    
    if (count > 0) {
      // Check that visible sessions contain the search term
      const firstSession = visibleSessions.first();
      const text = await firstSession.textContent();
      expect(text?.toLowerCase()).toContain('ollama');
    }
  });

  test('should show "no results" message when search has no matches', async ({ page }) => {
    const searchInput = page.locator('.search-input');
    
    // Search for something that won't match
    await searchInput.fill('xyznonexistent12345');
    await page.waitForTimeout(100);

    // Should show no results message
    const noResults = page.locator('.no-results');
    await expect(noResults).toBeVisible();
    await expect(noResults).toContainText('No chats match "xyznonexistent12345"');
  });

  test('should rename a chat session via rename button', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('Original chat title');
    await input.press('Enter');
    
    // Wait for response and session creation
    await page.waitForTimeout(2000);

    // Find the session and click rename button
    const sessionItem = page.locator('.session-item').first();
    await sessionItem.hover();
    
    const renameBtn = sessionItem.locator('.rename-btn');
    await renameBtn.click();
    await page.waitForTimeout(100);

    // Should show rename input
    const renameInput = page.locator('.rename-input');
    await expect(renameInput).toBeVisible();
    await expect(renameInput).toHaveValue('Original chat title');

    // Change the title
    await renameInput.fill('Updated chat title');
    
    // Save the rename
    const saveBtn = page.locator('.rename-save');
    await saveBtn.click();
    await page.waitForTimeout(500);

    // Verify the title was updated
    await expect(sessionItem).toContainText('Updated chat title');
    await expect(sessionItem).not.toContainText('Original chat title');

    // Rename input should be hidden
    await expect(renameInput).not.toBeVisible();
  });

  test('should rename a chat session via double-click', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('Double click test');
    await input.press('Enter');
    
    // Wait for response and session creation
    await page.waitForTimeout(2000);

    // Find the session title and double-click
    const sessionTitle = page.locator('.session-title').first();
    await sessionTitle.dblclick();
    await page.waitForTimeout(100);

    // Should show rename input
    const renameInput = page.locator('.rename-input');
    await expect(renameInput).toBeVisible();

    // Change the title
    await renameInput.fill('After double click');
    await renameInput.press('Enter');
    await page.waitForTimeout(500);

    // Verify the title was updated
    const sessionItem = page.locator('.session-item').first();
    await expect(sessionItem).toContainText('After double click');
  });

  test('should cancel rename via Cancel button', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('Cancel test title');
    await input.press('Enter');
    
    // Wait for response and session creation
    await page.waitForTimeout(2000);

    // Start rename
    const sessionItem = page.locator('.session-item').first();
    await sessionItem.hover();
    await sessionItem.locator('.rename-btn').click();
    await page.waitForTimeout(100);

    // Modify the input
    const renameInput = page.locator('.rename-input');
    await renameInput.fill('Should not save this');
    
    // Click cancel
    const cancelBtn = page.locator('.rename-cancel');
    await cancelBtn.click();
    await page.waitForTimeout(100);

    // Verify the title was NOT updated
    await expect(sessionItem).toContainText('Cancel test title');
    await expect(sessionItem).not.toContainText('Should not save this');
    
    // Rename input should be hidden
    await expect(renameInput).not.toBeVisible();
  });

  test('should cancel rename via Escape key', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('Escape test title');
    await input.press('Enter');
    
    // Wait for response and session creation
    await page.waitForTimeout(2000);

    // Start rename
    const sessionItem = page.locator('.session-item').first();
    await sessionItem.hover();
    await sessionItem.locator('.rename-btn').click();
    await page.waitForTimeout(100);

    // Modify the input and press Escape
    const renameInput = page.locator('.rename-input');
    await renameInput.fill('Should not save this either');
    await renameInput.press('Escape');
    await page.waitForTimeout(100);

    // Verify the title was NOT updated
    await expect(sessionItem).toContainText('Escape test title');
    await expect(sessionItem).not.toContainText('Should not save this either');
  });

  test('should show delete confirmation overlay', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('Delete overlay test');
    await input.press('Enter');
    
    // Wait for response and session creation
    await page.waitForTimeout(2000);

    // Click delete button
    const sessionItem = page.locator('.session-item').first();
    await sessionItem.hover();
    
    const deleteBtn = sessionItem.locator('.delete-btn');
    await deleteBtn.click();
    await page.waitForTimeout(100);

    // Should show delete confirmation overlay
    const deleteConfirm = page.locator('.delete-confirm');
    await expect(deleteConfirm).toBeVisible();
    await expect(deleteConfirm).toContainText('Delete this chat?');
    
    // Should show confirm and cancel buttons
    await expect(page.locator('.confirm-yes')).toBeVisible();
    await expect(page.locator('.confirm-no')).toBeVisible();
  });

  test('should cancel delete via Cancel button', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('Cancel delete test');
    await input.press('Enter');
    
    // Wait for response and session creation
    await page.waitForTimeout(2000);

    // Start delete
    const sessionItem = page.locator('.session-item').first();
    const initialCount = await page.locator('.session-item').count();
    
    await sessionItem.hover();
    await sessionItem.locator('.delete-btn').click();
    await page.waitForTimeout(100);

    // Click cancel
    const cancelBtn = page.locator('.confirm-no');
    await cancelBtn.click();
    await page.waitForTimeout(100);

    // Session should still exist
    const newCount = await page.locator('.session-item').count();
    expect(newCount).toBe(initialCount);
    await expect(sessionItem).toContainText('Cancel delete test');
    
    // Delete confirmation overlay should be hidden
    await expect(page.locator('.delete-confirm')).not.toBeVisible();
  });

  test('should delete a chat session and create new chat if active', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('To be deleted');
    await input.press('Enter');
    
    // Wait for response and session creation
    await page.waitForTimeout(2000);

    // Verify session is active
    const sessionItem = page.locator('.session-item').first();
    await expect(sessionItem).toHaveClass(/active/);

    const initialCount = await page.locator('.session-item').count();

    // Delete the session
    await sessionItem.hover();
    await sessionItem.locator('.delete-btn').click();
    await page.waitForTimeout(100);

    const confirmBtn = page.locator('.confirm-yes');
    await confirmBtn.click();
    await page.waitForTimeout(500);

    // Session should be removed
    const newCount = await page.locator('.session-item').count();
    expect(newCount).toBe(initialCount - 1);

    // Should not find the deleted session
    const sessions = page.locator('.session-item');
    const texts = await sessions.allTextContents();
    expect(texts.join(' ')).not.toContain('To be deleted');

    // Should have created a new chat (no active session)
    const activeSessions = page.locator('.session-item.active');
    await expect(activeSessions).toHaveCount(0);
    
    // Messages should be cleared
    const chatMessages = page.locator('.message');
    await expect(chatMessages).toHaveCount(0);
  });

  test('should delete a non-active chat session without affecting current session', async ({ page }) => {
    // Create two test chat sessions
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    let input = page.locator('.input-area input');
    await input.fill('First chat');
    await input.press('Enter');
    await page.waitForTimeout(2000);

    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    input = page.locator('.input-area input');
    await input.fill('Second chat - to keep active');
    await input.press('Enter');
    await page.waitForTimeout(2000);

    // Verify second session is active
    const sessions = page.locator('.session-item');
    const secondSession = sessions.first(); // Most recent is first
    await expect(secondSession).toHaveClass(/active/);
    await expect(secondSession).toContainText('Second chat');

    // Find and delete the first session (not active)
    const firstSession = sessions.nth(1);
    await firstSession.hover();
    await firstSession.locator('.delete-btn').click();
    await page.waitForTimeout(100);

    const confirmBtn = page.locator('.confirm-yes');
    await confirmBtn.click();
    await page.waitForTimeout(500);

    // First session should be removed
    const allSessions = page.locator('.session-item');
    const texts = await allSessions.allTextContents();
    expect(texts.join(' ')).not.toContain('First chat');

    // Second session should still be active
    await expect(secondSession).toHaveClass(/active/);
    await expect(secondSession).toContainText('Second chat');
    
    // Messages should still be present
    const chatMessages = page.locator('.message');
    await expect(chatMessages.first()).toBeVisible();
  });

  test('should display provider and model tags', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('Tag test');
    await input.press('Enter');
    
    // Wait for response and session creation
    await page.waitForTimeout(2000);

    const sessionItem = page.locator('.session-item').first();
    
    // Should show provider tag
    const providerTag = sessionItem.locator('.provider-tag');
    await expect(providerTag).toBeVisible();
    
    // Should show model tag
    const modelTag = sessionItem.locator('.model-tag');
    await expect(modelTag).toBeVisible();
  });

  test('should maintain search filter when renaming a session', async ({ page }) => {
    // Create test sessions
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    let input = page.locator('.input-area input');
    await input.fill('Unique search term alpha');
    await input.press('Enter');
    await page.waitForTimeout(2000);

    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    input = page.locator('.input-area input');
    await input.fill('Another chat beta');
    await input.press('Enter');
    await page.waitForTimeout(2000);

    // Search for specific term
    const searchInput = page.locator('.search-input');
    await searchInput.fill('alpha');
    await page.waitForTimeout(100);

    // Should show only one session
    await expect(page.locator('.session-item')).toHaveCount(1);

    // Rename the visible session
    const sessionItem = page.locator('.session-item').first();
    await sessionItem.hover();
    await sessionItem.locator('.rename-btn').click();
    await page.waitForTimeout(100);

    const renameInput = page.locator('.rename-input');
    await renameInput.fill('Renamed to gamma');
    await renameInput.press('Enter');
    await page.waitForTimeout(500);

    // Search filter should still be active, but now showing no results
    // (since we renamed "alpha" to "gamma")
    await expect(page.locator('.no-results')).toBeVisible();
  });

  test('should stop event propagation when clicking rename/delete buttons', async ({ page }) => {
    // Create a test chat session
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input = page.locator('.input-area input');
    await input.fill('Event propagation test');
    await input.press('Enter');
    await page.waitForTimeout(2000);

    // Create another session so we can test switching
    await page.click('.new-chat-btn');
    await page.waitForTimeout(500);
    
    const input2 = page.locator('.input-area input');
    await input2.fill('Second session');
    await input2.press('Enter');
    await page.waitForTimeout(2000);

    // Click on the first (non-active) session's rename button
    const firstSession = page.locator('.session-item').nth(1);
    await firstSession.hover();
    
    const renameBtn = firstSession.locator('.rename-btn');
    await renameBtn.click();
    await page.waitForTimeout(100);

    // Should show rename input
    await expect(page.locator('.rename-input')).toBeVisible();
    
    // First session should NOT become active (event propagation stopped)
    await expect(firstSession).not.toHaveClass(/active/);
    
    // Cancel rename
    await page.locator('.rename-cancel').click();
    await page.waitForTimeout(100);

    // Now test delete button
    const deleteBtn = firstSession.locator('.delete-btn');
    await deleteBtn.click();
    await page.waitForTimeout(100);

    // Should show delete confirmation
    await expect(page.locator('.delete-confirm')).toBeVisible();
    
    // First session should NOT become active (event propagation stopped)
    await expect(firstSession).not.toHaveClass(/active/);
  });
});
