# Feature Research: v2.6 Pipeline Rewrite

**Research date:** 2026-03-09
**Milestone:** v2.6 Pipeline Rewrite
**Question:** What does a cost-driver-first pipeline look like for insurance estimate comparison? What's table stakes vs differentiating?

---

## Context: What the Current Pipeline Does

The current pipeline:
1. **Analysis pass** — All categories analyzed together in one LLM call. Samples max 5 line items per category. Returns `AnalysisResult` with `category_analyses[]` and `scope_gaps[]`.
2. **Writer pass** — Takes full `AnalysisResult`, generates `DraftNarrative` with `overview`, `key_drivers[]`, `scope_observations[]`, `suggested_followups[]` in one LLM call.
3. **Compliance pass** — If quality gates fail, rewrites the whole `DraftNarrative` in one LLM call. Runs up to 2 times.

**Core problem:** Single-context monolith. All categories compete for the same context window. The LLM summarizes rather than analyzes. Per-category detail is lost.

---

## Table Stakes: What the v2.6 Pipeline Must Do

These are non-negotiable for the rewrite to be better than the current pipeline:

### 1. Trade Summary Extraction
- **What:** Extract the "Recap by Category" table from parser JSON for every document. This is already parsed (`recaps_and_summaries.recap_by_category`) and available on all doc types.
- **Fallback hierarchy:**
  - Level 1: `trade_summary` field (StateFarm final-draft only, 2/3 docs)
  - Level 2: `recap_by_category` (all doc types — this is the reliable baseline)
  - Level 3: Synthesized from individual section totals by CAT/SEL code
- **Why it matters:** Provides the comparison anchor for each driver — "category X was $Y in estimate A, $Z in estimate B"

### 2. Cost Driver Identification
- **What:** Identify top N cost drivers by absolute dollar delta across categories
- **How:** Compare `recap_by_category` totals between primary and comparison estimates; sort by `abs(delta)` descending; take top 5-8
- **Output:** Ordered list of `{category, primary_total, comparison_total, delta}` tuples
- **Why it matters:** Deterministic, data-driven ordering. The LLM does not choose which categories to analyze.

### 3. Per-Driver Line Item Mapping
- **What:** For each top cost driver, collect all line items from that category from both estimates
- **JSON verification:** Before passing to LLM, verify that line items sum approximately to category total (catch misattribution)
- **Why it matters:** Each driver LLM call sees ALL relevant line items, not a 5-item sample. This is the core context improvement.

### 4. Per-Driver LLM Pass
- **What:** Each cost driver gets its own LLM request: `{driver context} + {line items} + {trade summary} → {driver narrative}`
- **Output schema:** `DriverAnalysisResult` with `narrative`, `key_items`, `methodology_note` (optional)
- **Context isolation:** Each call has only its driver's data — no other category dilution
- **Why it matters:** Isolated context → more precise narrative; no cross-category confusion

### 5. Final Summary LLM Pass
- **What:** Aggregate all driver narratives → executive overview via dedicated LLM call
- **Input:** All `DriverAnalysisResult` outputs + grand total delta + scope gaps
- **Output schema:** `SummaryResult` with `overview` (4-6 sentences), `suggested_followups[]`, `scope_observations[]`
- **Why it matters:** The overview is now grounded in actual per-driver analyses, not re-derived from raw data

### 6. Rewrite System Rebuild
- **What:** One-pass quality rewrite, triggered only when quality score fails threshold
- **Threshold:** Define strict pass/fail — e.g., any GATE-01 or GATE-02 violation triggers rewrite
- **No default fallback text:** If rewrite fails, the original draft is returned unchanged (surface the quality issue, don't hide it)
- **Why it matters:** Current system runs rewrite unconditionally up to 2 times. New system: 0 or 1 rewrite, strict threshold.

---

## Differentiating: What Makes v2.6 Better

Beyond table stakes — these are what make the output noticeably better:

### Trade Context in Driver Prompts
Each driver LLM call includes the recap-by-category context from both estimates. The LLM sees "Painting: $45K vs $32K" as the anchor before analyzing line items. Reduces hallucination about dollar amounts.

### Fallback Elimination
No `_build_fallback_result()`, no `_finalize_with_error()` with placeholder text. If an individual driver call fails, that driver is noted as "analysis unavailable" but with the raw data — not a fabricated narrative. If the final summary fails, the job fails cleanly rather than producing misleading output.

### JSON Verification Gate
Before each driver LLM call: verify that the line items provided sum approximately to the category total from the recap. Flags misattribution early (wrong items assigned to driver) before sending bad data to LLM.

---

## Anti-Features: What NOT to Build in v2.6

| Feature | Reason Not To Build |
|---------|---------------------|
| Async parallel driver calls | Premature optimization; sync is simpler and acceptable |
| Multi-estimate comparison (3+ PDFs) | Still 2-PDF comparison; architecture can extend but don't build for it |
| Driver prioritization by LLM | Deterministic dollar-delta sort is correct and testable |
| Streaming LLM responses | Not needed; worker job runs to completion |
| New doc types / parser changes | Parser is v2.5-stable; no parser changes in v2.6 |
| LangChain / orchestration framework | No framework features needed; plain Python is simpler |

---

## Out of Scope

- XLSX report format changes (already clean 5-column Kalyvas layout)
- Frontend changes (output is XLSX, unchanged)
- New parser features (v2.5 complete, stable)
- Quality gate rule changes (GATE-01 through GATE-05 are correct)
- Auth / credits / job state machine (unchanged)
