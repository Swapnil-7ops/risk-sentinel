import { test, expect } from "playwright/test";

test("login page and invalid authentication flow", async ({ page }) => {
  await page.goto("http://127.0.0.1:5000/auth/login");
  await expect(page).toHaveTitle(/Sign in|Login|Risk Sentinel/i);
  await expect(page.locator('input[name="email"]')).toBeVisible();
  await expect(page.locator('input[name="password"]')).toBeVisible();

  await page.locator('input[name="email"]').fill("unknown-runtime@example.com");
  await page.locator('input[name="password"]').fill("definitely-not-valid");
  await page.locator('[type="submit"]').click();
  await expect(page.locator("body")).toContainText(/invalid|incorrect|unable|credentials/i);
});
