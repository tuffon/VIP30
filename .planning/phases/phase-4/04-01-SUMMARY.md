---
phase: 04-analysis-pass
plan: 01
subsystem: pipeline
tags: [llm, analysis, pydantic, prompt-engineering, token-reduction]

# Dependency graph
requires:
  - phase: 01-data-contracts
    provides: "AnalysisResult, CategoryAnalysis Pydantic models"
provides:
  - "run_analysis_pass() function for structured delta extraction"
  - "sample_line_items() for token reduction (100k+ -> 5-10k)"
  - "AnalysisInput Pydantic model for pass input"
  - "analysis_pass_v1 prompt template"
affects: [phase-5-writer, phase-6-orchestration]

# Tech tracking
tech-stack:
  added: []
  patterns: [line-item-sampling, llm-json-parsing, fallback-result-handling]

key-files:
  created:
    - apps/vip-parse/src/pipeline/passes/__init__.py
    - apps/vip-parse/src/pipeline/passes/analysis.py
    - apps/vip-parse/src/prompts/analysis_pass_v1.json
    - apps/vip-parse/tests/test_analysis_pass.py
  modified:
    - apps/vip-parse/src/pipeline/__init__.py

key-decisions:
  - "Use Any type for EstimatePair to avoid circular imports between passes and bid_comp"
  - "Fuzzy category matching via keyword mappings for section-to-category alignment"
  - "Fallback AnalysisResult with confidence='low' when parsing fails"
  - "Strip code fences from LLM responses before JSON parsing"

patterns-established:
  - "Pass input models: Pydantic BaseModel for each pass input (AnalysisInput)"
  - "Pass function signature: (pair, top_deltas, llm_adapter) -> Result model"
  - "Token reduction: Sample top N line items per category by amount"
  - "Graceful degradation: Return low-confidence fallback on LLM/parsing errors"

# Metrics
duration: 4min
completed: 2026-01-21
---

# Phase 4 Plan 01: Analysis Pass Summary

**LLM analysis pass with line item sampling (100k+ to 5-10k tokens) producing validated AnalysisResult with delta drivers and evidence**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-21T10:21:23Z
- **Completed:** 2026-01-21T10:25:40Z
- **Tasks:** 3
- **Files created:** 4
- **Files modified:** 1

## Accomplishments
- Implemented run_analysis_pass() accepting EstimatePair + top_deltas, returning validated AnalysisResult
- Created sample_line_items() with top 5 items per category by amount for token reduction
- Built analysis_pass_v1 prompt template with structured JSON output schema
- 21 comprehensive tests covering sampling, parsing, and error handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Create analysis pass module with line item sampling** - `8505447` (feat)
2. **Task 2: Create analysis_pass_v1 prompt template** - `7c1ccb9` (feat)
3. **Task 3: Add tests and update pipeline exports** - `a4e113d` (test)

## Files Created/Modified
- `apps/vip-parse/src/pipeline/passes/__init__.py` - Pass submodule exports
- `apps/vip-parse/src/pipeline/passes/analysis.py` - Analysis pass with AnalysisInput, sample_line_items, run_analysis_pass
- `apps/vip-parse/src/prompts/analysis_pass_v1.json` - Prompt template for analysis pass LLM call
- `apps/vip-parse/tests/test_analysis_pass.py` - 21 unit tests for analysis pass
- `apps/vip-parse/src/pipeline/__init__.py` - Updated exports for pass functions

## Decisions Made
- **Type annotation for EstimatePair:** Used `Any` type instead of importing EstimatePair to avoid circular imports between pipeline passes and bid_comp modules
- **Fuzzy category matching:** Implemented keyword-based mapping (e.g., "HVAC" matches "HEATING", "COOLING") for section-to-category alignment
- **Fallback strategy:** Return AnalysisResult with confidence="low" and basic category analyses when LLM or parsing fails
- **Code fence handling:** Strip markdown code fences before JSON parsing since LLMs often wrap responses

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - plan executed smoothly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Analysis pass complete and tested
- Ready for Phase 5 (Writer Pass) to consume AnalysisResult
- run_analysis_pass exported from src.pipeline module
- analysis_pass_v1 template registered in TemplateRegistry

---
*Phase: 04-analysis-pass*
*Completed: 2026-01-21*
