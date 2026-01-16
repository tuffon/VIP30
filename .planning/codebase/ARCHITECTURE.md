# Architecture

**Analysis Date:** 2026-01-15

## Pattern Overview

**Overall:** Monorepo with distributed frontend/backend services

**Key Characteristics:**
- Turborepo-managed pnpm workspace with two apps and one shared package
- Next.js 14 frontend with App Router and client-side Redux state
- FastAPI Python backend with RQ (Redis Queue) worker for async processing
- Presigned URL pattern for S3/R2 file uploads and downloads
- Job queue pattern for long-running PDF parsing and comparison tasks

## Layers

**Frontend (vipclaims-saas):**
- Purpose: User-facing SaaS web application
- Location: `apps/vipclaims-saas/`
- Contains: Next.js pages, React components, Redux store, API routes
- Depends on: Backend API (vip-parse), next-auth, @vip/shared
- Used by: End users via browser

**Backend API (vip-parse):**
- Purpose: REST API and business logic for document processing
- Location: `apps/vip-parse/`
- Contains: FastAPI routes, LLM adapters, PDF parsers, bid comparison logic
- Depends on: Redis, S3/R2, OpenAI, Qdrant, SendGrid
- Used by: Frontend via HTTP, RQ workers

**Worker (vip-parse worker):**
- Purpose: Background job processor for CPU-intensive tasks
- Location: `apps/vip-parse/src/tasks.py`
- Contains: RQ job handlers, parser orchestration, XLSX generation
- Depends on: Redis queue, S3/R2, OpenAI, parse modules
- Used by: API enqueues jobs, worker processes them

**Shared Package:**
- Purpose: Shared TypeScript types and constants
- Location: `packages/shared/`
- Contains: Common type definitions (currently minimal)
- Depends on: None
- Used by: vipclaims-saas

**Parser Core:**
- Purpose: Xactimate PDF parsing and data extraction
- Location: `apps/vip-parse/parse/xactimate/`
- Contains: XactimateRoughDraftParser, helpers, constants
- Depends on: pdfminer, internal utilities
- Used by: Worker tasks

**Bid Comparison Engine:**
- Purpose: Compare two parsed estimates and generate reports
- Location: `apps/vip-parse/src/bid_comp/`
- Contains: BidComp class, XLSX export, matchers, taxonomy
- Depends on: LLM adapters, parse output
- Used by: Worker tasks

## Data Flow

**Bid Comparison Flow:**

1. User uploads two PDFs via frontend (`apps/vipclaims-saas/app/bid-comp/page.tsx`)
2. Frontend requests presigned upload URLs from API (`/render/upload-url`)
3. Frontend uploads PDFs directly to S3/R2 using presigned URLs
4. Frontend enqueues job via API (`POST /render/bid-comp/keys`)
5. API creates RQ job with S3 keys (`apps/vip-parse/src/routes/bid_comp.py`)
6. Worker picks up job, downloads PDFs from S3 (`apps/vip-parse/src/tasks.py`)
7. Worker runs XactimateRoughDraftParser on each PDF
8. Worker runs BidComp to compare estimates and generate XLSX
9. Worker uploads results to S3/R2
10. Frontend polls job status, receives presigned download URL when complete
11. Optional: SendGrid email notification with download link

**State Management:**
- Frontend uses Redux Toolkit with RTK Query for API caching
- Job state persisted in Redis via RQ
- File artifacts stored in S3/R2 with presigned URLs

**Costbook Search Flow:**

1. User queries `/search` endpoint
2. API embeds query via OpenAI text-embedding-3-small
3. API queries Qdrant vector store for similar costbook items
4. Results returned as JSON array

## Key Abstractions

**BidComp:**
- Purpose: Core comparison engine for two estimate payloads
- Examples: `apps/vip-parse/src/bid_comp/core.py`
- Pattern: Dataclass-based artifacts (EstimatePair, NarrativeResult), category mapping, LLM narrative generation

**XactimateRoughDraftParser:**
- Purpose: Extract structured data from Xactimate PDF estimates
- Examples: `apps/vip-parse/parse/xactimate/parser.py`
- Pattern: PDF parsing with section extraction, recap generation

**LLMAdapterBase / OpenAIChatAdapter:**
- Purpose: Abstract LLM integration for narrative generation
- Examples: `apps/vip-parse/src/llm/adapter.py`
- Pattern: Template-based prompts, pluggable adapter interface

**S3Client:**
- Purpose: S3-compatible storage abstraction (works with Cloudflare R2)
- Examples: `apps/vip-parse/src/utils/s3_client.py`
- Pattern: Environment-based configuration with multiple alias support

## Entry Points

**Frontend:**
- Location: `apps/vipclaims-saas/app/layout.tsx`, `apps/vipclaims-saas/app/page.tsx`
- Triggers: User navigation
- Responsibilities: Root layout, authentication wrapper, page routing

**Backend API:**
- Location: `apps/vip-parse/src/api/main.py`
- Triggers: HTTP requests via Gunicorn/Uvicorn
- Responsibilities: FastAPI app initialization, CORS, router registration

**Worker:**
- Location: `apps/vip-parse/src/tasks.py`
- Triggers: RQ job dequeue
- Responsibilities: Job processing, parser orchestration, result upload

**API Routes:**
- `/` and `/healthz`: Health checks
- `/search`: Costbook semantic search
- `/render/bid-comp/keys`: Enqueue bid comparison job
- `/render/bid-comp/{job_id}`: Poll job status
- `/render/upload-url`: Generate presigned upload URL

## Error Handling

**Strategy:** Exception propagation with logging and HTTP error responses

**Patterns:**
- FastAPI HTTPException for API errors
- RQ job failure tracking with TTL
- Comprehensive logging with structured fields
- Try/except with fallback narratives in BidComp

## Cross-Cutting Concerns

**Logging:** Python logging module with structured format (`%(asctime)s %(levelname)-8s %(name)s :: %(message)s`), configurable via LOG_LEVEL env var

**Validation:** FastAPI Query/Pydantic for request validation, manual dict checking in bid_comp

**Authentication:** next-auth with SessionProvider wrapper, minimal implementation in current state

---

*Architecture analysis: 2026-01-15*
