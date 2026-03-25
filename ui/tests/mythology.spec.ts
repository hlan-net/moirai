import { test, expect } from '@playwright/test'

test.describe('Mythology Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/mythology')
  })

  test('has correct title and header', async ({ page }) => {
    // Page should have Moirai in the title
    await expect(page).toHaveTitle(/Moirai/)

    // Main header should be visible
    await expect(page.getByRole('heading', { name: 'The Three Fates' })).toBeVisible()
  })

  test('displays the three Fates cards', async ({ page }) => {
    // Clotho - The Spinner
    await expect(page.getByRole('heading', { name: 'Clotho' })).toBeVisible()
    await expect(page.getByText('The Spinner')).toBeVisible()

    // Lachesis - The Allotter
    await expect(page.getByRole('heading', { name: 'Lachesis' })).toBeVisible()
    await expect(page.getByText('The Allotter')).toBeVisible()

    // Atropos - The Inflexible
    await expect(page.getByRole('heading', { name: 'Atropos' })).toBeVisible()
    await expect(page.getByText('The Inflexible')).toBeVisible()
  })

  test('displays the Distaff/Userspace section', async ({ page }) => {
    await expect(
      page.getByRole('heading', { name: 'The Distaff — Userspace' })
    ).toBeVisible()
    await expect(page.getByText('distaff is the tool that holds')).toBeVisible()
  })

  test('displays the Divine Order section with all hierarchy cards', async ({ page }) => {
    // Section header
    await expect(page.getByRole('heading', { name: 'The Divine Order' })).toBeVisible()

    // The Olympians - Administrators
    await expect(page.getByRole('heading', { name: 'The Olympians' })).toBeVisible()
    await expect(page.getByText('Administrators').first()).toBeVisible()

    // The Titans - Users
    await expect(page.getByRole('heading', { name: 'The Titans' })).toBeVisible()
    await expect(page.getByText('Users').first()).toBeVisible()

    // The Mortals - Agents
    await expect(page.getByRole('heading', { name: 'The Mortals' })).toBeVisible()
    await expect(page.getByText('Agents').first()).toBeVisible()

    // The Quests - Issues
    await expect(page.getByRole('heading', { name: 'The Quests' })).toBeVisible()
    await expect(page.getByText('Issues, Events, Trends')).toBeVisible()

    // The Omens - Articles
    await expect(page.getByRole('heading', { name: 'The Omens' })).toBeVisible()
    await expect(page.getByText('Articles').first()).toBeVisible()

    // The Kingdoms - Userspaces
    await expect(page.getByRole('heading', { name: 'The Kingdoms' })).toBeVisible()
    await expect(page.getByText('Userspaces').first()).toBeVisible()
  })

  test('displays the Living Weave section', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'The Living Weave' })).toBeVisible()
  })

  test('displays stats from API', async ({ page }) => {
    // Wait for API to load (stats should appear in Fate cards)
    // Look for stat labels that indicate data loaded
    await expect(page.getByText('feeds spinning')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('articles measured')).toBeVisible()
    await expect(page.getByText('issues in the weave')).toBeVisible()
  })

  test('displays footer with Plato quote', async ({ page }) => {
    await expect(
      page.getByText('The spindle of Necessity turns', { exact: false })
    ).toBeVisible()
    await expect(page.getByText('Plato, Republic X')).toBeVisible()
  })

  test('navigation link to Mythology works', async ({ page }) => {
    // Go to home first
    await page.goto('/')

    // Click the Mythology nav link
    await page.click('a[href="/mythology"]')

    // Should be on Mythology page
    await expect(page.getByRole('heading', { name: 'The Three Fates' })).toBeVisible()
  })
})
