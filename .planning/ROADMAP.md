# Roadmap: VIP30 v2.6 Pipeline Rewrite

## Overview

Four phases to replace the monolithic analysis→writer→rewrite pipeline with a stepped, cost-driver-first architecture. Phase 29 builds the trade context layer from parser recap data. Phase 30 identifies cost drivers by dollar delta and maps line items with verification. Phase 31 implements per-driver LLM passes with isolated context and structured output. Phase 32 adds the final summary LLM pass, rebuilds the quality rewrite as single-pass, and wires the new `CostDriverPipeline` as a drop-in replacement.

## Milestones

- ✅ **v2.3 Report Quality** — Phases 18-22 (shipped 2026-03-07)
- ✅ **v2.4 Parser Coverage** — Phases 23-25 (shipped 2026-03-09)
- ✅ **v2.5 Parser Fixes** — Phases 26-28 (shipped 2026-03-09)
- 🚧 **v2.6 Pipeline Rewrite** — Phases 29-33 (implementation complete)

## Phases

<details>
<summary>✅ v2.3 Report Quality (Phases 18-22) — SHIPPED 2026-03-07</summary>

### Phase 18: Narrative Pipeline Fix
**Goal**: Fix NarrativeResult type mismatch causing empty narrative sections in XLSX
**Plans**: 1 plan — [x] 18-01: Fix overlay properties on NarrativeResult

### Phase 19: XLSX Report Polish
**Goal**: Professional visual upgrade — header, color palette, column widths, print-ready
**Plans**: 1 plan — [x] 19-01: Visual polish

### Phase 20: Cost Driver Narrative Quality
**Goal**: Writer prompt v2.2 — approach-first guidance, top-driver narrative contract
**Plans**: 2 plans — [x] 20-01, [x] 20-02

### Phase 21: Report Output Quality
**Goal**: Writer prompt v2.3 — overview schema, SUGGESTED FOLLOWUPS RULES, Kalyvas Analysis layout
**Plans**: 2 plans — [x] 21-01, [x] 21-02

### Phase 22: Executive Summary Narrative
**Goal**: Writer prompt v2.4 — mandatory approach-pair, anti-echo rules; 5-column Analysis sheet
**Plans**: 2 plans — [x] 22-01, [x] 22-02

</details>

<details>
<summary>✅ v2.4 Parser Coverage (Phases 23-25) — SHIPPED 2026-03-09</summary>

- [x] Phase 23: Parser Audit (2/2 plans) — completed 2026-03-07
- [x] Phase 24: Golden Masters (2/2 plans) — completed 2026-03-08
- [x] Phase 25: Coverage Harness (2/2 plans) — completed 2026-03-09

Full details: [.planning/milestones/v2.4-ROADMAP.md](milestones/v2.4-ROADMAP.md)

</details>

<details>
<summary>✅ v2.5 Parser Fixes (Phases 26-28) — SHIPPED 2026-03-09</summary>

- [x] Phase 26: Contractor-Final Parser (1/1 plans) — completed 2026-03-09
- [x] Phase 27: StateFarm Item Extraction (1/1 plans) — completed 2026-03-09
- [x] Phase 28: Metadata + Validation (2/2 plans) — completed 2026-03-09

Full details: [.planning/milestones/v2.5-ROADMAP.md](milestones/v2.5-ROADMAP.md)

</details>

### 🚧 v2.6 Pipeline Rewrite (In Progress)

**Milestone Goal:** Replace monolithic LLM pipeline with cost-driver-first architecture — each major cost driver gets its own context window and LLM request.

### Phase 29: Trade Summary Parsing
**Goal**: Build `TradeContext` from parser JSON recap data with fallback hierarchy — reliable category totals for all doc types
**Depends on**: Nothing (first phase of v2.6)
**Requirements**: TRADE-01, TRADE-02, TRADE-03
**Success Criteria** (what must be TRUE):
  1. `build_trade_context()` returns `TradeContext` with `primary_by_category` and `comparison_by_category` dicts populated from `recap_by_category`
  2. `TradeContext.source` reflects which fallback level was used ("recap_by_category", "trade_summary", or "synthesized")
  3. Tested against all 6 golden master JSONs — category totals match parser output values
  4. When StateFarm `trade_summary` field is present, it enriches the context
**Research**: Unlikely (recap_by_category schema confirmed in all 6 golden masters; ARCHITECTURE.md documents approach)
**Plans**: 1 plan

Plans:
- [ ] 29-01: Build TradeContext model + extractor + tests against golden masters

### Phase 30: Cost Driver Identification
**Goal**: Identify top cost drivers by absolute dollar delta; map all line items per driver; verify sums match category totals
**Depends on**: Phase 29
**Requirements**: DRIVER-01, DRIVER-02, DRIVER-03
**Success Criteria** (what must be TRUE):
  1. `identify_cost_drivers()` returns `List[CostDriver]` ordered by `abs(delta)` descending from `TradeContext`
  2. `map_driver_items()` returns `List[DriverWithItems]` with all line items from both estimates for each driver category
  3. `DriverWithItems.verification_ok` is True when line items sum within tolerance of category total; False with `verification_note` otherwise
  4. Tested against Kalyvas (887 items, 40 sections) — item mapping handles large categories correctly
**Research**: Unlikely (deterministic sort; `XACTIMATE_CATEGORY_CODE_MAP` already in bid_comp/core.py)
**Plans**: 1 plan

Plans:
- [ ] 30-01: Build CostDriver + DriverWithItems models + identify/map functions + verification gate + tests

### Phase 31: Per-Driver LLM Pass
**Goal**: Each top cost driver gets its own LLM request with isolated context, structured Pydantic output, and per-driver Redis cache
**Depends on**: Phase 30
**Requirements**: PASS-01, PASS-02, PASS-03
**Success Criteria** (what must be TRUE):
  1. `run_driver_pass()` calls LLM once per driver with context scoped to that driver only — no other category data in context
  2. LLM output is `DriverAnalysisResult` Pydantic model returned from `generate_structured()` — no JSON repair fallback
  3. Per-driver results cached by content-hash key; second run with same inputs skips LLM call (verified via logs)
  4. `driver_analysis_v1` prompt template produces coherent narratives for test estimates
**Research**: Unlikely (generate_structured() pattern established in analysis_pass_v1; existing LLMAdapterBase sufficient)
**Plans**: 1 plan

Plans:
- [x] 31-01: Build DriverAnalysisResult model + run_driver_pass() + driver_analysis_v1 prompt + per-driver cache

### Phase 32: Final Summary + Pipeline Integration
**Goal**: Aggregate driver analyses into executive overview; rebuild quality rewrite as single-pass; wire new `CostDriverPipeline` as drop-in replacement for `NarrativePipeline`
**Depends on**: Phase 31
**Requirements**: SUMM-01, SUMM-02, REWRITE-01, REWRITE-02, REWRITE-03, INTEG-01, INTEG-02
**Success Criteria** (what must be TRUE):
  1. `run_summary_pass()` produces `SummaryResult` with coherent executive overview grounded in all driver analysis outputs
  2. Quality rewrite triggers only on GATE-01/GATE-02 failure; max 1 rewrite attempt; no loop
  3. No `_build_fallback_result()` or `_finalize_with_error()` placeholder text anywhere in the codebase
  4. `run_bid_comp()` calls `CostDriverPipeline` without errors for Kalyvas/Lachman test estimates
  5. Existing `export_xlsx()` produces valid XLSX from `FinalNarrative` output — report format unchanged
**Research**: Unlikely (established patterns; prompt design builds on writer_pass_v2 conventions)
**Plans**: 2 plans

Plans:
- [x] 32-01: Build SummaryResult model + run_summary_pass() + final_summary_v1 prompt + rebuilt quality rewrite
- [x] 32-02: Build CostDriverPipeline orchestrator + assemble_final_narrative() + fallback removal + bid_comp integration

### Phase 33: Parser recap + trade summary completeness
**Goal**: Ensure `recap_by_category` and `trade_summary` are parsed into final JSON output wherever present, update golden JSON fixtures to match verified parser reality, and prevent regressions with validation coverage.
**Depends on**: Phase 32
**Requirements**: parser output contract + regression baseline completeness
**Success Criteria** (what must be TRUE):
  1. `recaps_and_summaries.recap_by_category` exists for all tracked parser corpus documents
  2. `trade_summary` is parsed when present and emitted as `null` when absent
  3. Known wrapped description cases in `SF_BSchacter.pdf` no longer land in `notes`
  4. Goldens and gap report are refreshed against the verified parser baseline
**Plans**: 3 plans

Plans:
- [x] 33-01: Lock recap/trade-summary parser contract and add contract tests
- [x] 33-02: Fix State Farm wrapped-description vs notes handling
- [x] 33-03: Refresh parser goldens, add new Schacter final-draft corpus entry, rerun regression suite and gap report

## Progress

**Execution Order:** 29 → 30 → 31 → 32

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 23. Parser Audit | v2.4 | 2/2 | Complete | 2026-03-07 |
| 24. Golden Masters | v2.4 | 2/2 | Complete | 2026-03-08 |
| 25. Coverage Harness | v2.4 | 2/2 | Complete | 2026-03-09 |
| 26. Contractor-Final Parser | v2.5 | 1/1 | Complete | 2026-03-09 |
| 27. StateFarm Item Extraction | v2.5 | 1/1 | Complete | 2026-03-09 |
| 28. Metadata + Validation | v2.5 | 2/2 | Complete | 2026-03-09 |
| 29. Trade Summary Parsing | v2.6 | 1/1 | Complete | 2026-03-10 |
| 30. Cost Driver Identification | v2.6 | 1/1 | Complete | 2026-03-10 |
| 31. Per-Driver LLM Pass | v2.6 | 1/1 | Complete | 2026-03-10 |
| 32. Final Summary + Pipeline Integration | v2.6 | 2/2 | Complete | 2026-03-10 |
| 33. Parser recap + trade summary completeness | v2.6 | 3/3 | Complete | 2026-03-11 |

### Phase 34: pipeline improvements using the recap by summary and trade summary output from the json

**Goal:** Recenter BidComp on parser category structures so `trade_summary` and `recap_by_category` drive category diffs, deterministic top cost driver selection, and evidence-grounded narrative synthesis.
**Requirements**: TRADE-01, TRADE-02, DRIVER-01, DRIVER-02, PASS-01, SUMM-01, SUMM-02, INTEG-01, INTEG-02
**Depends on:** Phase 33
**Success Criteria** (what must be TRUE):
  1. When `trade_summary` exists, the pipeline uses it as the preferred category evidence source because it already combines recap totals with associated line items
  2. When `trade_summary` is absent, `recap_by_category` still drives category diffs and only selected top-driver categories require deeper fallback line-item association
  3. Top cost drivers are selected deterministically from category deltas before any LLM step
  4. Per-driver prompt context is grounded in structured category evidence, line items, delta facts, and estimate metadata rather than thin raw item blobs alone
  5. Final summary synthesis and visible top-driver output remain aligned to the same category-diff truth without changing external report format compatibility
**Plans:** 3 plans

Plans:
- [ ] 34-01: Build trade-summary-first category evidence foundation with recap fallback
- [ ] 34-02: Rework deterministic top-driver grounding and driver-pass prompt context
- [ ] 34-03: Align summary/orchestrator flow and verify category-first end-to-end behavior
