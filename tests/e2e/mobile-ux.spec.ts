import { test, expect } from '@playwright/test';

// Use a narrow mobile viewport
const MOBILE_VIEWPORT = { width: 375, height: 667 };
const NARROW_VIEWPORT = { width: 320, height: 568 };

test.describe('Mobile viewport — 375px', () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  test('page loads without horizontal overflow', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    const viewportWidth = MOBILE_VIEWPORT.width;
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 5); // allow 5px tolerance
  });

  test('all tab buttons are visible and not clipped', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Find all tab buttons
    const tabs = page.getByRole('button').filter({ hasText: /Portfolio|Watchlist|Market|Advisor|Settings/i });
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(3); // at least some tabs visible
    // Each visible tab should be within viewport bounds
    for (let i = 0; i < count; i++) {
      const tab = tabs.nth(i);
      if (await tab.isVisible()) {
        const box = await tab.boundingBox();
        if (box) {
          expect(box.x).toBeGreaterThanOrEqual(0);
          expect(box.x + box.width).toBeLessThanOrEqual(MOBILE_VIEWPORT.width + 5);
        }
      }
    }
  });

  test('header does not overflow viewport', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    const header = page.locator('header, [role="banner"]').first();
    if (await header.isVisible()) {
      const box = await header.boundingBox();
      if (box) {
        expect(box.width).toBeLessThanOrEqual(MOBILE_VIEWPORT.width + 5);
      }
    }
  });
});

test.describe('Mobile viewport — 320px narrow', () => {
  test.use({ viewport: NARROW_VIEWPORT });

  test('page loads without horizontal overflow on narrow screen', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(NARROW_VIEWPORT.width + 10);
  });
});
