# Research Summary: v2.6 Pipeline Rewrite

**Project:** VIP30 — v2.6 Pipeline Rewrite
**Researched:** 2026-03-09
**Method:** Direct codebase analysis (orchestrator, analysis, writer, compliance, quality, bid_comp/core)
**Confidence:** High — all findings derived from reading actual source code

---

## Executive Summary

The current pipeline produces acceptable output but degrades silently: single-context LLM calls mean all categories share the same limited attention window, top cost drivers lose detail, and the fallback system hides failures behind placeholder text. v2.6 replaces this with a cost-driver-first architecture — each major driver gets its own context window and LLM request, fed by structured recap data already present in parser output.

**Key insight from codebase audit:** The `recap_by_category` field is already present in all 6 parsed document types. The v2.6 pipeline can start with this reliable baseline for trade context; `trade_summary` is an enrichment available only for StateFarm final-drafts. All other needed infrastructure (LLM adapter, caching, quality gates, XLSX export) is reusable without modification.

---

## Key Findings by Dimension

### Stack
- Plain Python, no LangChain — existing `LLMAdapterBase` is sufficient
- Synchronous execution — simpler, acceptable performance for worker jobs (6-12s for 5-6 LLM calls)
- Use `generate_structured()` (Pydantic structured outputs) for all new LLM passes — eliminates JSON repair hacks currently in writer.py
- No new dependencies required

### Features
- **Table stakes:** Trade context builder, cost driver identification (by dollar delta), driver line item mapping with JSON verification, per-driver LLM pass, final summary LLM pass, quality rewrite (single-pass, strict threshold)
- **Differentiators:** Context isolation per driver, fallback elimination (honest failure vs silent placeholder), verification gate before LLM call
- **Anti-features:** No async parallelization, no LangChain, no new parser features

### Architecture
- New pipeline: `CostDriverPipeline` with 6 sequential steps (3 pure data, 3 LLM)
- 7 new/rewritten files, 4 deprecated, 8 unchanged integration points
- Build order: models → data builders → LLM passes → orchestrator → assembly

### Pitfalls
- **Critical:** Fallback elimination needs explicit failure behavior defined upfront (honest error, not silent)
- **Critical:** Category mismatch (CAT codes vs display names) must be caught by JSON verification before LLM
- **Medium:** Per-driver context may still be too large for large estimates (item limit needed)
- **Medium:** Final summary LLM receives N driver narratives — summarize to 1-2 sentences per driver before passing
- **Low:** `NarrativePipeline` rename needed to avoid import breakage in `bid_comp/core.py`

---

## Implications for Roadmap

Based on this research, suggested phase structure:

### Phase 1: Trade Summary Parsing
- **Goal:** Extract and normalize `recap_by_category` from both estimate parser JSONs into `TradeContext`; handle fallback hierarchy
- **Addresses:** TABLE-STAKES-01 (trade context), PITFALL-07 (trade_summary absent in most docs — must use recap_by_category as primary)
- **Uses:** Existing parser JSON structure, no new parsing needed
- **Output:** `build_trade_context()` function, `TradeContext` data model, tested against all 6 golden masters

### Phase 2: Cost Driver Identification
- **Goal:** Identify top N cost drivers by dollar delta; map all line items per driver; verify sums match category totals
- **Addresses:** TABLE-STAKES-02/03 (cost driver identification + line item mapping), PITFALL-02 (category mismatch), PITFALL-03 (context size)
- **Uses:** `XACTIMATE_CATEGORY_CODE_MAP` from bid_comp/core.py; `DriverWithItems` model; verification gate
- **Output:** `identify_cost_drivers()`, `map_driver_items()` functions; unit tests with real data

### Phase 3: Per-Driver LLM Pass
- **Goal:** Each cost driver → own LLM request → `DriverAnalysisResult` with narrative
- **Addresses:** TABLE-STAKES-04 (per-driver pass), PITFALL-04 (final summary too large — needs driver summarization strategy)
- **Uses:** New `driver_analysis_v1` prompt template; `generate_structured()` pattern; per-driver Redis cache keys
- **Output:** `run_driver_pass()` function, prompt template, tested with real estimate data

### Phase 4: Final Summary + Rewrite
- **Goal:** Aggregate driver narratives → executive overview; rebuild quality rewrite as single-pass
- **Addresses:** TABLE-STAKES-05/06 (final summary + rewrite rebuild), PITFALL-01 (fallback elimination), PITFALL-05 (rewrite threshold)
- **Uses:** New `final_summary_v1` prompt template; existing `QualityEvaluator` (unchanged)
- **Output:** `run_summary_pass()`, rebuilt `run_quality_rewrite()`, new `CostDriverPipeline` orchestrator, `assemble_final_narrative()`

**Phase ordering rationale:**
- Data builders (phases 1-2) before LLM passes (phases 3-4) — testable without LLM calls
- Trade context before driver identification — drivers depend on category totals from trade context
- Per-driver pass before final summary — final summary depends on driver outputs
- Final summary and rewrite in same phase — tightly coupled; rewrite depends on quality gate evaluating summary output

**Research flags for phases:**
- Phase 1: Audit `recap_by_category` schema across all 6 golden masters to confirm field names before building extractor
- Phase 3: Profile token counts for largest drivers (Kalyvas, 887 items) before finalizing item limit
- Phase 4: Port APPROACH PAIR REQUIREMENT and anti-echo rules from writer_pass_v2 prompt to final_summary_v1

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| `recap_by_category` available on all doc types | High | Confirmed in AUDIT-REPORT.md and golden masters |
| `trade_summary` limited to 2/6 docs | High | Confirmed in AUDIT-REPORT.md |
| `LLMAdapterBase` sufficient for new passes | High | Confirmed from orchestrator.py and analysis.py |
| Synchronous performance acceptable | High | 5-6 calls × 1-2s each = 6-12s, fine for RQ job |
| Category mismatch risk | High | `XACTIMATE_CATEGORY_CODE_MAP` + section-level CAT codes confirmed in codebase |
| Item count for large drivers | Medium | Need to profile Kalyvas (887 items) at planning time |
