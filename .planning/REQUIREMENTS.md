# Requirements: VIP30 v2.4 Parser Coverage

**Defined:** 2026-03-07
**Core Value:** Reliable end-to-end bid comparison that produces actionable output

## v1 Requirements

Requirements for v2.4 Parser Coverage milestone. Goal: measure how much content the Xactimate parser actually captures before making any changes.

### Parser Audit

- [ ] **AUDIT-01**: Parser audit runs all PDFs in `./docs/` through the existing parser and captures JSON output for each document
- [ ] **AUDIT-02**: Audit compares parser output against PDF content for all extracted sections (summary header, line items, O&P, depreciation, metadata fields)
- [ ] **AUDIT-03**: Audit maps missed line items per section/trade — count of extracted items vs. items present in PDF
- [ ] **AUDIT-04**: Audit validates dollar amounts — parser-extracted totals and subtotals compared against actual PDF values
- [ ] **AUDIT-05**: Audit covers all document profiles present in `./docs/`: rough drafts (contractor), final drafts (contractor), StateFarm final drafts
- [ ] **AUDIT-06**: Audit findings documented per document type — rough draft gaps, contractor final gaps, and StateFarm gaps identified separately

### Golden Masters

- [ ] **GOLD-01**: Golden master JSON file produced for each document type (one rough draft, one contractor final draft, one StateFarm)
- [ ] **GOLD-02**: Each golden master represents the complete expected parser output — every section, every line item, every amount the parser should capture from that document type
- [ ] **GOLD-03**: All golden masters human-verified against source PDFs before being locked as ground truth
- [ ] **GOLD-04**: Golden masters stored in version control under `tests/golden/` (or equivalent location in `packages/parser/`)

### Coverage Harness

- [ ] **HARNESS-01**: Automated test suite runs each golden-master document through the parser and diffs output against the corresponding golden master
- [ ] **HARNESS-02**: Per-file test result produced — pass if output matches golden master within defined tolerance, fail with details if gaps detected
- [ ] **HARNESS-03**: Field-level diff report shows exactly which fields are missing, wrong, or extra per document
- [ ] **HARNESS-04**: Summary gap report produced across all tested documents — which sections and fields are consistently missing across doc types

## v2 Requirements

Deferred to v2.5. Not in current roadmap.

### Parser Fixes

- **FIX-01**: Fix parser gaps identified by v2.4 audit — targeted code changes to `packages/parser/` for each confirmed gap category

## Out of Scope

Explicitly excluded to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Parser code changes | Explicitly deferred to v2.5 — understand gaps first, fix in next milestone |
| New document types beyond `./docs/` | Scope to known examples; adding new PDFs is a separate exercise |
| Comparison pipeline changes | This milestone is parser measurement only |
| LLM prompt or XLSX changes | Report quality work completed in v2.3 |
| Production deployment changes | Infrastructure untouched this milestone |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | Phase 23 | Pending |
| AUDIT-02 | Phase 23 | Pending |
| AUDIT-03 | Phase 23 | Pending |
| AUDIT-04 | Phase 23 | Pending |
| AUDIT-05 | Phase 23 | Pending |
| AUDIT-06 | Phase 23 | Pending |
| GOLD-01 | Phase 24 | Pending |
| GOLD-02 | Phase 24 | Pending |
| GOLD-03 | Phase 24 | Pending |
| GOLD-04 | Phase 24 | Pending |
| HARNESS-01 | Phase 25 | Pending |
| HARNESS-02 | Phase 25 | Pending |
| HARNESS-03 | Phase 25 | Pending |
| HARNESS-04 | Phase 25 | Pending |

**Coverage:**
- v1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-07*
*Last updated: 2026-03-07 after initial definition*
