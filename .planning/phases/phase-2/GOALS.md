# Phase 2: Quality Gates (Deterministic)

**Goal:** Implement measurable quality checks that run without LLM calls

## Requirements Covered

- GATE-01: Hedging threshold check (≤3 soft qualifiers per section)
- GATE-02: Trade verbosity check (≤2 sentences per trade, avg ≤40 words)
- GATE-03: Valuation link check (every trade ties to dollar amount or delta)
- GATE-04: Summary length check (bullets ≤30 words, ≤6 total bullets)

## Success Criteria

- [ ] HedgingChecker counts hedge words (may, might, appears, suggests, etc.)
- [ ] VerbosityChecker validates sentence count and word averages using textstat
- [ ] ValuationLinkChecker detects dollar amounts or delta references via regex
- [ ] SummaryLengthChecker validates bullet constraints
- [ ] QualityEvaluator aggregates all checks into QualityReport
- [ ] Tests with known-passing and known-failing narrative samples

## Dependencies

- Phase 1: DraftNarrative and QualityReport models

## Downstream Consumers

- Phase 6: Pipeline orchestration uses quality gates for conditional rewrite

---

*Phase created: 2026-01-18*
