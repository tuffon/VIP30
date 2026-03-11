---
phase: 33-parser-recap-trade-summary-completeness
plan: 01
subsystem: parser
tags: [parser, recap-by-category, trade-summary, contract-tests, golden-corpus]

provides:
  - Explicit `recaps_and_summaries.trade_summary` contract with `null` when absent
  - Canonical `recap_by_category` contract coverage across the parser corpus
  - Parser corpus expanded to include `SCHACTER_RECON_6B_FINAL_DRAFT_CAR.pdf`
  - Contract tests for recap/trade-summary presence and structure

completed: 2026-03-11
---

# Phase 33 Plan 01 Summary

Locked the parser output contract for recap and trade summary data before fixture refresh.

## Delivered

- Updated `packages/parser/vip_parser/xactimate/parser.py` so `recaps_and_summaries.trade_summary` is always present, using `null` when the source document has no trade summary section
- Kept `recaps_and_summaries.recap_by_category` as the canonical normalized parser structure
- Added `packages/parser/tests/test_recap_trade_summary_contract.py`
- Extended `packages/parser/tests/test_coverage.py` with hard-failure contract checks
- Expanded `packages/parser/tests/conftest.py` to include the new `SCHACTER_RECON_6B_FINAL_DRAFT_CAR.pdf` corpus entry

## Requirements

- Phase 33 output contract: `recap_by_category` always present under `recaps_and_summaries`
- Phase 33 output contract: `trade_summary` parsed when present, `null` when absent
- Regression harness must fail when recap/trade-summary contract is violated

## Verification

- `PYTHONPATH=. pytest packages/parser/tests/test_recap_trade_summary_contract.py packages/parser/tests/test_coverage.py -k "trade_summary_contract or recap_by_category_contract or recap_trade_summary_contract" -q` — 18 passed

## Decisions

- Trade summary presence is determined by non-null content, not by key existence alone, because the parser now emits explicit `null`
- Contract tests rely on verified parser reality from the tracked corpus, not aspirational fixture values
