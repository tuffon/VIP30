# Phase 33: Parser recap + trade summary completeness - Research

**Researched:** 2026-03-10
**Domain:** Xactimate parser output completeness, golden-master maintenance, parser regression validation
**Confidence:** HIGH

## Summary

Phase 33 is parser-domain work, not pipeline orchestration work. The current parser already has extraction hooks for `recap_by_category` and `trade_summary` in `packages/parser/vip_parser/xactimate/parser.py`, and the final payload already writes `recaps_and_summaries`. The gaps are contract enforcement, completeness across the current document corpus, the wrapped-line vs notes bug in `SF_BSchacter.pdf`, and regression coverage that keeps goldens aligned with verified parser reality.

The natural execution order is:

1. Harden the parser output contract so `recaps_and_summaries.recap_by_category` is always present in canonical form and `recaps_and_summaries.trade_summary` is present as a fully parsed object when the source contains one, otherwise `null`.
2. Fix the wrapped-description vs notes ambiguity in the section parser, with targeted assertions for known `SF_BSchacter.pdf` examples.
3. Regenerate and extend golden masters only after parser behavior is stable, including the newly added contractor-final PDF, then run the full parser golden suite and regenerate the gap report.

The current coverage harness already provides most of the regression scaffolding:
- `packages/parser/tests/conftest.py` defines the document corpus.
- `packages/parser/tests/test_coverage.py` diffs parser output vs golden fixtures.
- `packages/shared-python/tests/conftest.py` and trade-context tests also consume the same goldens downstream.

The main technical risks are:
- changing recap/trade-summary shape in a way that breaks downstream consumers
- accidental broad golden churn without clear justification
- over-aggressive wrapped-line reclassification that steals true notes from line items

The safest approach is to keep the parser contract explicit, add targeted tests for the new guarantees, and only then update goldens from verified parser output.

## Existing Code Surfaces

### Parser payload assembly
- `packages/parser/vip_parser/xactimate/parser.py`
  - Builds `recaps_and_summaries` near the end of `run()`
  - Currently writes:
    - `summaries_by_coverage`
    - `recap_tax_op`
    - `recap_by_room`
    - `recap_by_category`
    - conditional `trade_summary`

### Recap parsing
- `_prepass_recap_by_category()` and `_parse_recap_by_category_section()`
  - already normalize recap sections into grouped category data and `subtotals`
  - already absorb wrapped continuation lines into coverage labels
  - should be the basis for canonical output, not a new parser subsystem

### Trade summary parsing
- `_parse_trade_summary_section()`
  - already parses State Farm trade summary tables
  - output currently lands in `result["trade_summary"]` and later gets copied into `recaps_and_summaries` only when present
  - needs contract hardening so absence becomes `null`, not silent omission

### Wrapped-line vs notes parsing
- `_parse_section()`
  - line items and notes are handled via:
    - `current_line_item`
    - `collecting_notes`
    - `pending_header_lines`
    - `_attach_pending_notes()`
  - this is where wrapped description detection must be refined

### Regression harness
- `packages/parser/tests/conftest.py`
  - current `DOCUMENTS` corpus includes 6 PDFs
  - must be extended for the new contractor-final PDF
- `packages/parser/tests/test_coverage.py`
  - currently compares metadata and section coverage
  - needs explicit contract assertions for recap/trade-summary presence and known wrap/note examples

## Current Corpus Facts

### Existing golden-backed PDFs
- Rough drafts:
  - `docs/rough-drafts/1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.pdf`
  - `docs/rough-drafts/KALYVAS_JVB_V6_KALY2_ROUGH_DRAFT_CAR.pdf`
- Final drafts:
  - `docs/final-drafts/BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf`
  - `docs/final-drafts/statefarm/SF_BSchacter.pdf`
  - `docs/final-drafts/statefarm/Estimate SF Structural damage Lachman 4.15.2025.pdf`
  - `docs/final-drafts/statefarm/Kalyvas Preliminary State Farm estimate9-25-25.pdf`

### New source file requiring golden coverage
- `docs/final-drafts/SCHACTER_RECON_6B_FINAL_DRAFT_CAR.pdf`

### Known wrap/note bug examples
- `docs/final-drafts/statefarm/SF_BSchacter.pdf`
  - estimate line item `#2`
  - estimate line item `#276`

## Recommended Plan Split

### Plan 33-01: Parser output contract + recap/trade summary validation
Scope:
- make `recaps_and_summaries.recap_by_category` and `trade_summary` contract explicit
- ensure canonical recap shape
- ensure `trade_summary: null` when truly absent
- add targeted parser tests for recap/trade-summary presence and structure

Why first:
- downstream goldens and regression fixtures should only be updated after the output contract is stable

### Plan 33-02: Wrapped line vs notes bug fix
Scope:
- refine section parsing heuristics for wrapped description lines
- add targeted assertions for `SF_BSchacter.pdf` known examples
- optionally research/use a lightweight local classifier if deterministic heuristics are insufficient

Why second:
- it touches the same parser core but has separate acceptance criteria and should stabilize before golden refresh

### Plan 33-03: Golden regeneration + corpus expansion + full regression
Scope:
- create a golden for the new contractor-final file
- regenerate affected golden masters from verified parser output
- expand document list and harness coverage
- rerun full parser golden suite and regenerate gap report

Why last:
- goldens must reflect final, approved parser behavior, not intermediate output

## Validation Architecture

### Deterministic contract tests
Add explicit parser assertions for:
- `recaps_and_summaries.recap_by_category` presence
- `recaps_and_summaries.trade_summary` presence when source contains section
- `trade_summary is null` when source does not contain section
- expected canonical recap structure (`subtotals` + grouped category lists)

### Known-example correctness tests
Add targeted checks for:
- `SF_BSchacter.pdf` line items `#2` and `#276`
- expected description vs notes behavior on known wrapped/known note lines

### Corpus regression
Run:
- full parser golden suite
- targeted assertions
- regenerated gap report

### Golden policy
- update goldens immediately when parser behavior is verified improved
- review broad unrelated golden churn manually
- keep full `trade_summary` in the fixture payloads

## Constraints for Planning

- No new product capabilities; parser correctness only
- Output belongs under `recaps_and_summaries`
- Goldens are the source-of-truth regression baseline for the document corpus in repo
- New docs added to the corpus must be wired into coverage in this phase
- Conservative fallback for ambiguous wrap/note lines remains “attach to notes”

---

*Phase: 33-pipeline-optimizations-and-refactors*
*Research completed: 2026-03-10*
