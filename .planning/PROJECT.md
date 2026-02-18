# VIP30

## What This Is

A SaaS application for insurance adjusters to compare Xactimate bid estimates. Users upload two PDF estimates, the system parses them, compares line items, and generates an XLSX report with professional adjuster-tone narrative analysis explaining the differences. Now includes user authentication, credit-based usage tracking, and job progress visibility.

## Core Value

Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report with professional-quality narratives.

## Current Milestone: v2.1 Repository Restructure

**Goal:** Clean up repository organization — clear directory names for API, worker, frontend, and shared code. Rename Render services to match.

**Target changes:**

*Directory restructure:*
- `apps/vip-parse/` → split into `apps/api/` (FastAPI) + `apps/worker/` (RQ) + `packages/shared-python/` (shared code)
- `apps/vipclaims-saas/` → `apps/frontend/`
- Shared Python code (models, pipeline, bid_comp, methodology, rules) extracted to `packages/shared-python/`

*Render service renaming:*
- `vip30-web` → `vip30-api` (currently confusingly named — it's the API, not a web frontend)
- `vip30-frontend` stays (already correct)
- `vip30-worker` stays (already correct)

*Import and reference cleanup:*
- All Python imports updated for new package structure
- Turborepo/pnpm workspace config updated
- Dockerfile updated for new paths
- render.yaml updated with new rootDir and service names

## Current State

**Version:** v2.0 shipped 2026-02-17

**Shipped features (v2.0):**
- Methodology analysis (O&P, depreciation, scope alignment, data provenance)
- Rules engine with 3 severity tiers, 6 alert types, structural pattern detection
- 5 quality gates (hedge, judgment, quantification, evidence grounding, methodology neutrality)
- 4 output modes (executive, carrier, litigation, internal)
- Enhanced multi-sheet XLSX with conditional formatting and audit trail
- Frontend output mode selector

**Shipped features (v1.2):**
- Enterprise B2B landing page with Xactimate-focused messaging
- Trust footer with Privacy Policy, Terms of Service, and Security pages
- User dropdown with session persistence via localStorage
- Credit balance display in Bid Comp UI
- Structured JSON logging with request IDs
- Health endpoints for Render monitoring

**Shipped features (v1.1):**
- PostgreSQL database with workspace-scoped schema
- Email OTP authentication with rate limiting and JWT cookies
- Automatic workspace + trial credits creation on signup
- Job state machine (queued → parsing → analyzing → writing → completed|failed)
- Ledger-style credit system with idempotent consumption
- Real-time job progress polling in frontend
- Job and credit history with pagination
- Complete auth UI (/login, /login/verify)

**Tech stack:** Turborepo monorepo, Next.js 14 frontend, FastAPI backend, RQ worker, Redis caching, PostgreSQL on Render

## Requirements

### Validated

- ✓ Xactimate PDF parsing extracts structured data — existing
- ✓ Job queue processes long-running tasks asynchronously — existing
- ✓ Presigned URL pattern for secure file upload/download — existing
- ✓ XLSX report generation with comparison data — existing
- ✓ LLM-powered narrative generation for bid differences — existing
- ✓ Frontend upload flow with job polling — existing
- ✓ Analysis pass: structured extraction of category deltas — v1.0.1
- ✓ Writer pass: style-controlled generation with adjuster tone — v1.0.1
- ✓ Quality gates: hedging, verbosity, valuation links, summary length, analyst tone — v1.0.1
- ✓ Compliance rewrite: triggered only when quality checks fail — v1.0.1
- ✓ Pass-level Redis caching to avoid redundant LLM calls — v1.0.1
- ✓ PostgreSQL database on Render for persistence — v1.1
- ✓ Workspace model: users + credits belong to workspace — v1.1
- ✓ Email OTP authentication with rate limiting — v1.1
- ✓ Login metadata stored (last_login_at, login_ip, login_method) — v1.1
- ✓ Ledger-style credit system (grants + consumptions) — v1.1
- ✓ Credits consumed only on successful job completion — v1.1
- ✓ Trial credits granted on signup (default 5) — v1.1
- ✓ Job state machine with progress tracking — v1.1
- ✓ Clear failure messaging with retry path — v1.1
- ✓ Frontend auth UI and credit balance display — v1.1
- ✓ Job progress shown with real-time polling — v1.1
- ✓ Job and credit history with pagination — v1.1
- ✓ UI rebrand to bid comparison terminology — v1.1

### Active (v2.1)

**Repository Restructure:**
- [ ] Split `apps/vip-parse/` into `apps/api/` and `apps/worker/`
- [ ] Extract shared Python code to `packages/shared-python/`
- [ ] Rename `apps/vipclaims-saas/` to `apps/frontend/`
- [ ] Update all Python imports for new package structure
- [ ] Update Turborepo/pnpm workspace config
- [ ] Update Dockerfile for new paths
- [ ] Update render.yaml (service names, rootDir, build/start commands)
- [ ] Verify deployment works end-to-end after restructure

### Validated (v2.0)

- ✓ Methodology analysis (O&P, depreciation, scope alignment, data provenance) — v2.0
- ✓ Rules engine with severity tiers, alert tags, structural pattern detection — v2.0
- ✓ 5 quality gates (hedge, judgment, quantification, evidence grounding, methodology neutrality) — v2.0
- ✓ 4 output modes (executive, carrier, litigation, internal) — v2.0
- ✓ Enhanced multi-sheet XLSX with conditional formatting and audit trail — v2.0
- ✓ Frontend output mode selector — v2.0

### Backlog (v3+)

**Landing Page:**
- [ ] Demo video walkthrough (60 seconds)
- [ ] Pricing page with usage tiers and Team/Enterprise options

**App Experience:**
- [ ] Date-range filtering for job/credit history

**Technical:**
- [ ] ~~Internal naming cleanup (vip_job → ComparisonJob)~~ — addressed in v2.1 restructure

### Out of Scope

- OAuth login (Google/Facebook) — post-MVP, start with email OTP
- Multi-user workspaces — MVP = 1 user per workspace, architecture supports expansion
- Additional document types beyond Xactimate — scope to known format
- Fine-tuning — premature optimization; few-shot sufficient
- G-Eval tone scoring — deferred to v2
- Low balance alerts — v2 feature
- Session device binding — v2 security enhancement

## Context

Brownfield codebase with functional bid comparison. Turborepo monorepo with Next.js frontend (`apps/vipclaims-saas`), FastAPI backend (`apps/vip-parse`), and RQ worker for async processing. Deployed to Render with auto-deploy on push.

**v2.0 shipped:** Methodology analysis, rules engine, quality gates, output modes, enhanced XLSX. Full analytical intelligence layer complete.

**Current structure (to be restructured in v2.1):**
- `apps/vip-parse/` — API + worker + all Python code (monolith)
- `apps/vipclaims-saas/` — Next.js frontend
- `packages/shared/` — TypeScript shared code
- Render: `vip30-web` (API, misnamed), `vip30-frontend`, `vip30-worker`, `vip30-redis`, `vip30-db`

## Constraints

- **Deployment:** Render.com — frontend, API, worker, Redis, PostgreSQL all managed there
- **Storage:** Cloudflare R2 via S3-compatible API
- **LLM:** OpenAI API (gpt-4o-mini default)
- **Auth:** Email OTP only (no OAuth for MVP)
- **Output format:** Enhanced XLSX — visual hierarchy via conditional formatting, multi-sheet structure (no PDF generation)
- **Language:** Must avoid subjective/emotional language — withstand legal scrutiny
- **Frontend-light:** Output intelligence lives in backend, frontend displays results

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Xactimate-only parsing | Known format, proven parser exists | ✓ Good |
| RQ for job queue | Simple Redis-based queue, fits Render deployment | ✓ Good |
| XLSX output format | Industry standard, adjusters expect spreadsheets | ✓ Good |
| Three-pass LLM pipeline | Separation of concerns, token reduction, style control | ✓ Good |
| Pydantic v2 data contracts | Type safety, validation, serialization | ✓ Good |
| Content-hash cache keys | Deterministic, input-based caching | ✓ Good |
| Workspace model from day one | Supports future multi-user, credits scoped correctly | ✓ Good |
| Email OTP over magic links | Research showed better UX, clearer error handling | ✓ Good |
| Ledger-style credits | Immutable audit trail, simple balance calculation | ✓ Good |
| JWT in HttpOnly cookie | Secure, works across subdomains, no localStorage | ✓ Good |
| Job state machine | Clear progress tracking, idempotent credit consumption | ✓ Good |
| Idempotent credit consumption | UNIQUE job_id constraint prevents double-charge | ✓ Good |

## Tech Debt

| Item | Severity | Notes |
|------|----------|-------|
| `POST /render/upload-url` unauthenticated | Low | Works, but any client can request URLs |
| `datetime.utcnow()` deprecated | Low | Python 3.12+ compatibility warning |
| JWT_SECRET has default value | Low | Should enforce in production |
| Internal naming inconsistency | Low | Legacy code uses vip_job, new code uses ComparisonJob |

---
*Last updated: 2026-02-17 after starting v2.1 milestone*
