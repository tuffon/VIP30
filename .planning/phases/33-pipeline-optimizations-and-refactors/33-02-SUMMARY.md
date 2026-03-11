---
phase: 33-parser-recap-trade-summary-completeness
plan: 02
subsystem: parser
tags: [parser, statefarm, wrapped-lines, notes, regression-tests]

provides:
  - Conservative wrapped-description detection in State Farm line-item parsing
  - Regression coverage for `SF_BSchacter.pdf` line items `#2` and `#276`
  - Preservation of true note text when wrap detection is not confident

completed: 2026-03-11
---

# Phase 33 Plan 02 Summary

Fixed the known State Farm wrapped-line versus notes bug without making notes handling aggressive.

## Delivered

- Updated `packages/parser/vip_parser/xactimate/parser.py` to split pending line fragments into:
  - wrapped description continuations
  - retained note text
- Added conservative wrap detection based on strong continuation signals only
- Added `packages/parser/tests/test_statefarm_wrapped_notes.py`

## Requirements

- Known `SF_BSchacter.pdf` wrapped-line cases parse correctly
- True notes remain attached as notes
- Ambiguous text still defaults to notes

## Verification

- `PYTHONPATH=. pytest packages/parser/tests/test_statefarm_wrapped_notes.py -q` — 1 passed
- `PYTHONPATH=. pytest packages/parser/tests/test_recap_trade_summary_contract.py packages/parser/tests/test_statefarm_wrapped_notes.py packages/parser/tests/test_coverage.py -k "trade_summary_contract or recap_by_category_contract or recap_trade_summary_contract or sf_bschacter" -q` — 21 passed

## Decisions

- Wrap promotion only happens on strong structural signals such as unmatched parentheses, explicit continuation punctuation, or short lower-case continuation chains
- Revision metadata like `End revisions by ...` remains in notes rather than being pulled into descriptions
