/**
 * Navigation smoke tests — verifies every top-level route loads without a
 * fatal runtime error. These are not functional tests; they only confirm
 * the page renders and does not crash before user interaction.
 */

import { test, expect } from "@playwright/test";

const ROUTES = [
  { path: "/",                label: "Overview / root" },
  { path: "/dashboard",       label: "Risk Command dashboard" },
  { path: "/risk-scan",       label: "Portfolio Risk Scan (no scan)" },
  { path: "/queue",           label: "Review Queue" },
  { path: "/workflow/events", label: "Workflow Events" },
  { path: "/workflow/metrics",label: "Reliability Metrics" },
];

test.describe("navigation smoke", () => {
  for (const route of ROUTES) {
    test(`${route.label} loads without fatal error`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));

      const response = await page.goto(route.path);

      // HTTP-level check
      expect(
        response?.status(),
        `${route.path} must not return a server error`
      ).toBeLessThan(500);

      // No uncaught JS exception
      expect(
        errors,
        `${route.path} must not throw a runtime JS error`
      ).toHaveLength(0);

      // Body must not be empty
      const bodyText = await page.evaluate(() => document.body.innerText.trim());
      expect(bodyText.length, `${route.path} must render some content`).toBeGreaterThan(0);
    });
  }
});
