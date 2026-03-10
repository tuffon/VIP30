# Roadmap: VIP30 v2.6 Pipeline Rewrite

## Overview

Four phases to replace the monolithic analysis→writer→rewrite pipeline with a stepped, cost-driver-first architecture. Phase 29 builds the trade context layer from parser recap data. Phase 30 identifies cost drivers by dollar delta and maps line items with verification. Phase 31 implements per-driver LLM passes with isolated context and structured output. Phase 32 adds the final summary LLM pass, rebuilds the quality rewrite as single-pass, and wires the new `CostDriverPipeline` as a drop-in replacement.

## Milestones

- ✅ **v2.3 Report Quality** — Phases 18-22 (shipped 2026-03-07)
- ✅ **v2.4 Parser Coverage** — Phases 23-25 (shipped 2026-03-09)
- ✅ **v2.5 Parser Fixes** — Phases 26-28 (shipped 2026-03-09)
- 🚧 **v2.6 Pipeline Rewrite** — Phases 29-32 (in progress)

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
