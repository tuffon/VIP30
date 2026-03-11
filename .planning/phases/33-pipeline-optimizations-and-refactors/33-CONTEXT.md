# Phase 33: Parser recap + trade summary completeness - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Ensure parser JSON output always includes `recap_by_category` and includes `trade_summary` whenever the source document contains it. Update and validate golden JSON files to reflect verified parser reality, add coverage for newly added source documents, and prevent regressions. Also resolve the known State Farm wrapped-line vs notes parsing bug without expanding scope into unrelated parser capabilities.

</domain>

<decisions>
## Implementation Decisions

### Output contract
- `recap_by_category` and `trade_summary` must live under `recaps_and_summaries`.
- If a document contains a trade summary, output must include `recaps_and_summaries.trade_summary`.
- `trade_summary` should be fully parsed from the document section and preserve the columns and row data present.
- `recap_by_category` should be emitted as a normalized canonical structure.
- Category mapping should remain 1:1 with Xactimate categories for apples-to-apples comparison across documents.

### Missing-data rules
- If a document truly has no trade summary, emit `trade_summary: null`.
- If `recap_by_category` exists in the source document, failure to parse it is a parser bug that must be fixed in this phase.
- Parser should iterate toward extracting `recap_by_category` every time it exists in the current document set; missing an existing recap block is not acceptable steady-state behavior.
- If recap rows are messy or partially irregular, parser should still capture the data as completely as possible rather than fail, omit rows, or mark the block incomplete.

### Golden file policy
- Improved parser output should update golden JSON files immediately once verified.
- Goldens are the TDD/regression baseline for the real documents currently in the repository.
- New source documents added to the docs directories must get corresponding golden JSON files and coverage in this phase.
- Goldens should include full parsed `trade_summary` objects.
- Golden churn outside the intended Phase 33 scope should be reviewed case by case until the fixtures are trustworthy; bad goldens are unacceptable.

### Regression validation
- Phase 33 should automatically handle golden creation and test coverage for newly added documents in the current corpus.
- Hard failures in validation include:
- missing `recap_by_category` when present in source
- missing `trade_summary` when present in source
- known wrapped-line vs notes misclassification cases
- Validation should include specific assertions for known State Farm line outputs and known note lines, not just broad section-level checks.
- Expected verification level for this phase is the full parser golden suite, targeted assertions, and regenerated gap reporting.

### Wrapped line vs notes behavior
- Known bug examples are in `docs/final-drafts/statefarm/SF_BSchacter.pdf`, including estimate line items `#2` and `#276`.
- Parser should try to detect whether text on the following line is a wrapped continuation of the line item description versus a true notes line.
- Research into a lightweight local NLP/classification aid is acceptable if it helps distinguish wrapped descriptions from notes.
- If the parser still cannot determine the distinction confidently, ambiguous text should remain attached to notes.
- Current bias is conservative: do not aggressively reclassify ambiguous note text into line-item descriptions unless the signal is strong.

### Claude's Discretion
- Exact heuristic or classifier choice for wrap-vs-notes detection.
- Exact canonical field naming inside normalized recap/trade-summary structures, as long as the contract stays stable and complete.
- Test organization and fixture layout for targeted assertions and golden regeneration.

</decisions>

<specifics>
## Specific Ideas

- State Farm final drafts are important validation sources because trade summaries are present in some of them.
- `SF_BSchacter.pdf` has concrete known examples where wrapped line-item text is being captured as notes.
- If output later needs to be abridged, that should happen downstream in the pipeline, not by dropping parsed trade-summary content from parser output.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within parser output completeness, golden validation, and known parsing correctness bugs for this phase.

</deferred>

---

*Phase: 33-pipeline-optimizations-and-refactors*
*Context gathered: 2026-03-10*
