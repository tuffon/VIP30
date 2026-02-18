# Roadmap: VIP30

## Milestones

- ✅ **v1.0.1 Professional Adjuster Narratives** - Phases 1-8 (shipped 2026-02-09)
- ✅ **v1.1 MVP Launch** - Phases 1-4 (shipped 2026-02-14)
- ✅ **v1.2 Launch Ready** - Phases 5-8 (shipped 2026-02-17)
- ✅ **v2.0 Analytical Intelligence** - Phases 9-12 (shipped 2026-02-17)
- ✅ **v2.1 Repository Restructure** - Phases 13-15 (shipped 2026-02-18)
- 🚧 **v2.2 Unified Output** - Phases 16-17 (in progress)

## Phases

- [ ] **Phase 16: Backend Output Unification** - Restructure XLSX to 2 sheets, remove mode system from pipeline
- [ ] **Phase 17: API & Frontend Cleanup** - Remove mode selector and output_mode API parameter

## Phase Details

### 🚧 v2.2 Unified Output

**Milestone Goal:** Replace 4 output modes with a single unified 2-sheet report. Simpler UX, no mode selection required.

### Phase 16: Backend Output Unification
**Goal**: Restructure XLSX export from 6 sheets to 2 (Summary + Analysis), remove OutputMode system from pipeline
**Depends on**: v2.0 (existing codebase)
**Requirements**: XLSX-01, XLSX-02, XLSX-03, XLSX-04, XLSX-05, MODE-01, MODE-04, MODE-05, PIPE-01, PIPE-02
**Success Criteria** (what must be TRUE):
  1. XLSX output has exactly 2 sheets: "Summary" and "Analysis"
  2. Summary sheet shows total delta, top cost drivers, and key observations
  3. Analysis sheet shows methodology detail, scope alignment, and full category-by-category side-by-side comparison
  4. No audit trail sheet in output
  5. Conditional formatting works on merged sheets (color scales, currency formatting)
  6. `OutputMode` enum and `OutputModeFilter` class no longer exist in codebase
  7. Pipeline produces unified output without any mode parameter
  8. `output_mode` column on ComparisonJob no longer written for new jobs
**Research**: Unlikely (internal refactoring, openpyxl patterns already established)

### Phase 17: API & Frontend Cleanup
**Goal**: Remove mode selector from frontend and output_mode from API request
**Depends on**: Phase 16 (backend must produce unified output before frontend/API can stop sending mode)
**Requirements**: MODE-02, MODE-03
**Success Criteria** (what must be TRUE):
  1. Frontend bid comp page has no mode selector — user uploads and submits directly
  2. API `CreateJobRequest` has no `output_mode` parameter
  3. Jobs complete successfully and produce 2-sheet XLSX output
**Research**: Unlikely (removing UI elements and API parameters)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 16. Backend Output Unification | 0/0 | Not started | - |
| 17. API & Frontend Cleanup | 0/0 | Not started | - |

---
*Last updated: 2026-02-18 — v2.1 archived, v2.2 in progress*
