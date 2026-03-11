# Phase 34: pipeline improvements using the recap by summary and trade summary output from the json - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Improve the bid-comp pipeline so `trade_summary` and `recap_by_category` become the core inputs for category diffing, top cost driver selection, and narrative grounding. This phase is about using existing parser outputs better inside the pipeline, not adding new parser extraction capabilities or inventing new category structures.

More specifically, this phase shifts the bid comparison toward a category-first model. The user wants the analysis page, top cost driver selection, and narrative generation to all flow from the same category structures already present in parser output, instead of rebuilding comparison logic ad hoc from raw line items. The intent is to make the pipeline simpler, more deterministic, and more faithful to how adjusters actually read estimate recaps.

</domain>

<decisions>
## Implementation Decisions

### Category diff foundation
- Category-level comparison is the core of the bid comp because the recap structures already express the estimates in the same conceptual frame adjusters use to evaluate differences. The user wants the bid comp centered on category deltas, not on a separate or synthesized analysis model.
- `trade_summary` is the preferred source of truth because it is effectively `recap_by_category` plus the associated line items already grouped to those categories.
- The practical reason to prefer `trade_summary` is that it saves lookup and association work during pipeline execution. Instead of starting from category totals and then separately figuring out which line items belong to each category, the pipeline can start from a structure that already contains both the category rollup and the supporting line-item evidence.
- `recap_by_category` remains the fallback source when `trade_summary` is absent or incomplete, but using it requires extra work to associate line items back to the chosen categories. That extra work is acceptable, but it should be understood as a fallback path rather than the ideal path.
- In rough drafts this association is straightforward because categories are explicit in the line items, so mapping category totals back to evidence is relatively cheap.
- In final drafts the association may require more intelligence, but the phase should still treat category totals as the governing structure and only perform deeper line-item association work for selected top-driver categories. The user does not want broad speculative matching work done everywhere if only a few categories matter for the comparison output.
- The analysis page should be driven by a direct diff of category totals from these structures because that produces the simplest and most defensible comparison surface: same categories, same totals, clear deltas, then ranked highlights.
- The pipeline must not invent or synthesize alternative category labels; category names should stay 1:1 with the parsed category names because the user wants the bid comp to remain directly grounded in the Xactimate-style category structure already present in the estimates.

### Cost driver selection
- Top cost drivers should be chosen deterministically from the largest category deltas because the user sees this as simple math, not a judgment call for the model to make.
- Cost driver selection should rely on basic category-delta math first, before any LLM step, so the ranking is stable, explainable, and not vulnerable to prompt variance.
- Only the top delta categories should have deeper narrative context gathered because those are the categories that actually matter in the output, and deeper evidence gathering for every category would add complexity without improving the report.
- When only `recap_by_category` is available, line-item association work should be done only for categories selected as top cost drivers. This keeps the fallback path practical while still producing enough evidence for concise driver narratives.

### Narrative grounding
- Final summary generation should be built from the deterministically selected top cost drivers plus a higher-level assessment of overall estimate approach and assumptions. The user wants the summary to read as a bird’s-eye explanation of what the estimates are doing differently, but still remain anchored in the top category deltas rather than generic prose.
- LLM inputs for top cost driver narratives should include:
  - category totals
  - delta amounts / percentages
  - associated line items
  - estimate metadata
  - explicit narrative instructions
- These inputs should be sent together because the LLM should not have to infer the ranking logic or reconstruct the evidence base. The model’s job is to explain the already-selected delta, not discover it.
- Key cost driver narratives should be concise, specific, and efficient because the user wants the output to feel sharp and useful rather than padded with obvious or generalized commentary.
- Narratives should avoid broad or generic statements and instead focus on pinpointed explanations of the observed delta. In practice, that means describing the actual scope or pricing difference behind the category variance, not repeating that one estimate is “higher” in general terms.

### Trade summary usage
- `trade_summary` should not be treated as an optional side signal; when present, it is the best available structured input because it already combines the category-level recap view with the category-linked line-item evidence needed for top-driver narratives.
- If only one side has `trade_summary`, the pipeline should still compare categories 1:1 using `recap_by_category`, and gather associated line items only for selected top-driver categories. The user does not want the absence of one trade summary to block category-first comparison; it just changes how much lookup work is required on that side.
- `recap_by_category` wins over recomputed line-item totals if there is disagreement; recap/trade summary data is the source of truth. The pipeline should treat recomputation as a support mechanism, not as authority over the parsed recap structures.

### Claude's Discretion
- Exact prompt wording for the concise top-cost-driver narrative contract.
- Exact heuristic for associating final-draft line items to categories when only `recap_by_category` is present, as long as it stays focused on supporting the selected top-driver categories.
- Exact shape of deterministic ranking and evidence assembly helpers, as long as category names remain 1:1, top-driver ranking remains purely delta-driven, and the resulting output stays centered on recap/trade-summary structures rather than invented abstractions.

</decisions>

<specifics>
## Specific Ideas

- "The analysis page should essentially be a diff of the recap by categories with highlights on the delta diffs." This is the clearest expression of how the user wants the visible comparison layer to behave.
- "Trade summary = recap_by_category + line items." This is the core mental model behind preferring trade summary whenever it exists.
- "Top cost drivers should be the top deltas from the analysis page categories diff with the narratives." This ties the analysis view and the narrative view together into one consistent selection model.
- "Final summary generation is essentially a verbose description of the top cost drivers plus assessing from a birds eye view the overall difference in approach or assumptions that each estimate is making." This clarifies that the final summary is not a separate ranking system; it is a synthesis step built on the same driver set.
- "Deterministic ranking first, then gather context, then send only the top deltas with strong prompt context to the LLM." This is the intended execution order for the improved pipeline.

</specifics>

<deferred>
## Deferred Ideas

- A more intelligent future strategy for associating final-draft line items to categories beyond current explicit category matching. This came up as a useful direction, but it is not required to establish the category-first pipeline flow in this phase.
- Broader classifier or smarter category-association work beyond what is needed to support top-driver categories in this phase. The current phase only needs enough matching quality to support the selected top-driver categories reliably.

</deferred>

---

*Phase: 34-pipeline-improvements-using-the-recap-by-summary-and-trade-summary-output-from-the-json*
*Context gathered: 2026-03-11*
