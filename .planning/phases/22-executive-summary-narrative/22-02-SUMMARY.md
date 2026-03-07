---
phase: 22-executive-summary-narrative
plan: "02"
subsystem: api
tags: [xlsx, export, openpyxl, bid-comp, analysis-sheet, overall-summary]

# Dependency graph
requires:
  - phase: 22-01
    provides: writer prompt v2.4 with rich natural overview — LLM now produces prose that makes synthetic scope_observations append redundant
  - phase: 21-02
    provides: Kalyvas-style Analysis table layout with O&P footer separation
provides:
  - 5-column Analysis sheet category table (no Notes column)
  - _build_overall_summary returns LLM prose directly with no post-processing append
affects: [future-xlsx-export-work]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "LLM prose is the output — no post-processing appends to narrative fields"
    - "Analysis sheet and Summary sheet columns are independent — removing Notes from Analysis does not affect Summary Top Cost Drivers Notes column"

key-files:
  created: []
  modified:
    - packages/shared-python/vip_shared/bid_comp/export_xlsx.py

key-decisions:
  - "Remove Notes column from Analysis sheet — Summary Top Cost Drivers table already covers notable drivers with Notes; Analysis is a data table, not a narrative supplement"
  - "Strip scope_observations append from _build_overall_summary — the v2.4 prompt fix is the root-cause solution; bolting synthetic text onto LLM prose was a bandaid"
  - "_narrative_by_category function kept — still used by Summary sheet Top Cost Drivers table"

patterns-established:
  - "When prompt quality improves, remove code-level compensations that were patching poor LLM output"
  - "Analysis sheet border/format loops use range(1, 6) for 5-column layout"

# Metrics
duration: ~20min
completed: 2026-03-07
---

# Phase 22 Plan 02: XLSX Cleanup Summary

**Stripped synthetic scope_observations append from _build_overall_summary and removed Notes column from Analysis sheet category table — LLM prose now renders directly with no post-processing.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-07
- **Completed:** 2026-03-07
- **Tasks:** 3 (2 auto + 1 checkpoint:human-verify)
- **Files modified:** 1

## Accomplishments

- `_build_overall_summary` now returns `narrative.overview` directly — "Key scope differences: ..." synthetic append removed
- Analysis sheet Category-by-Category table is now 5 columns: Category | Primary ($) | Comparison ($) | Delta ($) | Delta (% of Primary). Notes column removed.
- All border/format loops in Analysis table updated from `range(1, 7)` to `range(1, 6)`
- User visually confirmed XLSX output at checkpoint — Overall Summary reads as a professional paragraph, Analysis table is 5 columns wide
- 25/25 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Simplify _build_overall_summary — remove scope_observations append** - `5d6fc92` (fix)
2. **Task 2: Remove Notes column from Analysis sheet category table** - `7b438a1` (feat)
3. **Task 3: Visual checkpoint** - APPROVED by user

**Plan metadata:** (docs: complete XLSX cleanup plan — committed after summary)

## Files Created/Modified

- `packages/shared-python/vip_shared/bid_comp/export_xlsx.py` — Simplified `_build_overall_summary` (direct overview return, no scope_observations append); Analysis sheet `_write_analysis_sheet` headers reduced to 5 entries; trade_rows/footer_rows/Subtotal/Total border loops changed from `range(1, 7)` to `range(1, 6)`; `narrative_map`, `cat_key`, `driver_text` removed from Analysis table loop

## Decisions Made

- **Remove Notes from Analysis sheet:** Notes were added to compensate for poor LLM overview quality. The prompt fix in 22-01 addresses the root cause. The Analysis sheet is a data table — narrative belongs on the Summary sheet's Top Cost Drivers.
- **Strip scope_observations append from _build_overall_summary:** "Key scope differences: ..." was a mechanical bolted-on suffix that produced awkward output. With v2.4 prompts producing rich natural overviews, LLM text is the final output.
- **Keep `_narrative_by_category`:** Still used by the Summary sheet Top Cost Drivers Notes column — only its usage in `_write_analysis_sheet` was removed.

## Deviations from Plan

None — plan executed exactly as written. The `scope_observations` reference at line 216 and "Notes" at line 139 flagged by grep are in different functions (`_write_analysis_sheet` Scope Alignment section and `_write_summary_sheet` Top Cost Drivers respectively) — both intentional and correct per plan spec.

## Issues Encountered

None. Grep checks initially appeared to show residual matches, but investigation confirmed they were in different functions from those targeted by the plan. The actual target functions (`_build_overall_summary` and the Analysis sheet headers list) were clean as expected.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 22 is complete. Both plans (22-01 prompt upgrade, 22-02 XLSX cleanup) are shipped.
- The bid comparison output now uses clean LLM prose for the Overall Summary with no synthetic appends, and a tidy 5-column Analysis table.
- No blockers. The full milestone (v2.4 report quality) is ready.

---
*Phase: 22-executive-summary-narrative*
*Completed: 2026-03-07*
