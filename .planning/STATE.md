---
gsd_state_version: 1.0
milestone: v2.6
milestone_name: Pipeline Rewrite
status: complete
last_updated: "2026-03-16T00:00:00Z"
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 13
  completed_plans: 13
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-16)

**Core value:** Reliable end-to-end bid comparison that produces actionable output
**Current focus:** v2.6 complete — between milestones, planning next

## Current Position

Phase: 34.1 of 34.1 (exact category preservation no umbrella remapping in bid comp) — COMPLETE
Plan: 34.1-02 of 34.1-02 — complete
Status: v2.6 milestone complete — ready for next milestone planning

Last activity: 2026-03-16 — v2.6 milestone archived; ROADMAP.md and REQUIREMENTS.md archived to milestones/

Progress: ██████████ 13/13 plans (100%)

## Completed Milestones

| Version | Name | Phases | Shipped |
|---------|------|--------|---------|
| v2.6 | Pipeline Rewrite | 29-34, 34.1 | 2026-03-11 |
| v2.4 | Parser Coverage Harness | 23-25 | 2026-03-09 |
| v2.2 | Unified Output | 16-17 | 2026-02-18 |
| v2.1 | Repository Restructure | 13-15 | 2026-02-18 |
| v2.0 | Analytical Intelligence | 9-12 | 2026-02-17 |
| v1.2 | Launch Ready | 5-8 | 2026-02-17 |
| v1.1 | MVP Launch | 1-4 | 2026-02-14 |
| v1.0.1 | Professional Adjuster Narratives | 1-8 | 2026-02-09 |

## Accumulated Context

### What Was Built (v2.6)

Monolithic three-pass pipeline replaced with cost-driver-first stepped architecture:
- `TradeContext` — exact parsed category totals from `recap_by_category` with `trade_summary` enrichment; lazy-import pattern resolves circular dependency
- `CostDriver` + `DriverWithItems` — deterministic top-driver ranking by absolute delta; line-item mapping with verification gate
- `run_driver_pass()` — isolated context per driver, `generate_structured()` only, content-hash cache
- `CostDriverPipeline` — replaces `NarrativePipeline`; single-pass rewrite on GATE-01/GATE-02 only; explicit fallback per failed driver
- Exact category preservation — umbrella labels removed end-to-end; 67/67 regression tests

### Blockers/Concerns (carry forward)

- Full `apps/api` test suite has 2 unrelated non-passing migration naming tests in `tests/test_migrations_constraints.py` expecting `vip30-web` service naming.
- `packages/parser` suite currently has 1 unrelated non-passing coverage case in `tests/test_coverage.py` for `lachman_sf` (3 section item-count mismatches with matching totals).
- Remaining parser limitations (low priority, v2.7+): rough-draft insured_name not extractable; price_list suffix truncation; 3 lachman_sf sections with declared-vs-computed rounding deltas.

## Session Continuity

Last session: 2026-03-16
Stopped at: v2.6 milestone archived
Resume file: None
