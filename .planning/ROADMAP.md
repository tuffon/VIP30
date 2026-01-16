# Roadmap: VIP30

## Overview

Fix deployment configuration so frontend connects to production backend, then refine output quality based on real testing. Two focused phases to complete the bid comparison milestone.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Deployment Fix** - Frontend connects to production backend
- [ ] **Phase 2: Output Refinement** - XLSX and narrative quality improvements

## Phase Details

### Phase 1: Deployment Fix
**Goal**: Frontend connects to production backend and full flow works
**Depends on**: Nothing (first phase)
**Requirements**: ENV-01, ENV-02
**Success Criteria** (what must be TRUE):
  1. Frontend deployment uses `NEXT_PUBLIC_API_BASE_URL` env variable (not hardcoded localhost)
  2. User can upload PDFs and trigger bid comparison on hosted URL
  3. Job completes and returns download link
**Research**: Unlikely (configuration change)
**Plans**: TBD

Plans:
- [ ] 01-01: Fix API URL configuration

### Phase 2: Output Refinement
**Goal**: Comparison output is reliable and useful
**Depends on**: Phase 1
**Requirements**: OUT-01, OUT-02
**Success Criteria** (what must be TRUE):
  1. XLSX has consistent structure across different comparisons
  2. Narrative sections are well-organized and readable
  3. Report provides actionable comparison information
**Research**: Unlikely (internal code changes based on user feedback)
**Plans**: TBD (scope defined after testing)

Plans:
- [ ] 02-01: TBD based on testing feedback

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Deployment Fix | 0/TBD | Not started | - |
| 2. Output Refinement | 0/TBD | Not started | - |
