# Research Summary: v1.1 MVP Launch

**Synthesized:** 2026-02-13
**Domain:** Auth, Credits, Workspace, Job State Machine for existing FastAPI/RQ application
**Overall Confidence:** HIGH

## Executive Summary

Research validates all v1.1 architectural decisions and provides specific implementation guidance. The recommended stack is **SQLModel + Alembic** for ORM/migrations, **PyJWT + email OTP** for auth (no external auth service), **ledger-style credits** (credit_grants + credit_consumptions tables), and **database-backed job state machine** integrated with existing RQ. Critical pitfalls to avoid: credit race conditions (solved by ledger pattern + UNIQUE job_id constraint), OTP brute-force (rate limit by email, not IP), and RQ zombie jobs (add cleanup task + database job state).

## Key Findings by Dimension

### Stack
- **SQLModel 0.0.33** - FastAPI creator's ORM, single model for DB + Pydantic
- **PyJWT 2.11.0** - FastAPI-recommended JWT library (python-jose deprecated)
- **pwdlib 0.3.0** - Modern passlib replacement (passlib breaks Python 3.13+)
- **Resend 2.21.0** - Simple email API, 3k free emails/month
- **No external auth library** - Email OTP is ~50 lines with secrets + Redis

### Features
- **6-digit OTP, 10-minute expiry** - Industry standard
- **Rate limit by email** - Max 5 requests/hour, 5 attempts/code
- **Ledger-style credits** - Append-only tables, never decrement counters
- **Charge on completion only** - Failed jobs = no charge
- **Graduated low-balance alerts** - At 2 credits and 1 credit remaining

### Architecture
- **Stateless JWT in HttpOnly cookies** - No Redis sessions
- **Workspace-scoped everything** - All tables have workspace_id
- **Credit idempotency via UNIQUE(job_id)** - Prevents double-charging
- **Database job state + RQ** - DB is source of truth, RQ for execution
- **Build order:** Database → Auth → Credits → Job State Machine → Frontend

### Pitfalls
1. **Credit race conditions** - Solved by ledger pattern + UNIQUE constraint
2. **OTP brute-force** - Rate limit by email, not IP
3. **RQ zombie jobs** - Add `StartedJobRegistry.cleanup()` task
4. **JWT in localStorage** - Use HttpOnly cookies instead
5. **Connection pool exhaustion** - Configure SQLAlchemy pool properly

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Database Foundation
**Build:** PostgreSQL on Render, SQLModel models, Alembic migrations, async session factory
- Addresses: All persistence needs
- Avoids: Connection pool exhaustion (configure pool from start)
- Uses: SQLModel, Alembic, asyncpg

**Why first:** Everything depends on database. Cannot implement auth without user table, credits without credit tables, job state without job table.

### Phase 2: Workspace + Auth
**Build:** Workspace model, email OTP flow, JWT sessions, user creation
- Addresses: User authentication, workspace isolation
- Avoids: OTP brute-force (rate limiting by email built-in)
- Uses: PyJWT, pwdlib, Resend, HttpOnly cookies

**Why second:** Jobs and credits need user/workspace context. Frontend needs auth before showing anything user-specific.

### Phase 3: Credit System
**Build:** credit_grants, credit_consumptions tables, balance API, signup grant
- Addresses: Credit tracking, balance display, configurable defaults
- Avoids: Race conditions (ledger pattern is atomic)
- Uses: PostgreSQL transactions, UNIQUE constraints

**Why third:** Must exist before jobs can be charged, but simpler than job state machine.

### Phase 4: Job State Machine + Integration
**Build:** ComparisonJob model, state transitions in worker, progress tracking, credit consumption on success
- Addresses: Progress visibility, idempotent charging, retry path
- Avoids: Zombie jobs (database state + RQ cleanup), double-charging (UNIQUE job_id)
- Uses: Existing RQ, new database integration

**Why fourth:** Most complex phase, depends on all previous phases.

### Phase 5: Frontend Integration
**Build:** Auth UI (OTP flow), credit display, job progress polling, error handling
- Addresses: User-facing experience
- Avoids: XSS (HttpOnly cookies prevent token theft)
- Uses: All backend APIs

**Why last:** Backend must be stable before frontend integration.

### Phase 6: Rebrand + Polish
**Build:** Internal naming cleanup (comparison_job, bid_input), UI copy updates
- Addresses: Product positioning, code clarity
- Lower risk: No new functionality, mostly renaming

**Why last:** Polish after core functionality works.

### [Stretch] Phase 7: Narrative Enhancement
**Build:** More verbose narratives with budget guardrail
- Only if time allows, deferred if risk
- Requires: Define verbosity budget before implementing

**Phase ordering rationale:**
- Database first because everything depends on persistence
- Auth before credits because workspace context needed for credit grants
- Credits before job state because charge-on-success requires credit service
- Job state before frontend because progress APIs must work
- Frontend last because it consumes all backend APIs
- Rebrand is low-risk polish, can happen anytime after core functionality

**Research flags for phases:**
- Phase 1 (Database): Standard patterns, unlikely to need more research
- Phase 2 (Auth): OTP implementation well-researched, proceed with confidence
- Phase 4 (Job State): May need deeper research on RQ cleanup patterns if zombie jobs occur
- Phase 7 (Narrative): Would need research on verbosity budgeting approaches

## Dependencies Summary

```
Database (PostgreSQL + SQLModel)
    |
    +-- Workspace Model (workspace table)
    |       |
    |       +-- Auth System (users, otp_codes, JWT)
    |       |       |
    |       |       +-- Credit System (credit_grants, credit_consumptions)
    |       |               |
    |       |               +-- Job State Machine (comparison_jobs + RQ)
    |       |                       |
    |       |                       +-- Frontend Integration
    |       |
    |       +-- Internal Naming Cleanup (can happen anytime)
```

## Risk Assessment

| Phase | Risk Level | Reason |
|-------|------------|--------|
| Database | LOW | Standard PostgreSQL + SQLModel setup |
| Auth | MEDIUM | Email delivery reliability, OTP security |
| Credits | LOW | Ledger pattern is well-proven |
| Job State | MEDIUM | RQ integration complexity, zombie job handling |
| Frontend | LOW | Consumes stable APIs |
| Rebrand | LOW | No new functionality |
| Narrative | MEDIUM | If attempted, new complexity |

## Implementation Checklist

From PITFALLS.md, the critical checks for v1.1:

### Must Have Before Ship
- [ ] Connection pooling configured (pool_size, max_overflow)
- [ ] Alembic migrations, no create_all() in production
- [ ] All tables have workspace_id with foreign key
- [ ] OTP rate limiting by email (not IP)
- [ ] HttpOnly + Secure + SameSite cookies
- [ ] Ledger-style credits (append-only tables)
- [ ] UNIQUE(job_id) on credit_consumptions
- [ ] Credits charged on success only
- [ ] Job timeout + cleanup task for stuck jobs
- [ ] Tenant isolation in every query

## Sources

Research synthesized from 30+ sources including:
- PyPI package releases (Feb 2026 versions verified)
- FastAPI official documentation
- RQ documentation and GitHub issues
- PostgreSQL documentation
- Security advisories (CVE-2025-60424)
- Production implementation guides

Full citations in individual research files.

---
*Ready for `/gsd:define-requirements` to scope specific checkable requirements.*
