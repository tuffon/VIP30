# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Reliable end-to-end bid comparison that produces actionable output
**Current focus:** Between milestones — v1.2 shipped, v2 not started

## Current Position

Phase: —
Plan: —
Status: Between milestones
Last activity: 2026-02-17 — v1.2 shipped

Progress: No active milestone

## Completed Milestones

| Version | Name | Phases | Shipped |
|---------|------|--------|---------|
| v1.2 | Launch Ready | 5-8 | 2026-02-17 |
| v1.1 | MVP Launch | 1-4 | 2026-02-14 |
| v1.0.1 | Professional Adjuster Narratives | 1-8 | 2026-02-09 |

## Performance Metrics

**v1.2 Velocity:**
- Total plans completed: 6
- Phases: 4
- Timeline: 1 day

**v1.1 Velocity:**
- Total plans completed: 8
- Phases: 4
- Timeline: 2 days

## Accumulated Context

### Decisions

Decisions logged in PROJECT.md Key Decisions table.

v1.2 architecture decisions:
- Session persistence uses localStorage as UI cache, cookies remain auth source of truth
- python-json-logger for structured logging
- Request ID middleware for distributed tracing

v1.1 architecture decisions:
- Workspace model from day one (1 user per workspace for MVP)
- Credits belong to workspace, not user
- Email OTP over magic links
- Ledger-style credits: credit_grants + credit_consumptions
- Fixed job state machine: queued → parsing → analyzing → writing → completed|failed
- JWT in HttpOnly cookie

### Tech Debt (from v1.1 + v1.2)

- POST /render/upload-url is unauthenticated
- datetime.utcnow() deprecated in Python 3.12+
- JWT_SECRET has default value
- Internal naming partial (vip_job vs ComparisonJob)
- DESIGN-05: Using placeholder screenshots (replace before launch)

### Deferred Requirements

- HERO-V2-01: Demo video walkthrough
- PRICE-V2-01: Pricing page with tiers
- APP-V2-01: Date-range filtering for history

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-02-17
Stopped at: v1.2 milestone complete
Resume file: —

## Next Steps

1. Deploy v1.2 to production
2. `/gsd:new-milestone` when ready to start v2
