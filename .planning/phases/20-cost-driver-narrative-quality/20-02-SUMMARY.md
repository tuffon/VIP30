# 20-02 Summary - Summary Notes Column + Top Driver Narrative Contract

## Scope Executed
- Phase: 20 (Cost Driver Narrative Quality)
- Plan: 20-02
- Requirements addressed:
  - Phase-level requirement IDs were not explicitly defined in `ROADMAP.md` for Phase 20.

## Changes Implemented

### 1. Replaced Summary "Severity" column with "Notes"
- File: `packages/shared-python/vip_shared/bid_comp/export_xlsx.py`
- Summary Top Cost Drivers table column 6 changed from `Severity` to `Notes`.
- Added `_narrative_by_category()` helper to map narrative text by category.
- Notes cells now use wrapped italic styling for readability.
- Increased column F minimum width (`35`) for narrative legibility.

### 2. Preserved Analysis sheet severity behavior
- Analysis table still uses `Severity` values and color fills unchanged.

### 3. Implemented strict top-driver narrative contract (scope extension from user clarification)
- Files:
  - `packages/shared-python/vip_shared/pipeline/passes/writer.py`
  - `packages/shared-python/vip_shared/pipeline/orchestrator.py`
  - `packages/shared-python/vip_shared/bid_comp/core.py`
  - `apps/api/src/prompts/writer_pass_v1.json`
  - `apps/worker/src/prompts/writer_pass_v1.json`
  - `apps/api/src/prompts/writer_pass_v2.json`
  - `apps/worker/src/prompts/writer_pass_v2.json`
- Added explicit ordered `top_cost_drivers_json` input to writer prompts.
- Enforced normalization of model output back to the exact ordered top-driver category set.
- Added fail-fast behavior when required narratives are missing (handled by fallback path only when LLM call/output fails).
- Aligned pipeline-to-XLSX mapping so notes are inserted in correct table-row positions.

### 4. Added/updated regression coverage
- Files:
  - `apps/api/tests/test_writer_pass.py`
  - `apps/api/tests/test_bidcomp_pipeline_integration.py`
- Added contract tests for ordered top-driver mapping and context payload requirements.
- Updated integration expectations to new deterministic alignment behavior.

## Verification
- Ran:
  - `python3 -m pytest tests/test_bid_comp_categories.py tests/test_bidcomp_pipeline_integration.py -v`
  - `python3 -m pytest tests/test_writer_pass.py tests/test_bid_comp_categories.py tests/test_bidcomp_pipeline_integration.py -q`
- Result:
  - `48 passed` (targeted suite), no failures

## Task Commits
1. **Task 1: Notes column + helper + summary formatting** - `a24f066` (feat)
2. **Contract hardening requested during execution** - `19e00f5` (feat)

## Deviations from Plan
- Extended implementation beyond initial row-mapping helper to enforce an end-to-end top-driver contract in writer/pipeline.
- Reason: user clarified non-negotiable behavior that top drivers must always be narrated and mapped in-order unless LLM call fails.

## Self-Check
- PASS: Summary Top Cost Drivers now uses `Notes`
- PASS: Notes narratives map to correct categories/rows
- PASS: Analysis severity visuals unchanged
- PASS: Deterministic top-driver contract enforced in pipeline
- PASS: Regression tests pass

## Outcome
Plan 20-02 is complete. Summary report rows now carry deterministic, correctly positioned top-driver narratives under `Notes`, with strict upstream contract enforcement.
