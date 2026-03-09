# Roadmap: VIP30 v2.5 Parser Fixes

## Overview

Three phases to fix the parser gaps identified by v2.4. Phase 26 targets the contractor-final column schema mismatch (0% coverage, RESET/REMOVE/REPLACE layout). Phase 27 targets StateFarm grouped-row item extraction (3% on SF_BSchacter, partial gaps on lachman_sf/kalyvas_sf). Phase 28 extracts StateFarm metadata fields, regenerates all 4 final-draft golden masters from the fixed parser, and confirms all 12 pytest tests pass.

## Milestones

- ✅ **v2.3 Report Quality** — Phases 18-22 (shipped 2026-03-07)
- ✅ **v2.4 Parser Coverage** — Phases 23-25 (shipped 2026-03-09)
- 🚧 **v2.5 Parser Fixes** — Phases 26-28 (in progress)

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

### 🚧 v2.5 Parser Fixes (In Progress)

**Milestone Goal:** Fix all 3 confirmed gap categories; all 12 pytest coverage tests pass.

#### Phase 26: Contractor-Final Parser
**Goal**: Fix contractor-final column schema — extract line items using RESET/REMOVE/REPLACE/TAX/O&P layout
**Depends on**: Nothing (standalone parser change)
**Requirements**: CFINAL-01, CFINAL-02
**Success Criteria** (what must be TRUE):
  1. `XactimateRoughDraftParser` on BSchacter contractor-final produces ≥26 of 29 sections with line items (≥90%)
  2. Extracted line items map to RESET/REMOVE/REPLACE/TAX/O&P columns (not rough-draft unit-cost schema)
  3. Rough-draft baseline preserved — lachman and kalyvas `test_section_coverage` pass unchanged
**Research**: Unlikely (known root cause — column schema mismatch; existing parser codebase)
**Plans**: TBD

Plans:
- [ ] 26-01: TBD

#### Phase 27: StateFarm Item Extraction
**Goal**: Fix grouped-row extraction — all items per section captured across StateFarm documents
**Depends on**: Phase 26 (regression baseline confirmed)
**Requirements**: SF-01, SF-02, SFPART-01
**Success Criteria** (what must be TRUE):
  1. SF_BSchacter produces ≥27 sections with items (≥90% of 30 non-excluded sections)
  2. Each section contains all grouped-row items, not just last matched row
  3. lachman_sf and kalyvas_sf partial sections (including Ext_Surfaces) fully extracted
  4. Rough-draft baseline preserved
**Research**: Unlikely (known root cause — grouped-row layout; existing parser codebase)
**Plans**: TBD

Plans:
- [ ] 27-01: TBD

#### Phase 28: Metadata + Validation
**Goal**: Extract StateFarm metadata fields; regenerate golden masters; all 12 tests pass
**Depends on**: Phase 27 (parser fixes complete)
**Requirements**: META-01, META-02, META-03, VALID-01, VALID-02, VALID-03
**Success Criteria** (what must be TRUE):
  1. Parser extracts `insured_name`, `price_list`, `property_address` from StateFarm two-column summary page (all final-draft docs)
  2. All 4 final-draft golden master JSON files regenerated from fixed parser output and committed to version control
  3. All 12 pytest tests in `test_coverage.py` pass
  4. Rough-draft baseline preserved — lachman and kalyvas still 100% coverage
**Research**: Unlikely (pdfplumber pattern established in Phase 24-02; pytest harness already in place)
**Plans**: TBD

Plans:
- [ ] 28-01: TBD

## Progress

**Execution Order:** 26 → 27 → 28

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 23. Parser Audit | v2.4 | 2/2 | Complete | 2026-03-07 |
| 24. Golden Masters | v2.4 | 2/2 | Complete | 2026-03-08 |
| 25. Coverage Harness | v2.4 | 2/2 | Complete | 2026-03-09 |
| 26. Contractor-Final Parser | v2.5 | 0/? | Not started | - |
| 27. StateFarm Item Extraction | v2.5 | 0/? | Not started | - |
| 28. Metadata + Validation | v2.5 | 0/? | Not started | - |
