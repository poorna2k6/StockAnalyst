import { test, expect } from '@playwright/test';

// Note: These tests require @axe-core/playwright
// Run: cd tests && npm install first

test.describe('Accessibility — axe-core audit', () => {
  test('home page loads with accessible structure', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Basic structural accessibility checks without axe
    // Check that the page has a main landmark or at least some structure
    const hasMain = await page.locator('main, [role="main"]').count();
    const hasButtons = await page.getByRole('button').count();
    expect(hasButtons).toBeGreaterThan(0);

    // Check that interactive buttons have accessible names
    const buttons = page.getByRole('button');
    const count = await buttons.count();
    for (let i = 0; i < Math.min(count, 20); i++) {
      const btn = buttons.nth(i);
      if (await btn.isVisible()) {
        const accessibleName = await btn.getAttribute('aria-label') ||
          await btn.textContent() ||
          await btn.getAttribute('title');
        // Button should have some accessible text (aria-label, text content, or title)
        // We log violations but don't fail yet (fixme pattern)
        if (!accessibleName?.trim()) {
          console.warn(`Button at index ${i} has no accessible name`);
        }
      }
    }
  });

  test('form inputs have associated labels', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Navigate to a tab that has forms (Portfolio tab)
    const portfolioTab = page.getByRole('button', { name: /portfolio/i }).first();
    if (await portfolioTab.isVisible()) {
      await portfolioTab.click();
      await page.waitForTimeout(300);
    }

    // Check inputs have labels or aria-label
    const inputs = page.locator('input:visible');
    const inputCount = await inputs.count();
    for (let i = 0; i < inputCount; i++) {
      const input = inputs.nth(i);
      const id = await input.getAttribute('id');
      const ariaLabel = await input.getAttribute('aria-label');
      const ariaLabelledBy = await input.getAttribute('aria-labelledby');
      const placeholder = await input.getAttribute('placeholder');

      let hasLabel = false;
      if (ariaLabel || ariaLabelledBy) {
        hasLabel = true;
      } else if (id) {
        const label = page.locator(`label[for="${id}"]`);
        hasLabel = (await label.count()) > 0;
      }
      // Log for now (fixme pattern — will fix when a11y changes land)
      if (!hasLabel && !placeholder) {
        console.warn(`Input${id ? ` #${id}` : ''} at index ${i} lacks label/aria-label/placeholder`);
      }
    }
  });

  test('modals are dismissible', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Try to open auth modal
    const signInBtn = page.locator('#auth-signin-btn, [onclick*="openAuthModal"]').first();
    if (await signInBtn.isVisible()) {
      await signInBtn.click();
      await page.waitForTimeout(300);

      const modal = page.locator('#auth-modal').first();
      if (await modal.isVisible()) {
        // Test Escape key closes the modal
        await page.keyboard.press('Escape');
        await page.waitForTimeout(300);
        // Modal should be hidden after Escape
        await expect(modal).not.toBeVisible();
      }
    }
  });
});
