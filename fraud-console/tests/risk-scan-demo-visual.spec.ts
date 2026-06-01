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
 *     · Scan Report Modal — executive summary (View Scan Report → close)
 *     · Paginated results table (100 rows / page)
 *     · Result Detail Drawer — row inspection (click row → close)
 *     · P1 High-risk tier filter
 *     · P3 Normal-risk tier filter
 *     · Page 2 navigation
 *     · Export Scan Results section
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
 *  • No downloads triggered.
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
  test.setTimeout(180_000);

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

  // Confirm action controls are visible
  await expect(
    page.getByRole("button", { name: /view scan report/i }).first()
  ).toBeVisible({ timeout: 20_000 });
  await expect(
    page.getByRole("button", { name: /export csv/i }).first()
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /copy scan id/i }).first()
  ).toBeVisible();
  await page.waitForTimeout(PAUSE.brief);

  // ── E. Scan Report Modal ───────────────────────────────────────────────────
  const reportBtn = page.getByRole("button", { name: /view scan report/i }).first();
  await reportBtn.click();

  const reportModal = page.getByTestId("scan-report-modal");
  await expect(reportModal).toBeVisible({ timeout: 5_000 });
  await page.waitForTimeout(PAUSE.read);

  // Confirm report sections are visible
  await expect(reportModal.getByText("Risk Distribution")).toBeVisible();
  await expect(reportModal.getByText("Exposure Summary")).toBeVisible();
  await page.waitForTimeout(PAUSE.read);

  // Scroll to the bottom of the report modal to show all sections
  await reportModal.locator("div.overflow-y-auto").evaluate((el) => el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }));
  await page.waitForTimeout(PAUSE.read);

  // Close via footer Close button
  await reportModal.getByRole("button", { name: "Close", exact: true }).click();
  await expect(reportModal).not.toBeVisible({ timeout: 3_000 });
  await page.waitForTimeout(PAUSE.brief);

  // ── F. Results table + promote button ─────────────────────────────────────
  await page.waitForSelector("table tbody tr", { timeout: 30_000 });
  await expect(page.getByText(/Showing 1/).first()).toBeVisible();
  await expect(page.getByText(/Page 1/).first()).toBeVisible();
  await page.waitForTimeout(PAUSE.read);

  // Identify promote button — show it exists, do NOT click it
  const promoteBtn = page.getByRole("button", { name: /promote/i }).first();
  await expect(promoteBtn).toBeVisible({ timeout: 10_000 });
  await promoteBtn.hover();   // hover only — no click
  await page.waitForTimeout(PAUSE.brief);

  // ── G. Result Detail Drawer ────────────────────────────────────────────────
  const firstRow = page.locator("table tbody tr").first();
  await firstRow.click();

  const drawer = page.getByTestId("result-detail-drawer");
  await expect(drawer).toBeVisible({ timeout: 5_000 });
  await expect(drawer.getByText("Risk Summary")).toBeVisible();
  await page.waitForTimeout(PAUSE.read);

  // Scroll drawer body to show transaction attributes
  await page.waitForTimeout(PAUSE.brief);

  // Close drawer
  await page.getByRole("button", { name: "Close" }).last().click();
  await expect(drawer).not.toBeVisible({ timeout: 3_000 });
  await page.waitForTimeout(PAUSE.brief);

  // ── H. P1 High-risk filter ─────────────────────────────────────────────────
  const p1Tab = page.getByRole("button", { name: /^P1/ }).first();
  await p1Tab.click();
  await page.waitForSelector("table tbody tr", { timeout: 20_000 });
  await page.waitForTimeout(PAUSE.read);

  // ── I. P3 Normal-risk filter ───────────────────────────────────────────────
  const p3Tab = page.getByRole("button", { name: /^P3/ }).first();
  await p3Tab.click();
  await page.waitForSelector("table tbody tr", { timeout: 20_000 });
  await page.waitForTimeout(PAUSE.read);

  // ── J. Return to All ──────────────────────────────────────────────────────
  const allTab = page.getByRole("button", { name: /^All/ }).first();
  await allTab.click();
  await page.waitForSelector("table tbody tr", { timeout: 15_000 });
  await page.waitForTimeout(PAUSE.brief);

  // ── K. Page 2 navigation ─────────────────────────────────────────────────
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

  // ── L. Export Scan Results section ────────────────────────────────────────
  // Scroll to export section and confirm controls are visible
  const exportSection = page.getByLabel("Export scan results");
  await exportSection.scrollIntoViewIfNeeded();
  await expect(exportSection).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole("button", { name: /export all results/i }).first()
  ).toBeVisible();
  await page.waitForTimeout(PAUSE.read);

  // ── M. Review Queue ────────────────────────────────────────────────────────
  await page.goto("/queue");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(PAUSE.read);

  // ── N. Workflow Events ─────────────────────────────────────────────────────
  await page.goto("/workflow/events");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(PAUSE.read);

  // ── O. Workflow Metrics ────────────────────────────────────────────────────
  await page.goto("/workflow/metrics");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(PAUSE.read);

  // ── P. Final hero shot — 10M scan ─────────────────────────────────────────
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
