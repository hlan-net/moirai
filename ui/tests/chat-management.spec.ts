import { test, expect, Page } from '@playwright/test'

function getBasicAuthHeader(): string | null {
  const username = process.env.API_USERNAME
  const password = process.env.API_PASSWORD
  if (!username || !password) return null
  const token = Buffer.from(`${username}:${password}`).toString('base64')
  return `Basic ${token}`
}

// Helper functions to reduce code duplication
async function createChatSession(page: Page, title: string): Promise<void> {
  const initialCount = await page.locator('.session-item').count()

  await page.click('.new-chat-btn')
  const input = page.locator('.input-area input')
  await input.waitFor({ state: 'visible' })
  await input.fill(title)
  await input.press('Enter')

  // Wait for new session to appear in the list
  await expect(page.locator('.session-item')).toHaveCount(initialCount + 1)
}

async function searchSessions(page: Page, query: string): Promise<void> {
  const searchInput = page.locator('.search-input')
  await searchInput.fill(query)
  // No explicit wait needed - Playwright auto-waits for subsequent assertions
}

async function startRename(page: Page): Promise<void> {
  const sessionItem = page.locator('.session-item').first()
  await sessionItem.hover()
  const renameBtn = sessionItem.locator('.rename-btn')
  await renameBtn.click()
  // Wait for rename input to appear
  await page.locator('.rename-input').waitFor({ state: 'visible' })
}

async function confirmDelete(page: Page): Promise<void> {
  const sessionItem = page.locator('.session-item').first()
  await sessionItem.hover()
  const deleteBtn = sessionItem.locator('.delete-btn')
  await deleteBtn.click()
  // Wait for delete confirmation to appear
  await page.locator('.delete-confirm').waitFor({ state: 'visible' })
}

test.describe('Chat Session Management', () => {
  test.beforeEach(async ({ page }) => {
    const authHeader = getBasicAuthHeader()
    if (authHeader) {
      await page.setExtraHTTPHeaders({ Authorization: authHeader })
    }
    await page.goto('/#/chat')
    await page.waitForLoadState('networkidle')
    await page.locator('.new-chat-btn').waitFor({ state: 'visible' })
  })

  test('should search and filter chat sessions by title', async ({ page }) => {
    // Create a few test chat sessions with unique identifiers
    const uniqueId = Date.now().toString()
    const testChats = [
      `Linux kernel updates discussion ${uniqueId}`,
      `Python best practices ${uniqueId}`,
      `JavaScript frameworks comparison ${uniqueId}`,
    ]

    for (const title of testChats) {
      await createChatSession(page, title)
    }

    // Test search by title
    await searchSessions(page, `Linux kernel updates discussion ${uniqueId}`)

    // Should show only the Linux chat
    const visibleSessions = page.locator('.session-item')
    await expect(visibleSessions).toHaveCount(1)
    await expect(visibleSessions.first()).toContainText(
      `Linux kernel updates discussion ${uniqueId}`
    )

    // Clear search
    await page.click('.clear-search-btn')

    // Should show all sessions (at least the ones we created)
    await expect(page.locator('.session-item')).not.toHaveCount(1)

    // Verify our created sessions are present
    for (const title of testChats) {
      await expect(page.locator('.session-item', { hasText: title })).toBeVisible()
    }
  })

  test('should search and filter chat sessions by model', async ({ page }) => {
    await searchSessions(page, 'llama')

    // Verify filtering works - check if any sessions are visible
    const visibleSessions = page.locator('.session-item')
    const count = await visibleSessions.count()

    // Skip validation if no existing sessions match
    test.skip(count === 0, 'No existing sessions with llama model')

    // Verify visible sessions contain the search term
    await expect(visibleSessions.first()).toContainText(/llama/i)
  })

  test('should search and filter chat sessions by provider', async ({ page }) => {
    await searchSessions(page, 'ollama')

    // Verify filtering works - check if any sessions are visible
    const visibleSessions = page.locator('.session-item')
    const count = await visibleSessions.count()

    // Skip validation if no existing sessions match
    test.skip(count === 0, 'No existing sessions with ollama provider')

    // Verify visible sessions contain the search term
    await expect(visibleSessions.first()).toContainText(/ollama/i)
  })

  test('should show "no results" message when search has no matches', async ({ page }) => {
    await searchSessions(page, 'xyznonexistent12345')

    // Should show no results message
    const noResults = page.locator('.no-results')
    await expect(noResults).toBeVisible()
    await expect(noResults).toContainText('No chats match "xyznonexistent12345"')
  })

  test('should rename a chat session via rename button', async ({ page }) => {
    // Create a test chat session
    await createChatSession(page, 'Original chat title')

    // Find the session and click rename button
    await startRename(page)

    // Should show rename input with current value
    const renameInput = page.locator('.rename-input')
    await expect(renameInput).toHaveValue('Original chat title')

    // Change the title and save
    await renameInput.fill('Updated chat title')
    await page.locator('.rename-save').click()

    // Wait for rename input to disappear (indicating save completed)
    await expect(renameInput).not.toBeVisible()

    // Verify the title was updated
    const sessionItem = page.locator('.session-item').first()
    await expect(sessionItem).toContainText('Updated chat title')
    await expect(sessionItem).not.toContainText('Original chat title')
  })

  test('should rename a chat session via double-click', async ({ page }) => {
    // Create a test chat session
    await createChatSession(page, 'Double click test')

    // Find the session title and double-click
    const sessionTitle = page.locator('.session-title').first()
    await sessionTitle.dblclick()

    // Should show rename input
    const renameInput = page.locator('.rename-input')
    await expect(renameInput).toBeVisible()

    // Change the title and save with Enter
    await renameInput.fill('After double click')
    await renameInput.press('Enter')

    // Wait for rename to complete
    await expect(renameInput).not.toBeVisible()

    // Verify the title was updated
    await expect(page.locator('.session-item').first()).toContainText('After double click')
  })

  test('should cancel rename via Cancel button', async ({ page }) => {
    // Create a test chat session
    await createChatSession(page, 'Cancel test title')

    // Start rename
    await startRename(page)

    // Modify the input and cancel
    const renameInput = page.locator('.rename-input')
    await renameInput.fill('Should not save this')
    await page.locator('.rename-cancel').click()

    // Rename input should be hidden
    await expect(renameInput).not.toBeVisible()

    // Verify the title was NOT updated
    const sessionItem = page.locator('.session-item').first()
    await expect(sessionItem).toContainText('Cancel test title')
    await expect(sessionItem).not.toContainText('Should not save this')
  })

  test('should cancel rename via Escape key', async ({ page }) => {
    // Create a test chat session
    await createChatSession(page, 'Escape test title')

    // Start rename
    await startRename(page)

    // Modify the input and press Escape
    const renameInput = page.locator('.rename-input')
    await renameInput.fill('Should not save this either')
    await renameInput.press('Escape')

    // Rename input should be hidden
    await expect(renameInput).not.toBeVisible()

    // Verify the title was NOT updated
    await expect(page.locator('.session-item').first()).toContainText('Escape test title')
  })

  test('should show delete confirmation overlay', async ({ page }) => {
    // Create a test chat session
    await createChatSession(page, 'Delete overlay test')

    // Click delete button - confirmDelete already waits for overlay
    await confirmDelete(page)

    // Verify overlay is shown with correct content
    const deleteConfirm = page.locator('.delete-confirm')
    await expect(deleteConfirm).toContainText('Delete this chat?')
    await expect(page.locator('.confirm-yes')).toBeVisible()
    await expect(page.locator('.confirm-no')).toBeVisible()
  })

  test('should cancel delete via Cancel button', async ({ page }) => {
    // Create a test chat session
    await createChatSession(page, 'Cancel delete test')

    // Start delete
    const initialCount = await page.locator('.session-item').count()
    await confirmDelete(page)

    // Click cancel
    await page.locator('.confirm-no').click()

    // Delete confirmation overlay should be hidden
    await expect(page.locator('.delete-confirm')).not.toBeVisible()

    // Session should still exist
    await expect(page.locator('.session-item')).toHaveCount(initialCount)
    await expect(page.locator('.session-item').first()).toContainText('Cancel delete test')
  })

  test('should delete a chat session and create new chat if active', async ({ page }) => {
    // Create a test chat session
    await createChatSession(page, 'To be deleted')

    // Verify session is active
    await expect(page.locator('.session-item').first()).toHaveClass(/active/)

    const initialCount = await page.locator('.session-item').count()

    // Delete the session
    await confirmDelete(page)
    await page.locator('.confirm-yes').click()

    // Wait for session to be removed
    await expect(page.locator('.session-item')).toHaveCount(initialCount - 1)

    // Should not find the deleted session
    const texts = await page.locator('.session-item').allTextContents()
    expect(texts.join(' ')).not.toContain('To be deleted')

    // Should have created a new chat (no active session)
    await expect(page.locator('.session-item.active')).toHaveCount(0)

    // Messages should be cleared
    await expect(page.locator('.message')).toHaveCount(0)
  })

  test('should delete a non-active chat session without affecting current session', async ({
    page,
  }) => {
    // Create two test chat sessions
    await createChatSession(page, 'First chat')
    await createChatSession(page, 'Second chat - to keep active')

    // Verify second session is active
    const secondSession = page.locator('.session-item').first() // Most recent is first
    await expect(secondSession).toHaveClass(/active/)
    await expect(secondSession).toContainText('Second chat')

    // Find and delete the first session (not active)
    const firstSession = page.locator('.session-item').nth(1)
    await firstSession.hover()
    await firstSession.locator('.delete-btn').click()

    // Wait for delete confirmation
    await page.locator('.delete-confirm').waitFor({ state: 'visible' })
    await page.locator('.confirm-yes').click()

    // Wait for session to be removed
    await expect(page.locator('.session-item', { hasText: 'First chat' })).toHaveCount(0)

    // Second session should still be active
    await expect(secondSession).toHaveClass(/active/)
    await expect(secondSession).toContainText('Second chat')

    // Messages should still be present
    await expect(page.locator('.message').first()).toBeVisible()
  })

  test('should display provider and model tags', async ({ page }) => {
    // Create a test chat session
    await createChatSession(page, 'Tag test')

    const sessionItem = page.locator('.session-item').first()

    // Verify tags are displayed
    await expect(sessionItem.locator('.provider-tag')).toBeVisible()
    await expect(sessionItem.locator('.model-tag')).toBeVisible()
  })

  test('should maintain search filter when renaming a session', async ({ page }) => {
    // Create test sessions
    await createChatSession(page, 'Unique search term alpha')
    await createChatSession(page, 'Another chat beta')

    // Search for specific term
    await searchSessions(page, 'alpha')

    // Should show only one session
    await expect(page.locator('.session-item')).toHaveCount(1)

    // Rename the visible session
    const sessionItem = page.locator('.session-item').first()
    await sessionItem.hover()
    await sessionItem.locator('.rename-btn').click()

    // Wait for rename input
    const renameInput = page.locator('.rename-input')
    await renameInput.waitFor({ state: 'visible' })
    await renameInput.fill('Renamed to gamma')
    await renameInput.press('Enter')

    // Wait for rename to complete
    await expect(renameInput).not.toBeVisible()

    // Search filter should still be active, but now showing no results
    await expect(page.locator('.no-results')).toBeVisible()
  })

  test('should stop event propagation when clicking rename/delete buttons', async ({ page }) => {
    // Create two test chat sessions
    await createChatSession(page, 'Event propagation test')
    await createChatSession(page, 'Second session')

    // Click on the first (non-active) session's rename button
    const firstSession = page.locator('.session-item').nth(1)
    await firstSession.hover()
    await firstSession.locator('.rename-btn').click()

    // Should show rename input
    await expect(page.locator('.rename-input')).toBeVisible()

    // First session should NOT become active (event propagation stopped)
    await expect(firstSession).not.toHaveClass(/active/)

    // Cancel rename
    await page.locator('.rename-cancel').click()
    await expect(page.locator('.rename-input')).not.toBeVisible()

    // Now test delete button
    await firstSession.locator('.delete-btn').click()

    // Should show delete confirmation
    await expect(page.locator('.delete-confirm')).toBeVisible()

    // First session should NOT become active (event propagation stopped)
    await expect(firstSession).not.toHaveClass(/active/)
  })
})
