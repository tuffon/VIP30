# External Integrations

**Analysis Date:** 2026-01-15

## APIs & External Services

**OpenAI:**
- Used for: Text embeddings (semantic search), LLM chat completions (bid comparison narrative generation)
- SDK/Client: `openai` Python package 1.12.0
- Auth: `OPENAI_API_KEY` env var
- Models used:
  - `text-embedding-3-small` - Vector embeddings for costbook search
  - `gpt-4o-mini` (configurable via `OPENAI_MODEL`) - Narrative generation
- Files:
  - `apps/vip-parse/src/api/retriever.py` - Embedding queries
  - `apps/vip-parse/src/api/render.py` - LLM completions
  - `apps/vip-parse/src/llm/` - LLM adapter module
  - `apps/vip-parse/embeddings/embed_and_upload_bni_costs.py` - Batch embedding upload

**Qdrant (Vector Database):**
- Used for: Semantic search over costbook data
- SDK/Client: `qdrant-client` Python package 1.15.1
- Auth: `QDRANT_API_KEY` env var
- Endpoint: `QDRANT_URL` (defaults to AWS-hosted Qdrant Cloud)
- Collection: `costbook_data`
- Files:
  - `apps/vip-parse/src/api/retriever.py` - Search queries
  - `apps/vip-parse/embeddings/embed_and_upload_bni_costs.py` - Data upload
  - `apps/vip-parse/embeddings/create_payload_index.py` - Index management

**SendGrid:**
- Used for: Transactional email notifications when bid comparisons complete
- SDK/Client: Direct HTTP via `httpx` (custom minimal client)
- Auth: `SENDGRID_API_KEY` env var
- Sender config: `SENDGRID_FROM_EMAIL`, `SENDGRID_FROM_NAME`, `BRAND_NAME`
- API endpoint: `https://api.sendgrid.com/v3/mail/send`
- Files:
  - `apps/vip-parse/src/integrations/sendgrid_client.py` - Email client implementation
  - `apps/vip-parse/src/tasks.py` - Invokes email on job completion

**Google OAuth:**
- Used for: User authentication in frontend
- SDK/Client: `next-auth` with `GoogleProvider`
- Auth: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` env vars
- Files:
  - `apps/vipclaims-saas/app/api/auth/[...nextauth]/route.ts` - NextAuth configuration

## Data Storage

**Cloudflare R2 (S3-Compatible):**
- Used for: File uploads (PDFs), result storage (XLSX, JSON artifacts)
- SDK/Client: `boto3` Python package with S3 API
- Auth:
  - `S3_ENDPOINT` or `CLOUDFLARE_ACCOUNT_ID` (derives endpoint)
  - `S3_ACCESS_KEY_ID` / `CLOUDFLARE_R2_ACCESS_KEY_ID`
  - `S3_SECRET_ACCESS_KEY` / `CLOUDFLARE_R2_SECRET_ACCESS_KEY`
  - `S3_BUCKET` / `CLOUDFLARE_BUCKET`
- Operations:
  - Presigned upload URLs for client-side uploads
  - Presigned download URLs for result retrieval
  - Direct upload/download for worker processing
- Files:
  - `apps/vip-parse/src/utils/s3_client.py` - S3/R2 client factory
  - `apps/vip-parse/src/routes/s3.py` - Presigned URL endpoints
  - `apps/vip-parse/src/routes/bid_comp.py` - Download URL generation
  - `apps/vip-parse/src/tasks.py` - File operations in worker

**Redis:**
- Used for: Background job queue (RQ), job status tracking
- SDK/Client: `redis` Python package 5.0.1, `rq` 1.15.1
- Auth: `REDIS_URL` env var (composed from `REDIS_HOST`/`REDIS_PORT` in Render)
- Queue name: `bidcomp`
- Managed by: Render Redis service (`vip30-redis`)
- Files:
  - `apps/vip-parse/src/routes/bid_comp.py` - Job enqueue and status
  - `apps/vip-parse/src/tasks.py` - Job execution

**Supabase:**
- Used for: Marketing email signup storage
- SDK/Client: Direct HTTP via `httpx` (custom minimal client)
- Auth: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` env vars
- Table: Configurable via `SUPABASE_EMAIL_TABLE` (default: `email_signups`)
- API: REST endpoint with `resolution=merge-duplicates` for upserts
- Files:
  - `apps/vip-parse/src/integrations/supabase.py` - Marketing client
  - `apps/vip-parse/src/routes/marketing.py` - Signup endpoint

**File Storage (Local/Temp):**
- Used for: Temporary PDF processing, parser output
- Location: System temp directory (`tempfile.mkdtemp()`)
- Cleanup: Automatic after job completion
- Files:
  - `apps/vip-parse/src/tasks.py` - Temp file management

## Authentication & Identity

**Auth Provider:**
- NextAuth.js with Google OAuth provider
- Implementation: OAuth 2.0 flow with JWT session tokens
- Session callback enriches session with user ID from token
- Files:
  - `apps/vipclaims-saas/app/api/auth/[...nextauth]/route.ts`

**Required env vars:**
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`

## Monitoring & Observability

**Error Tracking:**
- None configured (no Sentry, Bugsnag, etc.)

**Logging:**
- Python: `logging` module with configurable level via `LOG_LEVEL`
- Format: `%(asctime)s %(levelname)-8s %(name)s :: %(message)s`
- Uvicorn access logs disabled to reduce noise
- Files:
  - `apps/vip-parse/src/api/main.py` - API logging config
  - `apps/vip-parse/src/tasks.py` - Worker logging config

## CI/CD & Deployment

**Hosting Platform:**
- Render.com
- Config: `render.yaml` (Infrastructure as Code)

**Services Deployed:**
| Service | Type | Environment | Root Dir |
|---------|------|-------------|----------|
| vip30-frontend | Web | Node.js | `.` (root) |
| vip30-web | Web | Python | `apps/vip-parse` |
| vip30-worker | Worker | Python | `apps/vip-parse` |
| vip30-redis | Redis | Managed | - |

**Build Commands:**
- Frontend: `pnpm install && pnpm --filter vipclaims-saas... --filter @vip/shared... build`
- Backend web: `pip install -r requirements-web.txt`
- Backend worker: `pip install -r requirements-worker.txt`

**Start Commands:**
- Frontend: `cd apps/vipclaims-saas && pnpm start`
- Backend web: `gunicorn src.main:app -k uvicorn.workers.UvicornWorker`
- Backend worker: `rq worker -u "$REDIS_URL" bidcomp`

**CI Pipeline:**
- Auto-deploy on push (configured in Render)
- No explicit CI workflow files detected

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing (Optional):**
- `DOWNSTREAM_API_URL` - POST callback when bid comparison job completes
- Auth: `DOWNSTREAM_API_KEY` as Bearer token
- Payload: `{ "context": recap_bundle, "template": template }`
- Files:
  - `apps/vip-parse/src/tasks.py` - Downstream API call

## API Endpoints

**Backend API Routes:**

| Route | Method | Purpose | File |
|-------|--------|---------|------|
| `/` | GET | Health check | `apps/vip-parse/src/api/main.py` |
| `/healthz` | GET | Health probe | `apps/vip-parse/src/api/main.py` |
| `/debug` | GET | Environment debug info | `apps/vip-parse/src/api/main.py` |
| `/search` | GET | Semantic costbook search | `apps/vip-parse/src/api/main.py` |
| `/render/upload-url` | POST | Generate presigned upload URL | `apps/vip-parse/src/routes/s3.py` |
| `/render/download-url` | GET | Generate presigned download URL | `apps/vip-parse/src/routes/s3.py` |
| `/render/bid-comp/keys` | POST | Enqueue bid comparison job | `apps/vip-parse/src/routes/bid_comp.py` |
| `/render/bid-comp/{job_id}` | GET | Get job status/results | `apps/vip-parse/src/routes/bid_comp.py` |
| `/marketing/signup` | POST | Capture marketing signup | `apps/vip-parse/src/routes/marketing.py` |

**Frontend API Routes:**
| Route | Method | Purpose | File |
|-------|--------|---------|------|
| `/api/auth/[...nextauth]` | GET/POST | NextAuth authentication | `apps/vipclaims-saas/app/api/auth/[...nextauth]/route.ts` |

## Environment Configuration

**Required env vars (Production):**
```
# Frontend
NEXT_PUBLIC_API_BASE_URL=https://vip30-web.onrender.com
NEXTAUTH_URL=<frontend-url>
NEXTAUTH_SECRET=<secret>
GOOGLE_CLIENT_ID=<oauth-client-id>
GOOGLE_CLIENT_SECRET=<oauth-client-secret>

# Backend
OPENAI_API_KEY=<api-key>
QDRANT_API_KEY=<api-key>
QDRANT_URL=<qdrant-url>
REDIS_URL=redis://<host>:<port>/0
S3_ENDPOINT=<r2-endpoint>
S3_ACCESS_KEY_ID=<access-key>
S3_SECRET_ACCESS_KEY=<secret-key>
S3_BUCKET=<bucket-name>
```

**Optional env vars:**
```
# Email notifications
SENDGRID_API_KEY=<api-key>
SENDGRID_FROM_EMAIL=<email>
SENDGRID_FROM_NAME=<name>
BRAND_NAME=ScopeVista

# Marketing database
SUPABASE_URL=<url>
SUPABASE_SERVICE_ROLE_KEY=<key>
SUPABASE_EMAIL_TABLE=email_signups

# Webhooks
DOWNSTREAM_API_URL=<url>
DOWNSTREAM_API_KEY=<token>

# Tuning
LOG_LEVEL=INFO
PARSE_CONCURRENCY=1
OPENAI_MODEL=gpt-4o-mini
PRESIGN_EXPIRE_SEC=900
EMAIL_DOWNLOAD_EXPIRE_SEC=86400
CORS_ALLOW_ORIGINS=*
CORS_ALLOW_CREDENTIALS=false
```

**Secrets Location:**
- Environment variables (not committed)
- Render dashboard for production secrets
- `.env` file for local development (gitignored)
- `.env.example` files document required vars

---

*Integration audit: 2026-01-15*
