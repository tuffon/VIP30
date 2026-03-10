# Pitfalls Research: v2.6 Pipeline Rewrite

**Research date:** 2026-03-09
**Milestone:** v2.6 Pipeline Rewrite
**Question:** What can go wrong with per-driver LLM passes and a rewritten pipeline?

---

## Pitfall 1: Fallback Elimination Breaks Silent Degradation Guarantee

**Risk:** The current pipeline always produces output — even if LLM calls fail, `_build_fallback_result()` and `_finalize_with_error()` ensure something is returned. Removing this means a failed driver call produces no narrative for that category.

**Warning signs:**
- Jobs that previously silently completed now fail visibly
- Users see empty driver sections instead of placeholder text

**Prevention:**
- Phase 1: Identify and remove fallback text but define explicit failure behavior
- A failed individual driver call → log warning, include `{category: "analysis unavailable", narrative: "LLM call failed for this category — see logs"}` in output (visible but honest)
- A failed final summary call → job failure with clear error (not silent placeholder)
- Do NOT replace silent fallback with different silent fallback

**Phase:** Trade summary parsing + cost driver identification phases must define failure behavior explicitly. Don't defer to "we'll handle errors in the orchestrator."

---

## Pitfall 2: Category Mismatch Between Parser JSON and Recap Table

**Risk:** The parser extracts line items with CAT/SEL codes (e.g., "FRM", "PAI") and the `recap_by_category` uses display names (e.g., "Framing", "Painting"). The mapping in `bid_comp/core.py` `XACTIMATE_CATEGORY_CODE_MAP` bridges this — but a mismatch means a driver's line items don't sum to its category total.

**Warning signs:**
- `verification_ok = False` for many drivers
- LLM receives partial line item lists and generates incorrect narratives

**Prevention:**
- Use the existing `XACTIMATE_CATEGORY_CODE_MAP` for code→category normalization
- Implement the `DriverWithItems.verification_ok` check (sum within 2% tolerance)
- If verification fails, include the raw sum discrepancy in the driver prompt: "Note: line items provided sum to $X but category total is $Y — discrepancy may indicate incomplete extraction"
- Do NOT silently send unverified data to LLM

**Phase:** Map driver items phase (phase 2 of pipeline). Must be tested before LLM passes.

---

## Pitfall 3: Per-Driver Context Still Too Large

**Risk:** If a category has 50+ line items in a large estimate (e.g., Roofing on a $1M claim), the per-driver context may still hit token limits or degrade LLM quality.

**Warning signs:**
- LLM truncates or summarizes line items rather than analyzing them
- Token count warnings in LLM adapter logs

**Prevention:**
- Keep a per-driver item limit (e.g., top 20 items by dollar amount within the category)
- Always include all items that contribute ≥$1000 to the delta
- Test with Kalyvas (40 sections, 887 items — largest test case)
- At planning time: check token counts for largest drivers before finalizing item limit

**Phase:** Map driver items phase. Item selection strategy must be explicit in the plan.

---

## Pitfall 4: Final Summary LLM Sees Too Many Driver Narratives

**Risk:** If there are 8 drivers, each with a 3-paragraph narrative, the final summary LLM receives a large input. Quality may degrade (summary becomes a list, not synthesis).

**Warning signs:**
- Final summary reads like a concatenation of driver summaries
- Overview paragraph length exceeds 6 sentences despite prompt rules

**Prevention:**
- Summarize each driver narrative to 1-2 sentences before passing to final summary LLM
- Or: pass driver narratives in structured form (category + delta + 1-sentence summary) rather than full paragraphs
- Existing APPROACH PAIR REQUIREMENT (v2.4 writer prompt) must be ported to final summary prompt

**Phase:** Final summary LLM pass. Prompt design is critical.

---

## Pitfall 5: Rewrite Without Fallback Creates Zero-Output Risk

**Risk:** If the single quality rewrite also fails quality gates, the current plan is to return the original draft. But if the original is truly bad, this surfaces the problem rather than hiding it — which is the right behavior but unexpected by users.

**Warning signs:**
- Jobs that "complete" but have quality gate violations visible in XLSX
- Rewrite pass called but output still fails quality check

**Prevention:**
- Define explicit threshold: rewrite is triggered by GATE-01 (hedging) or GATE-02 (judgment language) violations — not GATE-03 (quantification) or GATE-04 (evidence grounding), which may require re-analysis, not rewriting
- After single rewrite, if still failing: include quality check results in output metadata (log), return rewritten draft anyway
- Do NOT loop or retry — the current 2-loop system was a symptom of poor prompt quality; v2.6 prompts should be better

**Phase:** Quality rewrite rebuild.

---

## Pitfall 6: Orchestrator Import Breakage

**Risk:** `bid_comp/core.py` imports `NarrativePipeline` from `pipeline/__init__.py`. Replacing `NarrativePipeline` with `CostDriverPipeline` will break the import unless handled carefully.

**Warning signs:**
- `ImportError` in worker during deployment
- Tests pass locally but fail in CI if `__init__.py` exports are changed

**Prevention:**
- Either: rename the new class `NarrativePipeline` (same interface, different implementation — cleanest)
- Or: export both classes from `pipeline/__init__.py` and update `bid_comp/core.py` import
- Prefer rename (less churn, same interface contract)

**Phase:** New orchestrator phase. Check `pipeline/__init__.py` exports before final integration.

---

## Pitfall 7: Trade Summary Absent in Most Docs

**Risk:** User specified "trade summaries are in the PDFs" but audit data shows `trade_summary` is only in 2/6 documents (lachman_sf and kalyvas_sf — StateFarm final-drafts). Rough-drafts and contractor-finals do not have `trade_summary`.

**Warning signs:**
- Pipeline branches to `recap_by_category` fallback for most real jobs
- Trade summary "feature" appears unused in practice

**Prevention:**
- `recap_by_category` IS the reliable baseline (available on all doc types)
- Do not design pipeline to prefer `trade_summary` — design it with `recap_by_category` as primary, `trade_summary` as enrichment when available
- Audit PDFs first in trade summary parsing phase to confirm field names and schema before building extraction logic

**Phase:** Trade summary parsing phase. Audit-first approach mandatory.

---

## Pitfall 8: Redis Cache Miss on First Run After Pipeline Replacement

**Risk:** The new per-driver cache keys are completely different from the old analysis/writer keys. On first deployment, all existing Redis cache entries are useless for the new pipeline.

**Warning signs:** N/A — this is expected, not a bug.

**Prevention:**
- This is acceptable and expected. Don't try to migrate old cache entries.
- Set appropriate TTLs (1hr) and move on.
- Note in deployment: first run after v2.6 deploy will be cache-cold for all keys.

**Phase:** Not a code concern. Deployment note only.
