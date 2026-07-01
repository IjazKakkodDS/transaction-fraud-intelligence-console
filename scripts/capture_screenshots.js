#!/usr/bin/env node
"use strict";

/**
 * Phase 11Q - Automated screenshot capture for the Fraud Intelligence Console.
 *
 * Install and run (from project root):
 *   npm install -D playwright
 *   npx playwright install chromium
 *   node scripts/capture_screenshots.js
 *
 * Prerequisites:
 *   - Docker Compose stack running:  docker compose up -d
 *   - Frontend dev server running:   cd fraud-console && npm run dev
 *   - n8n workflow active on port 5678 (required for screenshot 09 workflow events)
 *   - Ollama running on host at port 11434 (required for screenshot 07 AI investigation)
 *   - Review case seeder present: python scripts/seed_review_cases.py
 *
 * Output:
 *   docs/screenshots/01_overview_command_center.png
 *   docs/screenshots/02_risk_command_dashboard.png
 *   docs/screenshots/03_transaction_intake.png
 *   docs/screenshots/04_scoring_result_handoff.png
 *   docs/screenshots/05_review_queue_prioritization.png
 *   docs/screenshots/06_case_dossier_risk_evidence.png
 *   docs/screenshots/07_ai_investigation_panel.png
 *   docs/screenshots/08_analyst_verdict_panel.png
 *   docs/screenshots/09_case_workflow_audit_trail.png
 *   docs/screenshots/10_false_positive_review_case.png
 *   docs/screenshots/11_workflow_events_audit_trail.png
 *   docs/screenshots/12_reliability_metrics_center.png
 *
 * Exit codes:
 *   0 - all screenshots captured successfully
 *   1 - pre-flight check failed or capture error
 */

const { chromium } = require("playwright");
const fs   = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Node version guard - require 18+ for global fetch
// ---------------------------------------------------------------------------

const [nodeMajor] = process.versions.node.split(".").map(Number);
if (nodeMajor < 18) {
  console.error("[capture] ERROR: Node.js 18 or later is required (global fetch support).");
  console.error(`  Current version: ${process.versions.node}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const FRONTEND_URL    = "http://localhost:3000";
const BACKEND_URL     = "http://localhost:8000";
const SCREENSHOTS_DIR = path.join(__dirname, "..", "docs", "screenshots");

const VIEWPORT = { width: 1440, height: 1200 };

const AFTER_NAV_MS    = 1500;  // extra wait after networkidle for data panels
const AFTER_SCROLL_MS = 900;   // wait after scrolling to a section
const CHART_WAIT_MS   = 2200;  // additional wait on chart-heavy pages

const POLL_INTERVAL_MS  = 2000;
const POLL_MAX_ATTEMPTS = 30;  // 60 seconds total polling window

// ---------------------------------------------------------------------------
// Logging
// ---------------------------------------------------------------------------

function log(msg)  { console.log(`[capture] ${msg}`); }
function warn(msg) { console.warn(`[capture] WARN: ${msg}`); }
function fail(msg) { console.error(`[capture] ERROR: ${msg}`); }

function sep() { console.log("[capture] " + "-".repeat(56)); }

// ---------------------------------------------------------------------------
// HTTP helpers (Node 18+ global fetch)
// ---------------------------------------------------------------------------

async function apiGet(urlPath) {
  try {
    const resp = await fetch(`${BACKEND_URL}${urlPath}`, {
      signal: AbortSignal.timeout(10_000),
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

async function apiPost(urlPath, body) {
  return fetch(`${BACKEND_URL}${urlPath}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  });
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// Unique transaction ID for the live intake screenshot submission
// ---------------------------------------------------------------------------

function generateScreenshotTxnId() {
  const n   = new Date();
  const pad = (v) => String(v).padStart(2, "0");
  return (
    `screenshot_intake_` +
    `${n.getFullYear()}${pad(n.getMonth() + 1)}${pad(n.getDate())}` +
    `_${pad(n.getHours())}${pad(n.getMinutes())}${pad(n.getSeconds())}`
  );
}

// ---------------------------------------------------------------------------
// Pre-flight checks
// ---------------------------------------------------------------------------

async function checkHealth() {
  log("Checking frontend...");
  try {
    const r = await fetch(FRONTEND_URL, { signal: AbortSignal.timeout(8_000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    log("  Frontend reachable at " + FRONTEND_URL);
  } catch (err) {
    throw new Error(
      `Frontend not reachable at ${FRONTEND_URL}: ${err.message}\n` +
      `  Ensure 'npm run dev' is running inside the fraud-console directory.`
    );
  }

  log("Checking backend...");
  const health = await apiGet("/health");
  if (!health || health.status !== "ok") {
    throw new Error(
      `Backend not healthy at ${BACKEND_URL}/health\n` +
      `  Ensure 'docker compose up -d' is running and all services are ready.`
    );
  }
  log("  Backend healthy at " + BACKEND_URL);

  log("Verifying canonical demo cases...");
  const case22 = await apiGet("/case/22");
  if (!case22) {
    throw new Error(
      `Case 22 not found. Run 'python scripts/seed_review_cases.py' to seed review cases.`
    );
  }
  const case21 = await apiGet("/case/21");
  if (!case21) {
    throw new Error(
      `Case 21 not found. Run 'python scripts/seed_review_cases.py' to seed review cases.`
    );
  }
  const case19 = await apiGet("/case/19");
  if (!case19) {
    warn("Case 19 not found - screenshot 09 (workflow audit trail) may be empty.");
  }
  log("  Cases 21 and 22 verified.");
}

// ---------------------------------------------------------------------------
// Pre-score the intake screenshot transaction via API
// ---------------------------------------------------------------------------

async function preScoreIntakeTransaction(txnId) {
  log(`Pre-scoring intake transaction: ${txnId}`);

  const payload = {
    transaction_id:    txnId,
    user_id:           "screenshot_user_001",
    merchant_id:       "screenshot_merchant_001",
    amount:            8500,
    currency:          "USD",
    payment_method:    "credit_card",
    timestamp:         "2026-05-14T02:30:00Z",
    country:           "RU",
    city:              "Moscow",
    merchant_category: "electronics",
    is_international:  true,
    device_id:         null,
    device_type:       "mobile",
    ip_address:        null,
  };

  let resp;
  try {
    resp = await apiPost("/predict", payload);
  } catch (err) {
    throw new Error(`POST /predict failed: ${err.message}`);
  }

  if (resp.status !== 200 && resp.status !== 202) {
    const body = await resp.text().catch(() => "");
    throw new Error(`POST /predict returned HTTP ${resp.status}: ${body}`);
  }

  log("  Transaction submitted. Polling for scored result...");

  for (let i = 0; i < POLL_MAX_ATTEMPTS; i++) {
    await sleep(POLL_INTERVAL_MS);
    const result = await apiGet(`/predictions/${txnId}`);
    if (result) {
      log(
        `  Scored on attempt ${i + 1}: ` +
        `decision=${result.decision}  risk_score=${result.risk_score}`
      );
      return result;
    }
    log(`  Attempt ${i + 1}/${POLL_MAX_ATTEMPTS} - not yet scored...`);
  }

  throw new Error(
    `Transaction ${txnId} was not scored within the polling window (${POLL_MAX_ATTEMPTS * POLL_INTERVAL_MS / 1000}s). ` +
    `Is the scoring consumer running?`
  );
}

// ---------------------------------------------------------------------------
// Navigation helper
// ---------------------------------------------------------------------------

async function nav(page, route) {
  await page.goto(`${FRONTEND_URL}${route}`, { waitUntil: "networkidle" });
  await sleep(AFTER_NAV_MS);
}

// ---------------------------------------------------------------------------
// Screenshot capture helper
// ---------------------------------------------------------------------------

async function capture(page, filename, description) {
  const dest = path.join(SCREENSHOTS_DIR, filename);
  await page.screenshot({ path: dest, fullPage: false });
  log(`[OK] ${filename}`);
  log(`     ${description}`);
}

// ---------------------------------------------------------------------------
// Scroll to a visible text anchor on the page
// ---------------------------------------------------------------------------

async function scrollToText(page, searchText, pixelFallback = 700) {
  try {
    const el = page.getByText(searchText, { exact: false }).first();
    await el.waitFor({ state: "visible", timeout: 6_000 });
    await el.scrollIntoViewIfNeeded();
    await sleep(AFTER_SCROLL_MS);
    return true;
  } catch {
    warn(`Text "${searchText}" not found for scroll anchor - using pixel scroll.`);
    await page.evaluate((px) => window.scrollBy(0, px), pixelFallback);
    await sleep(AFTER_SCROLL_MS);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Intake form field filling
//
// The intake form uses React controlled <input> elements wrapped in <label>
// elements with visible text content. Playwright's fill() clears existing
// content and types the new value, firing the React onChange handler.
// ---------------------------------------------------------------------------

async function fillInputByLabel(page, labelText, value) {
  const label = page
    .locator("label")
    .filter({ hasText: new RegExp(labelText, "i") })
    .first();
  const input = label.locator("input").first();
  try {
    await input.waitFor({ state: "visible", timeout: 5_000 });
    await input.fill(String(value));
  } catch {
    warn(`Could not fill field matching "${labelText}" - selector did not match.`);
  }
}

async function fillIntakeForm(page, txnId) {
  // --
  // Section A: Scoring Inputs
  // --
  await fillInputByLabel(page, "Amount",            "8500");
  await fillInputByLabel(page, "Timestamp",         "2026-05-14T02:30:00Z");
  await fillInputByLabel(page, "Payment Method",    "credit_card");
  await fillInputByLabel(page, "Country",           "RU");
  await fillInputByLabel(page, "Merchant Category", "electronics");
  await fillInputByLabel(page, "Device ID",         "");    // intentionally blank
  await fillInputByLabel(page, "Device Type",       "mobile");

  // International checkbox - label contains "Mark as cross-border" as display text
  try {
    const checkboxLabel = page
      .locator("label")
      .filter({ hasText: /Mark as cross-border/i })
      .first();
    const checkbox = checkboxLabel.locator('input[type="checkbox"]');
    await checkbox.waitFor({ state: "visible", timeout: 4_000 });
    const isChecked = await checkbox.isChecked();
    if (!isChecked) await checkbox.check();
  } catch {
    warn('Could not find or check the is_international checkbox.');
  }

  // --
  // Section B: Transaction Identity
  // --
  await fillInputByLabel(page, "Transaction ID", txnId);
  await fillInputByLabel(page, "User ID",        "screenshot_user_001");
  await fillInputByLabel(page, "Merchant ID",    "screenshot_merchant_001");
  await fillInputByLabel(page, "Currency",       "USD");

  // --
  // Section C: Investigation Context (hidden by default - must expand first)
  // --
  try {
    const toggleBtn = page.getByText("Show Investigation Context", { exact: true });
    await toggleBtn.waitFor({ state: "visible", timeout: 4_000 });
    await toggleBtn.click();
    await sleep(400);
    await fillInputByLabel(page, "City", "Moscow");
  } catch {
    warn("Could not expand Investigation Context section. City field not filled.");
  }
}

// ---------------------------------------------------------------------------
// Wait for a text to appear on the page with a configurable timeout
// ---------------------------------------------------------------------------

async function waitForText(page, text, timeoutMs = 15_000) {
  try {
    await page.getByText(text, { exact: false }).first().waitFor({
      state: "visible",
      timeout: timeoutMs,
    });
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Main capture sequence
// ---------------------------------------------------------------------------

async function captureAll(browser, txnId) {
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page    = await context.newPage();

  // Silence console noise from the Next.js dev server in the Playwright output
  page.on("console", () => {});
  page.on("pageerror", () => {});

  sep();

  // ------------------------------------------------------------------
  // 01: Overview - Fraud Intelligence Command Center
  // ------------------------------------------------------------------
  log("01/12  Overview - Fraud Intelligence Command Center");
  await nav(page, "/");
  await capture(
    page,
    "01_overview_command_center.png",
    "Live KPI strip, pipeline map, stale case pressure, status chips"
  );

  sep();

  // ------------------------------------------------------------------
  // 02: Risk Command Center
  // ------------------------------------------------------------------
  log("02/12  Risk Command Center");
  await nav(page, "/dashboard");
  await sleep(CHART_WAIT_MS); // allow Recharts to render
  await capture(
    page,
    "02_risk_command_dashboard.png",
    "Risk level verdict, decision mix chart, case intelligence stats, workflow health feed"
  );

  sep();

  // ------------------------------------------------------------------
  // 03: Transaction Intake - form filled, not submitted
  // ------------------------------------------------------------------
  log("03/12  Transaction Intake - filled form (not submitted)");
  await nav(page, "/intake");
  await fillIntakeForm(page, txnId);
  await sleep(500); // brief settle after form fill
  await capture(
    page,
    "03_transaction_intake.png",
    "Intake form with Case 22 profile: amount=8500, RU, credit_card, electronics, no device, international"
  );

  sep();

  // ------------------------------------------------------------------
  // 04: Scoring Result Handoff
  //
  // The intake page has a two-step flow:
  //   1. Click "Submit for Risk Scoring"  -> renders ConfirmationPanel
  //   2. Click "Confirm and Score"        -> submits to API, polls for result
  //
  // The transaction was pre-scored before navigating to /intake.
  // When the page polls GET /predictions/{txnId}, the pre-scored record
  // is returned on the first poll, producing the result state immediately.
  // ------------------------------------------------------------------
  log("04/12  Scoring Result Handoff");

  // Step 1: click the form submit button
  try {
    const submitBtn = page.getByText("Submit for Risk Scoring", { exact: true });
    await submitBtn.waitFor({ state: "visible", timeout: 5_000 });
    await submitBtn.click();
    log("  Form submitted - waiting for confirmation panel...");
  } catch {
    warn("Submit button not found. Attempting to find form and submit.");
    await page.locator('form').locator('button[type="submit"]').click();
  }

  // Step 2: click "Confirm and Score" in the confirmation panel
  try {
    const confirmBtn = page.getByText("Confirm and Score", { exact: true });
    await confirmBtn.waitFor({ state: "visible", timeout: 10_000 });
    log("  Confirmation panel visible. Clicking Confirm and Score...");
    await confirmBtn.click();
  } catch {
    warn("Confirmation panel did not appear. Capturing current page state for screenshot 04.");
    await capture(
      page,
      "04_scoring_result_handoff.png",
      "Scoring result - confirmation panel state (Confirm and Score not found)"
    );
    sep();
  }

  // Step 3: wait for the result panel
  // "Risk Scoring Complete" is the heading in ScoreResult component
  log("  Waiting for scoring result panel...");
  const resultAppeared = await waitForText(page, "Risk Scoring Complete", 25_000);
  if (resultAppeared) {
    await sleep(800);
    await capture(
      page,
      "04_scoring_result_handoff.png",
      "Scoring result: BLOCK decision, risk score, reason codes, Open Case Dossier link"
    );
  } else {
    // Timeout state is "Scoring In Progress" - still a valid screenshot showing the async flow
    warn("Result panel did not appear within timeout. Capturing current state.");
    warn("The scoring consumer may be slow. Screenshot 04 may show 'Scoring In Progress' state.");
    await capture(
      page,
      "04_scoring_result_handoff.png",
      "Scoring result - current page state (result or timeout state)"
    );
  }

  sep();

  // ------------------------------------------------------------------
  // 05: Review Queue
  // ------------------------------------------------------------------
  log("05/12  Review Queue - Analyst Workbench");
  await nav(page, "/queue");
  await capture(
    page,
    "05_review_queue_prioritization.png",
    "P0-P3 priority tiers, risk score bars, BLOCK red borders, decision and status badges"
  );

  sep();

  // ------------------------------------------------------------------
  // 06: Case Dossier - risk evidence (case 22)
  // ------------------------------------------------------------------
  log("06/12  Case Dossier - Risk Evidence (case 22)");
  await nav(page, "/cases/22");
  await capture(
    page,
    "06_case_dossier_risk_evidence.png",
    "Case 22 header: BLOCK badge, risk score 1.0, rule_flag=1, reason code tags"
  );

  sep();

  // ------------------------------------------------------------------
  // 07: AI Investigation Panel (case 22)
  //
  // Still on /cases/22 - scroll to the AI Investigation section.
  // Wait for the completed investigation to load (requires Ollama running).
  // Falls back gracefully if Ollama is unavailable.
  // ------------------------------------------------------------------
  log("07/12  AI Investigation Panel (case 22)");

  // Wait for a sign that the investigation report is loaded.
  // "Confirm Fraud" is the display label for CONFIRM_FRAUD recommendation.
  let investigationLoaded = await waitForText(page, "Confirm Fraud", 20_000);
  if (!investigationLoaded) {
    // Broader fallback: check for any investigation section content
    investigationLoaded = await waitForText(page, "Risk Factors", 8_000);
    if (!investigationLoaded) {
      warn(
        "AI investigation report not detected. Ollama may not be running. " +
        "Screenshot 07 may show pending or error state."
      );
    }
  }

  await scrollToText(page, "AI Investigation");
  await sleep(AFTER_SCROLL_MS);
  await capture(
    page,
    "07_ai_investigation_panel.png",
    "Case 22: AI investigation - CONFIRM_FRAUD, HIGH confidence, risk factors, rationale"
  );

  sep();

  // ------------------------------------------------------------------
  // 08: Analyst Verdict Panel (case 22)
  //
  // Still on /cases/22 - scroll to the Analyst Verdict section.
  // Case 22 is left unreviewed, so the form is in active (submittable) state.
  // Do NOT submit a verdict.
  // ------------------------------------------------------------------
  log("08/12  Analyst Verdict Panel (case 22) - active form, no submission");
  await scrollToText(page, "Analyst Verdict");
  await sleep(AFTER_SCROLL_MS);
  await capture(
    page,
    "08_analyst_verdict_panel.png",
    "Case 22: analyst verdict form - verdict dropdown, notes field, submit button (unsubmitted)"
  );

  sep();

  // ------------------------------------------------------------------
  // 09: Case Workflow Audit Trail (case 19)
  //
  // Case 19 has a mixed history: 4 FAILED events (pre-activation period)
  // and 2 SUCCESS events. This is the strongest workflow audit demo case.
  // ------------------------------------------------------------------
  log("09/12  Case Workflow Audit Trail (case 19) - mixed FAILED and SUCCESS events");
  await nav(page, "/cases/19");
  // Scroll to workflow section - try multiple text anchors
  const workflowFound = await scrollToText(page, "Workflow Automation");
  if (!workflowFound) {
    await scrollToText(page, "Automation Audit Trail");
  }
  await sleep(AFTER_SCROLL_MS);
  await capture(
    page,
    "09_case_workflow_audit_trail.png",
    "Case 19: workflow audit trail - FAILED rows (pre-activation) and SUCCESS rows visible"
  );

  sep();

  // ------------------------------------------------------------------
  // 10: False Positive Review Case (case 21)
  //
  // Case 21 shows a completed analyst verdict: REVIEW decision at 0.6,
  // rule_flag=0, FALSE_POSITIVE verdict with analyst notes (read state).
  // Scroll to the verdict panel to show the completed verdict context.
  // ------------------------------------------------------------------
  log("10/12  False Positive Review Case (case 21) - verdict in read state");
  await nav(page, "/cases/21");
  await scrollToText(page, "Analyst Verdict");
  await sleep(AFTER_SCROLL_MS);
  await capture(
    page,
    "10_false_positive_review_case.png",
    "Case 21: REVIEW decision, risk score 0.6, FALSE_POSITIVE verdict with analyst notes"
  );

  sep();

  // ------------------------------------------------------------------
  // 11: Workflow Events - Automation Audit Trail
  // ------------------------------------------------------------------
  log("11/12  Workflow Events - Automation Audit Trail");
  await nav(page, "/workflow/events");
  await sleep(CHART_WAIT_MS); // wait for event table and summary rail to render
  await capture(
    page,
    "11_workflow_events_audit_trail.png",
    "Full audit log: summary rail, 22 events, FAILED rows in red, SUCCESS rows with clean labels"
  );

  sep();

  // ------------------------------------------------------------------
  // 12: Reliability Metrics Center
  // ------------------------------------------------------------------
  log("12/12  Automation Reliability Center");
  await nav(page, "/workflow/metrics");
  await sleep(CHART_WAIT_MS); // wait for Recharts to fully render
  await capture(
    page,
    "12_reliability_metrics_center.png",
    "Degraded health verdict, SLO progress bars, failure spotlight, action/source breakdown charts"
  );

  sep();

  await context.close();
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main() {
  console.log("\nFraud Intelligence Console - Phase 11Q Screenshot Capture");
  console.log("=".repeat(60));
  console.log(`Frontend:     ${FRONTEND_URL}`);
  console.log(`Backend:      ${BACKEND_URL}`);
  console.log(`Output:       ${SCREENSHOTS_DIR}`);
  console.log(`Viewport:     ${VIEWPORT.width}x${VIEWPORT.height}`);
  console.log("=".repeat(60));
  console.log("");

  // Ensure output directory exists
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
    log(`Created output directory: ${SCREENSHOTS_DIR}`);
  } else {
    log(`Output directory exists: ${SCREENSHOTS_DIR}`);
  }

  console.log("");

  // Pre-flight checks
  try {
    await checkHealth();
  } catch (err) {
    fail(err.message);
    process.exit(1);
  }

  console.log("");

  // Pre-score the intake screenshot transaction before opening the browser
  const txnId = generateScreenshotTxnId();
  let preScoreResult;
  try {
    preScoreResult = await preScoreIntakeTransaction(txnId);
  } catch (err) {
    fail(err.message);
    process.exit(1);
  }

  if (!preScoreResult) {
    fail("Pre-score did not return a result. Aborting.");
    process.exit(1);
  }

  console.log("");

  // Launch browser
  log("Launching Chromium...");
  const browser = await chromium.launch({ headless: true });

  try {
    await captureAll(browser, txnId);
  } catch (err) {
    fail(`Screenshot capture failed: ${err.message}`);
    if (err.stack) console.error(err.stack);
    await browser.close();
    process.exit(1);
  }

  await browser.close();

  // Verify output
  const files = fs.readdirSync(SCREENSHOTS_DIR).filter((f) => f.endsWith(".png"));
  console.log("");
  console.log("=".repeat(60));
  log(`Screenshot package complete. ${files.length} PNG files in docs/screenshots/:`);
  files.sort().forEach((f) => log(`  ${f}`));
  console.log("=".repeat(60));
  console.log("");

  process.exit(0);
}

main().catch((err) => {
  fail(`Unhandled error: ${err.message}`);
  if (err.stack) console.error(err.stack);
  process.exit(1);
});
