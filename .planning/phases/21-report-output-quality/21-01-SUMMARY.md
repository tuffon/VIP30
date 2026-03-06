---
phase: 21-report-output-quality
plan: 01
subsystem: api
tags: [prompts, llm, writer-pass, json, adjuster-narratives]

# Dependency graph
requires:
  - phase: 20-cost-driver-narrative-quality
    provides: v2.2 approach-first writer prompts with top-driver narrative contract
provides:
  - v2.3 writer_pass_v1.json with SUGGESTED FOLLOWUPS RULES (BAD/GOOD examples) and corrected overview schema (4-6 sentences with sentence-by-sentence guidance)
affects: [report-generation, writer-pass, suggested-followups]

# Tech tracking
tech-stack:
  added: []
  patterns: [prompt-versioning, BAD/GOOD example guidance in system prompt]

key-files:
  created: []
  modified:
    - apps/api/src/prompts/writer_pass_v1.json
    - apps/worker/src/prompts/writer_pass_v1.json

key-decisions:
  - "Added BAD/GOOD examples directly in system prompt for suggested_followups — LLM needs concrete anti-patterns to avoid generic output"
  - "Overview schema in user prompt corrected to match system prompt (both now say 4-6 sentences with sentence-by-sentence breakdown)"

patterns-established:
  - "Prompt guidance pattern: BAD examples (label: NEVER write these) followed by GOOD examples (label: specific, actionable) in system prompt"
  - "Overview sentence contract: sentence 1 = loss type + approach, sentence 2 = top trades with $, sentences 3-4 = specific items, sentences 5-6 = methodology differences"

# Metrics
duration: 10min
completed: 2026-03-06
---

# Phase 21 Plan 01: Writer Prompt v2.3 Summary

**Writer prompt upgraded to v2.3: SUGGESTED FOLLOWUPS RULES with BAD/GOOD examples added to system prompt; overview schema corrected from 2-3 to 4-6 sentences with sentence-by-sentence guidance in CRITICAL RULES**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-06
- **Completed:** 2026-03-06
- **Tasks:** 2 (both pre-completed in prior session)
- **Files modified:** 2

## Accomplishments

- Added SUGGESTED FOLLOWUPS RULES section to system prompt with explicit BAD follow-up patterns (generic, zero value) and GOOD examples (specific, naming actual trades and dollar amounts)
- Corrected overview JSON schema from "2-3 sentences" to "Full paragraph (4-6 sentences)" with labeled sentence-by-sentence breakdown
- Replaced vague "overview sentences 2-6" CRITICAL RULE with precise per-sentence guidance (sentence 2: top trades with $, sentences 3-4: specific items, sentences 5-6: methodology differences)
- Both api and worker copies are identical and at v2.3

## Task Commits

Each task was committed atomically:

1. **Task 1: Add SUGGESTED FOLLOWUPS RULES to system prompt** - included in `753f505` (feat)
2. **Task 2: Fix overview schema, tighten CRITICAL RULES, bump version, sync worker** - included in `753f505` (feat)

**Plan metadata:** to be committed with this summary

## Files Created/Modified

- `apps/api/src/prompts/writer_pass_v1.json` - Added SUGGESTED FOLLOWUPS RULES with BAD/GOOD examples; fixed overview schema to 4-6 sentences; added sentence-by-sentence CRITICAL RULES; bumped to v2.3
- `apps/worker/src/prompts/writer_pass_v1.json` - Verbatim copy of api prompt (identical)

## Decisions Made

- BAD/GOOD example approach chosen for follow-ups guidance: concrete anti-patterns with NEVER label give the LLM stronger signal than positive-only guidance
- Overview sentence contract specified sentence-by-sentence in CRITICAL RULES (in user prompt) AND summarized in system prompt OVERVIEW RULES — belt-and-suspenders to ensure LLM picks up the requirement from both prompt sections

## Deviations from Plan

None — both files were already at v2.3 when execution began. Work was completed in a prior session (commit `753f505`). All verification checks confirmed correct state; 23/23 writer tests passed.

## Issues Encountered

None — plan executed cleanly in prior session. Current session verified and created documentation artifacts.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- v2.3 writer prompt deployed in both api and worker
- Ready for 21-02 (summary synthesis and analysis notes layout improvements)
- No blockers

---
*Phase: 21-report-output-quality*
*Completed: 2026-03-06*
