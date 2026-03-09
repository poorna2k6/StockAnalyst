import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E configuration
 *
 * Runs against a local Python http.server serving docs/:
 *   cd /home/user/StockAnalyst && python3 -m http.server 8000 --directory docs
 *
 * For CI, set BASE_URL env var to the GitHub Pages URL for preview deploys.
 */

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'html',

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 14'] },
    },
  ],
});
