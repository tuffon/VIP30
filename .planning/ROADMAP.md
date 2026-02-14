# Roadmap: VIP30 v1.1 MVP Launch

## Overview

Transform the existing bid comparison tool into a customer-ready MVP with user authentication, credit-based usage tracking, and real-time job progress. Four phases build sequentially: database foundation, auth system, job/credit integration, and frontend polish.

## Milestones

- 🚧 **v1.1 MVP Launch** - Phases 1-4 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (e.g., 2.1): Urgent insertions if needed

- [ ] **Phase 1: Database + Workspace Foundation** - PostgreSQL with workspace/user/credit schema
- [ ] **Phase 2: Auth + Workspace Creation** - Email OTP with automatic workspace setup
- [ ] **Phase 3: Jobs + Credits Integration** - State machine with credit consumption on success
- [ ] **Phase 4: Frontend + Usage + Polish** - Complete UX with history, progress, and rebrand

## Phase Details

### Phase 1: Database + Workspace Foundation
**Goal:** PostgreSQL infrastructure with workspace-scoped schema for all entities
**Depends on:** Nothing (first phase)
**Requirements:** DB-01, DB-02, DB-03, DB-04, DB-05, DB-06, WS-02, WS-03, WS-04, WS-05
**Success Criteria** (what must be TRUE):
  1. PostgreSQL instance running on Render with DATABASE_URL configured
  2. Alembic migrations create workspaces, users, credit_grants, credit_consumptions tables
  3. All tables have workspace_id foreign key enforced
  4. Async session factory with connection pooling handles concurrent requests
  5. workspace table has owner_user_id column
**Research:** Unlikely (standard PostgreSQL + SQLModel setup)
**Plans:** TBD

Plans:
- [ ] 01-01: PostgreSQL setup and SQLModel models *(planned)*

### Phase 2: Auth + Workspace Creation
**Goal:** Email OTP authentication that creates user + workspace + trial credits on first login
**Depends on:** Phase 1
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, AUTH-08, WS-01, CRED-04
**Success Criteria** (what must be TRUE):
  1. User can request 6-digit OTP via email
  2. Valid OTP creates user + workspace (if new) with trial credits
  3. JWT stored in HttpOnly cookie persists session across refresh
  4. Rate limiting blocks excessive OTP requests (5/hour) and attempts (5/code)
  5. Specific error messages for expired, invalid, too many attempts
  6. Login metadata (last_login_at, login_ip, login_method) stored
**Research:** Unlikely (OTP implementation well-researched)
**Plans:** TBD

Plans:
- [ ] 02-01: OTP send/verify endpoints with rate limiting *(planned)*
- [ ] 02-02: JWT sessions and workspace creation flow *(planned)*

### Phase 3: Jobs + Credits Integration
**Goal:** Job state machine with idempotent credit consumption on successful completion
**Depends on:** Phase 2
**Requirements:** JOB-01, JOB-02, JOB-03, JOB-04, JOB-05, JOB-06, CRED-02, CRED-03, CRED-05, CRED-06
**Success Criteria** (what must be TRUE):
  1. Job progresses through states: queued → parsing → analyzing → writing → completed|failed
  2. Job displays progress (state + percent) queryable via API
  3. Credits consumed only on successful completion (not on failure)
  4. Credit consumption is idempotent (UNIQUE job_id constraint)
  5. Failed jobs can be retried (creates new job)
  6. Job cannot start if workspace balance < 1 credit
**Research:** Unlikely (extends existing RQ worker patterns)
**Plans:** TBD

Plans:
- [ ] 03-01: ComparisonJob model and state machine
- [ ] 03-02: Credit consumption integration with worker

### Phase 4: Frontend + Usage + Polish
**Goal:** Complete user experience with auth UI, credit display, history, and rebrand
**Depends on:** Phase 3
**Requirements:** FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, USE-01, USE-02, USE-03, USE-04, CRED-01, NAME-01, NAME-02, NAME-03
**Success Criteria** (what must be TRUE):
  1. User can complete OTP flow (email entry → code verification → logged in)
  2. Credit balance displayed prominently in UI
  3. Job progress shown with real-time polling
  4. Job history and credit transaction history viewable with pagination
  5. Clear empty/error states (no jobs, failed job, expired OTP, insufficient credits)
  6. UI copy and internal naming reflect "bid comparison" terminology
**Research:** Unlikely (consumes stable backend APIs)
**Plans:** TBD

Plans:
- [ ] 04-01: Auth UI and credit display
- [ ] 04-02: Job progress and history views
- [ ] 04-03: Rebrand and naming cleanup

## Progress

**Execution Order:** 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Database + Workspace Foundation | 0/1 | Planned | - |
| 2. Auth + Workspace Creation | 0/2 | Planned | - |
| 3. Jobs + Credits Integration | 0/2 | Not started | - |
| 4. Frontend + Usage + Polish | 0/3 | Not started | - |

---
*Roadmap created: 2026-02-13*
*Last updated: 2026-02-13 — Phases 1, 2 planned*
