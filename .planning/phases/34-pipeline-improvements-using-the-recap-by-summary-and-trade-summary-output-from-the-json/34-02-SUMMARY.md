# Plan 34-02 Summary

## Outcome

Reworked the per-driver grounding contract so deterministic category selection stays upstream of the LLM and the model receives richer structured context for the chosen category. Driver-pass context now includes delta percentage, evidence summaries, item counts, and optional estimate names, and the prompt contract was tightened to require concise, pinpointed explanations rather than broad cost-driver prose.

## Key Changes

- Updated `packages/shared-python/vip_shared/pipeline/passes/driver_pass.py` to:
  - accept optional estimate-name metadata
  - compute and pass delta-percentage context
  - emit structured evidence summaries alongside raw item JSON
  - preserve isolated single-category context
- Added regression coverage in `packages/shared-python/tests/test_driver_pass.py` for:
  - new context keys
  - evidence-summary payloads
  - estimate-name propagation
- Tightened `driver_analysis_v1` prompts in:
  - `apps/api/src/prompts/driver_analysis_v1.json`
  - `apps/worker/src/prompts/driver_analysis_v1.json`

## Verification

- `PYTHONPATH=. pytest tests/test_cost_drivers.py tests/test_driver_pass.py -q`
- Result: `22 passed`

## Notes

- Wave 2 keeps ranking deterministic and LLM responsibility narrow: explain the selected category, do not decide what category matters.
- End-to-end wiring of estimate names into pipeline orchestration is deferred to 34-03.
