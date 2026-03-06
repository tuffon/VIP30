# 20-01 Summary - Prompt v2.2 Approach-First Narrative Update

## Scope Executed
- Phase: 20 (Cost Driver Narrative Quality)
- Plan: 20-01
- Requirements addressed:
  - Phase-level requirement IDs were not explicitly defined in `ROADMAP.md` for Phase 20.

## Changes Implemented

### 1. Upgraded writer prompt contract to v2.2 in API + worker
- Files:
  - `apps/api/src/prompts/writer_pass_v1.json`
  - `apps/worker/src/prompts/writer_pass_v1.json`
- Version bumped from `2.1` to `2.2`.
- Restored approach-first framing guidance and removed abstract difference-dimensions framing from v2.1.

### 2. Restored concrete approach-examples guidance
- Replaced abstract "DIFFERENCE DIMENSIONS" block with explicit "APPROACH EXAMPLES" table and examples.
- Updated overview guidance to emphasize loss type + approach difference in sentence 1.

### 3. Fixed user prompt schema contradictions
- Updated key driver narrative placeholder to explicitly require THREE-sentence structure.
- Updated critical rule for overview sentence 1 to require approach-difference framing.

### 4. Synced API and worker prompt copies
- Kept both prompt files identical to avoid runtime divergence between services.

## Verification
- Ran:
  - `python3 -m pytest tests/test_writer_pass.py -v`
- Result:
  - `22 passed`

## Task Commit
1. **Task 1 + Task 2: Prompt v2.2 update + worker parity** - `3b3f470` (feat)

## Self-Check
- PASS: `writer_pass_v1.json` updated to v2.2 in API and worker
- PASS: "APPROACH EXAMPLES" guidance present
- PASS: old difference-dimension framing removed
- PASS: writer pass tests pass

## Outcome
Plan 20-01 is complete. Writer prompt behavior is now approach-first, schema-consistent, and synchronized between API and worker services.
