---
phase: 24-golden-masters
plan: 02
subsystem: testing
tags: [pdfplumber, json, golden-masters, xactimate, statefarm, contractor-final]

# Dependency graph
requires:
  - phase: 24-01
    provides: rough-draft golden masters (lachman 32/525, kalyvas 40/887); golden master directory structure and README
  - phase: 23-02
    provides: AUDIT-REPORT.md with per-field coverage tables and gap inventory; audit output JSON files for all 6 PDFs
provides:
  - packages/parser/tests/golden/final-drafts/bschacter.golden.json (29 sections, 477 line items)
  - packages/parser/tests/golden/final-drafts/statefarm/customer_copy.golden.json (31 sections, 192 line items)
  - packages/parser/tests/golden/final-drafts/statefarm/lachman_sf.golden.json (34 sections, 368 line items)
  - packages/parser/tests/golden/final-drafts/statefarm/kalyvas_sf.golden.json (36 sections, 520 line items)
  - Complete case_metadata for all StateFarm files (extracted from PDF page 3 via pdfplumber)
affects:
  - phase-25-coverage-harness (can diff against all 6 golden masters; final-draft masters are ground truth for v2.5 parser)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Golden master case_metadata sourced from PDF page 3 (claim number, policy number, property address, date_of_loss, date_inspected, price_list)"
    - "Sections legitimately empty in PDF documented with _note fields rather than left unexplained"
    - "PRC RESTORATION INC. pattern: Bid items with EN flag have tax=0.0 (not mirroring total)"

key-files:
  created:
    - packages/parser/tests/golden/final-drafts/bschacter.golden.json
    - packages/parser/tests/golden/final-drafts/statefarm/customer_copy.golden.json
    - packages/parser/tests/golden/final-drafts/statefarm/lachman_sf.golden.json
    - packages/parser/tests/golden/final-drafts/statefarm/kalyvas_sf.golden.json
    - packages/parser/scripts/extract_bschacter.py
    - packages/parser/scripts/extract_statefarm.py
    - packages/parser/scripts/update_golden_masters.py
  modified:
    - packages/parser/tests/golden/final-drafts/statefarm/customer_copy.golden.json (post-checkpoint corrections)
    - packages/parser/tests/golden/final-drafts/statefarm/lachman_sf.golden.json (post-checkpoint corrections)
    - packages/parser/tests/golden/final-drafts/statefarm/kalyvas_sf.golden.json (post-checkpoint corrections)

key-decisions:
  - "BSchacter recap_tax_op=null is correct — contractor-final format uses category-level O&P summary (not per-section tax/OP table). Parser limitation confirmed."
  - "Sections with 0 line items in PDF are legitimately empty — customer_copy Dwelling Roof and kalyvas Mitigation/HVAC/Landscaping/Code Upgrades are explicitly excluded in PDF text. Not parser failures."
  - "PRC RESTORATION INC. tax field was incorrectly set to 14137.76 (total echoed into tax) — corrected to 0.0 (bid item with EN flag)"
  - "StateFarm case_metadata (claim, policy, address, dates) extracted from PDF page 3 via pdfplumber — parser cannot extract these from the two-column summary page layout"

patterns-established:
  - "Line item count is the primary metric for golden master completeness, not section count alone"
  - "case_metadata populated from PDF page 3 (always contains insured metadata in StateFarm format)"

# Metrics
duration: 90min
completed: 2026-03-08
---

# Phase 24 Plan 02: Final-Draft Golden Masters Summary

**Four final-draft golden masters created via pdfplumber PDF extraction: BSchacter contractor-final (29 sections, 477 items), StateFarm Customer Copy (31 sections, 192 items), StateFarm Lachman (34 sections, 368 items), StateFarm Kalyvas (36 sections, 520 items) — all with case_metadata populated and recaps verified.**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-03-08T00:00:00Z
- **Completed:** 2026-03-08T00:00:00Z
- **Tasks:** 2 (+ checkpoint + post-checkpoint corrections)
- **Files modified:** 7 total (4 golden masters, 3 scripts)

## Accomplishments

- Created BSchacter contractor-final golden master: 29 sections, 477 line items extracted via pdfplumber from a RESET/REMOVE/REPLACE/TAX/O&P column format the parser cannot handle
- Created 3 StateFarm final-draft golden masters from parser audit output supplemented with pdfplumber extraction for high-delta sections
- Populated case_metadata for all 3 StateFarm files (claim_number, policy_number, property_address, date_of_loss, date_inspected, price_list, loss_type) from PDF page 3
- Post-checkpoint corrections: added 5 Stairs line items to customer_copy, fixed PRC RESTORATION INC. tax bug in lachman, verified all recaps_and_summaries sub-fields populated

## Task Commits

Each task was committed atomically:

1. **Task 1: BSchacter contractor-final golden master** - `d21d8c2` (feat)
2. **Task 2: StateFarm golden masters** - `8b1b61e` (feat)
3. **Post-checkpoint corrections** - `7eaddb2` (fix)

## Files Created/Modified

- `packages/parser/tests/golden/final-drafts/bschacter.golden.json` - Contractor-final golden master, 29 sections, 477 line items, RESET/REMOVE/REPLACE/TAX/O&P column format
- `packages/parser/tests/golden/final-drafts/statefarm/customer_copy.golden.json` - StateFarm Customer Copy, 31 sections, 192 items; metadata and Stairs section added post-checkpoint
- `packages/parser/tests/golden/final-drafts/statefarm/lachman_sf.golden.json` - StateFarm Lachman, 34 sections, 368 items; metadata added, PRC RESTORATION INC. tax fixed
- `packages/parser/tests/golden/final-drafts/statefarm/kalyvas_sf.golden.json` - StateFarm Kalyvas, 36 sections, 520 items; metadata added post-checkpoint
- `packages/parser/scripts/extract_bschacter.py` - pdfplumber extraction script for BSchacter format
- `packages/parser/scripts/extract_statefarm.py` - pdfplumber extraction script for StateFarm format
- `packages/parser/scripts/update_golden_masters.py` - Post-checkpoint correction script

## Golden Master Final Summary

| File | Sections | Total Line Items | Recaps | Metadata |
|------|----------|------------------|--------|----------|
| bschacter.golden.json | 29 | 477 | summaries_by_coverage, recap_by_room, recap_by_category (recap_tax_op=null, parser limitation) | claim_number, policy_number, loss_type, property_address, date_entered |
| customer_copy.golden.json | 31 | 192 | all 4 fields populated | claim_number, policy_number, loss_type, property_address, date_of_loss, date_inspected, price_list |
| lachman_sf.golden.json | 34 | 368 | all 5 fields (incl. trade_summary) | claim_number, policy_number, loss_type, property_address, date_of_loss, date_inspected, price_list |
| kalyvas_sf.golden.json | 36 | 520 | all 5 fields (incl. trade_summary) | claim_number, policy_number, loss_type, property_address, date_of_loss, date_inspected, price_list |

### Sections with 0 Line Items (Legitimate — PDF confirms no items)

- **customer_copy — Dwelling Roof**: PDF explicitly states "No accidental direct physical loss noted to the dwelling roof." Total = $0.00
- **kalyvas — Mitigation & Cleaning**: PDF states exclusion text. Total = $0.00
- **kalyvas — HVAC**: PDF states "evaluation of the HVAC system is pending a specialty contractor." Total = $0.00
- **kalyvas — Landscaping**: PDF states "All landscaping repairs are excluded." Total = $0.00
- **kalyvas — Code Upgrades**: PDF states code upgrades addressed separately. Total = $0.00

## Decisions Made

- **BSchacter recap_tax_op=null is correct** — contractor-final format uses a category-level O&P breakdown (O&P Items / Non-O&P Items) not a per-section tax/OP table. Parser cannot extract this in the expected recap format. Documented as parser gap for v2.5.
- **Sections with 0 items in PDF are legitimate exclusions** — not parser failures. Dwelling Roof in customer_copy has an explicit "no loss" statement; kalyvas utility sections have explicit exclusion text. These sections SHOULD have 0 items in the golden master.
- **PRC RESTORATION INC. line item bug fixed** — tax field was incorrectly set to 14137.76 (total value echoed into tax column). PDF shows tax=0.00 for this bid item with EN flag. Corrected to tax=0.0, total=14137.76.
- **StateFarm case_metadata sourced from PDF page 3** — the parser cannot extract metadata from the StateFarm two-column summary page (page 3); pdfplumber extraction works reliably. Pattern established: claim_number, policy_number, property_address, date_of_loss, date_inspected, price_list are always on page 3 of StateFarm estimates.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PRC RESTORATION INC. tax value incorrect in lachman golden master**
- **Found during:** Post-checkpoint corrections
- **Issue:** tax field was 14137.76 (total echoed into tax); PDF clearly shows 0.00 tax for this bid item
- **Fix:** Corrected tax=0.0, added qty, unit_price, _note fields for clarity
- **Files modified:** packages/parser/tests/golden/final-drafts/statefarm/lachman_sf.golden.json
- **Verification:** Section total 14,137.76 unchanged; tax=0.0 confirmed correct from PDF
- **Committed in:** 7eaddb2 (post-checkpoint corrections)

---

**Total deviations:** 1 auto-fixed (1 data bug)
**Impact on plan:** Bug fix corrects incorrect tax attribution. No scope creep.

## Issues Encountered

- **StateFarm Customer Copy Stairs section**: Parser returned 0 items despite 5 line items in PDF. Items were extracted directly from PDF (page 13, items 27-31: I-joist, OSB sheathing, drilled bottom plate, stair tread paint, stair riser paint). Total confirmed $1,602.34 matches section declared total.
- **StateFarm metadata**: All 3 StateFarm files had null case_metadata from parser. Populated via pdfplumber extraction from page 3 of each PDF. Pattern established for v2.5 parser enhancement.
- **BSchacter recap_tax_op**: Parser could not extract the category-level O&P recap table. PDF pages 46-47 have a category breakdown (LABOR ONLY, PAINTING, STUCCO etc.) but not in the per-section format the parser expects. Documented as null with explanation; this is a parser format limitation not a data absence.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 6 golden masters now exist (2 rough-draft from Plan 24-01, 4 final-draft from Plan 24-02)
- Phase 25 coverage harness can diff parser output against all 6 golden masters
- rough-draft masters (lachman.golden.json, kalyvas.golden.json) are zero-delta regression baselines
- final-draft masters represent IDEAL parser output for v2.5 — current parser will have deltas which the harness can quantify
- BSchacter contractor-final: expected gap is 29 sections, 477 items (parser returns 0 sections)
- StateFarm Customer Copy: expected gap is significant (192 items vs ~32 parser items)
- StateFarm Lachman and Kalyvas: small gaps in specific sections only

---
*Phase: 24-golden-masters*
*Completed: 2026-03-08*
