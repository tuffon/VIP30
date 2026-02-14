# Requirements: VIP30 v1.1 MVP Launch

**Defined:** 2026-02-13
**Core Value:** Reliable end-to-end bid comparison that produces actionable output

## v1.1 Requirements

Requirements for MVP customer validation. Each maps to roadmap phases.

### Database

- [ ] **DB-01**: PostgreSQL instance provisioned on Render
- [ ] **DB-02**: SQLModel ORM with Alembic migrations (no create_all in production)
- [ ] **DB-03**: Async session factory with connection pooling configured
- [ ] **DB-04**: All tables have workspace_id foreign key for tenant isolation
- [ ] **DB-05**: credit_grants table (workspace_id, amount, source, timestamp)
- [ ] **DB-06**: credit_consumptions table (workspace_id, job_id UNIQUE, amount, timestamp)

### Workspace

- [ ] **WS-01**: Workspace created automatically when user signs up
- [ ] **WS-02**: User belongs to exactly one workspace
- [ ] **WS-03**: All data (jobs, credits) scoped to workspace via workspace_id
- [ ] **WS-04**: Enforce 1 user per workspace limit (MVP)
- [ ] **WS-05**: Store owner_user_id on workspace table

### Auth

- [ ] **AUTH-01**: User can request OTP via email (6-digit code)
- [ ] **AUTH-02**: OTP expires after 10 minutes
- [ ] **AUTH-03**: Issuing new OTP invalidates all previous codes for that email
- [ ] **AUTH-04**: Rate limiting: max 5 OTP requests per email per hour
- [ ] **AUTH-05**: Rate limiting: max 5 verification attempts per code
- [ ] **AUTH-06**: Specific error messages (expired, invalid, too many attempts)
- [ ] **AUTH-07**: Store login metadata (last_login_at, login_ip, login_method)
- [ ] **AUTH-08**: JWT session stored in HttpOnly + Secure + SameSite cookie

### Credits

- [ ] **CRED-01**: User can view current credit balance in UI
- [ ] **CRED-02**: Credits tracked via ledger (credit_grants + credit_consumptions)
- [ ] **CRED-03**: Credits only consumed on successful job completion
- [ ] **CRED-04**: Trial credits granted on signup (configurable: default 5)
- [ ] **CRED-05**: Credit consumption is idempotent (job can only consume once)
- [ ] **CRED-06**: Balance = SUM(grants) - SUM(consumptions), calculated not stored

### Jobs

- [ ] **JOB-01**: Job has defined states: queued, parsing, analyzing, writing, completed, failed
- [ ] **JOB-02**: Job displays progress indicator (current state + percent/step)
- [ ] **JOB-03**: Failed job stores human-readable error_reason
- [ ] **JOB-04**: User can retry failed job (creates new job, charges on success)
- [ ] **JOB-05**: Terminal states (completed, failed) are immutable
- [ ] **JOB-06**: Job cannot start if workspace has insufficient credits

### Usage

- [ ] **USE-01**: User can view job history list (status, date, credit cost)
- [ ] **USE-02**: User can view credit transaction history (grants + consumptions)
- [ ] **USE-03**: History supports server-side pagination
- [ ] **USE-04**: History supports basic date-range filtering

### Frontend

- [ ] **FE-01**: Auth UI: email entry screen and OTP verification screen
- [ ] **FE-02**: Credit balance displayed prominently in UI
- [ ] **FE-03**: Job progress shown with polling/real-time updates
- [ ] **FE-04**: Rebrand: UI copy reflects "bid comparison tool" positioning
- [ ] **FE-05**: Clear empty state: "No jobs yet" when history is empty
- [ ] **FE-06**: Clear error states: failed job, expired OTP, insufficient credits

### Internal Naming

- [ ] **NAME-01**: Rename vip_job → comparison_job in codebase
- [ ] **NAME-02**: Rename raw_upload → bid_input in codebase
- [ ] **NAME-03**: Update user-facing strings (UI labels, API responses, logs, errors)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Credits

- **CRED-V2-01**: Low balance alerts (in-app warnings at 2 credits, 1 credit)
- **CRED-V2-02**: Email notifications for low balance

### Auth

- **AUTH-V2-01**: OAuth login (Google/Facebook)
- **AUTH-V2-02**: Session device binding
- **AUTH-V2-03**: IP-based rate limiting (supplement email-based)

### Usage

- **USE-V2-01**: Usage analytics dashboard (trends, jobs per week)

### Narrative

- **NARR-V2-01**: More verbose narratives with verbosity budget guardrail

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Magic links | OTP preferred per research (UX issues with magic links) |
| Multi-user workspaces | MVP = 1 user per workspace, architecture supports later |
| Credit expiry | Adds complexity, not needed for MVP validation |
| Payment/billing integration | MVP uses granted credits only |
| SMS OTP | Email-only for MVP |
| Passkeys/WebAuthn | Future standard, too complex for MVP |
| Workspace switching | 1 workspace per user for MVP |
| CAPTCHA on OTP | Only add if abuse becomes a problem |
| Credit transfer | No multi-user = no transfers needed |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DB-01 | TBD | Pending |
| DB-02 | TBD | Pending |
| DB-03 | TBD | Pending |
| DB-04 | TBD | Pending |
| DB-05 | TBD | Pending |
| DB-06 | TBD | Pending |
| WS-01 | TBD | Pending |
| WS-02 | TBD | Pending |
| WS-03 | TBD | Pending |
| WS-04 | TBD | Pending |
| WS-05 | TBD | Pending |
| AUTH-01 | TBD | Pending |
| AUTH-02 | TBD | Pending |
| AUTH-03 | TBD | Pending |
| AUTH-04 | TBD | Pending |
| AUTH-05 | TBD | Pending |
| AUTH-06 | TBD | Pending |
| AUTH-07 | TBD | Pending |
| AUTH-08 | TBD | Pending |
| CRED-01 | TBD | Pending |
| CRED-02 | TBD | Pending |
| CRED-03 | TBD | Pending |
| CRED-04 | TBD | Pending |
| CRED-05 | TBD | Pending |
| CRED-06 | TBD | Pending |
| JOB-01 | TBD | Pending |
| JOB-02 | TBD | Pending |
| JOB-03 | TBD | Pending |
| JOB-04 | TBD | Pending |
| JOB-05 | TBD | Pending |
| JOB-06 | TBD | Pending |
| USE-01 | TBD | Pending |
| USE-02 | TBD | Pending |
| USE-03 | TBD | Pending |
| USE-04 | TBD | Pending |
| FE-01 | TBD | Pending |
| FE-02 | TBD | Pending |
| FE-03 | TBD | Pending |
| FE-04 | TBD | Pending |
| FE-05 | TBD | Pending |
| FE-06 | TBD | Pending |
| NAME-01 | TBD | Pending |
| NAME-02 | TBD | Pending |
| NAME-03 | TBD | Pending |

**Coverage:**
- v1.1 requirements: 39 total
- Mapped to phases: 0 (pending create-roadmap)
- Unmapped: 39

---
*Requirements defined: 2026-02-13*
*Last updated: 2026-02-13 after initial definition*
