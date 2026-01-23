# Phase 5: Writer Pass

**Goal:** Implement second LLM pass with adjuster tone control

## Requirements Covered

- PIPE-02: Writer pass generates adjuster-tone narratives from analysis output
- STYLE-01: Writer pass includes 3-5 real adjuster memo examples (few-shot)
- STYLE-02: Terminology glossary injected into writer prompt (PWI, MEP, ELE, PNT, SF, O&P)

## Success Criteria

- [ ] writer_pass_v1 prompt template with adjuster memo examples
- [ ] Terminology glossary (PWI, MEP, ELE, PNT, SF, O&P) injected into system prompt
- [ ] 3-5 real adjuster memo excerpts as few-shot examples
- [ ] run_writer_pass() function returns validated DraftNarrative
- [ ] Output matches adjuster tone characteristics (short, declarative, numbers present)
- [ ] Integration test: analysis → writer flow

## Dependencies

- Phase 1: DraftNarrative model
- Phase 4: AnalysisResult (input to writer)

## Downstream Consumers

- Phase 6: Pipeline orchestration runs writer after analysis
- Phase 7: Caching stores writer results

---

*Phase created: 2026-01-18*
