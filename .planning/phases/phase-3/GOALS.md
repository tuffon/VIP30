# Phase 3: Quality Gates (Pattern-Based)

**Goal:** Implement pattern detection for analyst tone and GPT-isms

## Requirements Covered

- GATE-05: Analyst tone detection (ban "suggests", "appears", "may indicate", "likely due to")
- GATE-06: Slop/GPT-ism detection (ban "it's worth noting", "delve", "comprehensive", etc.)

## Success Criteria

- [ ] AnalystToneChecker detects hedging phrases specific to analyst writing
- [ ] SlopChecker detects GPT-ism phrases (tapestry, delve, it's worth noting, etc.)
- [ ] Both checkers integrated into QualityEvaluator
- [ ] Banned phrase lists configurable via settings
- [ ] Tests with real LLM output samples showing detection accuracy

## Dependencies

- Phase 1: DraftNarrative and QualityReport models
- Phase 2: QualityEvaluator base implementation

## Downstream Consumers

- Phase 6: Pipeline orchestration uses quality gates for conditional rewrite

---

*Phase created: 2026-01-18*
