# Portfolio Risk Scan — Benchmark Evidence

## Purpose

This document records verified benchmark evidence for the **Portfolio Risk Scan** module of the
**Fraud Intelligence Console** (Project 2 — Real-Time Fraud Triage System).

All benchmarks described here are **local production-style benchmarks** executed against fully
synthetic transaction data. They are not claims of real-world bank production deployment,
regulatory-approved fraud model performance, or live customer transaction throughput.

The goal of these benchmarks is to verify that the async Portfolio Risk Scan pipeline can
complete end-to-end at increasing scale: upload → validate → score → persist → summarise →
paginate → filter → promote → export — with no data loss, no OOM kills, and stable API behaviour
throughout.

---

## Executive Benchmark Summary

| Scale | Status | Key Outcome | Notes |
|---|---|---|---|
| **1M rows** | ✅ Verified | COMPLETE, full export, all endpoints stable | Established baseline throughput |
| **2.5M rows** | ✅ Verified | COMPLETE after DB cleanup and streaming export | Postgres dead-space reclaim required first |
| **5M rows** | ✅ Verified | COMPLETE with hardened server-side streaming export | Initial export attempt failed; server-side cursor fix committed |
| **7.5M rows** | ⏳ Future target | Not yet attempted | Chunked CSV ingestion hardening recommended first |
| **10M rows** | ⏳ Future target | Not yet attempted | Depends on chunked ingestion and 7.5M verification |

---

## 5M Verification Summary

**Scan identifier**

| Field | Value |
|---|---|
| `scan_id` | `4f3438f7-cabf-49c8-848f-5cb2d717f48f` |
| DB row id | 68 |
| Status | `COMPLETE` |
| `processed_rows` | 5,000,000 |
| `total_rows` | 5,000,000 |

**Row classification**

| Category | Count |
|---|---|
| Valid rows | 5,000,000 |
| Invalid rows | 0 |
| Skipped rows | 0 |

**Risk tier distribution**

| Tier | Count |
|---|---|
| P0 — Critical | 749,839 |
| P1 — High | 472,412 |
| P2 — Medium | 0 |
| P3 — Low | 3,777,749 |

**Exposure summary**

| Metric | Value |
|---|---|
| Total portfolio exposure | $6,982,753,484.22 |
| Critical-tier exposure | $5,058,942,542.95 |
| High-tier exposure | $401,721,715.91 |

**Endpoint verification (post-COMPLETE)**

| Verification | Result |
|---|---|
| `GET /risk-scan/{id}/status` — COMPLETE | ✅ |
| `GET /risk-scan/{id}/summary` — counts and exposures correct | ✅ |
| `GET /risk-scan/{id}/results?page=1&page_size=100` — page 1 returns data | ✅ |
| `GET /risk-scan/{id}/results?page=2&page_size=100` — page 2 distinct from page 1 | ✅ |
| `GET /risk-scan/{id}/results?tier=P0` — P0 filter returns 749,839 rows | ✅ |
| `GET /risk-scan/{id}/results?tier=P1` — P1 filter returns 472,412 rows | ✅ |
| `GET /risk-scan/{id}/results?tier=P3` — P3 filter returns 3,777,749 rows | ✅ |
| `POST /risk-scan/{id}/promote/{result_id}` — promote VALID row to case | ✅ |
| Frontend scan resume — completed scan ID loads without re-upload | ✅ |
| `GET /risk-scan/{id}/export` — hardened streaming export (see below) | ✅ |
| `GET /health` — API healthy throughout | ✅ |

---

## Export Hardening Evidence

The 5M export path required a dedicated hardening fix before the full export succeeded.

### Before hardening (initial 5M export attempt)

| Metric | Value |
|---|---|
| Attempt duration | 1,614.8 s (~26 min 55 s) |
| Bytes downloaded | 0 |
| Client error | `curl: Empty reply from server` |
| API restart | Yes (container recycled after OOM-adjacent failure) |
| `OOMKilled` | false |
| Root cause | Export endpoint delegated to `get_scan_results_paginated`, which issued a `COUNT(*)` + repeated `OFFSET` queries — each page required a full-table scan; the connection timed out before any data was flushed |

### After hardening — commit `8b47d9e Harden risk scan CSV export`

| Metric | Value |
|---|---|
| HTTP status | 200 |
| Total duration | 61.46 s |
| Time-to-first-byte (TTFB) | 0.0055 s |
| Downloaded file size | 864,177,976 bytes / **824.14 MB** |
| Line count | **5,000,001** (header + 5,000,000 data rows) |
| API `RestartCount` | 0 |
| `OOMKilled` | false |
| Exit code | 0 |

The fix replaced the paginated helper with a `server-side cursor` query that streams rows
directly from Postgres in a single forward scan. The CSV header is yielded immediately (yielding
TTFB < 6 ms), then data rows are flushed in 5,000-row batches via `StreamingResponse`. Peak API
container RAM remained stable throughout (≤ 2.2 GiB against a 7.4 GiB limit).

---

## Bottleneck and Fix Timeline

| Phase | Bottleneck Observed | Fix Applied |
|---|---|---|
| 500k initial test | Summary recomputation re-scanned all accumulated rows after each chunk, producing O(n²) behaviour | Running aggregate counters introduced — O(1) per chunk |
| 2.5M scale-up | Postgres `portfolio_scan_results` had accumulated ~5M dead tuples (≈ 2 GB of bloat) from prior verification deletes; table reads slowed noticeably | `TRUNCATE` + `VACUUM ANALYZE` reclaimed dead space; table returned to 88 kB |
| 2.5M export | `GET /risk-scan/{id}/export` buffered the full result set in memory before flushing | Export replaced with `StreamingResponse`; rows yielded in 5,000-row batches (commit `671d9cd`) |
| 5M initial export | Hardened streaming export still routed through `get_scan_results_paginated`, which issued a `COUNT(*)` + repeated `LIMIT/OFFSET` queries — connection timed out after 26 min with zero bytes transferred | Server-side cursor export replaced pagination helper entirely (commit `8b47d9e`) |
| Cross-session resume | Completed 5M scan was inaccessible in the frontend after page reload; analysts had to re-upload | Scan resume by public `scan_id` UUID added to frontend (commit `ad82cfe`) |
| Git artifact hygiene | Generated benchmark input CSVs (up to 409 MB) and export verification CSVs (up to 824 MB) were accumulating untracked and risked accidental commit | `.gitignore` rules added for `scripts/test_*scan.csv`, `scripts/*_export.csv`, `docs/evidence/`, `scripts/evidence/` (commit `2cb1b84`) |

---

## Architecture Lessons

**Separate UI pagination from full export paths.**
The `/results` endpoint — designed for analyst page-by-page review — is not appropriate for
driving a full export of millions of rows. Routing the export through the same paginated helper
produced repeated full-table scans and `OFFSET`-based seeks that grow O(n) per page.

**Avoid `OFFSET` pagination for large exports.**
At 5M rows with a page size of 500, a naive `LIMIT/OFFSET` approach requires 10,000 separate
queries, each scanning progressively deeper into the table. For export, a single forward cursor
is orders of magnitude more efficient.

**Stream from the database with a server-side cursor.**
A server-side cursor opens one query, iterates forward, and closes. No full result set is
materialised in Python at any point. For 5M rows at ~165 bytes/row this avoids holding ~800 MB
of text in memory simultaneously.

**Yield the CSV header immediately to establish TTFB.**
`StreamingResponse` begins flushing as soon as the first `yield` occurs. Emitting the header
row first (< 1 KB) gives clients a valid TTFB under 10 ms regardless of how long the data
rows take, and confirms to proxies/load-balancers that the connection is live.

**Keep memory bounded with fixed batch sizes.**
Fetching 5,000 rows per batch caps the per-batch memory footprint at roughly 1 MB of Python
objects plus the serialised CSV bytes. Total peak API RAM remained ≤ 2.2 GiB throughout the
5M export (against a 7.4 GiB container limit).

**Preserve scan resume by stable public UUID.**
Committing to a stable, shareable `scan_id` UUID means a completed scan can be loaded by any
analyst session — or re-examined days later — without re-uploading the source CSV. This is
especially important for large scans that take 50+ minutes to complete.

**Keep large benchmark artifacts out of Git.**
Generated input CSVs for scale testing (100k–5M rows) range from 8 MB to 409 MB. Export
verification files can reach 824 MB. None of these belong in version control. Targeted
`.gitignore` patterns prevent accidental staging while leaving generator and verification
scripts available for future re-runs.

---

## Current Verified Capability Statement

> Verified 5M-transaction local production-style async Portfolio Risk Scan benchmark with
> persisted results, paginated analyst review, risk-tier filtering, frontend scan resume,
> promote-to-case support, and hardened server-side streaming CSV export.

This statement reflects benchmarks completed on the local Docker Compose stack using fully
synthetic transaction data. It is not a claim of real-world bank deployment or live customer
throughput.

---

## Known Limitations

- **Synthetic/local benchmark only.** All scale figures were produced against synthetic data on
  a local Docker Compose stack. No real customer data was used. No claim of regulatory-approved
  fraud model performance or bank-production deployment is made.

- **7.5M and 10M not yet verified.** These are future targets. Neither scale has been attempted.
  Completion is not guaranteed without additional ingestion-path hardening.

- **Upload/input path may need chunked ingestion before larger scans.** The current upload
  reads the entire CSV into memory as `file_bytes` before processing begins. At 5M rows this
  peaks at approximately 1.9 GiB of API container RAM. For 7.5M+ rows, true chunked CSV
  ingestion — where the file is read and processed in streaming chunks without holding all
  bytes in memory simultaneously — is recommended before attempting the next scale step.

- **`seen_transaction_ids` set grows with scan size.** The deduplication set accumulates one
  entry per processed row. At 5M rows this consumes approximately 320 MB of Python heap. For
  larger scans a Bloom filter or database-backed deduplication check may be preferable.

- **Auth/RBAC/deployment hardening remain future work.** The system currently has no
  authentication layer on scan endpoints. For any deployment beyond a local development
  environment, analyst authentication, role-based access control, and hardened network
  boundaries would be required.

- **Large generated CSVs are intentionally ignored and must not be committed.** The `.gitignore`
  rules added in commit `2cb1b84` prevent this, but the generator scripts that produce these
  files remain available locally for future benchmark runs.

---

## Next Recommended Benchmark Steps

1. **Chunked CSV ingestion hardening.** Refactor `process_portfolio_scan_job` to accept the
   source CSV as a stream rather than a pre-loaded `file_bytes` blob. This removes the
   memory ceiling imposed by holding the full file in RAM and is the primary prerequisite
   for the 7.5M and 10M targets.

2. **`seen_transaction_ids` deduplication scaling.** Evaluate replacing the in-process Python
   `set` with a Bloom filter or a temporary DB-backed check to cap per-scan memory growth.

3. **7.5M verification.** Once chunked ingestion is in place, generate a 7.5M-row synthetic
   CSV, raise `RISK_SCAN_MAX_ROWS` to 7,500,000, and run the full verification protocol:
   status → summary → paginated results → filter → promote → streaming export.

4. **10M verification.** Contingent on 7.5M passing without incident.

5. **Update this document** after each successful scale step, recording the scan UUID,
   throughput, timing, and any new bottlenecks encountered.

---

## Git and Artifact Policy

| Artifact type | Policy |
|---|---|
| Generated benchmark input CSVs (`scripts/test_*scan.csv`) | Ignored via `.gitignore`; regenerate locally with `scripts/generate_*_csv.py` |
| Generated export verification CSVs (`scripts/*_export.csv`) | Ignored via `.gitignore`; discard after visual spot-check |
| Generator scripts (`scripts/generate_*_csv.py`) | Kept locally untracked; not committed unless explicitly scoped |
| Verification scripts (`scripts/verify_*.py`, `scripts/verify_*.mjs`) | Kept locally untracked; not committed unless explicitly scoped |
| Phase evidence directories (`docs/evidence/`, `scripts/evidence/`) | Ignored via `.gitignore`; kept locally for reference only |
| Benchmark results (this document) | Tracked in `docs/RISK_SCAN_BENCHMARKS.md` — lightweight Markdown, no embedded data |

Benchmark evidence should always be captured as lightweight Markdown rather than committed data
files. Large generated artifacts belong on local disk or a dedicated object store, never in
the Git repository.
