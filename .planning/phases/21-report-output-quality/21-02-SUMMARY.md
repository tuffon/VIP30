---
phase: 21-report-output-quality
plan: 02
subsystem: api
tags: [xlsx, export, layout, analysis-sheet, kalyvas]

# Dependency graph
requires:
  - phase: 21-report-output-quality
    plan: 01
    provides: writer prompt v2.3 with corrected overview schema
provides:
  - Kalyvas-style Analysis sheet with O&P/tax/permits footer separation
  - Enhanced overall summary synthesis incorporating scope observations
  - Notes column in Analysis table with LLM narrative per category
  - Summary sheet improvements for legibility

key-files:
  modified:
    - packages/shared-python/vip_shared/bid_comp/export_xlsx.py

key-decisions:
  - "Analysis sheet footer separation: O&P, tax, and permits rows moved to separate footer section per Kalyvas template — makes subtotal vs total distinction clear"
  - "Scope observations synthesized into overall summary — LLM scope_observations items appended as 'Key scope differences:' to overview paragraph"
  - "Notes column added to Analysis table — LLM narrative per category displayed inline for context"

# Metrics
duration: ~20min
completed: 2026-03-06
---

# Phase 21 Plan 02: Report Output Quality — XLSX Layout Summary

**Analysis sheet restructured to Kalyvas template: O&P footer separation, Notes column with LLM narrative, enhanced overall summary synthesis.**

## Accomplishments

- Restructured Analysis sheet category table to separate trade rows from O&P/tax/permit footer rows (Kalyvas-style layout)
- Added Notes column to Analysis category table with LLM narrative per category driver
- Enhanced `_build_overall_summary` to synthesize scope_observations from LLM into the overall summary paragraph ("Key scope differences: ...")
- Improved summary sheet legibility with better column sizing and text formatting

## Task Commits

1. **Summary synthesis + analysis notes layout** — `378dadb`
2. **Kalyvas-style Analysis table with O&P footer separation** — `a87f7d4`

## Files Created/Modified

- `packages/shared-python/vip_shared/bid_comp/export_xlsx.py` — Kalyvas layout, Notes column, O&P footer rows, summary synthesis

## Issues Encountered

None.

---
*Phase: 21-report-output-quality*
*Completed: 2026-03-06*
