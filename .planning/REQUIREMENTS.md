# Requirements: VIP30 v2.6 Pipeline Rewrite

**Defined:** 2026-03-09
**Core Value:** Reliable end-to-end bid comparison that produces actionable output

## v1 Requirements

Requirements for v2.6. Goal: replace monolithic analysis→writer→rewrite pipeline with a stepped, cost-driver-first architecture.

### Trade Context

- [ ] **TRADE-01**: Pipeline builds `TradeContext` from `recap_by_category` in both estimate parser JSONs — normalized category totals available for all 6 doc types
- [ ] **TRADE-02**: When `trade_summary` field is present (StateFarm final-draft format), enrich `TradeContext` with trade summary data
- [ ] **TRADE-03**: When `recap_by_category` is absent, synthesize category totals from section-level line items as last-resort fallback

### Cost Driver Identification

- [ ] **DRIVER-01**: Pipeline identifies top cost drivers by absolute dollar delta across categories, sorted descending — deterministic, no LLM
- [ ] **DRIVER-02**: Pipeline maps all line items from each top driver category in both estimates to a `DriverWithItems` model
- [ ] **DRIVER-03**: Pipeline verifies that mapped line items sum approximately to category total before passing to LLM — logs discrepancy note if verification fails

### Per-Driver LLM Pass

- [x] **PASS-01**: Each top cost driver gets its own LLM request with isolated context: driver totals + line items + trade context
- [x] **PASS-02**: Per-driver LLM output is a `DriverAnalysisResult` Pydantic model validated via structured output — no JSON repair fallback
- [x] **PASS-03**: Per-driver results are cached by content-hash key (1hr TTL) — re-runs with same data skip redundant LLM calls

### Final Summary LLM Pass

- [ ] **SUMM-01**: All driver analyses are aggregated into a `SummaryResult` via a dedicated final summary LLM request with its own context window
- [ ] **SUMM-02**: Summary output contains: executive overview (4-6 sentences), suggested followups, scope observations — validated via Pydantic structured output

### Rewrite System

- [ ] **REWRITE-01**: Quality rewrite triggered only when GATE-01 (hedging) or GATE-02 (judgment language) fails — single pass, no loop
- [ ] **REWRITE-02**: Default fallback text eliminated — `_build_fallback_result()` and `_finalize_with_error()` placeholder text removed from pipeline
- [ ] **REWRITE-03**: Failed individual driver call produces explicit "analysis unavailable" entry with raw data, not silent placeholder

### Pipeline Integration

- [ ] **INTEG-01**: New `CostDriverPipeline` replaces `NarrativePipeline` in orchestrator — same interface contract so `bid_comp/core.py` requires minimal changes
- [ ] **INTEG-02**: Pipeline output assembles into existing `FinalNarrative` model — `export_xlsx()` and XLSX report format unchanged

## v2 Requirements

### Performance

- **PERF-01**: Async parallel per-driver LLM calls — sync is acceptable for v2.6; parallelize only if profiling identifies bottleneck

## Out of Scope

| Feature | Reason |
|---------|--------|
| Parser changes | v2.5 parser is stable; no parser modifications in v2.6 |
| XLSX report format changes | 5-column Kalyvas layout already correct |
| New document types | Known format only; out of scope by constraint |
| LangChain / orchestration framework | No framework features needed; existing `LLMAdapterBase` sufficient |
| Multi-estimate comparison (3+ PDFs) | Still 2-PDF comparison; architecture can extend but not in scope |
| Streaming LLM responses | Not needed; RQ worker job runs to completion |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRADE-01 | Phase 29 | Complete |
| TRADE-02 | Phase 29 | Complete |
| TRADE-03 | Phase 29 | Complete |
| DRIVER-01 | Phase 30 | Complete |
| DRIVER-02 | Phase 30 | Complete |
| DRIVER-03 | Phase 30 | Complete |
| PASS-01 | Phase 31 | Pending |
| PASS-02 | Phase 31 | Pending |
| PASS-03 | Phase 31 | Pending |
| SUMM-01 | Phase 32 | Pending |
| SUMM-02 | Phase 32 | Pending |
| REWRITE-01 | Phase 32 | Pending |
| REWRITE-02 | Phase 32 | Pending |
| REWRITE-03 | Phase 32 | Pending |
| INTEG-01 | Phase 32 | Pending |
| INTEG-02 | Phase 32 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after initial definition*
