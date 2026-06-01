import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for headed demo walkthroughs.
 * Extends the main config but removes testIgnore so the visual spec
 * (excluded from fast CI) can run via `npm run demo:visual`.
 */
export default defineConfig({
  testDir: "./tests",
  testMatch: ["**/*-visual.spec.ts"],
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "off",
  },

  outputDir: "test-results",

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
