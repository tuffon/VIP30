---
phase: 31-per-driver-llm-pass
plan: 01
subsystem: pipeline
tags: [pydantic, llm, structured-output, driver-pass, tdd, pytest, cache, prompt-template]

# Dependency graph
requires:
  - phase: 30-cost-driver-identification
    provides: DriverWithItems model (driver + primary_items + comparison_items + verification)
  - phase: 29-trade-summary-parsing
    provides: LLMAdapterBase.generate_structured() contract
affects:
  - phase 32 (final-summary-pipeline-integration): run_driver_pass feeds per-driver DriverAnalysisResult into CostDriverPipeline aggregation

provides:
  - DriverAnalysisResult Pydantic model (category, primary_total, comparison_total, delta, narrative, scope_observations, suggested_followups)
  - run_driver_pass(driver_with_items, llm_adapter, cache=None) -> DriverAnalysisResult
  - DriverPassInput Pydantic model for content-hash cache key computation
  - driver_analysis_v1 prompt template (apps/api + apps/worker)
  - 8 pytest tests covering PASS-01/02/03

# Tech tracking
tech-stack:
  added: []
  patterns:
    - structured-output-no-fallback: generate_structured() only; no try/except; exception propagates to caller (PASS-02)
    - pydantic-for-cache-key: DriverPassInput serialized via model_dump_json(exclude_none=True) for deterministic SHA256 hash
    - context-isolation: context dict scoped to single driver only; no cross-category keys passed to LLM (PASS-01)

key-files:
  created:
    - packages/shared-python/vip_shared/pipeline/passes/driver_pass.py
    - packages/shared-python/tests/test_driver_pass.py
    - apps/api/src/prompts/driver_analysis_v1.json
    - apps/worker/src/prompts/driver_analysis_v1.json
  modified:
    - packages/shared-python/vip_shared/pipeline/models.py
    - packages/shared-python/vip_shared/pipeline/passes/__init__.py

key-decisions:
  - "verification_context added to context dict alongside verification_note — prompt uses {verification_context} which produces a formatted note string or empty string; keeps prompt template clean (no conditional Jinja-style logic needed)"
  - "key variable computed before early-return cache hit — ensures key is in scope for cache.set() after LLM call even though early return happens before the body block"

patterns-established:
  - "No JSON repair in pipeline passes: driver_pass.py has zero try/except around generate_structured(); Phase 32 caller handles failed drivers with 'analysis unavailable'"
  - "Cache key lifecycle: compute key immediately when cache is not None; store in local variable; use for both get and set"

# Metrics
duration: 20min
completed: 2026-03-10
---

# Phase 31 Plan 01: Per-Driver LLM Pass Summary

**DriverAnalysisResult model + run_driver_pass() function implement PASS-01/02/03: isolated context per driver, generate_structured()-only with no JSON repair fallback, and content-hash PipelineCache integration; 8/8 tests pass, 42/42 shared-python tests pass, 12/12 parser baseline preserved.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-10T07:52:57Z
- **Completed:** 2026-03-10T08:12:57Z
- **Tasks:** 4 completed
- **Files modified/created:** 6

## Accomplishments

- DriverAnalysisResult Pydantic model added to pipeline/models.py: category, primary_total, comparison_total, delta, narrative, scope_observations (list), suggested_followups (list)
- run_driver_pass(): PASS-01 isolated context (7 keys, no cross-category data), PASS-02 generate_structured once with no try/except, PASS-03 cache.get before LLM + cache.set after miss
- DriverPassInput Pydantic model for deterministic SHA256 cache-key hashing via PipelineCache
- driver_analysis_v1.json prompt template created in apps/api/src/prompts/ and apps/worker/src/prompts/
- run_driver_pass and DriverPassInput exported from vip_shared.pipeline.passes.__init__
- 8/8 driver pass tests pass; 42/42 total shared-python tests pass; 12/12 parser baseline preserved

## Task Commits

Each task committed atomically:

1. **Task 1: Write failing tests (TDD RED)** - `285847a` (test)
2. **Task 2: Add DriverAnalysisResult to models.py** - `02409b7` (feat)
3. **Task 3: Create driver_pass.py** - `f6f95f5` (feat)
4. **Task 4: Prompt templates, export, full suite** - `6f0afe1` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `packages/shared-python/vip_shared/pipeline/passes/driver_pass.py` - New: run_driver_pass() + DriverPassInput; PASS-01/02/03 implemented
- `packages/shared-python/vip_shared/pipeline/models.py` - Added DriverAnalysisResult(BaseModel) after DriverWithItems
- `packages/shared-python/vip_shared/pipeline/passes/__init__.py` - Added run_driver_pass + DriverPassInput exports
- `packages/shared-python/tests/test_driver_pass.py` - New: 8 tests for PASS-01/02/03 (TDD RED then GREEN)
- `apps/api/src/prompts/driver_analysis_v1.json` - New: per-driver analysis prompt template
- `apps/worker/src/prompts/driver_analysis_v1.json` - New: per-driver analysis prompt template (worker copy)

## Decisions Made

**1. verification_context added to context dict**

The prompt template uses `{verification_context}` rather than `{verification_note}` directly. In driver_pass.py, `verification_context` is either an empty string (when verification_ok=True and note is empty) or a formatted multi-line string prefixed with "Note: Item sum verification flagged: ...". This keeps the prompt template clean without Jinja-style conditional logic — the context variable itself controls whether the note appears.

**2. key variable scoped above the early-return block**

The cache key is computed at the top of the `if cache is not None` block and stored in a local variable `key`. This ensures `key` is in scope for `cache.set(key, result)` after the LLM call, even though the early-return `if cached is not None: return cached` appears between key computation and cache set. The alternative (recomputing key after LLM call) would be equally correct but redundant.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. All tests passed GREEN on first run after implementation.

## Next Phase Readiness

Phase 32 (final-summary-pipeline-integration) can begin immediately:
- run_driver_pass() produces DriverAnalysisResult for each top driver
- DriverAnalysisResult exported and importable from vip_shared.pipeline.passes
- Cache integration ready (PipelineCache optional parameter)
- driver_analysis_v1 prompt deployed to both app prompt directories
- No regression in prior phases (42/42 shared-python, 12/12 parser)

---
*Phase: 31-per-driver-llm-pass*
*Completed: 2026-03-10*
