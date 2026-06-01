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

    // ── Export section — wait for summary data, then confirm controls ────
    // The export section only renders after summary.isLoading resolves.
    await expect(page.getByText("Export Scan Results")).toBeVisible({ timeout: 20000 });
    await expect(
      page.getByRole("button", { name: /export all results/i }).first()
    ).toBeVisible();

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

  test("opens and closes the scan report modal", async ({ page }) => {
    await page.goto(SCAN_URL);

    // "View Scan Report" only appears once summary has loaded
    const reportBtn = page.getByRole("button", { name: /view scan report/i });
    await expect(reportBtn).toBeVisible({ timeout: 25000 });

    // Open the modal
    await reportBtn.click();

    const modal = page.getByTestId("scan-report-modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Scan filename and 10M row count must appear in the report
    await expect(modal.getByText("risk-scan-12d8u-10m.csv")).toBeVisible();
    await expect(modal.getByText(/10,000,000/).first()).toBeVisible();

    // Close via the Close button in the footer
    await modal.getByRole("button", { name: "Close", exact: true }).click();
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });

  test("opens and closes the result detail drawer", async ({ page }) => {
    await page.goto(SCAN_URL);

    // Wait for results table to be ready
    await page.waitForSelector("table tbody tr", { timeout: 30000 });

    // Click the first data row to open the drawer
    const firstRow = page.locator("table tbody tr").first();
    await firstRow.click();

    // Drawer should appear
    const drawer = page.getByTestId("result-detail-drawer");
    await expect(drawer).toBeVisible({ timeout: 5000 });

    // Drawer contains a Risk Summary section
    await expect(drawer.getByText("Risk Summary")).toBeVisible();

    // Close via the × button
    await page.getByRole("button", { name: "Close" }).last().click();

    // Drawer should be gone
    await expect(drawer).not.toBeVisible({ timeout: 3000 });
  });
});
