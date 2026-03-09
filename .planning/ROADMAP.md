# Roadmap: VIP30 v2.5 Parser Fixes

## Overview

Three phases to fix the parser gaps identified by v2.4. Phase 26 targets the contractor-final column schema mismatch (0% coverage, RESET/REMOVE/REPLACE layout). Phase 27 targets StateFarm grouped-row item extraction (3% on SF_BSchacter, partial gaps on lachman_sf/kalyvas_sf). Phase 28 extracts StateFarm metadata fields, regenerates all 4 final-draft golden masters from the fixed parser, and confirms all 12 pytest tests pass.

## Milestones

- ✅ **v2.3 Report Quality** — Phases 18-22 (shipped 2026-03-07)
- ✅ **v2.4 Parser Coverage** — Phases 23-25 (shipped 2026-03-09)
- ✅ **v2.5 Parser Fixes** — Phases 26-28 (shipped 2026-03-09)

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

## Progress

**Execution Order:** 26 → 27 → 28

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 23. Parser Audit | v2.4 | 2/2 | Complete | 2026-03-07 |
| 24. Golden Masters | v2.4 | 2/2 | Complete | 2026-03-08 |
| 25. Coverage Harness | v2.4 | 2/2 | Complete | 2026-03-09 |
| 26. Contractor-Final Parser | v2.5 | 1/1 | Complete | 2026-03-09 |
| 27. StateFarm Item Extraction | v2.5 | 1/1 | Complete | 2026-03-09 |
| 28. Metadata + Validation | v2.5 | 2/2 | Complete | 2026-03-09 |
