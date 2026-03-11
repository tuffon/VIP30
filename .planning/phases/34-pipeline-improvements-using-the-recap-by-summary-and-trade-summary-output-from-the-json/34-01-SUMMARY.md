# Plan 34-01 Summary

## Outcome

Built the Phase 34 category-evidence foundation for the pipeline. `TradeContext` now carries source-aware category evidence bundles, `trade_summary` is treated as the preferred evidence source when present, recap totals remain authoritative when both recap and trade summary exist, and fallback line-item collection in `map_driver_items()` is scoped to the selected driver categories instead of all categories.

## Key Changes

- Added `CategoryEvidence` and expanded `TradeContext` in `packages/shared-python/vip_shared/pipeline/models.py`
- Updated `build_trade_context()` in `packages/shared-python/vip_shared/pipeline/passes/trade_context.py` to:
  - prefer `trade_summary` for category evidence
  - preserve recap totals as authoritative category totals when both structures exist
  - expose per-category evidence bundles for downstream use
  - normalize trade-summary nested items into line-item-like evidence rows
- Updated `map_driver_items()` in `packages/shared-python/vip_shared/pipeline/passes/cost_drivers.py` to:
  - accept optional `trade_ctx`
  - prefer trade-summary-derived supporting items when available
  - scope fallback section-item collection to selected top-driver categories
- Added regression coverage in:
  - `packages/shared-python/tests/test_trade_context.py`
  - `packages/shared-python/tests/test_cost_drivers.py`

## Verification

- `PYTHONPATH=. pytest tests/test_trade_context.py tests/test_cost_drivers.py -q`
- Result: `38 passed`

## Notes

- Phase 34 interpretation locked here: trade summary is the preferred evidence source, but recap totals still govern category totals when both structures are present.
- This wave intentionally stops short of prompt and summary/orchestrator changes; those belong to 34-02 and 34-03.
