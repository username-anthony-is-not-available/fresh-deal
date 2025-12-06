import { test, expect } from '@playwright/test';

test('homepage has correct title and form', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Smart Meal Planner/);

  // Check for main heading
  await expect(page.locator('h1')).toContainText('Eat Healthy');

  // Check if form elements exist
  await expect(page.locator('input[placeholder="e.g. H4T 1V6"]')).toBeVisible();
  await expect(page.locator('button[type="submit"]')).toContainText('Start Saving Today');
});
