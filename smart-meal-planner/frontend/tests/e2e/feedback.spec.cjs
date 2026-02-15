const { test, expect } = require('@playwright/test');

test('Feedback Dashboard and Rating', async ({ page }) => {
  // Set user_id in localStorage to skip login for simplicity if possible,
  // but better to actually login if the app requires it.

  await page.goto('http://localhost:3000/register');
  const email = `test_${Date.now()}@example.com`;
  await page.fill('input[placeholder="Email Address"]', email);
  await page.fill('input[placeholder="Password"]', 'Password123!');
  await page.fill('input[placeholder="Postal Code"]', 'H1A 1A1');
  await page.click('button[type="submit"]');

  // Wait for redirect to home or plan
  await page.waitForURL('**/');

  // Go to Meal Plan page
  await page.goto('http://localhost:3000/plan');

  // Check if "How do you like this Meal Plan?" section is there
  // (Might need to generate a plan first if it's empty)
  const feedbackHeading = page.locator('text=How do you like this Meal Plan?');
  if (await feedbackHeading.isVisible()) {
    // Rate the plan
    await page.locator('button >> .lucide-star').first().click();
    await page.fill('textarea[placeholder*="Any comments"]', 'Great variety this week!');
    await page.click('button:has-text("Submit Feedback")');

    // Wait for success toast
    await expect(page.locator('text=Thank you for your feedback')).toBeVisible();
  }

  // Go to Feedback Dashboard
  await page.goto('http://localhost:3000/feedback');
  await expect(page.locator('h1')).toContainText('Feedback Dashboard');

  // Check summary
  await expect(page.locator('text=Total Feedback')).toBeVisible();

  // Take a screenshot
  await page.screenshot({ path: 'feedback-dashboard.png' });
});
