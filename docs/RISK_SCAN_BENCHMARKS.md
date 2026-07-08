# Portfolio Risk Scan - Benchmark Evidence

## Purpose

This document records verified benchmark evidence for the **Portfolio Risk Scan** module of the
**Fraud Intelligence Console**.

All benchmarks described here are **local production-style synthetic benchmarks** executed
against fully synthetic transaction data in Docker Compose.

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
| **10M rows** | Verified | COMPLETE after result-query index hardening | Current verified controlled synthetic benchmark ceiling |

---

## Benchmark Evidence Pack

### Benchmark Scope

This evidence pack consolidates already documented local benchmark evidence for the Portfolio
Risk Scan and rich synthetic banking scenario layer. It does not introduce new scans or new
performance claims. The evidence covers synthetic transaction upload, validation, async
processing, persistence, pagination, filtering, promotion, export, rich reason-code rendering,
and generated artifact hygiene.

### Local Environment Boundary

Benchmarks were validated in a local production-style Docker Compose environment using synthetic
transaction data. The results demonstrate local system behavior under controlled benchmark
conditions. Deployment to an institution would require institution-specific validation, security
review, access controls, monitoring, data governance, and operational approval.

### Consolidated Evidence Table

| Evidence Item | Dataset size | Input type | Processing mode | Result | Key metrics | Source / reference doc |
|---|---:|---|---|---|---|---|
| Legacy 10k regression reference | 10,000 rows | Legacy synthetic CSV | Portfolio risk scan regression | Passed | P0 1,546 / P1 913 / P2 0 / P3 7,541; no rich boost applied | `docs/RICH_SYNTHETIC_BANKING_SCHEMA.md` |
| Early scale ramp | 50k rows | Legacy synthetic CSV | Async portfolio scan | Verified | Detailed numeric metrics are not preserved in current docs | Implementation progress reflected in public README and benchmark documentation |
| Early scale ramp | 100k rows | Legacy synthetic CSV | Async portfolio scan | Verified | Detailed numeric metrics are not preserved in current docs | Implementation progress reflected in public README and benchmark documentation |
| Intermediate scale ramp | 250k rows | Legacy synthetic CSV | Async portfolio scan | Verified | Detailed numeric metrics are not preserved in current docs | Implementation progress reflected in public README and benchmark documentation |
| Bottleneck discovery checkpoint | 500k rows | Legacy synthetic CSV | Async portfolio scan | Verified after summary optimization | Exposed O(n^2) summary recomputation; running aggregate counters introduced | Bottleneck timeline below |
| Major scale benchmark | 1M rows | Legacy synthetic CSV | Async portfolio scan | Verified | COMPLETE, full export, all endpoints stable; detailed numeric metrics are not preserved in current docs | Executive summary above |
| Table-bloat and export-risk checkpoint | 2.5M rows | Legacy synthetic CSV | Async portfolio scan | Verified after database cleanup | Postgres dead-space reclaim required; streaming export introduced | Executive summary above, bottleneck timeline below |
| Export hardening checkpoint | 5,000,000 rows | Legacy synthetic CSV | Async portfolio scan with hardened export | Passed | Scan `4f3438f7-cabf-49c8-848f-5cb2d717f48f`; 5,000,000 / 0 / 0 valid / invalid / skipped; export HTTP 200 in 61.46s; 824.14 MB / 5,000,001 lines; API RestartCount 0 | 5M verification summary below |
| Ingestion and index hardening checkpoint | 7,500,000 rows | Legacy synthetic CSV | Async portfolio scan with chunked ingestion and dedup benchmark mode | Passed | Scan `81ca48f2-e708-48b3-aa13-808989291fc0`; 7,500,000 / 0 / 0 valid / invalid / skipped; processing ~76m 24s; export HTTP 200 in 98.64s; 1.22 GiB / 7,500,001 lines | 7.5M verification summary below |
| 10M async scan verification | 10,000,000 rows | Legacy synthetic CSV | Async portfolio scan with bounded-memory benchmark mode | Passed | Scan `aa0971d2-bdb6-49c7-bac3-fa355aa161ad`; upload HTTP 202 in 5.79s; 10,000,000 / 0 / 0 valid / invalid / skipped; processing ~103m 35s; P1 8,420,051 / P3 1,579,949; total exposure $25,095,000,000.00; high exposure $24,455,516,419.00 | 10M verification summary below |
| 10M pagination and filtering | 10,000,000 rows | Persisted scan results | Indexed server-side pagination | Passed | Page 1: 0.676s; page 2: 0.247s; deep page 1000: 0.379s; P1 filter total 8,420,051 in 4.188s; P3 filter total 1,579,949 in 0.604s | 10M endpoint verification below |
| 10M streaming export | 10,000,000 rows | Persisted scan results | Server-side cursor CSV export | Passed | HTTP 200; TTFB 0.006987s; duration 113.63s; 10,000,001 lines; 1,638.95 MiB; API RestartCount 0; OOMKilled false | 10M export verification below |
| DB/index/resource evidence | Accumulated benchmark DB | Persisted scan history | Local Postgres evidence | Documented | `portfolio_scan_results` rows after run 22,752,000; total size 19 GB; index size 13 GB; database size 19 GB | Memory, database, and disk section below |
| Rich 10k scenario scan | 10,000 rows | Rich synthetic banking CSV | Rich scenario Portfolio Risk Scan | Passed | Scan `62c601b2-ddf7-487b-ad32-976a71b3bf58`; 10,000 / 0 / 0 valid / invalid / skipped; processing ~6s; P0 2,080 / P1 375 / P2 533 / P3 7,012; export 10,001 lines / ~2.0 MB; drawer scenario and chip rendering verified | `docs/RICH_SYNTHETIC_BANKING_SCHEMA.md` |
| Artifact hygiene | Generated CSVs, exports, media, helpers, env/cache files | Local artifacts | Git ignore policy | Passed | Generated benchmark CSVs, export CSVs, generated media, scratch scripts, evidence folders, environment files, caches, and build outputs remain untracked/ignored; rich banking generator and verifier remain tracked | `.gitignore`, `fraud-console/.gitignore` |

### Interpretation for Reviewers

The benchmark evidence supports the scalability story for a local synthetic Portfolio Risk Scan:
bounded-memory upload and processing, durable result persistence, indexed analyst pagination,
tier filtering, promotion support, and streaming CSV export at 10M rows. The rich 10k scan adds
scenario-aware synthetic banking evidence, including reason-code and drawer rendering coverage.

These results represent benchmark-scale validation of the async scan pipeline across
upload, scoring, persistence, indexed retrieval, and streaming export in a local
production-style environment. Institution-specific deployment would require
labelled-outcome model calibration, access controls, monitoring, governance, and
operational approval.

---

## Current Verified Capability Statement

> Verified 10M-transaction local production-style async Portfolio Risk Scan benchmark with bounded-memory ingestion, persisted results, paginated analyst review, deep pagination, risk-tier filtering, frontend scan resume, recent scan loading, scan detail header, promote-to-case support, and hardened server-side streaming CSV export.

## 10M Verification Summary

### 10M Evidence Lock Table

| Evidence area | Locked value |
|---|---|
| Scan ID | `aa0971d2-bdb6-49c7-bac3-fa355aa161ad` |
| DB row ID | 79 |
| Input CSV | `C:\tmp\risk-scan-12d8u-10m.csv` |
| Input size | 754,587,572 bytes / 719.63 MiB |
| Runtime environment | `RISK_SCAN_MAX_ROWS=10000000`; `RISK_SCAN_CHUNK_SIZE=2000`; `RISK_SCAN_ENABLE_IN_MEMORY_DEDUP=false` |
| Upload | HTTP 202 in 5.79s |
| Processing status | COMPLETE |
| Processed rows | 10,000,000 / 10,000,000 |
| Valid / invalid / skipped | 10,000,000 / 0 / 0 |
| Started | 2026-06-01 01:34:37 UTC |
| Completed | 2026-06-01 03:18:13 UTC |
| Duration | ~103m 35s |
| Average throughput | ~1,610 rows/sec |
| Priority distribution | P0 0 / P1 8,420,051 / P2 0 / P3 1,579,949 |
| Exposure | Total $25,095,000,000.00; high-tier $24,455,516,419.00 |
| API performance | Summary 0.008s; page 1 0.676s; page 2 0.247s; deep page 1000 0.379s; P1 filter 4.188s; P3 filter 0.604s |
| Export | HTTP 200; TTFB 0.006987s; duration 113.63s; size 1.64 GiB / 1,638.95 MiB; 10,000,001 lines |
| Runtime health | API RestartCount 0; OOMKilled false |
| Frontend checks | Query-param resume passed; Recent Scans panel passed; Scan Detail Header passed; result loading passed |
| Regression checks | `/health` passed; existing 5M scan readable; existing 7.5M scan readable |
| DB footprint after run | 22,752,000 `portfolio_scan_results` rows; total size 19 GB; index size 13 GB |

**Reviewer interpretation:** This validates async ingestion, persisted result storage, indexed
review, paginated retrieval, filtered querying, frontend resume/detail behavior, and streaming
export at 10M-row scale in a local production-style synthetic benchmark environment. The results
confirm system-level behavior under controlled benchmark conditions. Institution-specific
deployment would require labelled-outcome calibration, access controls, monitoring, governance,
and operational approval.

### Resource, Latency, and Throughput Evidence

#### Throughput

| Metric | Evidence | Operational interpretation |
|---|---|---|
| Upload acceptance | HTTP 202 in 5.79s | The API accepted the 10M-row file as an async job instead of blocking the request until scoring completed. |
| Processing duration | ~103m 35s | The background scan completed the full synthetic dataset without data loss. |
| Average throughput | ~1,610 rows/sec | The local benchmark sustained portfolio-scale scoring throughput across the full run. |
| Processing model | Async upload and background scoring | Ingestion acceptance is separated from long-running validation, scoring, persistence, and summary work. |

#### API Latency

| Endpoint / query | Evidence | Operational interpretation |
|---|---|---|
| Summary endpoint | 0.008s | Scan-level status and aggregate metrics remained fast after 10M persisted results. |
| Results page 1 | 0.676s | Initial analyst review page loaded through bounded server-side pagination. |
| Results page 2 | 0.247s | Adjacent result pages remained responsive and distinct. |
| Deep page 1000 | 0.379s | Composite ordered indexes supported deep review without loading the full scan into browser memory. |
| P1 filter | 4.188s for 8,420,051 matching rows | Large filtered retrieval remained correct; the total count over the dominant tier is the visible high-cardinality cost. |
| P3 filter | 0.604s for 1,579,949 matching rows | Lower-cardinality filtered retrieval remained comfortably interactive. |

#### Export Performance

| Metric | Evidence | Operational interpretation |
|---|---|---|
| Export status | HTTP 200 | Full-scan export completed successfully. |
| Time to first byte | 0.006987s | The server-side cursor emitted the CSV header immediately. |
| Export duration | 113.63s | The complete 10M-row export streamed in bounded batches. |
| Export size | 1.64 GiB / 1,638.95 MiB | The export path handled a multi-GiB result artifact without routing through frontend memory. |
| Export line count | 10,000,001 lines | Header plus all 10,000,000 result rows were present. |

#### Runtime Health

| Metric | Evidence | Operational interpretation |
|---|---|---|
| API RestartCount | 0 | The API stayed up through scan verification and export. |
| OOMKilled | false | No out-of-memory kill was recorded during the verified export path. |
| Frontend usability | Resume, recent scans, scan detail header, and result loading passed | The analyst-facing scan surface remained usable against the large persisted scan. |
| Regression readability | Existing 5M and 7.5M scans remained readable | Large-scan hardening did not break previously retained benchmark scans. |

#### Database Footprint

| Metric | Evidence | Operational interpretation |
|---|---|---|
| Accumulated result rows | 22,752,000 rows in `portfolio_scan_results` after the run | The database retained multiple large scans for review and evidence preservation. |
| Result table size | 19 GB total size | Large local synthetic evidence has a meaningful storage footprint. |
| Index size | 13 GB index size | Indexed pagination and filtering trade disk space for reviewer-facing query responsiveness. |
| Reviewer takeaway | 19 GB local database footprint after accumulated benchmarks | Future repeated benchmark work needs retention, archive, or cleanup planning before additional large runs. |

#### Interpretation

- Async upload separates job acceptance from long-running validation, scoring, persistence, and
  summary generation.
- Indexed pagination supports analyst review without loading the entire scan into browser memory.
- Filtered queries demonstrate operational retrieval against large result sets, while high-cardinality
  totals still have measurable cost.
- Streaming CSV export supports audit and report extraction without materializing the full output
  in the frontend.
- The database footprint highlights the storage and index trade-offs required for large local
  synthetic benchmark evidence.
- Institution deployment would require environment-specific validation, access control, security
  review, monitoring, governance, and cost planning.

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

`RISK_SCAN_ENABLE_IN_MEMORY_DEDUP=false` was used as memory-bounded benchmark mode because the
synthetic benchmark generator produced guaranteed-unique transaction IDs. Exact cross-chunk
duplicate detection remains available for normal scans by setting the variable to `true`.

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
| 10M verification | Needed full end-to-end proof after ingestion/export/dedup/index hardening | 10M controlled synthetic benchmark passed end-to-end |

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
Exact cross-chunk duplicate detection remains the default for normal scans. Memory-bounded
benchmark mode disables cross-chunk in-memory dedup only when synthetic transaction IDs are
guaranteed unique.

**Keep large benchmark artifacts out of Git.**
Generated input CSVs and export verification CSVs can reach multiple GiB. They belong on local
disk or object storage, not in the repository.

---

## Validation and Deployment Scope

- **Validation environment.** Synthetic transaction benchmarks validate system throughput,
  persistence, pagination, export, and workflow behavior in a local production-style environment.

- **Deployment requirements.** Real institution deployment would require additional model
  validation, regulatory review, security controls, access governance, operational monitoring,
  and data/security assessment.

---

## Operating Constraints

- **Large local DB footprint.** After accumulated 5M, 7.5M, and 10M scans, the local database
  reached about 19 GB and `portfolio_scan_results` reached 22,752,000 rows. Repeated future
  benchmark runs need an archive, cleanup, or retention strategy.

- **P1 count cost remains visible.** P1 filtering is indexed and correct, but the paginated
  response still computes a total count over 8,420,051 matching rows. This took 4.188s during
  10M verification.

- **Deployment readiness layer.** Authentication, authorization, environment
  isolation, and deployment observability are the next production hardening layer.

- **Generated artifacts stay untracked.** Generated benchmark CSVs and export files must remain
  untracked. Generator and verification scripts should not be committed unless explicitly scoped.

- **Benchmark environment may need reset.** `.env` may be left in 10M benchmark mode after scale
  verification. Reset row caps and dedup settings for normal development if needed.

---

## Post-10M Benchmark Hygiene

### Storage footprint after 10M verification (2026-06-01)

**Database**

| Object | Size |
|---|---|
| `portfolio_scan_results` total | **19 GB** |
| `portfolio_scan_results` heap | 5,392 MB |
| `portfolio_scan_results` indexes (12) | 13 GB |
| Full database | 19 GB |
| Docker volume `pgdata` | part of 20.9 GB local volumes |
| Total accumulated result rows | **22,752,000** |

Largest indexes by size:

| Index | Size |
|---|---|
| `ix_scan_results_scan_score_row` | 2,669 MB |
| `ix_scan_results_scan_validation_row` | 2,649 MB |
| `ix_scan_results_scan_priority_score_row_nullslast` | 2,198 MB |
| `ix_scan_results_scan_score_row_nullslast` | 2,009 MB |
| `ix_portfolio_scan_results_transaction_id` | 1,462 MB |

**Local generated artifacts (C:\tmp)**

| File | Size |
|---|---|
| `risk-scan-12d8u-10m-export.csv` | 1,638.9 MB |
| `risk-scan-12d8r-7p5m-export.csv` | 1,221.3 MB |
| `risk-scan-12d8u-10m.csv` | 719.6 MB |
| `risk-scan-12d8r-7p5m.csv` | 532 MB |
| Smaller verification files | < 10 MB |
| **Total C:\tmp benchmark files** | **~4.1 GB** |

These files are untracked and outside the repository. They can be deleted once the benchmark
documentation is confirmed to be fully captured in this file.

**Environment reset needed**

`.env` was left in 10M benchmark mode after scale verification. The following variables need
to be reset for normal development before the next product feature phase:

| Variable | Current (benchmark) | Reset to (normal dev) |
|---|---|---|
| `RISK_SCAN_MAX_ROWS` | `10000000` | `5000000` or lower |
| `RISK_SCAN_CHUNK_SIZE` | `2000` | `2000` (unchanged; already correct) |
| `RISK_SCAN_ENABLE_IN_MEMORY_DEDUP` | `false` | `true` |

`RISK_SCAN_ENABLE_IN_MEMORY_DEDUP` is the most important reset: leaving it `false` means
cross-chunk duplicate detection is silently inactive for normal analyst scans. Reset to `true`
before any non-benchmark use.

### Cleanup decision options

| Option | Action | Trade-off |
|---|---|---|
| **A — Preserve everything** | No change; keep all 22.7M rows | Safest for evidence; 19 GB database remains |
| **B — Keep large scans only** | Delete result rows for scans below 1M (IDs 66–77) after approval | Frees ~200k rows, negligible space saving — not worth the risk |
| **C — Keep 10M + 7.5M + 5M only** | Delete rows for scans 66–77 after approval; preserve IDs 68, 78, 79 | Frees ~192k rows; DB stays at ~19 GB (dominated by large scans) |
| **D — Archive then TRUNCATE all** | Export all remaining scan summaries to Markdown; TRUNCATE results table | Smallest DB footprint; irreversible without re-running benchmarks |
| **E — Keep as-is until demo/video** | No action now; clean after final portfolio screenshots are captured | Recommended if UI demos have not yet been recorded against live 10M data |

**Recommended: Option E for now, then Option C after demo/video is complete.**

The 10M and 7.5M benchmark scans are live in the database and accessible from the frontend.
Recording a product walkthrough or case study demo against real scan data is best done before
any cleanup. The small development scans (IDs 66–77) can be deleted later — they are
verification artifacts, not portfolio evidence.

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
