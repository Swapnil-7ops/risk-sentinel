import { test, expect } from "playwright/test";

test("public UI renders with security headers and theme toggle", async ({ page }) => {
  const response = await page.goto("http://127.0.0.1:5000/auth/login");
  expect(response).not.toBeNull();
  expect(response.status()).toBe(200);
  expect(response.headers()["content-security-policy"]).toContain("script-src 'self'");
  await expect(page.locator("body")).toBeVisible();

  const theme = page.locator("[data-theme-toggle]");
  if (await theme.count()) {
    const before = await page.locator("html").getAttribute("data-theme");
    await theme.click();
    const after = await page.locator("html").getAttribute("data-theme");
    expect(after).not.toBe(before);
    await expect(theme).toHaveAttribute("aria-label", /Switch to (light|dark) theme/);
  }
});
