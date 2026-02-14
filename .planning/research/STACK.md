# Stack Research: v1.1 MVP Launch

**Researched:** 2026-02-13
**Domain:** Auth, credits, session management for FastAPI/PostgreSQL
**Overall Confidence:** HIGH

## Executive Summary

For email OTP auth with workspace model and ledger-style credits on FastAPI/PostgreSQL, use the standard 2026 stack: **SQLModel** for ORM (single model for DB + Pydantic validation), **Alembic** for migrations, **PyJWT** for session tokens, **Python secrets module** for OTP generation, and **Resend** for transactional email. No external auth library needed - email OTP is simple enough to implement directly with these primitives.

The credit system requires no external libraries - implement the ledger pattern with two tables (credit_grants, credit_consumptions) using PostgreSQL transactions for atomicity. This is a data modeling problem, not a library problem.

## Recommended Stack

### Database / ORM

| Component | Recommendation | Version | Rationale |
|-----------|---------------|---------|-----------|
| ORM | SQLModel | 0.0.33 | FastAPI creator's ORM - single model for DB + Pydantic validation, eliminates duplicate model definitions. Built on SQLAlchemy 2.0 + Pydantic v2. |
| Migrations | Alembic | 1.18.4 | Standard SQLAlchemy migration tool, works with SQLModel via `SQLModel.metadata`. Autogenerate migrations from model changes. |
| Async Driver | asyncpg | 0.31.0 | 5x faster than psycopg3 in benchmarks. Native async, works with SQLModel's async engine. Already standard for FastAPI + PostgreSQL. |
| Sync Driver | psycopg2-binary | 2.9.x | For Alembic migrations only (Alembic doesn't support async). Keep asyncpg for app code. |

**Installation:**
```bash
pip install sqlmodel==0.0.33 alembic==1.18.4 asyncpg==0.31.0 psycopg2-binary
```

**Why SQLModel over raw SQLAlchemy:**
- Write one model class, use it as both DB table and API schema
- Native FastAPI integration (responses serialize cleanly)
- Type hints throughout, Pydantic validation built-in
- Can drop to raw SQLAlchemy for complex queries when needed
- Same author as FastAPI, designed for this exact use case

### Email OTP / Auth

| Component | Recommendation | Version | Rationale |
|-----------|---------------|---------|-----------|
| OTP Generation | Python `secrets` | stdlib | Cryptographically secure 6-digit codes via `secrets.randbelow(1000000)`. No library needed - this is 3 lines of code. |
| OTP Storage | Redis (existing) | 5.0.1 | Store `{email: otp_hash}` with 10-minute TTL. Already have Redis for RQ - reuse it. Hash OTP before storing (secrets exposure). |
| Password Hashing | pwdlib[argon2] | 0.3.0 | Modern replacement for passlib (which breaks on Python 3.13+). Argon2 is current OWASP recommendation for password hashing. |
| Session Tokens | PyJWT | 2.11.0 | FastAPI official recommendation (replaced python-jose). Production-stable, simple API. |
| Email Sending | Resend | 2.21.0 | Modern developer-focused email API. 5-minute setup vs 30-60 for SendGrid. Free tier: 3,000 emails/month. Built on AWS SES infrastructure. |

**Installation:**
```bash
pip install "pwdlib[argon2]"==0.3.0 pyjwt==2.11.0 resend==2.21.0
```

**Why NOT use fastapi-otp-auth or auth libraries:**
- Email OTP is simple: generate code, store hash in Redis, send email, verify on submission
- External auth libraries add complexity for a ~50 line implementation
- No TOTP/2FA needed (that would justify pyotp)
- Keep control over rate limiting, retry logic, and workspace integration

### Session Management

| Component | Recommendation | Version | Rationale |
|-----------|---------------|---------|-----------|
| Token Type | JWT (access + refresh) | - | Stateless auth, scalable across instances. Access token: 15 min, Refresh token: 7 days. |
| Token Storage | HttpOnly cookies | - | Secure by default, no client-side JS access. Refresh token in HttpOnly cookie, access token in memory/cookie. |
| Refresh Storage | Redis (existing) | 5.0.1 | Store refresh token hashes for revocation capability. Already have Redis. |
| Rate Limiting | Simple Redis counter | - | `INCR email:{email}:otp_attempts` with TTL. Block after 5 attempts in 15 minutes. |

**Why JWT over session IDs:**
- FastAPI is stateless by design, JWT fits naturally
- Already have Redis for RQ - can store refresh token hashes for revocation
- Horizontal scaling friendly (any instance can validate)
- Industry standard for API auth

### Credit System

**Approach:** Ledger pattern with two append-only tables. No external library needed - this is pure data modeling.

**Schema:**
```sql
-- credit_grants: money in
CREATE TABLE credit_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    source VARCHAR(50) NOT NULL,  -- 'signup_bonus', 'purchase', 'manual'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB  -- stripe_payment_id, admin_note, etc.
);

-- credit_consumptions: money out
CREATE TABLE credit_consumptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    job_id UUID NOT NULL REFERENCES comparison_jobs(id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Balance calculation:**
```sql
SELECT
    COALESCE(SUM(g.amount), 0) - COALESCE(SUM(c.amount), 0) as balance
FROM workspaces w
LEFT JOIN credit_grants g ON g.workspace_id = w.id
LEFT JOIN credit_consumptions c ON c.workspace_id = w.id
WHERE w.id = $1;
```

**Why ledger pattern:**
- Append-only = full audit trail
- No race conditions on balance updates
- Easy to debug ("why does user have X credits?")
- Standard pattern for SaaS billing (Stripe, etc.)

**Why NOT double-entry bookkeeping:**
- Overkill for single-currency credits
- Double-entry needed when tracking multiple accounts (payments, refunds, transfers)
- MVP has one "currency" (comparison credits) and one account type (workspace)

### Workspace Model

**Schema:**
```sql
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    email VARCHAR(255) NOT NULL UNIQUE,
    email_verified_at TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    last_login_ip INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- MVP: 1 user per workspace, but architecture supports multi-user
CREATE UNIQUE INDEX idx_workspace_single_user ON users(workspace_id);
```

**Why workspace model for MVP:**
- Credits belong to workspace, not user (future: team shares credits)
- Jobs belong to workspace (future: team sees all jobs)
- Clean upgrade path to multi-user without schema changes
- Just remove the unique index when ready for teams

## What NOT to Use

| Library | Why Not |
|---------|---------|
| **passlib** | Breaks on Python 3.13+ (uses deprecated `crypt` module). Use pwdlib instead. |
| **python-jose** | Abandoned for 3 years until May 2025 patch. FastAPI docs now recommend PyJWT. |
| **fastapi-otp-auth** | Adds complexity for a simple flow. Email OTP is ~50 lines of code with secrets + Redis. |
| **pyotp** | TOTP/HOTP library for authenticator apps. Not needed for email OTP (different flow). |
| **SQLAlchemy directly** | More boilerplate, duplicate Pydantic models. SQLModel is a thin wrapper that eliminates this. |
| **Auth0 / Clerk / Supabase Auth** | External dependency, cost, and complexity for simple email OTP. Keep auth in-house for MVP. |
| **SendGrid** | Legacy SDK patterns, 15+ year old codebase. Resend is modern with better DX. |
| **Amazon SES directly** | Requires IAM setup, approval process, manual DKIM/SPF. Resend uses SES under the hood with simpler setup. |

## Integration Notes

### With Existing FastAPI

SQLModel integrates directly with FastAPI:
```python
from sqlmodel import SQLModel, Field, Session
from fastapi import Depends

class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspace.id")

# Response model = same class (or use SQLModel without table=True for read-only)
@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: uuid.UUID, session: Session = Depends(get_session)):
    return session.get(User, user_id)
```

### With Existing Redis (RQ)

Reuse the same Redis connection for OTP storage:
```python
# Already have this for RQ
redis_conn = Redis.from_url(settings.REDIS_URL)

# OTP storage (same connection)
def store_otp(email: str, otp_hash: str):
    redis_conn.setex(f"otp:{email}", 600, otp_hash)  # 10 min TTL
```

### With Render PostgreSQL

Render provides internal URLs for low-latency connections:
```python
# Use internal URL for app-to-db (same region)
DATABASE_URL = os.getenv("DATABASE_INTERNAL_URL")  # postgres://...@dpg-xxx.render.com/db

# asyncpg async engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

# Convert postgres:// to postgresql+asyncpg://
async_url = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(async_url)
```

**Connection Pooling:**
- Render's PostgreSQL has connection limits based on instance size
- asyncpg handles pooling via SQLAlchemy's pool settings
- If hitting limits: deploy PgBouncer as Render private service

### Migration Path

1. Add SQLModel + Alembic to requirements-web.txt
2. Create `alembic.ini` and `migrations/` directory
3. Define models in `app/models/`
4. Generate initial migration: `alembic revision --autogenerate -m "initial"`
5. Apply to Render PostgreSQL: `alembic upgrade head`

## Render Deployment Compatibility

| Component | Render Compatibility | Notes |
|-----------|---------------------|-------|
| PostgreSQL | Native | Render Postgres, internal URL for low latency |
| Redis | Native | Render Redis or existing setup |
| Alembic migrations | Deploy command | Add `alembic upgrade head` to deploy command |
| asyncpg | Compatible | Works with Render PostgreSQL |
| Resend | Compatible | External API, just needs API key in env |
| JWT sessions | Compatible | Stateless, works across instances |

**render.yaml additions:**
```yaml
services:
  - type: web
    name: vip-parse
    env: python
    buildCommand: pip install -r requirements-web.txt && alembic upgrade head
    startCommand: gunicorn app.main:app -k uvicorn.workers.UvicornWorker
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: vip-db
          property: connectionString
      - key: RESEND_API_KEY
        sync: false
```

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| SQLModel + Alembic | HIGH | Official FastAPI recommendation, widely used, verified versions on PyPI |
| asyncpg driver | HIGH | Standard for FastAPI + PostgreSQL async, verified current |
| PyJWT for sessions | HIGH | FastAPI docs explicitly recommend over python-jose |
| pwdlib for hashing | HIGH | Modern replacement for passlib, verified works on Python 3.13+ |
| Resend for email | MEDIUM | Newer service (2023), but built on AWS SES. Fallback: fastapi-mail with SMTP |
| Ledger pattern for credits | HIGH | Industry standard, no external dependencies, well-documented |
| Redis for OTP | HIGH | Already have Redis, trivial addition |
| Render compatibility | HIGH | All components are standard Python/PostgreSQL, no exotic requirements |

## Sources

### Primary (HIGH confidence)
- [PyPI: SQLModel 0.0.33](https://pypi.org/project/sqlmodel/) - Released Feb 11, 2026
- [PyPI: Alembic 1.18.4](https://pypi.org/project/alembic/) - Released Feb 10, 2026
- [PyPI: PyJWT 2.11.0](https://pypi.org/project/pyjwt/) - Released Jan 30, 2026
- [PyPI: pwdlib 0.3.0](https://pypi.org/project/pwdlib/) - Released Oct 25, 2025
- [PyPI: asyncpg 0.31.0](https://pypi.org/project/asyncpg/) - Released Nov 24, 2025
- [PyPI: Resend 2.21.0](https://pypi.org/project/resend/) - Released Jan 22, 2026
- [FastAPI Official Docs: SQL Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [FastAPI Official Docs: OAuth2 JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

### Secondary (MEDIUM confidence)
- [Render Docs: PostgreSQL Connection Pooling](https://render.com/docs/postgresql-connection-pooling)
- [TestDriven.io: FastAPI SQLModel Alembic](https://testdriven.io/blog/fastapi-sqlmodel/)
- [pgledger: Ledger Implementation in PostgreSQL](https://www.pgrs.net/2025/03/24/pgledger-ledger-implementation-in-postgresql/)
- [Email APIs in 2025: SendGrid vs Resend vs AWS SES](https://medium.com/@nermeennasim/email-apis-in-2025-sendgrid-vs-resend-vs-aws-ses-a-developers-journey-8db7b5545233)

### Tertiary (verified with official sources)
- [GitHub Discussion: python-jose abandonment](https://github.com/fastapi/fastapi/discussions/11345)
- [pwdlib Discussion: Modern passlib replacement](https://github.com/frankie567/pwdlib/discussions/1)
- [Double-Entry Ledgers: The Missing Primitive](https://www.pgrs.net/2025/06/17/double-entry-ledgers-missing-primitive-in-modern-software/)
