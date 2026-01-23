# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-18)

**Core value:** Reliable end-to-end bid comparison that produces actionable output
**Current focus:** v1.0 — Professional Adjuster Narratives

## Current Position

Phase: 7 of 7 (Caching & Integration)
Plan: 07-01 complete
Status: Phase 7 complete, v1.0 roadmap COMPLETE
Last activity: 2026-01-23 — Completed 07-01-PLAN.md (Caching & Integration)

Progress: ██████████ 100%

## Phase Progress

| Phase | Name | Status | Started | Completed |
|-------|------|--------|---------|-----------|
| 1 | Data Contracts | Complete | 2026-01-20 | 2026-01-20 |
| 2 | Quality Gates (Deterministic) | Complete | 2026-01-20 | 2026-01-20 |
| 3 | Quality Gates (Pattern-Based) | Complete | 2026-01-20 | 2026-01-21 |
| 4 | Analysis Pass | Complete | 2026-01-21 | 2026-01-21 |
| 5 | Writer Pass | Complete | 2026-01-21 | 2026-01-21 |
| 6 | Pipeline Orchestration | Complete | 2026-01-21 | 2026-01-22 |
| 7 | Caching & Integration | Complete | 2026-01-23 | 2026-01-23 |

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 5 min
- Total execution time: 34 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 1 | 4 min | 4 min |
| 2 | 1 | 5 min | 5 min |
| 3 | 1 | 4 min | 4 min |
| 4 | 1 | 4 min | 4 min |
| 5 | 1 | 4 min | 4 min |
| 6 | 1 | 6 min | 6 min |
| 7 | 1 | 7 min | 7 min |

**Recent Trend:**
- Last 5 plans: 04-01 (4 min), 05-01 (4 min), 06-01 (6 min), 07-01 (7 min)
- Trend: stable

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Three-pass LLM pipeline (analysis -> writer -> compliance rewrite)
- Quality gate with 5 measurable criteria
- Adjuster tone reference captured from real samples
- Stack: DeepEval + textstat for quality gating, keep existing OpenAI adapter
- Pass-level Redis caching for analysis and writer passes

**From 01-01 execution:**
- Pydantic v2 BaseModel for all pipeline data contracts (validation + serialization)
- Literal types for constrained string fields instead of Enum
- computed_field for derived properties like failed_checks
- timezone-aware datetime.now(timezone.utc) for Python 3.12+ compatibility

**From 02-01 execution:**
- textstat for NLP sentence/word counting (more accurate than naive splitting)
- Whole word regex matching for hedge words to avoid false positives
- Per-driver quality checks (GATE-02, GATE-03 run on each driver narrative)
- Quality checker pattern: check_name property + check() method returning QualityCheckResult

**From 03-01 execution:**
- Zero tolerance default for analyst phrases and GPT-isms (max_violations=0)
- Single words use whole-word regex matching to avoid false positives
- Multi-word phrases use substring matching (case-insensitive)
- GATE-05 and GATE-06 run on overview AND each driver narrative

**From 04-01 execution:**
- Use Any type for EstimatePair to avoid circular imports between passes and bid_comp
- Fuzzy category matching via keyword mappings for section-to-category alignment
- Fallback AnalysisResult with confidence='low' when parsing fails
- Strip code fences from LLM responses before JSON parsing

**From 05-01 execution:**
- Few-shot examples from real adjuster memos for tone calibration
- Terminology glossary in system prompt (PWI, MEP, ELE, PNT, SF, O&P)
- Fallback DraftNarrative with basic content when LLM/parsing fails
- Comparative framing required: Carrier vs Contractor with delta amounts

**From 06-01 execution:**
- Max 2 rewrite iterations to prevent infinite compliance loops
- Quality passed -> skip compliance (logged as compliance_skipped)
- Compliance pass returns original draft unchanged on LLM failure
- PipelineState.pair typed as Any for flexible EstimatePair input
- Per-pass timing recorded in pass_timings_ms dict

**From 07-01 execution:**
- cache_key() uses SHA256 hash of model_dump_json(exclude_none=True) for determinism
- Analysis pass cached with 1hr TTL, writer pass with 30min TTL
- Compliance pass explicitly never cached (quality gates may change)
- Cache hits tracked as analysis_cached/writer_cached in passes_executed
- BidComp accepts optional redis parameter for caching
- Legacy _generate_narrative_legacy preserved as fallback

### Pending Todos

None - v1.0 roadmap complete.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-01-23T00:22:00Z
Stopped at: Completed 07-01-PLAN.md (Caching & Integration) - v1.0 COMPLETE
Resume file: None

## v1.0 Milestone Complete

All PIPE requirements satisfied:
- PIPE-01: Data contracts (Pydantic models for all pipeline passes)
- PIPE-02: Quality gates (6 deterministic checks, all measurable)
- PIPE-03: Three-pass pipeline (analysis -> writer -> compliance)
- PIPE-04: Pass-level caching (Redis with content-hash keys)

Production integration complete:
- BidComp uses NarrativePipeline for narrative generation
- Optional Redis caching reduces LLM costs on repeated comparisons
- Legacy fallback preserved for edge cases
- 47 pipeline tests + 29 new tests = 76+ tests covering the pipeline
