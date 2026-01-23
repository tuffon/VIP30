# Phase 6: Pipeline Orchestration

**Goal:** Wire passes together with conditional compliance rewrite

## Requirements Covered

- PIPE-03: Compliance rewrite pass triggers only when quality gates fail

## Success Criteria

- [ ] NarrativePipeline class orchestrates pass sequence
- [ ] Quality gates run after writer pass
- [ ] Compliance rewrite skipped when quality passes (logged as compliance_skipped)
- [ ] Compliance rewrite triggered when quality fails
- [ ] compliance_rewrite_v1 prompt template with failed checks injection
- [ ] Max 2 rewrite iterations (prevent infinite loops)
- [ ] Error handling with fallbacks per pass
- [ ] Timing and logging per pass
- [ ] End-to-end integration test

## Dependencies

- Phase 1: All data models (PipelineState, etc.)
- Phase 2, 3: All quality gates
- Phase 4: Analysis pass
- Phase 5: Writer pass

## Downstream Consumers

- Phase 7: Caching wraps pipeline calls
- BidComp: Replaces _generate_narrative

---

*Phase created: 2026-01-18*
