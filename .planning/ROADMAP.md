# Roadmap: VIP30 v2.4 Parser Coverage

## Overview

Three phases to measure Xactimate parser coverage before writing a single line of parser fix code. First audit what the parser currently captures across all document types in `./docs/`. Then produce human-verified golden master JSON files that represent the complete expected output per document type. Finally build an automated coverage harness that compares live parser output against golden masters and produces a structured gap report — the direct input to v2.5 parser fixes.

## Milestones

- ✅ **v2.3 Report Quality** — Phases 18-22 (shipped 2026-03-07)
- ✅ **v2.4 Parser Coverage** — Phases 23-25 (shipped 2026-03-09)

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

## Progress

**Execution Order:** 23 → 24 → 25

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 23. Parser Audit | v2.4 | 2/2 | Complete | 2026-03-07 |
| 24. Golden Masters | v2.4 | 2/2 | Complete | 2026-03-08 |
| 25. Coverage Harness | v2.4 | 2/2 | Complete | 2026-03-09 |
