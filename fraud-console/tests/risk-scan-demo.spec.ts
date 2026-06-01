/**
 * Demo walkthrough verification for the 10M Portfolio Risk Scan.
 *
 * Navigates to the live 10M scan via query-param resume and verifies the
 * analyst surfaces described in the Phase 12D-8U verification record:
 *   - Scan Detail Header with status badge and row counts
 *   - Recent Portfolio Scans panel with the 10M filename
 *   - Summary metrics and risk-tier distribution
 *   - Paginated results table (page_size=100 — never full result set)
 *   - Tier filter tabs (P1, P3 — P0/P2 are 0 for this scan)
 *   - Page 2 navigation
 *   - Export and Copy Scan ID controls
 *   - Promote button presence (not clicked — DB mutation avoided in automation)
 *
 * Scan facts (10M verified benchmark):
 *   scan_id   aa0971d2-bdb6-49c7-bac3-fa355aa161ad
 *   P0        0
 *   P1        8,420,051
 *   P2        0
 *   P3        1,579,949
 */

import { test, expect } from "@playwright/test";

const SCAN_ID = "aa0971d2-bdb6-49c7-bac3-fa355aa161ad";
const SCAN_URL = `/risk-scan?scan_id=${SCAN_ID}`;

test.describe("10M risk scan demo walkthrough", () => {
  test("loads key analyst surfaces and uses paginated results", async ({ page }) => {
    // Track /results API calls to verify pagination is in use.
    const resultCalls: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/risk-scan/") && req.url().includes("/results")) {
        resultCalls.push(req.url());
      }
    });

    // ── Navigate ───────────────────────────────────────────────────────────
    await page.goto(SCAN_URL);

    // ── Page heading ───────────────────────────────────────────────────────
    await expect(
      page.getByRole("heading", { name: "Portfolio Risk Scan" })
    ).toBeVisible();

    // ── Recent Portfolio Scans panel — 10M filename visible ────────────────
    await expect(
      page.getByText("risk-scan-12d8u-10m.csv").first()
    ).toBeVisible({ timeout: 12000 });

    // ── Scan Detail Header ─────────────────────────────────────────────────
    // Status badge text (no CSS transform on this element)
    await expect(page.getByText("Completed scan record")).toBeVisible({
      timeout: 15000,
    });

    // Full scan UUID rendered in the metadata row
    await expect(page.getByText(SCAN_ID)).toBeVisible();

    // Row count rendered in the metrics strip — wait for API response
    await expect(page.getByText(/10,000,000/).first()).toBeVisible({
      timeout: 20000,
    });

    // Copy Scan ID and Export CSV action buttons
    await expect(
      page.getByRole("button", { name: /copy scan id/i }).first()
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /export csv/i }).first()
    ).toBeVisible();

    // ── Results table ──────────────────────────────────────────────────────
    // Wait for the results table to render with at least one row
    await page.waitForSelector("table tbody tr", { timeout: 30000 });

    // Pagination controls: "Page 1" text and Next button
    await expect(page.getByText(/Page 1/).first()).toBeVisible({
      timeout: 15000,
    });
    await expect(
      page.getByRole("button", { name: /next/i }).first()
    ).toBeVisible();

    // Row range indicator
    await expect(page.getByText(/Showing 1/)).toBeVisible();

    // ── Pagination API check ───────────────────────────────────────────────
    // The frontend must have called the paginated endpoint, not a full fetch.
    const pagedCall = resultCalls.find(
      (u) => u.includes("page=1") && u.includes("page_size=100")
    );
    expect(pagedCall, "results must use page=1&page_size=100").toBeTruthy();

    // No unbounded results call (no /results without page_size)
    const unbounded = resultCalls.find(
      (u) => u.includes("/results") && !u.includes("page_size")
    );
    expect(unbounded, "results must never be fetched without page_size").toBeFalsy();

    // ── Promote button present (not clicked) ───────────────────────────────
    const promoteBtn = page.getByRole("button", { name: /promote/i }).first();
    await expect(promoteBtn).toBeVisible({ timeout: 10000 });

    // ── Tier filter — P1 (8.4M rows) ──────────────────────────────────────
    const p1Tab = page.getByRole("button", { name: /^P1/ }).first();
    await p1Tab.click();
    await page.waitForSelector("table tbody tr", { timeout: 20000 });
    // Should still show paginated rows — no fatal error
    await expect(page.getByText(/Showing 1/)).toBeVisible();

    // ── Tier filter — P3 (1.5M rows) ──────────────────────────────────────
    const p3Tab = page.getByRole("button", { name: /^P3/ }).first();
    await p3Tab.click();
    await page.waitForSelector("table tbody tr", { timeout: 20000 });
    await expect(page.getByText(/Showing 1/)).toBeVisible();

    // ── Return to All ─────────────────────────────────────────────────────
    await page.getByRole("button", { name: /^All/ }).first().click();
    await page.waitForSelector("table tbody tr", { timeout: 15000 });

    // ── Page 2 navigation ─────────────────────────────────────────────────
    await page.getByRole("button", { name: /next/i }).first().click();
    await expect(page.getByText(/Page 2/).first()).toBeVisible({ timeout: 15000 });
    await page.waitForSelector("table tbody tr", { timeout: 15000 });

    // ── Screenshot to ignored artifact folder ──────────────────────────────
    await page.screenshot({
      path: "test-results/risk-scan-10m-demo.png",
      fullPage: false,
    });
  });
});
