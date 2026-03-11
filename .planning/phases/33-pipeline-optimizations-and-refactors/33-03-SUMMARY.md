---
phase: 33-parser-recap-trade-summary-completeness
plan: 03
subsystem: parser
tags: [goldens, gap-report, coverage, regression-suite, fixtures]

provides:
  - Refreshed parser golden corpus for all tracked documents
  - New golden for `SCHACTER_RECON_6B_FINAL_DRAFT_CAR.pdf`
  - Gap report regenerated from the updated parser baseline
  - Full parser suite green on the seven-document corpus

completed: 2026-03-11
---

# Phase 33 Plan 03 Summary

Rebuilt the parser regression baseline after the contract and wrapped-line fixes.

## Delivered

- Regenerated the tracked parser goldens in `packages/parser/tests/golden/`
- Added `packages/parser/tests/golden/final-drafts/SCHACTER_RECON_6B_FINAL_DRAFT_CAR.golden.json`
- Added the source PDF `docs/final-drafts/SCHACTER_RECON_6B_FINAL_DRAFT_CAR.pdf` to the tracked regression corpus
- Updated `packages/parser/scripts/generate_gap_report.py` to match duplicate section names positionally, consistent with `test_coverage.py`
- Regenerated `packages/parser/tests/GAP-REPORT.md`

## Requirements

- Golden corpus matches verified parser reality
- New Schacter final-draft document is represented in tests and fixtures
- Full parser regression suite passes
- Gap report reflects the updated baseline

## Verification

- `PYTHONPATH=. pytest packages/parser/tests -q` — 36 passed
- `PYTHONPATH=packages/parser:. python packages/parser/scripts/generate_gap_report.py` — regenerated report with 100% coverage on the tracked corpus

## Decisions

- Golden refresh was applied to the full tracked parser corpus so the explicit `trade_summary: null` contract is consistent everywhere
- Gap report duplicate-section matching now follows the same positional approach as the coverage harness, preventing false partial coverage on `SF_BSchacter`
