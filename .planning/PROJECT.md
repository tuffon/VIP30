# VIP30

## What This Is

A SaaS application for insurance adjusters to compare Xactimate bid estimates. Users upload two PDF estimates, the system parses them, compares line items, and generates an XLSX report with professional adjuster-tone narrative analysis explaining the differences. Now includes user authentication, credit-based usage tracking, and job progress visibility.

## Core Value

Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report with professional-quality narratives.

## Current Milestone: v2.2 Unified Output

**Goal:** Replace 4 output modes with a single unified 2-sheet report. Simpler UX, no mode selection required.

**Target changes:**

*XLSX output restructure:*
- 6 sheets → 2 sheets: **Summary** + **Analysis**
- Summary: total delta, top cost drivers, key observations (merges Executive Summary + Ranked Impact)
- Analysis: methodology detail, scope alignment, full category-by-category side-by-side comparison (merges Methodology + Scope + Category Detail)
- Audit trail sheet dropped (developer telemetry, no user value)

*Output mode removal:*
- Remove `OutputMode` enum and `OutputModeFilter` class
- Remove mode selector radio buttons from frontend bid comp page
- Remove `output_mode` parameter from API `CreateJobRequest`
- Remove mode passthrough from worker/pipeline
- Drop `output_mode` column usage on `ComparisonJob` model

*LLM pipeline:*
- Unchanged — same 3-pass generation, fix output format only

## Current State

**Version:** v2.1 shipped 2026-02-18

**Shipped features (v2.1):**
- Repository restructured: monolith split into `apps/api/`, `apps/worker/`, `apps/frontend/`
- Standalone packages: `packages/parser/` (10 modules), `packages/shared-python/` (46 modules)
- Render services properly named: vip30-api, vip30-frontend, vip30-worker
- Dead preflight code removed

**Shipped features (v2.0):**
- Methodology analysis (O&P, depreciation, scope alignment, data provenance)
- Rules engine with 3 severity tiers, 6 alert types, structural pattern detection
- 5 quality gates (hedge, judgment, quantification, evidence grounding, methodology neutrality)
- 4 output modes (executive, carrier, litigation, internal) — being replaced in v2.2
- Enhanced multi-sheet XLSX with conditional formatting and audit trail — being simplified in v2.2
- Frontend output mode selector — being removed in v2.2

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

**Current structure:**
- `apps/api/` — FastAPI server
- `apps/worker/` — RQ worker
- `apps/frontend/` — Next.js frontend
- `packages/parser/` — Xactimate PDF parser
- `packages/shared-python/` — Shared business logic (pipeline, bid_comp, rules, methodology, etc.)
- `packages/shared/` — TypeScript shared code
- Render: `vip30-api`, `vip30-frontend`, `vip30-worker`, `vip30-redis`, `vip30-db`

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
- ✓ Methodology analysis (O&P, depreciation, scope alignment, data provenance) — v2.0
- ✓ Rules engine with severity tiers, alert tags, structural pattern detection — v2.0
- ✓ 5 quality gates (hedge, judgment, quantification, evidence grounding, methodology neutrality) — v2.0
- ⚠️ 4 output modes (executive, carrier, litigation, internal) — v2.0 — being replaced by unified output in v2.2
- ⚠️ Enhanced multi-sheet XLSX with conditional formatting and audit trail — v2.0 — being simplified to 2 sheets in v2.2
- ⚠️ Frontend output mode selector — v2.0 — being removed in v2.2
- ✓ Monolith split into apps/api + apps/worker — v2.1
- ✓ Standalone parser and shared-python packages — v2.1
- ✓ Frontend renamed from vipclaims-saas — v2.1
- ✓ Render services properly named and configured — v2.1
- ✓ All Python imports resolve with new package structure — v2.1

### Active (v2.2)

**Unified Output:**
- [ ] Merge Executive Summary + Ranked Impact into single "Summary" sheet
- [ ] Merge Methodology + Scope + Category Detail into single "Analysis" sheet
- [ ] Drop audit trail sheet
- [ ] Remove OutputMode enum and OutputModeFilter class
- [ ] Remove mode selector from frontend bid comp page
- [ ] Remove output_mode from API request and job model
- [ ] Remove mode passthrough from worker/pipeline

### Backlog (v3+)

**Landing Page:**
- [ ] Demo video walkthrough (60 seconds)
- [ ] Pricing page with usage tiers and Team/Enterprise options

**App Experience:**
- [ ] Date-range filtering for job/credit history

### Out of Scope

- OAuth login (Google/Facebook) — post-MVP, start with email OTP
- Multi-user workspaces — MVP = 1 user per workspace, architecture supports expansion
- Additional document types beyond Xactimate — scope to known format
- Fine-tuning — premature optimization; few-shot sufficient
- G-Eval tone scoring — deferred to v2
- Low balance alerts — v2 feature
- Session device binding — v2 security enhancement

## Constraints

- **Deployment:** Render.com — frontend, API, worker, Redis, PostgreSQL all managed there
- **Storage:** Cloudflare R2 via S3-compatible API
- **LLM:** OpenAI API (gpt-4o-mini default)
- **Auth:** Email OTP only (no OAuth for MVP)
- **Output format:** XLSX with 2 sheets (Summary + Analysis) — conditional formatting, no PDF generation
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
| Monolith → apps + packages split | Clearer boundaries, independent deployment possible | ✓ Good |
| Unified 2-sheet output over 4 modes | Modes were presentation filters, not generation variants. Carrier=Internal, Litigation=Internal minus follow-ups. Simpler UX, same LLM cost. | — Pending |

## Tech Debt

| Item | Severity | Notes |
|------|----------|-------|
| `POST /render/upload-url` unauthenticated | Low | Works, but any client can request URLs |
| `datetime.utcnow()` deprecated | Low | Python 3.12+ compatibility warning |
| JWT_SECRET has default value | Low | Should enforce in production |

---
*Last updated: 2026-02-18 after v2.1 milestone completion*
