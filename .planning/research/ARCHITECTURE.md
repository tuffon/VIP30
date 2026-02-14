# Architecture Research: v1.1 MVP Launch

**Researched:** 2026-02-13
**Domain:** FastAPI auth/workspace/credits with RQ job processing
**Confidence:** HIGH (patterns verified with official docs and production-proven implementations)

## Executive Summary

Adding auth, workspaces, and credits to the existing FastAPI/RQ architecture requires minimal disruption to the current job processing flow. The recommended approach uses PostgreSQL for persistence, stateless JWT sessions with HttpOnly cookies, a simple workspace-scoped data model (not multi-tenant schemas), and ledger-style credit tracking with idempotent consumption tied to job IDs.

The critical integration point is the RQ worker: credit consumption must happen atomically with job completion, using the job_id as a natural idempotency key to prevent double-charging on retries.

## Component Overview

### New Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Auth Router** | Email OTP send/verify, JWT issue/refresh, logout | `src/routes/auth.py` |
| **Auth Dependencies** | `get_current_user`, `require_auth`, workspace resolution | `src/dependencies/auth.py` |
| **Database Models** | SQLAlchemy models for workspace/user/credit/job tables | `src/models/` |
| **Database Session** | Async SQLAlchemy session factory, Alembic migrations | `src/db/` |
| **Credit Service** | Grant/consume/balance operations with idempotency | `src/services/credits.py` |
| **Job Service** | State machine transitions, progress tracking | `src/services/jobs.py` |

### Modified Components

| Existing Component | What Changes |
|--------------------|--------------|
| **`src/api/main.py`** | Add auth router, DB session middleware, CORS credentials |
| **`src/routes/bid_comp.py`** | Require auth, create ComparisonJob record before enqueue, return job_id from DB |
| **`src/tasks.py`** | Update job state transitions, consume credits on success only |
| **Frontend API client** | Send cookies with credentials, handle 401 responses |

## Data Model

### Entity Relationships

```
Workspace 1--* User              (MVP: 1 user per workspace)
Workspace 1--* CreditGrant       (credits added to workspace)
Workspace 1--* CreditConsumption (credits spent on jobs)
Workspace 1--* ComparisonJob     (jobs belong to workspace)
User 1--* ComparisonJob          (user who initiated job)
ComparisonJob 1--0..1 CreditConsumption (job linked to consumption)
```

### Key Tables

#### workspaces
```sql
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    last_login_ip INET,
    login_method VARCHAR(50), -- 'email_otp'
    UNIQUE(email)
);
CREATE INDEX idx_users_workspace ON users(workspace_id);
```

#### otp_codes (ephemeral, could use Redis instead)
```sql
CREATE TABLE otp_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    code_hash VARCHAR(255) NOT NULL, -- bcrypt hash of 6-digit code
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_otp_email_expires ON otp_codes(email, expires_at);
```

#### credit_grants
```sql
CREATE TABLE credit_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    source VARCHAR(100) NOT NULL, -- 'signup_bonus', 'manual_grant', 'purchase'
    granted_by UUID REFERENCES users(id), -- NULL for system grants
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT
);
CREATE INDEX idx_credit_grants_workspace ON credit_grants(workspace_id);
```

#### credit_consumptions
```sql
CREATE TABLE credit_consumptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    job_id UUID NOT NULL UNIQUE, -- UNIQUE ensures idempotency
    amount INTEGER NOT NULL CHECK (amount > 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_credit_consumptions_workspace ON credit_consumptions(workspace_id);
```

**Idempotency note:** The `UNIQUE(job_id)` constraint on `credit_consumptions` prevents double-charging. If a worker crashes and retries, attempting to insert a second consumption for the same job_id will fail with a constraint violation, which we handle gracefully.

#### comparison_jobs
```sql
CREATE TABLE comparison_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    created_by UUID NOT NULL REFERENCES users(id),

    -- State machine
    state VARCHAR(50) NOT NULL DEFAULT 'queued',
    -- Valid states: queued, parsing, analyzing, writing, completed, failed

    -- Progress tracking
    progress_percent INTEGER DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),
    current_step VARCHAR(100), -- e.g., 'Parsing primary estimate'

    -- Input metadata
    primary_filename VARCHAR(255),
    comparison_filename VARCHAR(255),
    primary_s3_key VARCHAR(500),
    comparison_s3_key VARCHAR(500),

    -- Output
    result_s3_key VARCHAR(500),
    narrative_s3_key VARCHAR(500),

    -- Failure handling
    error_code VARCHAR(50),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- RQ integration
    rq_job_id VARCHAR(100), -- RQ's internal job ID for status queries

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_jobs_workspace ON comparison_jobs(workspace_id);
CREATE INDEX idx_jobs_state ON comparison_jobs(state);
CREATE INDEX idx_jobs_rq ON comparison_jobs(rq_job_id);
```

### Credit Balance Calculation

No stored balance field. Calculate on demand:

```sql
SELECT
    COALESCE(SUM(g.amount), 0) - COALESCE(SUM(c.amount), 0) AS balance
FROM workspaces w
LEFT JOIN credit_grants g ON g.workspace_id = w.id
LEFT JOIN credit_consumptions c ON c.workspace_id = w.id
WHERE w.id = :workspace_id;
```

For performance at scale, consider a materialized view or denormalized `balance` column with triggers.

## Data Flow

### Auth Flow (Email OTP)

```
1. POST /auth/otp/send {email}
   ├── Validate email format
   ├── Generate 6-digit code
   ├── Hash code, store in otp_codes (expires in 10 min)
   ├── Send email via SendGrid
   └── Return {success: true}

2. POST /auth/otp/verify {email, code}
   ├── Lookup unexpired otp_code for email
   ├── Verify bcrypt hash matches
   ├── Mark code as used
   ├── Lookup or create User (and Workspace for new users)
   ├── Grant default credits to new workspace (5 early, 3 later via env var)
   ├── Update user.last_login_at, last_login_ip
   ├── Create signed JWT with {sub: user_id, workspace_id, exp}
   ├── Set HttpOnly cookie with JWT
   └── Return {user, workspace}

3. Protected routes: Depends(get_current_user)
   ├── Extract JWT from cookie
   ├── Verify signature and expiration
   ├── Lookup user by ID
   └── Return User object or raise 401
```

**Session storage decision:** Use stateless JWT in HttpOnly cookies. Existing Redis is for job queue and caching, not sessions. JWTs avoid Redis session lookup overhead and simplify horizontal scaling. Trade-off: no immediate revocation (acceptable for MVP, add blacklist later if needed).

### Job + Credit Flow

```
1. POST /render/bid-comp/keys {carrier_key, contractor_key}
   ├── Depends(get_current_user) → user, workspace
   ├── Check workspace credit balance >= 1
   │   └── If insufficient: return 402 {error: "insufficient_credits"}
   ├── Create ComparisonJob record (state='queued')
   ├── Enqueue RQ task with job.id
   └── Return {job_id: job.id, status: 'queued'}

2. RQ Worker: run_bid_comp_keys(db_job_id, ...)
   ├── Load ComparisonJob from DB
   ├── Update state → 'parsing', progress → 10%
   ├── Parse primary PDF
   ├── Update progress → 30%
   ├── Parse comparison PDF
   ├── Update state → 'analyzing', progress → 50%
   ├── Run BidComp analysis
   ├── Update state → 'writing', progress → 70%
   ├── Generate XLSX, upload to S3
   ├── Update progress → 90%
   │
   ├── ON SUCCESS:
   │   ├── Try: INSERT credit_consumption (workspace_id, job_id, amount=1)
   │   │   └── If duplicate key (job_id exists): skip (already charged)
   │   ├── Update job: state='completed', result_s3_key=..., completed_at=now()
   │   └── Send notification email if requested
   │
   └── ON FAILURE:
       ├── Update job: state='failed', error_code=..., error_message=...
       └── Do NOT consume credits (job didn't complete)

3. GET /render/bid-comp/{job_id}
   ├── Depends(get_current_user) → verify user.workspace_id matches job.workspace_id
   ├── Return job state, progress, result URLs if completed
   └── Frontend polls until completed/failed
```

**Double-charge prevention:** The `UNIQUE(job_id)` constraint on `credit_consumptions` makes credit deduction idempotent. The worker can crash after charging but before marking complete; on retry, the INSERT fails harmlessly, and we proceed to mark complete.

### Retry Without Double-Charge

```
User clicks "Retry" on failed job:
1. POST /render/bid-comp/{job_id}/retry
   ├── Verify job.state = 'failed'
   ├── Verify job.workspace_id = current_user.workspace_id
   ├── Check workspace credit balance >= 1 (retries cost credits)
   ├── Create NEW ComparisonJob record (state='queued')
   │   └── Copy input metadata from original job
   │   └── Link: new_job.retry_of = original_job.id (optional tracking)
   ├── Enqueue RQ task with new_job.id
   └── Return {job_id: new_job.id, status: 'queued'}
```

**Rationale:** Retries create new jobs rather than re-running failed ones. This keeps job history clean, maintains audit trail, and the new job_id ensures separate credit consumption tracking.

## Integration Points

### With Existing RQ Worker

**Current flow:**
```python
# src/routes/bid_comp.py
job = _q.enqueue("src.tasks.run_bid_comp_keys", job_id, ...)
return {"job_id": job.id, "status": "queued"}
```

**New flow:**
```python
# src/routes/bid_comp.py
async def enqueue_bid_comp_keys(
    payload: BidCompRequest,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    # Check credits
    balance = await credit_service.get_balance(db, user.workspace_id)
    if balance < 1:
        raise HTTPException(402, detail="insufficient_credits")

    # Create DB job record
    db_job = ComparisonJob(
        workspace_id=user.workspace_id,
        created_by=user.id,
        state="queued",
        primary_s3_key=payload.carrier_key,
        comparison_s3_key=payload.contractor_key,
        primary_filename=payload.carrier_filename,
        comparison_filename=payload.contractor_filename,
    )
    db.add(db_job)
    await db.commit()

    # Enqueue RQ task
    rq_job = _q.enqueue(
        "src.tasks.run_bid_comp_keys",
        str(db_job.id),  # Pass DB job ID, not RQ job ID
        payload.carrier_key,
        payload.contractor_key,
        ...
    )

    # Store RQ job ID for reference
    db_job.rq_job_id = rq_job.id
    await db.commit()

    return {"job_id": str(db_job.id), "status": "queued"}
```

**Worker changes:**
```python
# src/tasks.py
def run_bid_comp_keys(db_job_id: str, carrier_key: str, ...):
    # Get DB session (sync, worker runs in separate process)
    with get_sync_db_session() as db:
        job = db.query(ComparisonJob).get(db_job_id)
        if not job:
            raise ValueError(f"Job {db_job_id} not found")

        try:
            job.state = "parsing"
            job.started_at = datetime.utcnow()
            db.commit()

            # ... existing parsing logic ...

            job.state = "analyzing"
            job.progress_percent = 50
            db.commit()

            # ... existing analysis logic ...

            job.state = "writing"
            job.progress_percent = 70
            db.commit()

            # ... existing XLSX generation ...

            # Consume credit (idempotent)
            try:
                consumption = CreditConsumption(
                    workspace_id=job.workspace_id,
                    job_id=job.id,
                    amount=1
                )
                db.add(consumption)
                db.commit()
            except IntegrityError:
                db.rollback()  # Already charged, continue

            job.state = "completed"
            job.result_s3_key = xlsx_key
            job.completed_at = datetime.utcnow()
            job.progress_percent = 100
            db.commit()

        except Exception as e:
            db.rollback()
            job.state = "failed"
            job.error_code, job.error_message = diagnose_failure(e)
            db.commit()
            raise
```

### With Existing Redis

**Keep Redis for:**
- RQ job queue (unchanged)
- LLM response caching (existing content-hash cache)

**Do NOT use Redis for:**
- Session storage (use stateless JWT)
- OTP storage (use PostgreSQL for audit trail, or Redis with TTL if preferred)

**Rationale:** Redis is already overloaded with job queue duties. Adding session state increases operational complexity. JWT cookies are simpler and scale better.

## Suggested Build Order

### Phase 1: Database Foundation
**Build:** PostgreSQL setup, SQLAlchemy models, Alembic migrations, DB session management

**Why first:** Everything else depends on persistent storage. Cannot implement auth without user table, cannot implement credits without credit tables.

**Deliverables:**
- Render PostgreSQL instance configured
- SQLAlchemy async engine and session factory
- Alembic migration for all tables
- Basic model classes with relationships

### Phase 2: Auth System
**Build:** OTP send/verify endpoints, JWT creation, auth dependencies, user/workspace creation

**Why second:** Jobs and credits need user context. Frontend needs auth before it can show credit balance or job history.

**Dependencies:** Phase 1 (users table, workspaces table)

**Deliverables:**
- `POST /auth/otp/send`
- `POST /auth/otp/verify`
- `POST /auth/logout`
- `get_current_user` dependency
- Automatic workspace+credit grant on first login

### Phase 3: Credit System
**Build:** Credit grant on signup, balance query endpoint, consumption service

**Why third:** Must exist before jobs can charge credits, but simpler than job state machine.

**Dependencies:** Phase 2 (workspace context from auth)

**Deliverables:**
- `GET /workspace/credits` (balance + grant history)
- Credit service with `get_balance()`, `consume()` methods
- Default grant on workspace creation (env-configurable amount)

### Phase 4: Job State Machine
**Build:** ComparisonJob model, state transitions in worker, progress tracking, API changes

**Why fourth:** Most complex, depends on all previous phases.

**Dependencies:** Phase 3 (credit check before enqueue, consumption on complete)

**Deliverables:**
- `POST /render/bid-comp/keys` with auth + credit check
- `GET /render/bid-comp/{job_id}` with progress fields
- Worker state transitions with DB updates
- Idempotent credit consumption

### Phase 5: Frontend Integration
**Build:** Auth UI, credit display, job progress polling, retry flow

**Why last:** Backend APIs must be stable before frontend integration.

**Dependencies:** All backend phases

## Middleware and Dependencies

### Recommended Dependency Structure

```python
# src/dependencies/database.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

# src/dependencies/auth.py
async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user = await db.get(User, payload["sub"])
        return user
    except JWTError:
        return None

async def require_auth(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    if not user:
        raise HTTPException(401, detail="Not authenticated")
    return user

# src/dependencies/workspace.py
async def get_workspace(
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
) -> Workspace:
    workspace = await db.get(Workspace, user.workspace_id)
    if not workspace:
        raise HTTPException(500, detail="Workspace not found")
    return workspace
```

### CORS Update Required

```python
# src/api/main.py - update CORS for credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],  # Explicit origins required
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Note:** `allow_origins=["*"]` with `allow_credentials=True` is not allowed by browsers. Must specify explicit origins.

## Configuration

### New Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Auth
JWT_SECRET=<32+ character random string>
JWT_EXPIRE_MINUTES=10080  # 7 days
OTP_EXPIRE_MINUTES=10

# Credits
DEFAULT_CREDITS_SIGNUP=5  # Early adopters
# Change to 3 later

# Email (existing SendGrid, add templates)
SENDGRID_OTP_TEMPLATE_ID=d-xxxxx
```

## Confidence Assessment

| Area | Confidence | Rationale |
|------|------------|-----------|
| Auth flow (OTP + JWT) | HIGH | Pattern verified with FastAPI docs, Scalekit guide, production implementations |
| Workspace model | HIGH | Simple foreign key relationship, not complex multi-tenancy |
| Credit ledger | HIGH | Standard pattern from fintech implementations; INSERT idempotency via UNIQUE constraint is PostgreSQL-native |
| Job state machine | HIGH | Extends existing RQ pattern; state field + DB updates are straightforward |
| RQ integration | HIGH | Existing codebase already uses RQ; changes are additive |
| Double-charge prevention | HIGH | `UNIQUE(job_id)` on credit_consumptions is bulletproof; matches Saga pattern for distributed transactions |

## Open Questions

1. **OTP storage: PostgreSQL vs Redis?**
   - PostgreSQL: Better audit trail, simpler ops (one less Redis dependency concern)
   - Redis: Native TTL expiration, faster
   - **Recommendation:** Start with PostgreSQL for simplicity; migrate to Redis if volume requires it

2. **Token refresh strategy**
   - Sliding expiration (extend on each request) vs fixed expiration with refresh token
   - **Recommendation:** Start with fixed 7-day expiration; add refresh tokens in v1.2 if session length becomes an issue

3. **Job history retention**
   - How long to keep completed/failed jobs in DB?
   - **Recommendation:** Keep indefinitely for MVP; add archival/cleanup in v1.2

## Sources

### Primary (HIGH confidence)
- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [Scalekit FastAPI OTP Implementation Guide](https://www.scalekit.com/blog/fastapi-passwordless-magic-link-otp-implementation)
- [MergeBoard Multi-tenancy with FastAPI SQLAlchemy PostgreSQL](https://mergeboard.com/blog/6-multitenancy-fastapi-sqlalchemy-postgresql/)
- [RQ Documentation](https://python-rq.org/docs/)

### Secondary (MEDIUM confidence)
- [FastAPI Redis Session Management](https://blog.poespas.me/posts/2025/02/13/fastapi-session-management-realtime-web-applications/)
- [idemptx Idempotency for FastAPI](https://medium.com/@riley.dev/a-simple-way-to-handle-idempotency-in-fastapi-using-idemptx-08d57f0faf88)
- [Saga Pattern for Distributed Transactions](https://microservices.io/patterns/data/saga.html)
- [Double-Entry Ledger Systems](https://medium.com/@altuntasfatih42/how-to-build-a-double-entry-ledger-f69edcea825d)
- [SaaS Credits System Guide 2026](https://colorwhistle.com/saas-credits-system-guide/)

### Tertiary (verified against existing codebase)
- Existing `src/routes/bid_comp.py` - current RQ enqueue pattern
- Existing `src/tasks.py` - current worker implementation
- Existing `src/api/main.py` - current FastAPI app structure
