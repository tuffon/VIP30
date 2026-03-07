---
gsd_state_version: 1.0
milestone: v2.3
milestone_name: report-quality
status: complete
last_updated: "2026-03-07T00:00:00.000Z"
progress:
  total_phases: 22
  completed_phases: 22
  total_plans: 7
  completed_plans: 7
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Reliable end-to-end bid comparison that produces actionable output
**Current focus:** Milestone v2.3 complete — planning next milestone

## Current Position

Phase: 22 of 22 (Executive Summary Narrative) — COMPLETE
Status: Milestone v2.3 archived. ROADMAP.md deleted. Ready to plan next milestone.
Last activity: 2026-03-07 — v2.3 milestone complete and archived to milestones/. MILESTONES.md updated. PROJECT.md evolved. Git tag v2.3 created.

Progress: ██████████ 100%

## Completed Milestones

| Version | Name | Phases | Shipped |
|---------|------|--------|---------|
| v2.2 | Unified Output | 16-17 | 2026-02-18 |
| v2.1 | Repository Restructure | 13-15 | 2026-02-18 |
| v2.0 | Analytical Intelligence | 9-12 | 2026-02-17 |
| v1.2 | Launch Ready | 5-8 | 2026-02-17 |
| v1.1 | MVP Launch | 1-4 | 2026-02-14 |
| v1.0.1 | Professional Adjuster Narratives | 1-8 | 2026-02-09 |

## Accumulated Context

### Roadmap Evolution

- Phase 20 added: Cost Driver Narrative Quality — key cost drivers missing narrative text, prompts need fixing
- Phase 21 added: Report Output Quality — Notes too small, summary too vague, key observations need integration, follow-ups too generic, analysis layout should match Kalyvas template (file in project root)
- Phase 20 completed: prompts upgraded to v2.2 approach-first guidance; Summary Top Cost Drivers now uses Notes mapped to deterministic top-driver narrative contract.
- Phase 21-01 completed: writer prompt upgraded to v2.3 — SUGGESTED FOLLOWUPS RULES with BAD/GOOD examples added to system prompt; overview schema corrected to 4-6 sentences with sentence-by-sentence CRITICAL RULES.
- Phase 21-02 completed: summary synthesis and analysis notes layout improvements shipped.
- Phase 22 added: Executive Summary Narrative — remove Notes column from Analysis category table; fix Overall Summary regression (raw data fields in output); rewrite as executive-grade narrative paragraph with scope observations woven in naturally.
- Phase 22-01 completed: writer prompt upgraded to v2.4 — raw Overall Direction/Confidence fields removed from user prompt; anti-echo rule added; anti-forward-reference rule added; APPROACH PAIR REQUIREMENT added to system prompt; sentence 1 CRITICAL RULE strengthened to reference APPROACH EXAMPLES table. 23/23 tests pass.
- Phase 22-02 completed: XLSX cleanup — Notes column removed from Analysis sheet category table (5-column layout); scope_observations synthetic append stripped from _build_overall_summary (LLM prose is now the direct output, no post-processing). 25/25 tests pass.

### Decisions

- [22-01] Remove Overall Direction and Confidence fields from user prompt — LLM echoed these verbatim (e.g., "Overall direction: primary_higher") instead of synthesizing narrative. LLM derives direction from category amounts and top cost drivers data already present.
- [22-01] APPROACH PAIR REQUIREMENT placed as hard constraint in system prompt (not just user CRITICAL RULES) — approach-pair framing must be mandatory, not optional inspiration.
- [22-02] Remove Notes column from Analysis sheet — Summary Top Cost Drivers table already covers notable drivers; Analysis is a data table, not a narrative supplement.
- [22-02] Strip scope_observations append from _build_overall_summary — v2.4 prompt fix is the root-cause solution; mechanical suffix was a bandaid over poor LLM overview quality.

Additional decisions logged in PROJECT.md Key Decisions table.

### Blockers/Concerns

- Full `apps/api` test suite has 2 unrelated non-passing migration naming tests in `tests/test_migrations_constraints.py` expecting `vip30-web` service naming.

## Session Continuity

Last session: 2026-03-07
Stopped at: Phase 22-02 SUMMARY.md created and committed — Phase 22 complete
Resume file: None
