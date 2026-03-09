---
phase: 27-statefarm-item-extraction
verified: 2026-03-09T16:49:38Z
status: passed
score: 4/4 must-haves verified
---

# Phase 27: StateFarm Item Extraction Verification Report

**Phase Goal:** Fix grouped-row extraction — all items per section captured across StateFarm documents
**Verified:** 2026-03-09T16:49:38Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                      | Status     | Evidence                                                                                                                      |
|----|--------------------------------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------------------------------------------------|
| 1  | SF_BSchacter parser produces ≥27 of 30 non-excluded sections with line items (≥90%)        | VERIFIED   | Live parse: 30/31 sections with items, 306 total items — 96.8%, well above 90% threshold                                     |
| 2  | lachman_sf PRC RESTORATION INC. section produces exactly 1 line item (was 0)               | VERIFIED   | Live parse: PRC RESTORATION INC. section has 1 item — `Cleaning (Bid Item) 1.0 EA total=14,137.76`                           |
| 3  | kalyvas_sf Ext_Surfaces section produces 7 line items (was 5)                              | VERIFIED   | Live parse: Ext_Surfaces has 7 items — includes items 480 (Stucco color coat) and 483 (Soda blasting), the two asterisk-price items |
| 4  | Rough-draft baseline preserved — lachman and kalyvas test_section_coverage still pass       | VERIFIED   | `pytest -k "rough and section_coverage"`: 2 passed, 0 failed in 94.72s                                                      |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact                                                        | Expected                                                  | Status   | Details                                                                                          |
|-----------------------------------------------------------------|-----------------------------------------------------------|----------|--------------------------------------------------------------------------------------------------|
| `packages/parser/vip_parser/xactimate/constants.py`             | "GCO&P" in HEADER_VARIANTS O&P set                        | VERIFIED | Line 57: `"O&P": {"O&P", "OP", "O & P", "O / P", "OVERHEAD/PROFIT", "O&P.", "GCO&P"}` — present |
| `packages/parser/vip_parser/xactimate/helpers.py`               | `has_op='O&P' in top_tokens` in layout_a_candidates branch | VERIFIED | Line 272: `has_op='O&P' in top_tokens` in layout_a_candidates branch (line 264-274). Also present at line 249 in Family C branch (correct). |
| `packages/parser/vip_parser/xactimate/parser.py`                | `price_star_pat` regex defined and used                   | VERIFIED | Line 773: `price_star_pat = re.compile(r'^[\d,]+\.\d+\*[A-Za-z]*$')`. Line 782: used in `if tokens and price_star_pat.match(tokens[-1])`. Full has_asterisk_price flag, field mapping, and item dict write guards implemented at lines 781-835. |

### Key Link Verification

| From                                          | To                                    | Via                                            | Status   | Details                                                                                                                                    |
|-----------------------------------------------|---------------------------------------|------------------------------------------------|----------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `helpers.py:layout_a_candidates` branch       | `parser.py:_parse_layout_a_line`       | `TableColumns(has_op=True)` for SF tables      | WIRED    | Live test: `is_table_header("DESCRIPTION QUANTITY UNIT PRICE TAX GCO&P RCV", ...)` returns `family=A, has_op=True, has_tax=True`. Regular Layout A (no GCO&P) still returns `has_op=False`. |
| `parser.py:_parse_layout_a_line`              | `constants.py:HEADER_VARIANTS`         | GCO&P normalized to O&P by normalize_header_label | WIRED | Live test: `normalize_header_label("GCO&P")` returns `"O&P"`. This flows through `is_table_header` → `top_tokens` → `has_op='O&P' in top_tokens`. |

### Requirements Coverage

| Requirement | Status    | Notes                                                                                              |
|-------------|-----------|----------------------------------------------------------------------------------------------------|
| SF-01       | SATISFIED | Parser extracts all line items including asterisk-price items — price_star_pat pop unblocks qty_unit parsing |
| SF-02       | SATISFIED | SF_BSchacter: 30/31 sections with items (96.8% ≥ 90%)                                              |
| SFPART-01   | SATISFIED | lachman_sf PRC: 1 item; kalyvas_sf Ext_Surfaces: 7 items                                           |
| VALID-01    | SATISFIED | 2/2 rough-draft test_section_coverage PASS — no regression                                         |

### Anti-Patterns Found

None. Scanned `constants.py`, `helpers.py`, and `parser.py` for TODO/FIXME/placeholder/stub patterns — zero matches.

### Human Verification Required

None. All must-haves verified programmatically via live parser runs against real PDFs and pytest regression suite.

### Additional Observations

- The summary claimed 30/31 sections with items. Verification confirms exactly that — 1 section has no items (likely a zero-total legitimately excluded section, consistent with Phase 24-02 findings).
- lachman_sf shows 34/34 sections with items (368 total items), with 3 sections having declared-vs-computed deltas (Office Bath, Master Bathroom, Linen Closet) — noted in summary as low-priority, not part of Phase 27 must-haves.
- kalyvas_sf shows 32/36 sections with items — the 4 zero-item sections are consistent with known excluded sections, not a regression.
- The `has_op='O&P' in top_tokens` pattern appears at both line 249 (Family C branch) and line 272 (layout_a_candidates branch). Both are correct — Family C legitimately has O&P and was already handled; the Phase 27 fix targeted line 272 only.

---

_Verified: 2026-03-09T16:49:38Z_
_Verifier: Claude (gsd-verifier)_
