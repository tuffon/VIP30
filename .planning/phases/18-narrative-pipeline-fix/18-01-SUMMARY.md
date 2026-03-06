# 18-01 Summary - Fix NarrativeResult -> export_xlsx Type Mismatch

## Scope Executed
- Phase: 18 (Narrative Pipeline Fix)
- Plan: 18-01
- Requirements addressed:
  - NARR-01
  - NARR-02
  - NARR-03
  - NARR-04

## Changes Implemented

### 1. Added overlay properties to `NarrativeResult`
- File: `packages/shared-python/vip_shared/bid_comp/core.py`
- Added three read-only properties that map existing `sections` payload keys to attribute names expected by XLSX export:
  - `overview` -> `sections["overview_of_estimates"]`
  - `scope_observations` -> `sections["scope_observations"]`
  - `suggested_followups` -> `sections["suggested_followups"]`
- This preserves current pipeline/fallback behavior while restoring compatibility with `export_xlsx.py` attribute access.

### 2. Added integration tests for narrative content presence
- File: `apps/api/tests/test_bidcomp_pipeline_integration.py`
- Added `TestNarrativeXLSXContent` test class covering:
  - Summary sheet overview narrative appears in XLSX output
  - `NarrativeResult.overview` property returns non-empty string
  - `NarrativeResult.scope_observations` returns populated list
  - Fallback narrative path also provides non-empty `overview`
- Added required imports: `io`, `openpyxl`.

## Verification
- Ran:
  - `PYTHONPATH=/mnt/c/Users/benav.TUFFON_AMD/Documents/Projects/VIP30/packages/shared-python python -m pytest tests/test_bidcomp_pipeline_integration.py -v`
- Result:
  - `18 passed`
  - All tests succeeded

## Self-Check
- PASS: Plan tasks completed
- PASS: Required artifacts created and updated
- PASS: Integration test suite for this plan passes

## Outcome
Plan 18-01 is complete. Narrative text now flows from `NarrativeResult.sections` into XLSX narrative fields via compatible properties, and regression coverage ensures Summary and narrative-accessor behavior remain non-empty for both pipeline and fallback paths.
