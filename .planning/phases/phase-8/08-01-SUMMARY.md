# Phase 8 Plan 1: Narrative Regression Fixes Summary

## One-Liner
Fixed key_driver numeric values via top_deltas lookup, enhanced writer prompt with two-sentence narratives and 2-3 sentence overview structure.

## Metadata

| Field | Value |
|-------|-------|
| Phase | 08-narrative-regression-fixes |
| Plan | 01 |
| Duration | 4 min |
| Completed | 2026-01-23 |
| Tasks | 3/3 |
| Tests Added | 4 |
| Lines Modified | ~220 |

## Commits

| Hash | Message |
|------|---------|
| 959c6bc | fix(08-01): populate numeric values in key_drivers from top_deltas |
| 4f35024 | feat(08-01): update writer prompt for two-sentence narratives and expanded overview |
| f690f33 | test(08-01): add regression tests for key_driver numeric values (REGR-01) |

## What Was Built

### Task 1: Fix Missing Numeric Values in key_drivers (REGR-01)
- **File**: `apps/vip-parse/src/bid_comp/core.py` (modified)
- Added `top_deltas` parameter to `_convert_pipeline_result` method
- Built lookup dict from `top_deltas` by category (case-insensitive matching)
- Populated `primary_total`, `comparison_total`, `delta_total` from top_deltas
- Updated call site in `_generate_narrative_via_pipeline` to pass `top_deltas`

### Task 2: Update Writer Prompt (REGR-02, REGR-03, REGR-04)
- **File**: `apps/vip-parse/src/prompts/writer_pass_v1.json` (modified)
- **Two-sentence narratives (REGR-02)**:
  - Sentence 1: State delta amount and direction
  - Sentence 2: Identify primary cause
- **Expanded overview (REGR-03)**:
  - 2-3 sentences covering delta magnitude, primary causes, key assumptions
- **Estimate name usage (REGR-04)**:
  - Added rule to always reference estimates by `{primary_name}` and `{comparison_name}`
- Updated all examples to demonstrate two-sentence pattern
- Added `narrative_structure` and `overview_structure` to metadata
- Bumped version to 1.1

### Task 3: Regression Tests
- **File**: `apps/vip-parse/tests/test_bidcomp_pipeline_integration.py` (modified)
- `TestKeyDriverNumericValues` class with 4 tests:
  - `test_key_drivers_have_numeric_values`: Verify primary_total, comparison_total, delta_total populated
  - `test_category_matching_is_case_insensitive`: Verify case-insensitive category lookup
  - `test_fallback_when_category_not_in_top_deltas`: Verify graceful degradation
  - `test_key_drivers_full_pipeline_integration`: Verify full pipeline produces correct values
- Updated `sample_bid_context` fixture with proper HVAC keyword items

## Key Implementation Details

### Numeric Value Population Flow
```python
# In _convert_pipeline_result():
delta_by_category = {
    d.get("category", "").lower(): d for d in top_deltas
}

for d in final.key_drivers:
    delta_data = delta_by_category.get(d.category.lower(), {})
    key_drivers.append({
        "category": d.category,
        "primary_total": delta_data.get("primary_total"),
        "comparison_total": delta_data.get("comparison_total"),
        "delta_total": delta_data.get("delta"),
        "narrative": d.narrative,
    })
```

### Updated Writer Prompt Structure
| Section | Requirement |
|---------|-------------|
| overview | 2-3 sentences: delta magnitude, causes, assumptions |
| narrative | Exactly 2 sentences: delta assessment + cause analysis |
| framing | Use estimate names in comparative framing |

## Tests Added

| File | Tests | Coverage |
|------|-------|----------|
| test_bidcomp_pipeline_integration.py | 4 | key_driver numeric values, category matching |

## Files Modified

### Modified
- `apps/vip-parse/src/bid_comp/core.py` - Numeric value population (+16 lines, -10 lines)
- `apps/vip-parse/src/prompts/writer_pass_v1.json` - Two-sentence narrative requirements
- `apps/vip-parse/tests/test_bidcomp_pipeline_integration.py` - Regression tests (+204 lines)

## Verification Results

All checks passed:
- [x] `pytest tests/test_bidcomp_pipeline_integration.py -v` - 14 tests passed
- [x] `pytest tests/test_orchestrator.py -v` - 18 tests passed
- [x] New regression tests verify numeric values in key_drivers
- [x] Writer prompt has updated requirements for two-sentence narratives
- [x] Writer prompt requires 2-3 sentence overview with cause analysis
- [x] Existing tests continue to pass (32 total tests)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated test fixture for proper category matching**
- **Found during:** Task 3 test execution
- **Issue:** `sample_bid_context` fixture used item names ("Condenser", "Ductwork") that didn't match CATEGORY_KEYWORDS, causing items to fall back to "Other / Unclassified" instead of "HVAC / Mechanical"
- **Fix:** Updated fixture items to use HVAC keywords ("HVAC Unit Replacement", "HVAC Ductwork")
- **Files modified:** `test_bidcomp_pipeline_integration.py`
- **Commit:** f690f33

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Case-insensitive category matching | LLM outputs may vary in casing; lookup should be robust |
| Graceful degradation for unknown categories | Values return None when category not found, no exceptions |
| Two-sentence per driver | Improves narrative quality with explicit structure |

## Regressions Fixed

| ID | Issue | Resolution |
|----|-------|------------|
| REGR-01 | Key drivers missing numeric values | Populated from top_deltas via category lookup |
| REGR-02 | Driver narratives need two sentences | Updated writer prompt with explicit requirement |
| REGR-03 | Overview too short | Updated writer prompt for 2-3 sentences |
| REGR-04 | Estimate names need consistent display | Added rule to always use {primary_name} and {comparison_name} |

## Next Phase Readiness

This completes Phase 8 and all v1.0.1 regression fixes.

### All Regressions Addressed
- REGR-01: Numeric values now populated in key_drivers
- REGR-02: Writer prompt requires two-sentence narratives
- REGR-03: Writer prompt requires 2-3 sentence overview
- REGR-04: Writer prompt enforces estimate name usage

### Production Ready
The narrative pipeline now produces:
- Complete key_drivers with numeric values for xlsx export
- Higher quality narratives with explicit structure requirements
- Consistent estimate name usage in comparative framing
