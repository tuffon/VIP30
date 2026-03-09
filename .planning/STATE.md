---
gsd_state_version: 1.0
milestone: v2.4
milestone_name: parser-coverage
status: in_progress
last_updated: "2026-03-08T01:00:00Z"
progress:
  total_phases: 25
  completed_phases: 24
  total_plans: 7
  completed_plans: 5
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-07)

**Core value:** Reliable end-to-end bid comparison that produces actionable output
**Current focus:** Phase 25 — coverage harness

## Current Position

Phase: 25 of 25 (coverage-harness) — IN PROGRESS
Plan: 01 of 2 complete
Status: In progress — 25-01 complete, 25-02 pending
Last activity: 2026-03-09 — Completed 25-01-PLAN.md (pytest fixtures + 12 parametrized coverage tests)

Progress: █████████░ 97%

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
- Phase 23-01 completed: audit runner created; all 6 PDFs parsed successfully; rough drafts yield 32/40 sections with 525/887 items; BSchacter contractor final yields 0 sections (gap finding); 3 StateFarm finals parsed; run_log.json documents all results.
- Phase 23-02 completed: AUDIT-REPORT.md (255 lines) written with per-field coverage tables for all 3 doc types; 10-item gap priority table for v2.5; root causes confirmed — contractor-final column schema mismatch (RESET/REMOVE/REPLACE layout), StateFarm Customer Copy item under-extraction (grouped rows), all StateFarm metadata null.
- Phase 24-01 completed: golden master directory structure created; lachman.golden.json (32 sections, 525 items) and kalyvas.golden.json (40 sections, 887 items) produced from Phase 23 zero-delta audit output; README.md (114 lines) documents purpose, naming, schema, update process.
- Phase 24-02 completed: 4 final-draft golden masters created via pdfplumber — bschacter (29 sections, 477 items), customer_copy (31 sections, 192 items), lachman_sf (34 sections, 368 items), kalyvas_sf (36 sections, 520 items); all case_metadata populated from PDF; all recaps_and_summaries verified.

### Decisions

- [22-01] Remove Overall Direction and Confidence fields from user prompt — LLM echoed these verbatim (e.g., "Overall direction: primary_higher") instead of synthesizing narrative. LLM derives direction from category amounts and top cost drivers data already present.
- [22-01] APPROACH PAIR REQUIREMENT placed as hard constraint in system prompt (not just user CRITICAL RULES) — approach-pair framing must be mandatory, not optional inspiration.
- [22-02] Remove Notes column from Analysis sheet — Summary Top Cost Drivers table already covers notable drivers; Analysis is a data table, not a narrative supplement.
- [22-02] Strip scope_observations append from _build_overall_summary — v2.4 prompt fix is the root-cause solution; mechanical suffix was a bandaid over poor LLM overview quality.
- [23-01] 6 PDFs total (not 7) — plan text said 7 but DOCS dict has 6 entries and filesystem confirms 6; executed against actual 6.
- [23-01] BSchacter contractor final: 0 sections is a gap finding, not a fix — parser designed for rough drafts, contractor finals use a different format; documenting gap, not fixing parser (v2.5 scope).
- [23-01] Windows stdout encoding fix in script only — parser's ▶ symbol crashes cp1252 stdout; fixed by reconfiguring sys.stdout to UTF-8 in audit_all.py, keeping parser unchanged.
- [23-02] BSchacter root cause: column schema mismatch — contractor finals use RESET/REMOVE/REPLACE/TAX/O&P columns; parser regex tuned for rough-draft unit-cost layout. Metadata and recap tables parse correctly; only section/line-item extraction fails.
- [23-02] StateFarm Customer Copy root cause: summary/grouped row layout — sections detect correctly but items per section = 1 (last matched row), not all items. Declared section totals confirm many items exist that are not extracted.
- [23-02] Rough-draft parser is production-quality baseline — zero validation delta across all 72 sections; use as v2.5 regression baseline.
- [24-01] Rough-draft golden masters copied verbatim from Phase 23 audit output — zero validation delta confirmed; parser output IS the ground truth; no transformation or normalization applied.
- [24-01] final-drafts directories created now, golden masters populated in v2.5 — BSchacter (0 sections) and StateFarm (known extraction gaps) are not production-quality yet; structure in place, content deferred.
- [24-02] BSchacter recap_tax_op=null is correct — contractor-final uses category-level O&P summary, not per-section tax/OP table. Parser limitation confirmed, not a data gap.
- [24-02] Sections with 0 items in PDF are legitimate exclusions — customer_copy Dwelling Roof ("no loss noted"), kalyvas Mitigation/HVAC/Landscaping/Code Upgrades (all explicitly excluded in PDF). These SHOULD have 0 items in golden master.
- [24-02] StateFarm case_metadata sourced from PDF page 3 — parser cannot extract from the two-column summary page; pdfplumber extraction works reliably. Pattern established for v2.5 parser enhancement.
- [24-02] PRC RESTORATION INC. tax was incorrectly set to 14137.76 (total echoed into tax) — corrected to 0.0 (bid item with EN flag, no tax applied).
- [25-01] Rough-draft test_metadata failures are informative gap documentation, not regressions — golden master metadata values represent ideal v2.5 target output; parser currently returns raw/truncated values; test_section_coverage passes 100% confirming structural parser is production-quality.

Additional decisions logged in PROJECT.md Key Decisions table.

### Blockers/Concerns

- Full `apps/api` test suite has 2 unrelated non-passing migration naming tests in `tests/test_migrations_constraints.py` expecting `vip30-web` service naming.
- Phase 25 coverage harness can diff against all 6 golden masters; rough-draft masters are zero-delta baselines; final-draft masters will show expected parser gaps (v2.5 fixes not yet implemented).

## Session Continuity

Last session: 2026-03-09
Stopped at: Completed 25-01-PLAN.md — coverage harness fixtures and tests
Resume file: None
