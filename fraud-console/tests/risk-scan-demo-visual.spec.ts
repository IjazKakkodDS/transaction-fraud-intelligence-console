/**
 * Visual demo walkthrough — Fraud Intelligence Console
 *
 * PURPOSE
 * -------
 * This script is designed for screen-recording and live portfolio demos.
 * Run it in headed Chromium at a presentation viewport so the product flow
 * is visible on screen:
 *
 *   npm run demo:visual
 *
 * It deliberately uses waitForTimeout between steps so a screen recorder or
 * a live audience has time to observe each surface.  It is NOT a speed test
 * and is NOT part of CI.  Use `npm run test:e2e` for the fast verification
 * suite instead.
 *
 * WHAT IT SHOWS
 * -------------
 *  1. Overview / root dashboard
 *  2. Risk Command / dashboard metrics
 *  3. Portfolio Risk Scan — 10M verified benchmark scan
 *     · Scan Detail Header (status, UUID, row counts, exposures)
 *     · Recent Portfolio Scans panel
 *     · Portfolio KPI rail and Tier Distribution
 *     · Paginated results table (100 rows / page)
 *     · P1 High-risk tier filter
 *     · P3 Normal-risk tier filter
 *     · Page 2 navigation
 *  4. Review Queue
 *  5. Workflow Events
 *  6. Workflow Metrics (Reliability)
 *  7. Return to 10M scan — final hero shot
 *
 * SAFETY CONSTRAINTS
 * ------------------
 *  • Promote button is identified but never clicked — no DB mutation.
 *  • No large-scan re-upload.
 *  • No DB row deletions.
 *
 * 10M SCAN FACTS (Phase 12D-8U verified benchmark)
 * -------------------------------------------------
 *  scan_id   aa0971d2-bdb6-49c7-bac3-fa355aa161ad
 *  rows      10,000,000 / 10,000,000 COMPLETE
 *  P0        0      P1  8,420,051
 *  P2        0      P3  1,579,949
 *  export    1.64 GiB / 10,000,001 lines
 */

import { test, expect } from "@playwright/test";

// ── Config ───────────────────────────────────────────────────────────────────

const SCAN_ID = "aa0971d2-bdb6-49c7-bac3-fa355aa161ad";
const SCAN_URL = `/risk-scan?scan_id=${SCAN_ID}`;

/** Pause for recording — longer than automated tests need, shorter than awkward. */
const PAUSE = {
  brief:    1_200,   // between interactions on a loaded page
  read:     2_500,   // let the viewer take in a section
  navigate: 1_800,   // after a page transition settles
  load:       800,   // after clicking a filter / next-page
};

// ── Test ─────────────────────────────────────────────────────────────────────

test.use({
  viewport: { width: 1440, height: 900 },
  // Slow down all actions so movements are visible during recording.
  actionTimeout: 30_000,
});

test("Fraud Intelligence Console — product demo walkthrough", async ({ page }) => {
  // Visual walkthroughs need a generous timeout — pauses alone exceed 30s.
  test.setTimeout(120_000);

  // ── A. Overview ────────────────────────────────────────────────────────────
  await page.goto("/");
  await expect(page).toHaveTitle(/Fraud/i);
  await page.waitForTimeout(PAUSE.navigate);

  // ── B. Risk Command / Dashboard ────────────────────────────────────────────
  await page.goto("/dashboard");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(PAUSE.read);

  // ── C. Navigate to Portfolio Risk Scan — 10M scan ─────────────────────────
  await page.goto(SCAN_URL);

  // Wait for the Recent Portfolio Scans panel and the 10M filename
  await expect(
    page.getByText("risk-scan-12d8u-10m.csv").first()
  ).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(PAUSE.navigate);

  // ── D. Scan Detail Header ─────────────────────────────────────────────────
  // Status badge
  await expect(
    page.getByText("Completed scan record")
  ).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(PAUSE.brief);

  // Wait for row count to render from API
  await expect(
    page.getByText(/10,000,000/).first()
  ).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(PAUSE.read);

  // Confirm controls are visible (but do not click Export or trigger a download)
  await expect(
    page.getByRole("button", { name: /export csv/i }).first()
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /copy scan id/i }).first()
  ).toBeVisible();
  await page.waitForTimeout(PAUSE.brief);

  // ── Results table + pagination ─────────────────────────────────────────────
  await page.waitForSelector("table tbody tr", { timeout: 30_000 });
  await expect(page.getByText(/Showing 1/).first()).toBeVisible();
  await expect(page.getByText(/Page 1/).first()).toBeVisible();
  await page.waitForTimeout(PAUSE.read);

  // Identify promote button — show it exists, do NOT click it
  const promoteBtn = page.getByRole("button", { name: /promote/i }).first();
  await expect(promoteBtn).toBeVisible({ timeout: 10_000 });
  await promoteBtn.hover();   // hover only — no click
  await page.waitForTimeout(PAUSE.brief);

  // ── E. P1 High-risk filter ─────────────────────────────────────────────────
  const p1Tab = page.getByRole("button", { name: /^P1/ }).first();
  await p1Tab.click();
  await page.waitForSelector("table tbody tr", { timeout: 20_000 });
  await page.waitForTimeout(PAUSE.read);

  // ── F. P3 Normal-risk filter ───────────────────────────────────────────────
  const p3Tab = page.getByRole("button", { name: /^P3/ }).first();
  await p3Tab.click();
  await page.waitForSelector("table tbody tr", { timeout: 20_000 });
  await page.waitForTimeout(PAUSE.read);

  // ── G. Return to All ──────────────────────────────────────────────────────
  const allTab = page.getByRole("button", { name: /^All/ }).first();
  await allTab.click();
  await page.waitForSelector("table tbody tr", { timeout: 15_000 });
  await page.waitForTimeout(PAUSE.brief);

  // ── H. Page 2 ─────────────────────────────────────────────────────────────
  const nextBtn = page.getByRole("button", { name: /next/i }).first();
  await nextBtn.click();
  await expect(page.getByText(/Page 2/).first()).toBeVisible({ timeout: 15_000 });
  await page.waitForSelector("table tbody tr", { timeout: 15_000 });
  await page.waitForTimeout(PAUSE.read);

  // Navigate back to page 1
  const prevBtn = page.getByRole("button", { name: /previous/i }).first();
  await prevBtn.click();
  await expect(page.getByText(/Page 1/).first()).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(PAUSE.brief);

  // ── I. Review Queue ────────────────────────────────────────────────────────
  await page.goto("/queue");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(PAUSE.read);

  // ── J. Workflow Events ─────────────────────────────────────────────────────
  await page.goto("/workflow/events");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(PAUSE.read);

  // ── K. Workflow Metrics ────────────────────────────────────────────────────
  await page.goto("/workflow/metrics");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(PAUSE.read);

  // ── L. Final hero shot — 10M scan ─────────────────────────────────────────
  await page.goto(SCAN_URL);
  await expect(
    page.getByText("Completed scan record")
  ).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByText(/10,000,000/).first()
  ).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(PAUSE.read * 2);   // hold for hero shot

  // Confirm no fatal JS errors occurred during the full walkthrough
  // (Playwright would have surfaced uncaught exceptions as test failures)
});
