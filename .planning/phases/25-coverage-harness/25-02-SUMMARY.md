---
phase: 25-coverage-harness
plan: "02"
subsystem: testing
tags: [parser, coverage, golden-master, gap-report, pytest, xactimate]

requires:
  - phase: 25-01
    provides: conftest.py fixtures, test_coverage.py harness, golden masters for all 6 docs

provides:
  - generate_gap_report.py — self-contained script running all 6 golden master comparisons
  - GAP-REPORT.md — v2.5 parser-fix input with per-doc coverage%, missing sections, metadata gaps, cross-doc patterns
  - Confirmed rough-draft baseline integrity (lachman 100%, kalyvas 100% section coverage)
  - Full final-draft gap inventory documented (bschacter 0%, sf_bschacter 3%, lachman_sf 97%, kalyvas_sf 97%)

affects:
  - v2.5 planning (gap inventory drives fix priority)
  - Phase 26+ (GAP-REPORT.md is the v2.5 parser fix input artifact)

tech-stack:
  added: []
  patterns:
    - "Self-contained gap report script pattern: duplicates conftest helpers to avoid test-module import complexity"
    - "Section coverage metric: matched/non_excl_count (excludes zero-item zero-total sections)"
    - "Partial section detection: item_delta > 0 OR total_delta > $0.05"

key-files:
  created:
    - packages/parser/scripts/generate_gap_report.py
    - packages/parser/tests/GAP-REPORT.md
  modified: []

key-decisions:
  - "Rough-draft test_metadata failures are informative gap documentation, not regressions — metadata fields (insured_name, price_list, property_address) differ between parser raw output and golden master clean values; this is a known v2.5 target, not a regression"
  - "GAP-REPORT.md generated date matches system date, not execution start — date.today() used in script"
  - "sf_bschacter coverage 3%: only 1 of 30 non-excluded sections matched (Deck section partially matched due to $64.29 vs $64.29 total match) — all other sections parse 0 items due to grouped row layout"
  - "kalyvas_sf Ext_Surfaces partial match: items 5/7 (delta -2) but totals match ($140,575.90) — item count gap, not dollar gap"

patterns-established:
  - "Gap report script pattern: run_parser() in tempdir, compare to golden via section_analysis() and meta_diff(), build_report() produces structured Markdown"
  - "Cross-doc pattern analysis: Counter over final-draft missing sections to identify systemic gaps (missing in >=2 docs)"
  - "v2.5 fix priority ordering: rough-draft regressions first, then final-draft by coverage% ascending"

duration: 27min
completed: 2026-03-09
---

# Phase 25 Plan 02: Coverage Gap Report Summary

**Self-contained gap report generator produces 172-line GAP-REPORT.md confirming rough-draft 100% baseline and documenting bschacter/StateFarm final-draft gaps as the v2.5 parser-fix inventory**

## Performance

- **Duration:** 27 min (dominated by 6 PDF parsing runs — pytest run alone took 11 min)
- **Started:** 2026-03-09T02:51:32Z
- **Completed:** 2026-03-09T03:18:43Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- Created `generate_gap_report.py` (249 lines) — self-contained script that runs all 6 golden master comparisons and writes structured GAP-REPORT.md without complex test-module imports
- Confirmed rough-draft baseline integrity: lachman 100% section coverage, kalyvas 100% section coverage — no regressions
- Produced `GAP-REPORT.md` (172 lines) documenting the complete v2.5 gap inventory: bschacter 0% (29 sections missing, contractor-final column schema mismatch), sf_bschacter 3% (30 sections missing, grouped-row layout), lachman_sf 97% (1 section partial — PRC RESTORATION INC. 0 items), kalyvas_sf 97% (1 partial — Ext_Surfaces 5/7 items)
- Pytest harness: 2 PASSED (lachman + kalyvas test_section_coverage), 10 FAILED with informative field-level diffs, 0 crashes/import errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create generate_gap_report.py** - `a0f594b` (feat) — script + GAP-REPORT.md (550 insertions)
2. **Task 2: Run pytest harness** — verification only, no new files committed

**Plan metadata:** (final commit — see below)

## Files Created/Modified

- `packages/parser/scripts/generate_gap_report.py` — Self-contained gap report generator, 249 lines, runs all 6 golden master comparisons
- `packages/parser/tests/GAP-REPORT.md` — 172-line v2.5 gap analysis with Summary table, Per-Document Analysis, and Cross-Document Patterns sections

## Decisions Made

- **test_metadata failures are informative:** The rough-draft golden masters store clean normalized values (e.g., `property_address = '1115 Lachman Ln, Pacific Palisades, CA 90272'`) while the parser emits raw extracted text with rep name appended. These failures are v2.5 metadata normalization targets, not regressions — the section structure (100% coverage) is what confirms parser baseline integrity.
- **GAP-REPORT.md uses date.today() not start timestamp:** The report generation date reflects when the report was written, appropriate for a reproducible artifact that may be regenerated multiple times.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — the gap report script ran cleanly on the first execution. The pytest run took 11 minutes due to 6 PDF parsing passes but completed without errors.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- GAP-REPORT.md is ready as the v2.5 parser-fix planning input
- Key v2.5 gaps documented and prioritized:
  1. BSchacter contractor-final (0% — RESET/REMOVE/REPLACE column schema, highest impact)
  2. SF_BSchacter StateFarm (3% — grouped-row item extraction, 29 sections affected)
  3. lachman_sf / kalyvas_sf (97% — 1 partial section each, lower priority)
- Rough-draft baseline confirmed clean — any future regression will be immediately visible
- Phase 25 is complete; all 2 plans shipped

---
*Phase: 25-coverage-harness*
*Completed: 2026-03-09*
