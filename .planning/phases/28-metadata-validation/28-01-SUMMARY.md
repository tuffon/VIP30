---
phase: 28-metadata-validation
plan: 01
subsystem: parser
tags: [pdfplumber, xactimate, metadata, regex, statefarm]

requires:
  - phase: 27-statefarm-extraction
    provides: StateFarm item extraction fixes; SF_BSchacter 30/31 sections passing
  - phase: 26-contractor-final
    provides: Contractor-final column schema fix; bschacter 29 sections extracted

provides:
  - read_sf_summary_page_text() method in ParserIO — scans first 8 pages for SF summary page
  - SF_INSURED_PATTERN, SF_PRICE_LIST_PATTERN, SF_PROPERTY_PATTERN in constants.py
  - _augment_sf_metadata() in XactimateRoughDraftParser — populates insured_name/price_list/property_address
  - StateFarm metadata extraction: insured_name, price_list, property_address now non-null for all 3 SF PDFs

affects:
  - 28-02 (golden master regeneration — metadata fields now populated, regeneration will capture new values)
  - Any future phase that uses case_metadata output from SF PDFs

tech-stack:
  added: []
  patterns:
    - SF augmentation guard — only call _augment_sf_metadata when both insured_name and price_list are null
    - SF branding discriminator — require 'State Farm' in page text to avoid false-positive on contractor-final
    - Summary Guide skip — skip page 2 (reference page with placeholder values) before scanning

key-files:
  created: []
  modified:
    - packages/parser/vip_parser/xactimate/io.py
    - packages/parser/vip_parser/xactimate/constants.py
    - packages/parser/vip_parser/xactimate/parser.py

key-decisions:
  - "Skip 'Building Estimate Summary Guide' page (page 2) which has same field labels as real summary page but with placeholder values"
  - "Require 'State Farm' branding marker to distinguish SF pages from contractor-final page 1 (both have Insured:/Price List:/Estimate:)"
  - "SF augmentation guard: only trigger when both insured_name and price_list are null — rough-drafts have price_list from page 1 so they are never augmented"

patterns-established:
  - "Page-type detection before extraction: use branding markers and exclusion keywords to identify target page"
  - "Guard-clause for augmentation: check null conditions before calling SF-specific path to avoid cross-doc contamination"

duration: 35min
completed: 2026-03-09
---

# Phase 28 Plan 01: Metadata Validation Summary

**StateFarm metadata extraction implemented — insured_name, price_list, property_address now non-null for all 3 SF final-draft PDFs via two-column summary page (page 3) parsing.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-03-09T16:10:00Z
- **Completed:** 2026-03-09T16:45:00Z
- **Tasks:** 5
- **Files modified:** 3

## Accomplishments

- SF_BSchacter gap confirmed: "Dwelling Roof" section has total=$0.00 and 0 items — legitimately excluded per test logic (not a parser gap); Phase 27 achieves 30/30 (100%) non-excluded sections
- `read_sf_summary_page_text()` added to ParserIO: reliably returns page 3 text for all 3 SF PDFs while returning None for bschacter contractor-final
- Three regex patterns added to constants.py: SF_INSURED_PATTERN, SF_PRICE_LIST_PATTERN, SF_PROPERTY_PATTERN; all verified against actual PDF text
- `_augment_sf_metadata()` added to parser: extracts insured_name/price_list/property_address from SF summary page; called from `_parse_case_metadata` via null-guard
- Rough-draft baseline preserved: test_section_coverage PASSED for lachman and kalyvas (2/2)

## Task Commits

Each task was committed atomically:

1. **Task 1: Investigate SF_BSchacter 1-section gap** — investigation only, no code change; documented in summary
2. **Task 2: Add read_sf_summary_page_text()** — `d053173` (feat)
3. **Task 3: Add SF metadata patterns to constants.py** — `ab245c0` (feat)
4. **Task 4: Add _augment_sf_metadata() to parser.py** — `c69d914` (feat)
5. **Fix: Add State Farm branding discriminator** — `7146b5a` (fix, deviation Rule 1)
6. **Task 5: Regression test** — verification only, no code change

## Files Created/Modified

- `packages/parser/vip_parser/xactimate/io.py` — added `read_sf_summary_page_text()` with Summary Guide skip and State Farm branding discriminator
- `packages/parser/vip_parser/xactimate/constants.py` — added SF_INSURED_PATTERN, SF_PRICE_LIST_PATTERN, SF_PROPERTY_PATTERN and their __all__ entries
- `packages/parser/vip_parser/xactimate/parser.py` — added `md['insured_name'] = None` init, SF augmentation call in `_parse_case_metadata`, and `_augment_sf_metadata()` method

## Decisions Made

- **Skip 'Building Estimate Summary Guide' page:** SF PDFs have a page 2 "Building Estimate Summary Guide" reference page with placeholder labels (e.g. `Insured: Smith, Joe & Jane`). Same field names as real data — must be excluded before scanning.
- **Require 'State Farm' branding marker:** Contractor-final PDFs (bschacter) have all four detection markers (`Insured:`, `Price List:`, `Estimate:`, `Claim Number:`) on page 1 but without `State Farm` branding. Adding `State Farm` as a required discriminator makes detection specific to SF-issued documents.
- **SF augmentation guard (insured_name AND price_list both null):** Rough-draft PDFs successfully extract `price_list` from page 1 via `PRICE_LIST_PATTERN`, so the null-guard (`price_list is None`) prevents SF augmentation from ever being called for rough-drafts. insured_name is initialized to None as a neutral default.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 'Building Estimate Summary Guide' page 2 triggered false positive in read_sf_summary_page_text()**

- **Found during:** Task 2 verification / Task 4 full-parser verification
- **Issue:** SF PDFs have a page 2 reference guide with placeholder labels identical to the real summary page labels. Scanning from page 1 returned the guide page (with `Smith, Joe & Jane` placeholder) instead of the real page 3.
- **Fix:** Added `if 'Summary Guide' in text: continue` before the detection check in `read_sf_summary_page_text()`.
- **Files modified:** `packages/parser/vip_parser/xactimate/io.py`
- **Verification:** All 3 SF PDFs returned page 3 preview showing correct insured names.
- **Committed in:** `c69d914` (part of Task 4 commit)

**2. [Rule 1 - Bug] Contractor-final bschacter triggered false positive — read_sf_summary_page_text() returned non-None**

- **Found during:** Task 5 verification (plan verification criteria: "returns None for bschacter")
- **Issue:** bschacter contractor-final page 1 contains `Insured:`, `Price List:`, `Estimate:`, and `Claim Number:` — same four markers used for detection. `read_sf_summary_page_text()` was incorrectly returning bschacter's page 1.
- **Fix:** Added `'State Farm' in text` as a required discriminator. bschacter page 1 is issued by Jared V. Boergadine (public adjuster), not State Farm — no "State Farm" text present. SF summary pages always have "State Farm" as a header.
- **Files modified:** `packages/parser/vip_parser/xactimate/io.py`
- **Verification:** bschacter returns `found=False`; all 3 SF PDFs still return `found=True`.
- **Committed in:** `7146b5a`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs in detection logic)
**Impact on plan:** Both fixes required for correctness. The SF augmentation guard (`price_list is None`) would have prevented incorrect augmentation of bschacter even without Fix 2, but `read_sf_summary_page_text()` returning a false positive for bschacter violates the stated verification criterion and is a correctness issue.

## Issues Encountered

- **SF page 2 placeholder interference:** The "Building Estimate Summary Guide" reference page (page 2 in all SF PDFs) reuses the same field labels as the real data page. Required explicit exclusion by page type keyword.
- **Contractor-final false positive:** bschacter page 1 contains all four detection markers. Required domain-specific discriminator ("State Farm" branding) rather than just field labels.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 28-02 (golden master regeneration) is ready: all 3 SF PDFs now produce non-null insured_name/price_list/property_address; golden masters need regeneration to capture new metadata values
- Rough-draft baseline preserved: 2/2 test_section_coverage PASS
- bschacter metadata unchanged: insured_name=None (contractor-final has no SF summary page), consistent with prior behavior

---
*Phase: 28-metadata-validation*
*Completed: 2026-03-09*
