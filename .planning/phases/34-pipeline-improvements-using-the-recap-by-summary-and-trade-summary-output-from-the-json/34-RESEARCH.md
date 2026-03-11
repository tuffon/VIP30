# Phase 34: pipeline improvements using the recap by summary and trade summary output from the json - Research

**Researched:** 2026-03-11
**Domain:** Category-first bid comparison pipeline using parser `trade_summary` and `recap_by_category`
**Confidence:** HIGH

## Summary

Phase 34 is pipeline-domain work, not parser-domain work. Phase 33 already made `recaps_and_summaries.recap_by_category` and `trade_summary` reliably available in parser output. The remaining gap is that the current pipeline still treats those structures as shallow inputs instead of the core bid-comp model.

The current state is:
- `TradeContext` primarily extracts category totals from `recap_by_category`
- `trade_summary` is only carried forward as a raw `line_items` list
- `identify_cost_drivers()` ranks by category delta correctly, but only from totals
- `map_driver_items()` falls back to broad line-item category mapping from sections
- `run_driver_pass()` sends raw line items and totals, but not a strong category-evidence package
- `CostDriverPipeline` and `BidComp` still do not fully align the visible analysis layer, top-driver narratives, and final summary around one canonical category-diff model

The user wants the bid comp to become explicitly category-first:

1. Category diffs are the core comparison surface.
2. `trade_summary` is the preferred source when present because it is effectively `recap_by_category + associated line items`.
3. `recap_by_category` is the fallback when `trade_summary` is missing, with line-item association work only for selected top-driver categories.
4. Top cost drivers should be deterministic top category deltas, not LLM-selected topics.
5. LLM usage should be reduced to concise explanation of already-ranked categories using structured evidence.

That means the right execution order is:

1. Build a better category-evidence layer from `trade_summary` / `recap_by_category`.
2. Rework cost-driver selection and driver-pass grounding to use that layer deterministically.
3. Align final summary/orchestrator behavior and tests so the final narrative and visible analysis reflect the same category-diff truth.

## Existing Code Surfaces

### Trade context extraction
- `packages/shared-python/vip_shared/pipeline/passes/trade_context.py`
  - `build_trade_context()` currently:
    - reads `recap_by_category`
    - falls back to synthesized section totals
    - carries `trade_summary` line items separately via `primary_trade_items` / `comparison_trade_items`
  - limitation:
    - category totals and evidence are still separate concepts
    - no canonical “category evidence bundle” exists yet

### Deterministic cost-driver selection
- `packages/shared-python/vip_shared/pipeline/passes/cost_drivers.py`
  - `identify_cost_drivers()` is already deterministic and category-delta-based
  - `map_driver_items()` currently maps all evidence by section line-item `cat` codes only
  - limitations:
    - ignores `trade_summary` as a first-class evidence source
    - broad line-item collection is heavier than needed for non-top-driver categories
    - final-draft evidence mapping is weaker than rough-draft mapping because section items do not always align as directly

### Driver prompt grounding
- `packages/shared-python/vip_shared/pipeline/passes/driver_pass.py`
  - currently sends:
    - category
    - totals
    - raw primary/comparison items JSON
    - optional verification note
  - limitations:
    - no explicit category delta percentages
    - no estimate metadata in context
    - no normalized structured explanation of why this category was chosen
    - no distinction between “trade-summary evidence” and “fallback mapped evidence”

### Pipeline orchestration
- `packages/shared-python/vip_shared/pipeline/cost_driver_pipeline.py`
  - current flow:
    - `build_trade_context()`
    - `identify_cost_drivers()`
    - `map_driver_items()`
    - `run_driver_pass()`
    - `run_summary_pass()`
  - limitation:
    - the pipeline is category-aware, but not yet category-evidence-first
    - it still assembles driver narratives from a thinner evidence structure than the user wants

### BidComp integration
- `packages/shared-python/vip_shared/bid_comp/core.py`
  - already computes category recap artifacts and top deltas for visible report output
  - already passes estimate payloads and top deltas into the new pipeline
  - limitation:
    - the pipeline does not fully reuse the same “analysis page truth” as the visible category diff layer
    - top-delta count is used, but the actual detailed category comparison model is not fully shared

### Test surfaces
- `packages/shared-python/tests/test_trade_context.py`
- `packages/shared-python/tests/test_cost_drivers.py`
- `packages/shared-python/tests/test_driver_pass.py`
- `packages/shared-python/tests/test_summary_pass.py`
- `packages/shared-python/tests/test_cost_driver_pipeline.py`

These tests already cover the core v2.6 pipeline seams and are the right place to lock the stronger category-first behavior.

## Key Technical Findings

### 1. Trade summary should be elevated from enrichment to first-class evidence
The current code treats `trade_summary` as optional enrichment. The user wants the opposite: when present, it should be the primary source because it already combines category totals with the evidence needed to explain those totals.

### 2. Driver ranking is already deterministic, but the evidence assembly is not optimized around that fact
`identify_cost_drivers()` already does the right basic ranking. The next improvement is to gather the evidence layer after ranking, and only for the selected categories. This is both closer to user intent and more efficient.

### 3. The current fallback evidence path is too generic
`map_driver_items()` iterates all sections and groups by Xactimate `cat` code. That is acceptable for rough drafts, but it does not encode the stronger rule: category structures govern first, line-item evidence supports them second.

### 4. Prompt grounding is under-structured
`run_driver_pass()` currently sends raw item JSON blobs. The user wants a stronger prompt package:
- chosen category
- primary/comparison totals
- delta and percentage context
- supporting line items
- estimate metadata
- explicit instruction to produce concise, pinpointed explanation

### 5. Final summary should synthesize the chosen drivers, not rediscover them
The user described the final summary as a bird’s-eye explanation of overall estimate approach and assumptions built on top of the same top-driver set. That means the summary layer should consume the deterministic driver set as source material rather than performing a softer, more generic synthesis.

## Recommended Plan Split

### Plan 34-01: Build category evidence foundation from trade summary and recap data
Scope:
- strengthen `TradeContext` / pipeline models so categories carry both totals and source-aware evidence
- make `trade_summary` the first-choice category evidence source when present
- keep `recap_by_category` as fallback
- gather fallback line-item evidence only for selected top-driver categories
- add deterministic tests around source preference and category evidence assembly

Why first:
- this establishes the core data model the rest of the phase depends on

### Plan 34-02: Rework deterministic top-driver selection and driver-pass grounding
Scope:
- keep ranking purely delta-driven
- ensure selected top drivers come from the same category diff model used by analysis output
- pass stronger, structured category evidence into `run_driver_pass()`
- update driver-pass tests and prompts so narratives stay concise and category-specific

Why second:
- once the evidence layer exists, driver ranking and LLM grounding can be tightened without guessing

### Plan 34-03: Align summary/orchestrator behavior and end-to-end verification
Scope:
- ensure final summary synthesis is built from the deterministic driver set and category evidence
- align `CostDriverPipeline` / `BidComp` integration with the category-first comparison model
- verify that visible top drivers and pipeline-generated top drivers remain consistent
- rerun shared-python pipeline tests

Why last:
- orchestration and end-to-end verification should follow once the lower-level category and driver contracts are stable

## Validation Architecture

### Deterministic category evidence tests
Add or extend tests to prove:
- `trade_summary` is preferred over plain recap data when both are available
- fallback to `recap_by_category` remains correct when trade summary is absent
- selected categories carry the correct totals and source-aware supporting evidence

### Deterministic driver selection tests
Add or extend tests to prove:
- top cost drivers come from the largest category deltas
- only selected top-driver categories trigger deeper fallback item association work
- driver ranking remains independent of LLM behavior

### Driver prompt-context tests
Add tests to prove driver-pass context includes:
- category totals
- delta magnitude / percentage
- structured supporting evidence
- estimate metadata
- no cross-category leakage

### End-to-end pipeline alignment tests
Add tests to prove:
- `CostDriverPipeline` summary uses the selected driver set rather than rediscovering categories
- `BidComp` analysis output and top-driver narratives remain aligned to the same category-diff truth
- existing XLSX/export integration remains intact

## Constraints for Planning

- No new parser extraction work in this phase
- No invented category taxonomy; category names remain 1:1 with parsed category names
- Deterministic category ranking happens before any LLM call
- LLM responsibility is explanation, not selection
- Fallback line-item association should be limited to selected top-driver categories
- Visible analysis and narrative layers should both derive from the same category comparison model

---

*Phase: 34-pipeline-improvements-using-the-recap-by-summary-and-trade-summary-output-from-the-json*
*Research completed: 2026-03-11*
