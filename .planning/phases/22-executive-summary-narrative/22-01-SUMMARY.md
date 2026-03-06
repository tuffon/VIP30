---
phase: 22-executive-summary-narrative
plan: 01
subsystem: api
tags: [prompts, llm, writer-pass, narrative, json]

# Dependency graph
requires:
  - phase: 21-report-output-quality
    provides: writer prompt v2.3 with SUGGESTED FOLLOWUPS RULES and overview schema
provides:
  - writer_pass_v1.json at v2.4 (api and worker copies identical)
  - Anti-echo rule: prohibits echoing raw field labels like "Overall direction: primary_higher"
  - Anti-forward-reference rule: prohibits "See key drivers below for details"
  - APPROACH PAIR REQUIREMENT in system prompt making approach-first sentence 1 mandatory
  - Sentence 1 CRITICAL RULE updated to reference APPROACH EXAMPLES table explicitly
affects: [22-executive-summary-narrative, future prompt upgrade phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prompt versioning: bump version in metadata.version field and document changes in SUMMARY"
    - "Writer prompt dual-copy: api and worker copies are always identical; copy api to worker after edits"

key-files:
  created: []
  modified:
    - apps/api/src/prompts/writer_pass_v1.json
    - apps/worker/src/prompts/writer_pass_v1.json

key-decisions:
  - "Remove Overall Direction and Confidence raw fields from user prompt — LLM echoed these verbatim instead of synthesizing narrative"
  - "Add APPROACH PAIR REQUIREMENT as mandatory constraint in system prompt, not optional inspiration, to force approach-first sentence 1"

patterns-established:
  - "Anti-echo pattern: raw enum values from analysis pipeline must never appear in LLM user prompt as labeled fields"
  - "Mandatory framing: approach pair selection is required in sentence 1, not optional — enforced by both system APPROACH PAIR REQUIREMENT and user CRITICAL RULES"

# Metrics
duration: 10min
completed: 2026-03-06
---

# Phase 22 Plan 01: Executive Summary Narrative — Writer v2.4 Summary

**Writer prompt upgraded to v2.4: raw echo regressions fixed by removing Overall Direction/Confidence fields and adding mandatory approach-pair framing constraint.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-06T20:00:00Z
- **Completed:** 2026-03-06T20:13:03Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Removed `Overall Direction: {overall_delta_direction}` and `Confidence: {confidence}` lines from user prompt — these caused LLM to echo `primary_higher` verbatim into output
- Added two new rules at top of CRITICAL RULES: anti-echo (no field-name: value patterns) and anti-forward-reference (no "See key drivers below")
- Added APPROACH PAIR REQUIREMENT block to system prompt after the 7-pair table, making approach-first sentence 1 mandatory rather than optional inspiration
- Strengthened sentence 1 CRITICAL RULE to explicitly reference the APPROACH EXAMPLES table in the system prompt

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove raw data fields and add anti-echo rules / APPROACH PAIR REQUIREMENT** - `67d8996` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `apps/api/src/prompts/writer_pass_v1.json` - v2.3 -> v2.4; raw fields removed; anti-echo/anti-forward-reference rules added; APPROACH PAIR REQUIREMENT added; sentence 1 CRITICAL RULE strengthened
- `apps/worker/src/prompts/writer_pass_v1.json` - Identical copy of api file at v2.4

## Decisions Made

- **Remove raw fields rather than rephrase them:** Overall Direction and Confidence added no information the LLM couldn't derive from category amounts and top cost drivers, but caused consistent verbatim echo artifacts. Removal is cleaner than trying to rephrase them.
- **APPROACH PAIR REQUIREMENT as hard constraint in system prompt:** The 7-pair table was already present but framed as optional inspiration. Adding an explicit REQUIREMENT block immediately after the table (rather than only in user CRITICAL RULES) ensures the constraint is visible in the system context where the LLM processes behavioral rules.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All 23 writer pass tests passed without modification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- v2.4 prompt deployed to both api and worker; ready for live testing against Kalyvas or similar report
- Phase 22-02 plan exists and can be executed if further executive summary improvements are needed
- Known blocker (unrelated): 2 migration naming tests in `tests/test_migrations_constraints.py` expecting `vip30-web` service naming remain non-passing

---
*Phase: 22-executive-summary-narrative*
*Completed: 2026-03-06*
