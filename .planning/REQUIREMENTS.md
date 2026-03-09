# Requirements: VIP30 v2.5 Parser Fixes

**Defined:** 2026-03-09
**Core Value:** Reliable end-to-end bid comparison that produces actionable output

## v1 Requirements

Requirements for v2.5. Goal: fix all 3 parser gap categories identified by v2.4 GAP-REPORT.md and confirm via coverage harness.

### Contractor-Final Parser

- [x] **CFINAL-01**: Parser detects contractor-final document format and applies RESET/REMOVE/REPLACE/TAX/O&P column schema (not rough-draft unit-cost schema)
- [x] **CFINAL-02**: Parser achieves ≥90% section coverage on BSchacter contractor-final document (currently 0% — 0 of 29 sections)

### StateFarm Item Extraction

- [ ] **SF-01**: Parser extracts all line items per section from StateFarm grouped-row layout (currently extracts only last matched row per section)
- [ ] **SF-02**: Parser achieves ≥90% section coverage on SF_BSchacter document (currently 3% — 1 of 30 non-excluded sections)

### Metadata Extraction

- [ ] **META-01**: Parser extracts `insured_name` from StateFarm two-column summary page (currently null on all final-draft documents)
- [ ] **META-02**: Parser extracts `price_list` from StateFarm two-column summary page (currently null)
- [ ] **META-03**: Parser extracts `property_address` from StateFarm two-column summary page (currently null)

### StateFarm Partial Gaps (lachman_sf / kalyvas_sf)

- [ ] **SFPART-01**: Parser closes remaining partial-extraction gaps in lachman_sf and kalyvas_sf StateFarm documents (currently 97% — 1-2 sections partially extracted per doc, including kalyvas_sf Ext_Surfaces 5/7 items)

### Validation

- [ ] **VALID-01**: Rough-draft parser baseline preserved — lachman and kalyvas `test_section_coverage` tests continue to pass after all parser changes (no regressions)
- [ ] **VALID-02**: All 4 final-draft golden master JSON files regenerated from fixed parser output and committed to version control
- [ ] **VALID-03**: All 12 pytest tests in `test_coverage.py` pass after golden master regeneration

## v2 Requirements

Deferred. Scope is tightly bounded to the 3 confirmed gap categories.

*(none — all confirmed gaps addressed in v2.5)*

## Out of Scope

Explicitly excluded to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Comparison pipeline changes (bid_comp, pipeline) | v2.6 — parser must stabilize first |
| XLSX report changes | v2.6 |
| New document types beyond `./docs/` corpus | Not in scope — known format only |
| lachman_sf / kalyvas_sf item-level noise below 97% | Items that cannot be matched due to structural ambiguity with no dollar impact — not in scope |

## Constraints

- Must not regress rough-draft baseline (lachman + kalyvas tests must stay passing)
- Golden masters updated only after parser fix is confirmed correct
- Authoritative gap input: `packages/parser/tests/GAP-REPORT.md`
- Success definition: all 12 pytest tests in `test_coverage.py` pass

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFINAL-01 | Phase 26 | Complete |
| CFINAL-02 | Phase 26 | Complete |
| SF-01 | Phase 27 | Complete |
| SF-02 | Phase 27 | Complete |
| SFPART-01 | Phase 27 | Complete |
| META-01 | Phase 28 | Pending |
| META-02 | Phase 28 | Pending |
| META-03 | Phase 28 | Pending |
| VALID-01 | Phase 28 | Pending |
| VALID-02 | Phase 28 | Pending |
| VALID-03 | Phase 28 | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after roadmap creation (phases confirmed)*
