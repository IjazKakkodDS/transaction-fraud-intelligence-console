#!/usr/bin/env node
"use strict";

/**
 * Phase 20L — Targeted screenshot refresh for three stale screenshots:
 *   01_overview_command_center.png  (stale: missing Guided Investigation Command Panel)
 *   06_case_dossier_evidence.png    (stale: missing Model Attribution panel)
 *   07_ai_investigation_panel.png   (stale: pre-attribution layout)
 *
 * Run from project root:
 *   node scripts/capture_screenshots_20l.js
 *
 * Prerequisites:
 *   - Docker Compose stack running:  docker compose up -d
 *   - Frontend dev server running:   cd fraud-console && npm run dev
 *   - Case 22 present in DB (canonical showcase case)
 *   - API rebuilt with Phase 20H code (GET /cases/{case_id}/explain must return 200)
 */

const { chromium } = require("playwright");
const fs   = require("fs");
const path = require("path");

const FRONTEND_URL    = "http://localhost:3000";
const BACKEND_URL     = "http://localhost:8000";
const SCREENSHOTS_DIR = path.join(__dirname, "..", "docs", "screenshots");

// Timing constants
const AFTER_NAV_MS    = 2000;
const AFTER_SCROLL_MS = 1200;
const CHART_WAIT_MS   = 2500;

function log(msg)  { console.log(`[20L] ${msg}`); }
function warn(msg) { console.warn(`[20L] WARN: ${msg}`); }
function sep()     { console.log("[20L] " + "-".repeat(60)); }

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function apiGet(urlPath) {
  try {
    const resp = await fetch(`${BACKEND_URL}${urlPath}`, { signal: AbortSignal.timeout(10_000) });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

async function nav(page, route) {
  await page.goto(`${FRONTEND_URL}${route}`, { waitUntil: "networkidle" });
  await sleep(AFTER_NAV_MS);
}

async function capture(page, filename, description) {
  const dest = path.join(SCREENSHOTS_DIR, filename);
  await page.screenshot({ path: dest, fullPage: false });
  const stat = fs.statSync(dest);
  log(`[OK] ${filename}  (${Math.round(stat.size / 1024)} KB)`);
  log(`     ${description}`);
}

async function waitForText(page, text, timeoutMs = 15_000) {
  try {
    await page.getByText(text, { exact: false }).first().waitFor({ state: "visible", timeout: timeoutMs });
    return true;
  } catch {
    return false;
  }
}

async function scrollToElement(page, locator, extraPx = 0) {
  try {
    await locator.waitFor({ state: "visible", timeout: 10_000 });
    await locator.scrollIntoViewIfNeeded();
    if (extraPx !== 0) {
      await page.evaluate((px) => window.scrollBy(0, px), extraPx);
    }
    await sleep(AFTER_SCROLL_MS);
    return true;
  } catch {
    return false;
  }
}

async function scrollToText(page, text, extraPx = 0) {
  const el = page.getByText(text, { exact: false }).first();
  return scrollToElement(page, el, extraPx);
}

// ---------------------------------------------------------------------------
// Pre-flight checks
// ---------------------------------------------------------------------------

async function preflight() {
  log("Checking frontend...");
  try {
    const r = await fetch(FRONTEND_URL, { signal: AbortSignal.timeout(8_000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    log("  Frontend OK at " + FRONTEND_URL);
  } catch (err) {
    throw new Error(`Frontend not reachable: ${err.message}. Run: cd fraud-console && npm run dev`);
  }

  log("Checking backend health...");
  const health = await apiGet("/health");
  if (!health || health.status !== "ok") {
    throw new Error(`Backend not healthy at ${BACKEND_URL}. Run: docker compose up -d`);
  }
  log("  Backend OK");

  log("Checking explain endpoint (Phase 20H)...");
  const explain = await apiGet("/cases/22/explain");
  if (!explain || !explain.features) {
    throw new Error(
      "GET /cases/22/explain returned no data. " +
      "Rebuild the API container: docker compose build api && docker compose up -d api"
    );
  }
  log(`  Explain endpoint OK — ${explain.features.length} features returned`);

  log("Checking canonical demo cases...");
  const case22 = await apiGet("/case/22");
  if (!case22) throw new Error("Case 22 not found. Run: POST /demo/seed or python scripts/demo_seed.py");
  log(`  Case 22: decision=${case22.decision} score=${case22.risk_score}`);
}

// ---------------------------------------------------------------------------
// Capture sequence
// ---------------------------------------------------------------------------

async function captureAll(browser) {
  // -------------------------------------------------------------------------
  // 01: Overview — Guided Investigation Command Panel
  // Viewport 1440x900 — matches existing file dimensions
  // The Guided Investigation Command Panel is the first content block after
  // the page header, so it should be fully visible at the top of the viewport.
  // -------------------------------------------------------------------------
  sep();
  log("01/03  Overview — Guided Investigation Command Panel");
  log("       Viewport: 1440x900 (matching existing file)");

  const ctx01  = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page01 = await ctx01.newPage();
  page01.on("console", () => {});
  page01.on("pageerror", () => {});

  await nav(page01, "/");

  // Wait for key elements confirming the Guided Investigation panel has rendered
  const panelLoaded = await waitForText(page01, "Launch Guided Investigation", 12_000);
  if (!panelLoaded) {
    warn("'Launch Guided Investigation' CTA not found within timeout. Capturing current state.");
  }

  // Allow charts and KPI strip to settle
  await sleep(CHART_WAIT_MS);

  await capture(
    page01,
    "01_overview_command_center.png",
    "Guided Investigation Command Panel: CTA, six capability cards, workflow path strip; KPI strip above"
  );
  await ctx01.close();

  // -------------------------------------------------------------------------
  // 06: Case Dossier — Model Attribution panel
  // Viewport 1600x1400 — matches existing file dimensions
  // Scroll so the Model Attribution panel (with contribution bars) is clearly
  // visible. Some evidence context from the intelligence groups above is
  // preserved in the viewport.
  // -------------------------------------------------------------------------
  sep();
  log("06/03  Case Dossier — Model Attribution panel (case 22)");
  log("       Viewport: 1600x1400 (matching existing file)");

  const ctx06  = await browser.newContext({ viewport: { width: 1600, height: 1400 } });
  const page06 = await ctx06.newPage();
  page06.on("console", () => {});
  page06.on("pageerror", () => {});

  await nav(page06, "/cases/22");

  // Wait for Model Attribution panel to load with feature data (not skeleton)
  // We look for "Baseline model feature contributions" heading in the loaded state
  const attrLoaded = await waitForText(page06, "Baseline model feature contributions", 15_000);
  if (!attrLoaded) {
    warn("Model Attribution heading not found. Panel may be in loading or error state.");
    // Also check for contribution bars via the "Increases risk" legend
    await waitForText(page06, "Increases risk", 5_000);
  }

  // Scroll the Model Attribution panel into view. Using the section label text
  // "Model Attribution" as the anchor. Scroll up a bit (-100px) to show the
  // section label and the evidence group above it.
  const attrScrolled = await scrollToText(page06, "Baseline model feature contributions", -80);
  if (!attrScrolled) {
    warn("Could not scroll to Model Attribution — trying fallback scroll.");
    await page06.evaluate(() => window.scrollBy(0, 900));
    await sleep(AFTER_SCROLL_MS);
  }

  // Extra settle for bar animations
  await sleep(800);

  await capture(
    page06,
    "06_case_dossier_evidence.png",
    "Case 22 Model Attribution: XGBoost TreeSHAP feature contributions ranked by magnitude with direction bars"
  );
  await ctx06.close();

  // -------------------------------------------------------------------------
  // 07: AI Investigation Panel
  // Viewport 1600x1600 — matches existing file dimensions
  // Navigate to case 22, scroll to AI Investigation section.
  // Use existing investigation data only — no Ollama call.
  // -------------------------------------------------------------------------
  sep();
  log("07/03  AI Investigation Panel (case 22)");
  log("       Viewport: 1600x1600 (matching existing file)");

  const ctx07  = await browser.newContext({ viewport: { width: 1600, height: 1600 } });
  const page07 = await ctx07.newPage();
  page07.on("console", () => {});
  page07.on("pageerror", () => {});

  await nav(page07, "/cases/22");

  // Wait for AI investigation data to load
  const invLoaded = await waitForText(page07, "Confirm Fraud", 20_000);
  if (!invLoaded) {
    warn("'Confirm Fraud' recommendation not found — investigation may not be COMPLETE.");
    await waitForText(page07, "AI Investigation", 5_000);
  }

  // Scroll to the AI Investigation panel, backing up 80px to show the heading
  const invScrolled = await scrollToText(page07, "AI Investigation", -80);
  if (!invScrolled) {
    warn("Could not scroll to AI Investigation — trying fallback.");
    await page07.evaluate(() => window.scrollBy(0, 1400));
    await sleep(AFTER_SCROLL_MS);
  }

  await sleep(600);

  await capture(
    page07,
    "07_ai_investigation_panel.png",
    "Case 22: AI Investigation panel — CONFIRM_FRAUD, HIGH confidence, risk factors, rationale, agent_version"
  );
  await ctx07.close();
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main() {
  console.log("\nPhase 20L — Targeted Screenshot Refresh");
  console.log("=".repeat(60));
  console.log(`Frontend:     ${FRONTEND_URL}`);
  console.log(`Backend:      ${BACKEND_URL}`);
  console.log(`Output:       ${SCREENSHOTS_DIR}`);
  console.log("=".repeat(60));
  console.log("");

  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }

  try {
    await preflight();
  } catch (err) {
    console.error(`[20L] PRE-FLIGHT FAILED: ${err.message}`);
    process.exit(1);
  }

  console.log("");
  log("Launching Chromium...");
  const browser = await chromium.launch({ headless: true });

  try {
    await captureAll(browser);
  } catch (err) {
    console.error(`[20L] CAPTURE FAILED: ${err.message}`);
    if (err.stack) console.error(err.stack);
    await browser.close();
    process.exit(1);
  }

  await browser.close();

  sep();
  log("Screenshot refresh complete.");
  console.log("=".repeat(60));
  console.log("");
  process.exit(0);
}

main().catch((err) => {
  console.error(`[20L] Unhandled error: ${err.message}`);
  process.exit(1);
});
