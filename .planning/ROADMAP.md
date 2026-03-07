# Roadmap: VIP30 v2.3 Report Quality

## Milestones

- ✅ **v1.0.1 Professional Adjuster Narratives** — Phases 1-8 (shipped 2026-02-09)
- ✅ **v1.1 MVP Launch** — Phases 1-4 (shipped 2026-02-14)
- ✅ **v1.2 Launch Ready** — Phases 5-8 (shipped 2026-02-17)
- ✅ **v2.0 Analytical Intelligence** — Phases 9-12 (shipped 2026-02-17)
- ✅ **v2.1 Repository Restructure** — Phases 13-15 (shipped 2026-02-18)
- ✅ **v2.2 Unified Output** — Phases 16-17 (shipped 2026-02-18)
- ✅ **v2.3 Report Quality** — Phases 18-22 (shipped 2026-03-07)

## Overview

Fix the narrative regression that causes output sections to be empty, then elevate the XLSX report to professional, client-shareable quality. Two focused phases: repair the pipeline, then polish the output.

## Phases

- [x] **Phase 18: Narrative Pipeline Fix** — Diagnose and repair the LLM narrative regression (completed 2026-03-06)
- [x] **Phase 19: XLSX Report Polish** — Professional visual upgrade for client-ready output (completed 2026-03-06)
- [x] **Phase 20: Cost Driver Narrative Quality** — Fix prompts so key cost drivers have associated narrative text (completed 2026-03-06)
- [x] **Phase 21: Report Output Quality** — Notes legibility, summary depth, key observations integration, follow-up specificity, analysis layout per Kalyvas template
- [x] **Phase 22: Executive Summary Narrative** — Remove Notes column from Analysis category table; rewrite Overall Summary as an executive-grade narrative paragraph (not robotic/disjointed); weave scope observations in naturally (completed 2026-03-07)

## Phase Details

### Phase 18: Narrative Pipeline Fix
**Goal**: Diagnose and fix the regression causing narrative sections to not populate in the XLSX output
**Depends on**: Existing codebase (v2.2)
**Requirements**: NARR-01, NARR-02, NARR-03, NARR-04
**Success Criteria** (what must be TRUE):
  1. Running a job produces an XLSX where narrative text appears in the Analysis sheet for each category
  2. The Summary sheet overview narrative section is populated
  3. Key drivers section contains written context, not empty cells
  4. No completed job has a blank narrative section
**Research**: Likely (regression tracing — need to identify where narrative output drops in the pipeline)
**Research topics**: Trace narrative output path through pipeline, compare pre/post v2.2 changes, identify where content stops flowing to XLSX cells
**Plans**: TBD

Plans:
- [x] 18-01: Fix NarrativeResult → export_xlsx type mismatch (add overlay properties)

### Phase 19: XLSX Report Polish
**Goal**: Professional visual upgrade for both Summary and Analysis sheets — client-shareable output
**Depends on**: Phase 18 (narrative must work before polishing presentation)
**Requirements**: XLSX-01, XLSX-02, XLSX-03, XLSX-04, XLSX-05
**Success Criteria** (what must be TRUE):
  1. Report header cleanly displays title, report date, and job reference
  2. Color palette is restrained and professional — appropriate for client distribution
  3. All column widths sized to content — no truncated text
  4. Layout is print-ready — no column overflow on standard paper sizes
  5. Both Summary and Analysis sheets have consistent typography and clear visual hierarchy
**Research**: Unlikely (openpyxl patterns established in codebase — extension of existing export code)
**Plans**: TBD

Plans:
- [x] 19-01: Visual polish — header, color palette, column widths, print setup

### Phase 20: Cost Driver Narrative Quality
**Goal**: Fix LLM prompts so key cost drivers have associated narrative text in report output
**Depends on**: Phase 19
**Plans**: TBD

Plans:
- [x] 20-01: Prompt v2.2 — restore approach table, fix narrative schema
- [x] 20-02: Replace Severity with Notes column in Summary Top Cost Drivers table

### Phase 21: Report Output Quality
**Goal**: Elevate report readability and analytical depth — Notes legibility, richer overview summary, key observations integrated into summary, specific follow-ups, analysis section styled after Kalyvas template
**Depends on**: Phase 20
**Reference**: COMP-BID-Template-2025 Kalyvas.xlsx in project root (target layout for Analysis sheet category comparison)

Plans:
- [x] 21-01: Prompt v2.3 — fix overview schema, add SUGGESTED FOLLOWUPS RULES
- [x] 21-02: XLSX display — Notes legibility, richer summary, Kalyvas-style Analysis table with O&P footer

### Phase 22: Executive Summary Narrative
**Goal**: The Overall Summary cell must read as a polished executive-facing paragraph — not robotic or disjointed. Remove Notes column from the Analysis category-by-category table entirely. Diagnose why the overview outputs raw data fields ("Overall direction: primary_higher") instead of LLM narrative, and fix the root cause (prompt or code). Scope observations must be woven into the paragraph naturally, not appended as "Key scope differences: ...".
**Depends on**: Phase 21
**Reference**: Output example showing regression — "Overall direction: primary_higher. See key drivers below for details." and clunky scope observations append.

Plans:
- [ ] TBD (run /gsd:plan-phase 22 to break down)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 18. Narrative Pipeline Fix | v2.3 | 1/1 planned | Complete | 2026-03-06 |
| 19. XLSX Report Polish | v2.3 | 1/1 planned | Complete | 2026-03-06 |
| 20. Cost Driver Narrative Quality | v2.3 | 2/2 planned | Complete | 2026-03-06 |
| 21. Report Output Quality | v2.3 | 2/2 planned | Complete | 2026-03-06 |
| 22. Executive Summary Narrative | v2.3 | 2/2 planned | Complete | 2026-03-07 |

---
*Roadmap created: 2026-03-05*
