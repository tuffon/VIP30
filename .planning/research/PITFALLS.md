# Pitfalls Research: v1.1 MVP Launch

**Researched:** 2026-02-13
**Domain:** Auth, Credits, Job State Machine for FastAPI/RQ/PostgreSQL
**Confidence:** HIGH (verified with official docs, multiple sources)

## Executive Summary

The highest-risk pitfalls when adding auth and credits to an existing FastAPI/RQ application are: (1) **credit race conditions** that can result in double-charging or negative balances, (2) **OTP brute-force vulnerabilities** from inadequate rate limiting, and (3) **RQ job state inconsistencies** where jobs get stuck in limbo after worker crashes. These three areas require explicit mitigation patterns at architecture time, not as afterthoughts.

---

## Critical Pitfalls

### 1. Credit System Race Conditions (Double-Charging)

**What goes wrong:** Two concurrent requests check balance, both see sufficient credits, both debit. User ends up with negative balance or is charged twice for the same job. This is especially dangerous with async workers where job completion triggers credit deduction.

**Warning signs:**
- Balance checks happen in application code (`if user.balance >= cost`)
- Debit operations are separate from balance checks (not atomic)
- No idempotency keys on credit operations
- Users report negative balances or duplicate charges

**Prevention:**
1. **Use PostgreSQL row-level locking** for balance updates:
   ```sql
   SELECT * FROM credit_grants WHERE workspace_id = $1 FOR UPDATE;
   ```
2. **Make credit operations atomic** - check and deduct in single transaction
3. **Use idempotency keys** - every credit operation gets a unique key (e.g., `job_id + operation_type`), reject duplicates
4. **Consider ledger-style credits** - immutable `credit_grants` and `credit_consumptions` tables, never update balances directly, calculate balance as `SUM(grants) - SUM(consumptions)`
5. **Enforce at database level** - add CHECK constraint or trigger preventing negative effective balance

**Address in phase:** Database/Credits phase (early - before any credit operations)

**Sources:**
- [Modern Treasury: Designing Ledgers with Optimistic Locking](https://www.moderntreasury.com/journal/designing-ledgers-with-optimistic-locking)
- [Antradar: Avoid Stripe Double Charges](http://www.antradar.com/blog-avoid-stripe-double-charges)
- [pgledger: PostgreSQL Double-Entry Implementation](https://github.com/pgr0ss/pgledger)

---

### 2. OTP Brute-Force via Rate Limit Bypass

**What goes wrong:** Attackers bypass rate limiting using IP rotation, header manipulation (X-Forwarded-For), or session ID rotation. With 6-digit OTP and no effective rate limiting, brute force takes ~17 minutes at 1000 req/sec.

**Warning signs:**
- Rate limiting only checks IP address
- Rate limiting trusts X-Forwarded-For header from client
- New OTP can be requested unlimited times
- OTP validity window exceeds 10 minutes
- No account lockout after failed attempts

**Prevention:**
1. **Rate limit by user identifier, not IP** - use email/phone as the rate limit key
2. **Limit OTP requests per user** - max 3 OTP sends per 15 minutes per email
3. **Limit verification attempts per OTP** - max 5 attempts, then require new OTP
4. **Short OTP validity** - 5-10 minutes maximum
5. **Exponential backoff** - increase delay between allowed attempts
6. **Never trust X-Forwarded-For for rate limiting** - use it for logging only
7. **Add CAPTCHA after 2 failed attempts**

**Address in phase:** Auth phase (implement during OTP endpoint design)

**Sources:**
- [CVE-2025-60424: Nagios Fusion OTP Bypass](https://zeropath.com/blog/cve-2025-60424-nagios-fusion-otp-bypass)
- [OTP Brute-Force Via Rate Limit Bypass](https://systemweakness.com/brute-forcing-otp-via-bypassing-rate-limit-c5ee6b25c2a8)
- [Rate Limit Bypass Techniques](https://medium.com/@rajatpatel08e/rate-limit-bypass-techniques-real-world-examples-and-how-to-defend-against-it-5fd0d82673db)

---

### 3. RQ Job Stuck in StartedJobRegistry (Zombie Jobs)

**What goes wrong:** Worker crashes mid-job (OOM, SIGKILL, power failure). Job remains in `StartedJobRegistry` with status "started" indefinitely. Job never completes, never fails, never retries. User sees job "processing" forever.

**Warning signs:**
- Jobs with status "started" for hours/days
- `rq info` shows workers that don't exist
- Jobs disappear from monitoring but aren't in finished/failed registries
- Worker restarts don't automatically recover stuck jobs

**Prevention:**
1. **Set explicit job timeouts** - `job_timeout` parameter on all jobs
2. **Implement job TTL** - jobs expire and fail if not completed
3. **Add periodic cleanup task** that runs `StartedJobRegistry.cleanup()`:
   ```python
   from rq.registry import StartedJobRegistry
   registry = StartedJobRegistry('default', connection=redis)
   registry.cleanup()  # Moves expired jobs to FailedJobRegistry
   ```
4. **Store job state in database** - don't rely solely on RQ registries; job table with `status`, `started_at`, `updated_at`
5. **Heartbeat pattern** - jobs update `updated_at` periodically; separate process detects stale jobs
6. **Configure worker properly**:
   ```python
   Worker(..., job_monitoring_interval=5)  # Check job health every 5 seconds
   ```

**Address in phase:** Job State Machine phase (core infrastructure)

**Sources:**
- [RQ Issue #787: Identifying & Clearing Zombie Workers](https://github.com/rq/rq/issues/787)
- [RQ Issue #1553: Jobs Go Into Bad State](https://github.com/rq/rq/issues/1553)
- [The Interrupted Asynchronous Task Problem with Python RQ](https://medium.com/picus-security-engineering/the-interrupted-asynchronous-task-problem-and-solution-with-python-rq-435f1a597631)

---

### 4. JWT/Session Cookie Security Gaps

**What goes wrong:** Storing JWT in localStorage enables XSS theft. Using cookies without proper flags enables CSRF. Mixing approaches without understanding tradeoffs creates security holes.

**Warning signs:**
- JWT stored in localStorage or sessionStorage
- Cookies without `HttpOnly`, `Secure`, `SameSite` flags
- No CSRF protection when using cookie-based auth
- Same token used for API calls and cookie refresh

**Prevention:**
1. **Use HttpOnly cookies for refresh tokens** - cannot be accessed by JavaScript
2. **Short-lived access tokens (15-30 min)** - stored in memory only, not persisted
3. **Set all cookie security flags**:
   ```python
   response.set_cookie(
       key="refresh_token",
       value=token,
       httponly=True,
       secure=True,  # HTTPS only
       samesite="lax",  # or "strict"
       max_age=604800  # 7 days
   )
   ```
4. **Implement CSRF protection** - double-submit cookie pattern:
   - Set non-HttpOnly CSRF cookie
   - Require CSRF token in request header
   - Compare header value to cookie value
5. **Bind session to browser** - include fingerprint in token, reject on mismatch

**Address in phase:** Auth phase (session management design)

**Sources:**
- [FastAPI Security Design Guide 2025](https://blog.greeden.me/en/2025/10/14/a-beginners-guide-to-serious-security-design-with-fastapi-authentication-authorization-jwt-oauth2-cookie-sessions-rbac-scopes-csrf-protection-and-real-world-pitfalls/)
- [FastAPI JWT HttpOnly Cookie](https://www.fastapitutorial.com/blog/fastapi-jwt-httponly-cookie/)
- [JWT in Cookies - FastAPI JWT Auth](https://indominusbyte.github.io/fastapi-jwt-auth/usage/jwt-in-cookies/)

---

## Medium-Risk Pitfalls

### 5. Database Connection Pool Exhaustion

**What goes wrong:** Each request creates new database connection. Under load, connections exceed PostgreSQL's `max_connections` (default 100). New requests block or fail.

**Warning signs:**
- "too many connections" errors under load
- Slow response times that worsen with traffic
- Connection count grows but never shrinks
- Memory usage correlates with request volume

**Prevention:**
1. **Use connection pooling** - SQLAlchemy's pool or PgBouncer
2. **Configure pool size appropriately**:
   ```python
   engine = create_async_engine(
       DATABASE_URL,
       pool_size=10,
       max_overflow=20,
       pool_pre_ping=True,  # Validate connections
       pool_recycle=3600    # Refresh hourly
   )
   ```
3. **Use dependency injection with yield** - ensures connection cleanup:
   ```python
   async def get_db():
       async with AsyncSession(engine) as session:
           yield session
   ```
4. **Never create engine per-request** - create once at startup
5. **Monitor connection counts** - alert when approaching limit

**Address in phase:** Database phase (infrastructure setup)

**Sources:**
- [Handling PostgreSQL Connection Limits in FastAPI](https://medium.com/@rameshkannanyt0078/handling-postgresql-connection-limits-in-fastapi-efficiently-379ff44bdac5)
- [FastAPI Production Deployment Best Practices (Render)](https://render.com/articles/fastapi-production-deployment-best-practices)

---

### 6. Charging Credits Before Job Completion

**What goes wrong:** Credits deducted when job starts. Job fails. User lost credits but got nothing. Refund logic is complex and error-prone.

**Warning signs:**
- Credit deduction happens in API endpoint before enqueuing
- No mechanism to refund failed jobs
- Users complain about lost credits on failures

**Prevention:**
1. **Reserve, don't charge** - mark credits as "pending" when job starts
2. **Charge on success only** - create `credit_consumption` record only when job completes successfully
3. **Use idempotent completion handler**:
   ```python
   def on_job_success(job_id):
       # Idempotency: only charge if not already charged
       if not credit_consumption_exists(job_id):
           create_credit_consumption(job_id, amount)
   ```
4. **Failed jobs release reservation** - clear pending state, credits return to available
5. **Store job cost with job record** - know what to charge at completion time

**Address in phase:** Credits + Job State Machine phases (integration point)

**Sources:**
- [Best Practices for Retry Pattern](https://harish-bhattbhatt.medium.com/best-practices-for-retry-pattern-f29d47cd5117)
- [Building Resilient Task Queues with ARQ Retries](https://davidmuraya.com/blog/fastapi-arq-retries/)

---

### 7. Tenant Isolation Leaks in Workspace Model

**What goes wrong:** Query forgets `WHERE workspace_id = ?`. User sees data from another workspace. Or worse, can modify it.

**Warning signs:**
- Queries don't consistently filter by workspace
- API endpoints accept workspace_id as parameter (trust client)
- No automated tests for tenant isolation
- Debug endpoints expose raw queries

**Prevention:**
1. **Derive workspace_id from session** - never from request params
2. **Use scoped query helpers**:
   ```python
   def get_jobs(db: Session, workspace_id: UUID):
       return db.query(Job).filter(Job.workspace_id == workspace_id).all()
   ```
3. **Consider Row-Level Security** (PostgreSQL):
   ```sql
   CREATE POLICY workspace_isolation ON jobs
   USING (workspace_id = current_setting('app.current_workspace_id')::uuid);
   ```
4. **Automated tenant isolation tests** - every query tested with multiple workspaces
5. **Never expose internal IDs in URLs** - use workspace-scoped slugs

**Address in phase:** Workspace/Database phase (schema + query layer design)

**Sources:**
- [WorkOS: Developer's Guide to Multi-Tenant Architecture](https://workos.com/blog/developers-guide-saas-multi-tenant-architecture)
- [Multi-Tenant Database Architecture Patterns](https://www.bytebase.com/blog/multi-tenant-database-architecture-patterns-explained/)

---

### 8. Optimistic Locking Misunderstandings

**What goes wrong:** Developer expects SQLAlchemy `version_id_col` to work across HTTP requests (like Hibernate). It doesn't - it's transaction-scoped only. Concurrent updates still overwrite each other.

**Warning signs:**
- Using `version_id_col` but conflicts aren't detected
- No explicit version number in API responses
- Updates don't include version in request body
- `StaleDataError` never raised in production

**Prevention:**
1. **Understand scope** - SQLAlchemy versioning is in-transaction only
2. **Implement application-level optimistic locking**:
   ```python
   # Include version in response
   {"id": 123, "name": "Job", "version": 5}

   # Require version in update
   def update_job(job_id, updates, expected_version):
       result = db.execute(
           update(Job)
           .where(Job.id == job_id, Job.version == expected_version)
           .values(**updates, version=expected_version + 1)
       )
       if result.rowcount == 0:
           raise ConflictError("Job was modified by another request")
   ```
3. **Handle conflicts gracefully** - return 409 Conflict, not 500
4. **Log conflicts** - high rates indicate design problem

**Address in phase:** Database phase (update patterns)

**Sources:**
- [SQLAlchemy Versioning Documentation](https://docs.sqlalchemy.org/en/21/orm/versioning.html)
- [SQLAlchemy Database Locks Using FastAPI](https://medium.com/@mojimich2015/sqlalchemy-database-locks-using-fastapi-a-simple-guide-3e7dcd552d87)

---

### 9. Missing Database Migration Strategy

**What goes wrong:** First deployment works. Second deployment fails because schema changed. Or migrations run on application startup and block/fail under load.

**Warning signs:**
- Using `create_all()` instead of migrations
- Migrations run automatically on startup
- No migration testing before deploy
- Long-running migrations lock tables

**Prevention:**
1. **Use Alembic from day one** - never `create_all()` in production
2. **Run migrations separately from application startup**:
   ```bash
   # Deploy process
   alembic upgrade head  # Run first, separately
   # Then restart application
   ```
3. **Test migrations on production-like data** - some migrations are slow
4. **Design for backwards compatibility**:
   - Add columns as nullable or with defaults
   - Deploy new code that handles both schemas
   - Run migration
   - Deploy code that requires new schema
5. **Set statement timeouts** - migrations shouldn't hold locks forever

**Address in phase:** Database phase (infrastructure setup)

**Sources:**
- [SQL Migrations in PostgreSQL (Miro Engineering)](https://medium.com/miro-engineering/sql-migrations-in-postgresql-part-1-bc38ec1cbe75)
- [PostgreSQL Migration Playbook](https://www.percona.com/blog/best-practices-for-postgresql-migration/)

---

## Low-Risk / Edge Cases

### 10. OTP Email Delivery Timing
- **Issue:** User requests OTP, email takes 5 minutes, OTP expires before arrival
- **Mitigation:** Use reliable email provider (SendGrid, Resend), 10-minute OTP validity, allow resend after 60 seconds

### 11. Redis Connection Loss Mid-Job
- **Issue:** Worker loses Redis connection, can't update job status
- **Mitigation:** Job timeout + cleanup process, reconnection logic with backoff

### 12. Clock Skew in Distributed Workers
- **Issue:** Worker A thinks token expired, Worker B thinks it's valid
- **Mitigation:** Use NTP, add small tolerance (30 seconds) to expiry checks

### 13. Sequence Sync After Migration
- **Issue:** PostgreSQL sequences not updated after data migration, next insert fails
- **Mitigation:** Run `SELECT setval()` after any data migration
- **Source:** [Moving Tables Across PostgreSQL Instances](https://ananthakumaran.in/2025/11/02/moving-tables-across-postgres-instances.html)

### 14. Job Retry Causes Duplicate Work
- **Issue:** Job partially completed, retried, creates duplicate outputs
- **Mitigation:** Idempotency keys, check-before-write pattern, transactional consistency

### 15. Forgot to Run ANALYZE After Migration
- **Issue:** Query planner uses stale statistics, queries slow after migration
- **Mitigation:** Always run `ANALYZE` after bulk data operations
- **Source:** [PostgreSQL Migration Best Practices](https://www.percona.com/blog/best-practices-for-postgresql-migration/)

---

## Checklist for v1.1

### Auth Phase
- [ ] OTP rate limiting by email (not IP)
- [ ] Max 3 OTP sends per 15 minutes per email
- [ ] Max 5 verification attempts per OTP
- [ ] OTP expires in 10 minutes
- [ ] HttpOnly + Secure + SameSite cookies
- [ ] CSRF protection implemented
- [ ] Session binding (fingerprint or similar)

### Database Phase
- [ ] Connection pooling configured (pool_size, max_overflow)
- [ ] Alembic initialized, no create_all() in production
- [ ] All tables have workspace_id column
- [ ] Foreign key from jobs to workspace
- [ ] Row-level security OR strict query scoping

### Credits Phase
- [ ] Ledger-style tables (credit_grants, credit_consumptions)
- [ ] Idempotency keys on all credit operations
- [ ] Atomic balance check + deduction (single transaction)
- [ ] Credits charged on success only (not on queue)
- [ ] Balance calculated from ledger, not stored as mutable field

### Job State Machine Phase
- [ ] Job table with status, started_at, updated_at, completed_at
- [ ] Job timeout configured for all job types
- [ ] Cleanup task for stuck jobs (StartedJobRegistry.cleanup())
- [ ] Heartbeat pattern for long-running jobs
- [ ] Idempotent job completion handler
- [ ] Failed jobs have retry path (if applicable)

### Integration Phase
- [ ] Credit reservation on job start
- [ ] Credit consumption on job success
- [ ] Credit release on job failure
- [ ] Tenant isolation test for every query
- [ ] Concurrent request test for credit operations

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Credit race conditions | HIGH | Multiple official sources, well-documented pattern |
| OTP security | HIGH | CVE-2025-60424 + multiple security research sources |
| RQ job states | HIGH | Official RQ docs + GitHub issues with confirmed behavior |
| Session management | HIGH | FastAPI official docs + multiple production guides |
| Connection pooling | HIGH | SQLAlchemy docs + Render-specific guidance |
| Tenant isolation | MEDIUM | Pattern well-known but PostgreSQL RLS specifics need validation |
| Migration strategy | HIGH | Alembic docs + production experience widely documented |
| Optimistic locking | MEDIUM | SQLAlchemy docs clear, but cross-request pattern is app-specific |

**Research date:** 2026-02-13
**Valid until:** 2026-03-15 (patterns stable, security advisories may update)
