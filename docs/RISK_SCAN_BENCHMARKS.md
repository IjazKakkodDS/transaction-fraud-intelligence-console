# Portfolio Risk Scan - Benchmark Evidence

## Purpose

This document records verified benchmark evidence for the **Portfolio Risk Scan** module of the
**Fraud Intelligence Console**.

All benchmarks described here are **local production-style synthetic benchmarks** executed
against fully synthetic transaction data in Docker Compose. They are not claims of real-world
bank production deployment, regulatory-approved fraud model performance, or live customer
transaction throughput.

The benchmark goal is to verify that the async Portfolio Risk Scan pipeline can complete
end-to-end at increasing scale: upload -> validate -> score -> persist -> summarize ->
paginate -> filter -> promote -> export, with no data loss, no OOM kills, and stable API
behavior throughout.

---

## Executive Benchmark Summary

| Scale | Status | Key Outcome | Notes |
|---|---|---|---|
| **1M rows** | Verified | COMPLETE, full export, all endpoints stable | Established baseline throughput |
| **2.5M rows** | Verified | COMPLETE after DB cleanup and streaming export | Postgres dead-space reclaim required first |
| **5M rows** | Verified | COMPLETE with hardened server-side streaming export | Initial export attempt failed; server-side cursor fix committed |
| **7.5M rows** | Verified | COMPLETE with chunked ingestion and dedup benchmark mode | Confirmed API heap stayed stable |
| **10M rows** | Verified | COMPLETE after result-query index hardening | Current verified local synthetic benchmark ceiling |

---

## Current Verified Capability Statement

> Verified 10M-transaction local production-style async Portfolio Risk Scan benchmark with persisted results, paginated analyst review, deep pagination, risk-tier filtering, frontend scan resume, recent scan loading, scan detail header, promote-to-case support, and hardened server-side streaming CSV export.

This statement reflects benchmarks completed on the local Docker Compose stack using fully
synthetic transaction data. It is not a claim of real-world bank deployment, regulatory approval,
or real-world fraud model performance.

---

## 10M Verification Summary

**Scan identifier**

| Field | Value |
|---|---|
| `scan_id` | `aa0971d2-bdb6-49c7-bac3-fa355aa161ad` |
| DB row id | 79 |
| Status | `COMPLETE` |
| `processed_rows` | 10,000,000 |
| `total_rows` | 10,000,000 |
| Input file | `C:\tmp\risk-scan-12d8u-10m.csv` |
| Input size | 754,587,572 bytes / 719.63 MiB |

**Benchmark environment**

| Variable | Value |
|---|---|
| `RISK_SCAN_MAX_ROWS` | `10000000` |
| `RISK_SCAN_CHUNK_SIZE` | `2000` |
| `RISK_SCAN_ENABLE_IN_MEMORY_DEDUP` | `false` |

`RISK_SCAN_ENABLE_IN_MEMORY_DEDUP=false` was used only because the synthetic benchmark generator
produced guaranteed-unique transaction IDs. Exact cross-chunk deduplication remains available for
normal scans by setting the variable to `true`.

**Processing**

| Metric | Value |
|---|---|
| Upload response | HTTP 202 in 5.79s |
| Started | 2026-06-01 01:34:37 UTC |
| Completed | 2026-06-01 03:18:13 UTC |
| Processing time | ~103m 35s |
| Average throughput | ~1,610 rows/sec |
| Early throughput | ~1.7k rows/sec |
| Late throughput | ~1.5k-1.6k rows/sec |

**Row classification**

| Category | Count |
|---|---:|
| Valid rows | 10,000,000 |
| Invalid rows | 0 |
| Skipped rows | 0 |

**Operational priority distribution**

| Tier | Count |
|---|---:|
| P0 | 0 |
| P1 | 8,420,051 |
| P2 | 0 |
| P3 | 1,579,949 |

**Exposure summary**

| Metric | Value |
|---|---:|
| Total portfolio exposure | $25,095,000,000.00 |
| Critical-tier exposure | $0.00 |
| High-tier exposure | $24,455,516,419.00 |

**Endpoint verification**

| Verification | Result |
|---|---|
| `GET /risk-scan/{id}/summary` | PASS, 0.008s |
| Page 1 results, `page_size=100` | PASS, 100 rows, 0.676s |
| Page 2 results | PASS, 100 rows, distinct from page 1, 0.247s |
| Deep page 1000 | PASS, 100 rows, 0.379s |
| P0 filter | PASS, total 0 |
| P1 filter | PASS, total 8,420,051, 4.188s |
| P2 filter | PASS, total 0 |
| P3 filter | PASS, total 1,579,949, 0.604s |
| Promote valid row | PASS, result `17725831` -> case `82`, HTTP 200 in 0.047s |
| Frontend query-param resume | PASS |
| Recent Scans panel | PASS, 10M scan appears at top |
| Scan Detail Header | PASS |
| Frontend result loading | PASS, observed `/results?page=1&page_size=100` |
| Browser console | No issues captured |

**Export verification**

| Metric | Value |
|---|---|
| HTTP status | 200 |
| Time-to-first-byte | 0.006987s |
| Duration | 113.63s |
| Downloaded file | `C:\tmp\risk-scan-12d8u-10m-export.csv` |
| Downloaded size | 1,718,562,740 bytes / 1,638.95 MiB |
| Line count | 10,000,001 including header |
| API RestartCount | 0 |
| OOMKilled | false |

**Memory, database, and disk**

| Metric | Value |
|---|---|
| API peak sampled during scan | ~915 MiB |
| API memory after export | ~216 MiB |
| Postgres memory after export | ~1.88 GiB |
| Temp upload cleanup | PASS, 0 `/tmp/riskscan_*.csv` files left |
| `portfolio_scan_results` rows after run | 22,752,000 |
| `portfolio_scan_results` total size | 19 GB |
| `portfolio_scan_results` index size | 13 GB |
| Database size | 19 GB |
| C: free after run | ~526.5 GB |
| Docker local volumes | 21 GB |

**Regression checks**

| Check | Result |
|---|---|
| `/health` | PASS |
| Existing 5M scan readable | PASS, `4f3438f7-cabf-49c8-848f-5cb2d717f48f` |
| Existing 7.5M scan readable | PASS, `81ca48f2-e708-48b3-aa13-808989291fc0` |

---

## Prior Large-Scale Verification Summaries

### 7.5M Verification Summary

| Metric | Value |
|---|---|
| `scan_id` | `81ca48f2-e708-48b3-aa13-808989291fc0` |
| DB row id | 78 |
| Status | `COMPLETE` |
| Processed rows | 7,500,000 / 7,500,000 |
| Valid / invalid / skipped | 7,500,000 / 0 / 0 |
| Priority counts | P0 0, P1 6,315,038, P2 0, P3 1,184,962 |
| Processing time | ~76m 24s |
| Average throughput | ~1,636 rows/sec |
| Export | HTTP 200, 98.64s, TTFB ~0.006s |
| Export size / line count | 1.22 GiB / 7,500,001 lines |
| API stability | RestartCount 0, OOMKilled false |

### 5M Verification Summary

| Metric | Value |
|---|---|
| `scan_id` | `4f3438f7-cabf-49c8-848f-5cb2d717f48f` |
| DB row id | 68 |
| Status | `COMPLETE` |
| Processed rows | 5,000,000 / 5,000,000 |
| Valid / invalid / skipped | 5,000,000 / 0 / 0 |
| Priority counts | P0 749,839, P1 472,412, P2 0, P3 3,777,749 |
| Total exposure | $6,982,753,484.22 |
| Critical exposure | $5,058,942,542.95 |
| Hardened export | HTTP 200, 61.46s, TTFB 0.0055s |
| Export size / line count | 824.14 MB / 5,000,001 lines |
| API stability | RestartCount 0, OOMKilled false |

---

## Export Hardening Evidence

The 5M export path required dedicated hardening before the full export succeeded.

### Before hardening

| Metric | Value |
|---|---|
| Attempt duration | 1,614.8s (~26m 55s) |
| Bytes downloaded | 0 |
| Client error | `curl: Empty reply from server` |
| API restart | Yes |
| `OOMKilled` | false |
| Root cause | Export endpoint delegated to paginated result retrieval, causing repeated count/offset work before data was flushed |

### After hardening

The export path now uses a server-side cursor and `StreamingResponse`. The CSV header is yielded
immediately, then rows are fetched in bounded batches from Postgres. This keeps Python memory
bounded and avoids using analyst UI pagination for full-file export.

---

## Bottleneck and Fix Timeline

| Phase | Bottleneck Observed | Fix Applied |
|---|---|---|
| 500k initial test | Summary recomputation re-scanned accumulated rows after each chunk, producing O(n^2) behavior | Running aggregate counters introduced, O(1) per chunk |
| 2.5M scale-up | Postgres table bloat from prior verification churn slowed reads | Cleanup and vacuum stabilized the table for the next run |
| 2.5M export | Export buffered too much result data before flushing | `StreamingResponse` introduced |
| 5M initial export | Export still routed through paginated helper and timed out before first byte | Server-side cursor export replaced pagination helper (commit `8b47d9e`) |
| Cross-session resume | Completed scans were lost from frontend state after page reload | Scan resume by public `scan_id` UUID added (commit `ad82cfe`) |
| Large upload heap | Async upload and processing needed bounded memory at higher scale | Temp-file spooling plus chunked CSV ingestion implemented (commit `6f97224`) |
| Dedup memory | Cross-scan Python set grew O(N) for duplicate detection | `RISK_SCAN_ENABLE_IN_MEMORY_DEDUP=false` benchmark mode added for guaranteed-unique synthetic IDs (commit `d8d64a7`) |
| 7.5M query scale | Page and filter queries scanned by `scan_id` then sorted millions of rows; deep page spilled to disk | Ordered composite indexes with `NULLS LAST` added (commit `cdf4874`) |
| 10M verification | Needed full end-to-end proof after ingestion/export/dedup/index hardening | 10M local synthetic benchmark passed end-to-end |

---

## Architecture Lessons

**Separate UI pagination from full export paths.**
The `/results` endpoint is designed for analyst page-by-page review. Full exports use a dedicated
server-side cursor path so millions of rows can stream without materializing the result set in
Python.

**Match indexes to the exact result ordering.**
The result query orders by `risk_score DESC NULLS LAST, row_number ASC`. At 7.5M, indexes without
`NULLS LAST` still forced large sort nodes. Adding ordered composite indexes matching the exact
query shape eliminated the sort and disk spill before the 10M run.

**Keep benchmark dedup mode explicit.**
Exact cross-chunk duplicate detection remains the default for normal scans. Benchmark mode disables
cross-chunk in-memory dedup only when synthetic transaction IDs are guaranteed unique.

**Keep large benchmark artifacts out of Git.**
Generated input CSVs and export verification CSVs can reach multiple GiB. They belong on local
disk or object storage, not in the repository.

---

## Known Limitations

- **Synthetic/local benchmark only.** All scale figures were produced against synthetic data on a
  local Docker Compose stack. No real customer data was used. No claim of regulatory-approved
  fraud model performance or bank-production deployment is made.

- **Large local DB footprint.** After accumulated 5M, 7.5M, and 10M scans, the local database
  reached about 19 GB and `portfolio_scan_results` reached 22,752,000 rows. Repeated future
  benchmark runs need an archive, cleanup, or retention strategy.

- **P1 count cost remains visible.** P1 filtering is indexed and correct, but the paginated
  response still computes a total count over 8,420,051 matching rows. This took 4.188s during
  10M verification.

- **Auth/RBAC/deployment hardening remain future work.** The system currently has no production
  authentication layer on scan endpoints. Deployment hardening remains out of scope for the local
  benchmark.

- **Generated artifacts stay untracked.** Generated benchmark CSVs and export files must remain
  untracked. Generator and verification scripts should not be committed unless explicitly scoped.

- **Benchmark environment may need reset.** `.env` may be left in 10M benchmark mode after scale
  verification. Reset row caps and dedup settings for normal development if needed.

---

## Next Recommended Phases

1. **Post-10M DB cleanup/archive strategy.** Preserve evidence scans while defining what can be
   archived, exported, or purged before repeated benchmark work.

2. **Scan history/detail UX polish.** Improve large-scan history browsing, scan detail context,
   result detail drawer, filtered exports, and scan report generation.

3. **Schema mapping and data quality layer.** Support varied transaction file layouts, column
   mapping, quality scoring, and rejected-row reporting.

4. **Richer synthetic banking dataset generator.** Add user baselines, merchants, device variety,
   velocity patterns, and fraud injections to improve benchmark realism without claiming real-world
   fraud model performance.

5. **Enhanced fraud decision engine and Case Dossier 2.0.** Add per-dimension decision evidence,
   richer investigation brief hardening, and better analyst traceability.

6. **Workflow, audit, and governance hardening.** Improve operational audit controls and workflow
   governance surfaces.

7. **Observability, durable worker architecture, auth/RBAC, and deployment/demo-safe mode.** Move
   from local benchmark maturity toward deployable operational readiness.

8. **Final portfolio case study/demo video.** Package the verified local synthetic benchmark and
   product walkthrough without overstating production claims.

---

## Git and Artifact Policy

| Artifact type | Policy |
|---|---|
| Generated benchmark input CSVs (`scripts/test_*scan.csv`, `C:\tmp\risk-scan-*.csv`) | Ignored or kept outside the repo; regenerate locally when needed |
| Generated export verification CSVs (`scripts/*_export.csv`, `C:\tmp\risk-scan-*-export.csv`) | Ignored or kept outside the repo; do not commit |
| Generator scripts (`scripts/generate_*_csv.py`) | Kept locally untracked; not committed unless explicitly scoped |
| Verification scripts (`scripts/verify_*.py`, `scripts/verify_*.mjs`) | Kept locally untracked; not committed unless explicitly scoped |
| Phase evidence directories (`docs/evidence/`, `scripts/evidence/`) | Ignored via `.gitignore`; kept locally for reference only |
| Benchmark results (this document) | Tracked in `docs/RISK_SCAN_BENCHMARKS.md` as lightweight Markdown, no embedded data |

Benchmark evidence should always be captured as lightweight Markdown rather than committed data
files. Large generated artifacts belong on local disk or a dedicated object store, never in the
Git repository.
