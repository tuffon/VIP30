# Roadmap: VIP30 v2.6 Pipeline Rewrite

## Overview

Four phases to replace the monolithic analysis→writer→rewrite pipeline with a stepped, cost-driver-first architecture. Phase 29 builds the trade context layer from parser recap data. Phase 30 identifies cost drivers by dollar delta and maps line items with verification. Phase 31 implements per-driver LLM passes with isolated context and structured output. Phase 32 adds the final summary LLM pass, rebuilds the quality rewrite as single-pass, and wires the new `CostDriverPipeline` as a drop-in replacement.

## Milestones

- ✅ **v2.3 Report Quality** — Phases 18-22 (shipped 2026-03-07)
- ✅ **v2.4 Parser Coverage** — Phases 23-25 (shipped 2026-03-09)
- ✅ **v2.5 Parser Fixes** — Phases 26-28 (shipped 2026-03-09)
- ✅ **v2.6 Pipeline Rewrite** — Phases 29-34, 34.1 (shipped 2026-03-11)

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

<details>
<summary>✅ v2.6 Pipeline Rewrite (Phases 29-34, 34.1) — SHIPPED 2026-03-11</summary>

- [x] Phase 29: Trade Summary Parsing (1/1 plans) — completed 2026-03-10
- [x] Phase 30: Cost Driver Identification (1/1 plans) — completed 2026-03-10
- [x] Phase 31: Per-Driver LLM Pass (1/1 plans) — completed 2026-03-10
- [x] Phase 32: Final Summary + Pipeline Integration (2/2 plans) — completed 2026-03-10
- [x] Phase 33: Parser recap + trade summary completeness (3/3 plans) — completed 2026-03-11
- [x] Phase 34: Pipeline improvements (category-first) (3/3 plans) — completed 2026-03-11
- [x] Phase 34.1: Exact category preservation — no umbrella remapping (2/2 plans) — completed 2026-03-11

Full details: [.planning/milestones/v2.6-ROADMAP.md](milestones/v2.6-ROADMAP.md)

</details>
