import { test, expect } from "playwright/test";

test("health and static asset flow", async ({ request }) => {
  const health = await request.get("http://127.0.0.1:5000/healthz");
  expect(health.ok()).toBeTruthy();
  expect(await health.json()).toEqual({ status: "ok" });

  const css = await request.get("http://127.0.0.1:5000/static/app.css?v=20261104-4");
  expect(css.ok()).toBeTruthy();
  expect(await css.text()).toContain("--accent");
});
