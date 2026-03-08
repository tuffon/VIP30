# Roadmap: VIP30 v2.4 Parser Coverage

## Overview

Three phases to measure Xactimate parser coverage before writing a single line of parser fix code. First audit what the parser currently captures across all document types in `./docs/`. Then produce human-verified golden master JSON files that represent the complete expected output per document type. Finally build an automated coverage harness that compares live parser output against golden masters and produces a structured gap report — the direct input to v2.5 parser fixes.

## Milestones

- ✅ **v2.3 Report Quality** — Phases 18-22 (shipped 2026-03-07)
- 🚧 **v2.4 Parser Coverage** — Phases 23-25 (in progress)

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

### 🚧 v2.4 Parser Coverage (In Progress)

**Milestone Goal:** Measure how much content the Xactimate parser captures across all document types before making any changes. No parser code changes — audit, golden masters, and harness only.

---

### Phase 23: Parser Audit
**Goal**: Run all PDFs in `./docs/` through the existing parser and document what is captured vs. missed per document type
**Depends on**: Existing codebase (packages/parser/)
**Requirements**: AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05, AUDIT-06
**Success Criteria** (what must be TRUE):
  1. All 7 PDFs in `./docs/` run through parser with JSON output captured for each
  2. Parser output compared against actual PDF content — sections, line items, amounts, metadata
  3. Gap inventory documented per document type (rough draft, contractor final, StateFarm)
  4. Audit report produced summarizing what's missing per profile
**Research**: Likely (need to understand parser code, output schema, what sections it currently extracts)
**Research topics**: Parser entry points, output schema/models, which sections each doc type exercises, how to invoke parser standalone
**Plans**: 2 plans

Plans:
- [ ] 23-01: Explore parser codebase — entry points, output schema, invoke standalone on each PDF
- [ ] 23-02: Compare parser output vs. PDF content per doc type — produce structured gap inventory

---

### Phase 24: Golden Masters
**Goal**: Produce human-verified golden master JSON files for each document type as ground truth for coverage testing
**Depends on**: Phase 23 (audit identifies what SHOULD be captured)
**Requirements**: GOLD-01, GOLD-02, GOLD-03, GOLD-04
**Success Criteria** (what must be TRUE):
  1. Golden master JSON exists for each document type (rough draft, contractor final, StateFarm)
  2. Each golden master captures complete expected output — all sections, all line items, all amounts
  3. All golden masters human-verified against source PDFs and committed to version control
  4. Golden masters stored in `packages/parser/tests/golden/` (or equivalent) in version control
**Research**: Unlikely (manual inspection and JSON authoring, no new technology)
**Plans**: 2 plans

Plans:
- [ ] 24-01: Create golden masters for rough draft and contractor final draft document types
- [ ] 24-02: Create golden masters for StateFarm document types + final human verification pass

---

### Phase 25: Coverage Harness
**Goal**: Automated test suite that runs parser against golden masters and produces a structured gap report per document type
**Depends on**: Phase 24 (golden masters must exist as ground truth)
**Requirements**: HARNESS-01, HARNESS-02, HARNESS-03, HARNESS-04
**Success Criteria** (what must be TRUE):
  1. Single command (`pytest` or equivalent) runs all golden master comparisons
  2. Per-file pass/fail result produced — fails with field-level diff showing missing/wrong/extra fields
  3. Coverage percentage reported per document type (e.g., "rough-draft: 73% field coverage")
  4. Summary gap report produced showing which sections/fields are consistently missing across all doc types
**Research**: Unlikely (pytest patterns already in codebase, diff logic is standard Python)
**Plans**: 2 plans

Plans:
- [ ] 25-01: Build coverage harness — pytest fixtures, golden master loader, field-level diff logic
- [ ] 25-02: Run harness against all golden masters — produce final gap report as v2.5 input

---

## Progress

**Execution Order:** 23 → 24 → 25

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 23. Parser Audit | v2.4 | 2/2 | Complete | 2026-03-07 |
| 24. Golden Masters | v2.4 | 2/2 | Complete | 2026-03-08 |
| 25. Coverage Harness | v2.4 | 0/2 | Not started | - |
