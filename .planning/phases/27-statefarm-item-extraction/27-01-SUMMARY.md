---
phase: 27-statefarm-item-extraction
plan: 01
subsystem: parser
tags: [xactimate, statefarm, layout-a, item-extraction, pdfplumber, regex, python]

# Dependency graph
requires:
  - phase: 26-contractor-final-parser
    provides: Phase C (contractor-final) parser with RESET/REMOVE/REPLACE column layout
  - phase: 25-coverage-harness
    provides: pytest coverage tests and golden masters as regression baseline
provides:
  - StateFarm Customer Copy item extraction — all line items per section extracted (not just non-asterisk items)
  - GCO&P header normalized to O&P via HEADER_VARIANTS
  - has_op=True for Layout A tables containing GCO&P
  - price_star_pat stripping asterisk-flagged price tokens from _parse_layout_a_line
  - Correct field mapping for tax/op when asterisk price is present
affects:
  - phase-28-golden-master-regeneration
  - GAP-REPORT.md (sf_bschacter coverage jumps from 3% to ~97%)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "price_star_pat: regex '^[\\d,]+\\.\\d+\\*[A-Za-z]*$' matches StateFarm asterisk-flagged unit prices"
    - "has_asterisk_price flag: controls required_numeric threshold and tax/op field mapping"
    - "top_tokens vs top_filtered: check pre-filter tokens for optional columns (O&P) not in candidate set"

key-files:
  created: []
  modified:
    - packages/parser/vip_parser/xactimate/constants.py
    - packages/parser/vip_parser/xactimate/helpers.py
    - packages/parser/vip_parser/xactimate/parser.py

key-decisions:
  - "GCO&P added to HEADER_VARIANTS O&P set — StateFarm uses GCO&P (General Contractor O&P) label instead of O&P"
  - "has_op check uses top_tokens (pre-filter) not top_filtered — layout_a_candidates set intentionally excludes O&P so it must be checked before filtering"
  - "required_numeric=1 for asterisk-price items — bid items may omit op, so only total is guaranteed at end"
  - "item dict uses 'if tax_token is not None' not 'if columns.has_tax' — prevents writing None when asterisk items omit tax"

patterns-established:
  - "Pre-filter token check: when optional columns are filtered out of candidate set, check original top_tokens for those columns before building TableColumns"
  - "Asterisk-price stripping: pop flagged token after pure-numeric stripping; set has_asterisk_price flag to adjust downstream logic"

# Metrics
duration: 14min
completed: 2026-03-09
---

# Phase 27 Plan 01: StateFarm Item Extraction Summary

**price_star_pat regex pops asterisk-flagged unit prices from Layout A token stream, enabling full item extraction from StateFarm Customer Copy format — SF_BSchacter jumps from 1/31 to 30/31 sections with items**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-09T15:06:18Z
- **Completed:** 2026-03-09T15:20:42Z
- **Tasks:** 4/4
- **Files modified:** 3

## Accomplishments

- SF_BSchacter: 30/31 sections with items (306 total items) — was 1/31 (3%) before fix
- kalyvas_sf Ext_Surfaces: 7 items extracted — was 5 (2 asterisk-price items now parsed)
- lachman_sf PRC RESTORATION INC.: 1 item — was 0
- Rough-draft baseline preserved: both lachman and kalyvas test_section_coverage PASS (2/2)
- GCO&P correctly normalized to O&P, has_op=True for StateFarm Layout A tables

## Task Commits

Each task was committed atomically:

1. **Task 1: Add GCO&P to HEADER_VARIANTS in constants.py** - `b0ca8f9` (feat)
2. **Task 2: Fix has_op detection for Layout A with GCO&P in helpers.py** - `609eb29` (feat)
3. **Task 3: Fix _parse_layout_a_line in parser.py to handle price-with-asterisk tokens** - `8f41c59` (feat)
4. **Task 4: Regression tests** - (read-only verification, no files changed)

**Plan metadata:** committed with docs(27-01) metadata commit

## Files Created/Modified

- `packages/parser/vip_parser/xactimate/constants.py` - Added `"GCO&P"` to the O&P variants set in HEADER_VARIANTS
- `packages/parser/vip_parser/xactimate/helpers.py` - Changed `has_op=False` to `has_op='O&P' in top_tokens` in layout_a_candidates fallback branch
- `packages/parser/vip_parser/xactimate/parser.py` - Added `price_star_pat`, `has_asterisk_price` flag, adjusted `required_numeric`, fixed `op_token`/`tax_token` field mapping, changed item dict write guard to `if tax_token is not None` and added `if op_token is not None`

## Decisions Made

- **GCO&P added to HEADER_VARIANTS O&P set** — StateFarm Customer Copy uses "GCO&P" (General Contractor O&P) as the column label. normalize_header_label("GCO&P") returned None before this fix, causing the token to be silently dropped from top_tokens.
- **has_op check uses pre-filter top_tokens** — The layout_a_candidates set is `{"DESCRIPTION", "QUANTITY", "UNIT", "PRICE", "TAX", "RCV"}` and intentionally excludes O&P (regular Layout A never has it). Checking top_filtered for O&P would always return False. The fix checks top_tokens (which includes O&P after GCO&P normalization) before filtering.
- **required_numeric=1 for asterisk-price items** — Normal Layout A requires price+tax+total at end (3 with has_tax). When price has asterisk, price is consumed by the pop, so end numerics are only [total, op, tax]. Some bid-type items omit op, so only total is guaranteed. Setting required_numeric=1 handles all cases.
- **item dict uses `if tax_token is not None`** — Replaces `if columns.has_tax:` to prevent assigning None to item['tax'] when tax_token was not available (e.g., asterisk items without enough trailing numerics).

## Deviations from Plan

None — plan executed exactly as written. PDF paths differed from those listed in the plan (plan referenced `docs/final-drafts/SF_BSchacter-01.28.26-Est-JVB-StateFarm-Customer-Copy.pdf` style paths; actual paths are under `docs/final-drafts/statefarm/` at project root), but this was a documentation difference only. The conftest.py fixtures confirmed the correct paths and were used for verification.

## Issues Encountered

None. All three code changes were straightforward targeted fixes. The price_star_pat pop correctly unblocks qty_unit parsing for asterisk-price items without affecting any other line types.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- StateFarm item extraction complete — SF_BSchacter at 30/31 sections (97%+), lachman_sf and kalyvas_sf at full item coverage
- Phase 28 (golden master regeneration) ready: parser output is now the correct ground truth for StateFarm documents
- GAP-REPORT.md should be regenerated to reflect the Phase 27 improvements (sf_bschacter ~3% → ~97%)
- Remaining section delta (lachman_sf 3 sections with declared vs computed delta): Office Bath, Master Bathroom, Linen Closet — these have partial item extraction (items found but totals don't match declared); low-priority investigation
- kalyvas_sf 4 sections with no items (32/36): likely excluded/zero-item sections similar to those documented in Phase 24-02

---
*Phase: 27-statefarm-item-extraction*
*Completed: 2026-03-09*
