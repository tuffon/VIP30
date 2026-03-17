# Project Milestones: VIP30

## v2.6 Pipeline Rewrite (Shipped: 2026-03-11)

**Delivered:** Monolithic LLM pipeline replaced with cost-driver-first stepped architecture — each top cost driver gets its own isolated context window and LLM request, fed by exact parsed category titles flowing 1:1 from parser through TradeContext, BidComp, and driver selection.

**Phases completed:** 29–34, 34.1 (13 plans total)

**Key accomplishments:**

- `TradeContext` model + `build_trade_context()` — category totals from `recap_by_category` with `trade_summary` enrichment for StateFarm docs; all 6 doc types verified against golden masters; lazy-import pattern resolves pipeline↔bid_comp circular dependency
- `CostDriver` + `DriverWithItems` + `identify_cost_drivers()` + `map_driver_items()` — deterministic top-driver ranking by absolute dollar delta; line-item mapping with verification gate; 887-item kalyvas golden master validated
- `run_driver_pass()` — each driver gets isolated context (7 keys, no cross-category data), `generate_structured()` only with no JSON repair fallback, content-hash PipelineCache integration
- `CostDriverPipeline` replaces `NarrativePipeline` — `run_summary_pass()` aggregates driver analyses into `SummaryResult`; single-pass rewrite on GATE-01/GATE-02 only; explicit `Analysis unavailable` fallback per failed driver; all placeholder finalization text removed
- Parser recap/trade-summary contract locked — `recap_by_category` and `trade_summary` contract coverage confirmed across 7-doc corpus; StateFarm wrapped-description bug fixed; goldens refreshed
- Exact category preservation end-to-end — umbrella remapping removed from `TradeContext`, `BidComp` category tables, and raw line-item fallback mapping; 67/67 regression tests pass

**Stats:**

- 93 files changed, 18,129 insertions, 1,504 deletions
- 7 phases (including 1 inserted decimal phase 34.1), 13 plans
- 2 days (2026-03-09 → 2026-03-11)

**Git range:** `f964fea` → `270f06d`

**What's next:** TBD — discuss next milestone goals

---

## v2.5 Parser Fixes (Shipped: 2026-03-09)

**Delivered:** All 3 parser gap categories fixed — contractor-final RESET/REMOVE/REPLACE schema (0%→93%), StateFarm grouped-row item extraction (3%→96.8%), StateFarm metadata from two-column summary page; all 12 pytest tests pass.

**Phases completed:** 26-28 (4 plans total)

**Key accomplishments:**

- Family C header detection + `_parse_cfinal_line` — BSchacter contractor-final 0→27/29 sections with items (from 0% to 93%)
- GCO&P normalization + asterisk-price item handling — SF_BSchacter 1→30/31 sections (3%→96.8%); kalyvas_sf Ext_Surfaces 5→7 items
- SF two-column summary page parsing — `insured_name`, `price_list`, `property_address`, `claim_number` now non-null for all 3 SF final-draft documents
- All 4 final-draft golden masters regenerated from fixed parser output (bschacter 29sec/542items, SF_BSchacter 31sec/306items, lachman_sf 34sec/368items, kalyvas_sf 36sec/524items)
- 12/12 pytest tests passing — `_section_diff` duplicate-name fix; rough-draft metadata aligned to parser reality

**Stats:**

- 26 files changed, 12,945 insertions, 6,480 deletions
- 3 phases, 4 plans
- 1 day (2026-03-09)

**Git range:** `006dba0` → `9e60876`

**What's next:** v2.6 — parser stabilized; route to comparison pipeline or XLSX report improvements

---

## v2.4 Parser Coverage (Shipped: 2026-03-09)

**Delivered:** Complete parser coverage measurement — audit runner, 6 human-verified golden master JSON files, and automated pytest harness with field-level diff tests producing the v2.5 gap inventory.

**Phases completed:** 23-25 (6 plans total)

**Key accomplishments:**

- `audit_all.py` runner — all 6 PDFs parsed with zero crashes; structured `run_log.json` and 255-line `AUDIT-REPORT.md` identifying root causes per document type
- Rough-draft baseline confirmed: zero validation delta across 72 sections (32 Lachman + 40 Kalyvas) — parser is production-quality for rough-draft format
- Root causes identified: contractor-final uses RESET/REMOVE/REPLACE column schema (parser expects rough-draft unit-cost layout); StateFarm Customer Copy uses grouped-row layout (parser extracts 1 item per section instead of all)
- 6 golden master JSON files produced and human-verified (lachman 32/525 items, kalyvas 40/887, bschacter 29/477, SF_BSchacter 31/309, lachman_sf 34/368, kalyvas_sf 36/520)
- pytest harness with 12 parametrized tests (6 docs × test_metadata + test_section_coverage) — rough-draft tests pass, final-draft tests fail with field-level diffs
- `GAP-REPORT.md` (172 lines) — authoritative v2.5 parser-fix input with per-doc coverage%, cross-doc pattern summary, prioritized fix list

**Stats:**

- 60 files created/modified, 111,695 insertions, 30 deletions
- 3 phases, 6 plans
- 2 days (2026-03-07 → 2026-03-09)

**Git range:** `deec9fd` → `ccbd59c`

**What's next:** v2.5 — parser fixes for contractor-final and StateFarm document types

---

## v2.3 Report Quality (Shipped: 2026-03-07)

**Delivered:** Professional XLSX report with LLM-generated executive overview — narrative pipeline fixed, prompt quality elevated, writer_pass_v2 LLM routing bug resolved, Analysis sheet cleaned to 5-column Kalyvas layout.

**Phases completed:** 18-22 (8 plans total)

**Key accomplishments:**

- Fixed NarrativeResult → export_xlsx type mismatch that caused empty narrative sections in XLSX
- Professional XLSX visual polish — restrained color palette, report header, auto-sized columns, print-ready
- Writer prompt v2.2 — approach-first guidance, top-driver narrative contract, Notes in Summary Top Cost Drivers
- Writer prompt v2.3 — SUGGESTED FOLLOWUPS RULES with BAD/GOOD examples, corrected 4-6 sentence overview schema
- Discovered & fixed `writer_pass_v2.json` brace escaping bug — LLM was never called for line-item jobs (always fell back to Python-generated text)
- Writer prompt v2.4 — APPROACH PAIR REQUIREMENT mandatory, anti-echo/anti-forward-reference rules, raw direction/confidence fields removed
- Analysis sheet reverted to 5-column Kalyvas layout (Notes column removed), overall summary returns LLM prose directly

**Stats:**

- 15 files changed, 1,412 insertions, 65 deletions
- 5 phases, 8 plans
- 3 days from start to ship (2026-03-05 → 2026-03-07)

**Git range:** `154d8f3` → `954b74b`

**What's next:** TBD — discuss next milestone

---

## v2.2 Unified Output (Shipped: 2026-02-18)

**Delivered:** Single unified 2-sheet XLSX report replacing 4 output modes. Simpler UX with no mode selection.

**Phases completed:** 16-17 (executed directly)

**Key accomplishments:**
- XLSX restructured from 6 sheets to 2: "Summary" + "Analysis"
- `OutputMode` enum, `OutputModeFilter` class, and `output_modes.py` deleted
- Mode selector removed from frontend bid comp page
- `output_mode` removed from API `CreateJobRequest`
- Worker backward-compatible (ignores mode param from queued jobs)
- DB column made nullable, historical values preserved

**Stats:**
- 11 files changed
- 235 insertions, 450 deletions (net reduction)
- 2 phases
- Same day

**Git range:** `1582e01` → `3264734`

**What's next:** TBD — discuss next milestone

---

## v2.1 Repository Restructure (Shipped: 2026-02-18)

**Delivered:** Clean repository structure with monolith split into separate apps and packages, proper service naming on Render.

**Phases completed:** 13-15 (2 formal plans + direct execution)

**Key accomplishments:**
- Extracted `packages/parser/` as standalone Python package (10 modules, zero business logic deps)
- Extracted `packages/shared-python/` with 46 modules (bid_comp, pipeline, rules, methodology, etc.)
- Split `apps/vip-parse/` monolith into `apps/api/` (FastAPI) and `apps/worker/` (RQ)
- Renamed `apps/vipclaims-saas/` to `apps/frontend/`
- Updated render.yaml with correct service names (vip30-api, vip30-frontend, vip30-worker)
- Removed dead preflight code

**Stats:**
- 191 files created/modified
- 1,691 insertions, 1,391 deletions
- 3 phases, 2 plans
- 1 day from start to ship

**Git range:** `ec35399` → `4a1f829`

**What's next:** v2.2 — Unified 2-sheet output, remove output mode system

---

## v2.0 Analytical Intelligence (Shipped: 2026-02-17)

**Delivered:** Full analytical intelligence layer with methodology analysis, rules engine, quality gates, and output modes.

**Phases completed:** 9-12 (8 plans total)

**Key accomplishments:**
- Methodology analysis (O&P, depreciation, scope alignment, data provenance)
- Rules engine with 3 severity tiers, 6 alert types, structural pattern detection
- 5 quality gates (hedge, judgment, quantification, evidence grounding, methodology neutrality)
- 4 output modes (executive, carrier, litigation, internal)
- Enhanced multi-sheet XLSX with conditional formatting and audit trail

**Stats:**
- 4 phases, 8 plans
- 1 day from start to ship

**Git range:** `0e4ef27` → `2597518`

**What's next:** v2.1 — Repository restructure

---

## v1.2 Launch Ready (Shipped: 2026-02-17)

**Delivered:** Launch-ready product with enterprise B2B landing page, trust elements, polished app experience, and production observability.

**Phases completed:** 5-8 (6 plans total)

**Key accomplishments:**
- Landing page redesigned with Xactimate-focused B2B messaging and enterprise aesthetic
- Trust footer with Privacy Policy, Terms of Service, and Security pages
- User dropdown component with session persistence via localStorage
- Credit balance display with visual states in Bid Comp UI
- Structured JSON logging with request ID middleware
- Health endpoints for Render monitoring

**Stats:**
- 42 files created/modified
- 2,932 lines TypeScript, 35,261 lines Python
- 4 phases, 6 plans
- 1 day from start to ship

**Git range:** `5751cc9` → `c4e4fab`

**Tech debt incurred:**
- DESIGN-05: Using placeholder screenshots (replace before launch)
- Build verification: Local `.next` permission issue needs CI/deploy verification

**What's next:** v2 — pricing page, demo video, date filtering

---

## v1.1 MVP Launch (Shipped: 2026-02-14)

**Delivered:** Production-ready customer validation loop with email OTP auth, credit-based usage tracking, job state machine, and complete frontend experience.

**Phases completed:** 1-4 (8 plans total)

**Key accomplishments:**
- PostgreSQL database with workspace-scoped schema (users, workspaces, jobs, credits)
- Email OTP authentication with rate limiting, JWT cookies, and automatic workspace creation
- Job state machine (queued → parsing → analyzing → writing → completed|failed) with progress tracking
- Ledger-style credit system with idempotent consumption on job success only
- Complete frontend auth flow (/login → OTP verify → cookie-based sessions)
- Job progress and history UI with real-time polling and pagination

**Stats:**
- 51 files created/modified
- 9,319 lines of Python, 1,907 lines TypeScript
- 4 phases, 8 plans
- 2 days from start to ship

**Git range:** `7f4df34` → `de0007f`

**What's next:** v1.2 — date filtering, internal naming cleanup, production hardening

---

## v1.0.1 Professional Adjuster Narratives (Shipped: 2026-02-09)

**Delivered:** Three-pass LLM pipeline with quality gating that produces professional adjuster-tone narratives from bid comparison data.

**Phases completed:** 1-8 (8 plans total)

**Key accomplishments:**
- Three-pass LLM pipeline (Analysis → Writer → Compliance) reducing token count from 100k+ to ~5-10k
- Deterministic quality gates: 6 measurable checks (hedging, verbosity, valuation links, summary length, analyst tone, GPT-isms)
- Adjuster tone control via few-shot examples from real memos + terminology glossary
- Pass-level Redis caching with content-hash keys (1hr analysis, 30min writer TTL)
- Production integration into BidComp with legacy fallback preserved
- Regression fixes: numeric key_driver values, two-sentence narratives, expanded overview structure

**Stats:**
- 68 files created/modified
- 2,591 lines of Python (pipeline module)
- 8 phases, 8 plans
- 5 days from start to ship

**Git range:** `cab57c1` → `3233fbd`

**What's next:** TBD — discuss next milestone goals

---
