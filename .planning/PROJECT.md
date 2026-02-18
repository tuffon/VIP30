# VIP30

## What This Is

A SaaS application for insurance adjusters to compare Xactimate bid estimates. Users upload two PDF estimates, the system parses them, compares line items, and generates a unified 2-sheet XLSX report with professional adjuster-tone narrative analysis explaining the differences. Includes user authentication, credit-based usage tracking, and job progress visibility.

## Core Value

Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report with professional-quality narratives.

## Current State

**Version:** v2.2 shipped 2026-02-18

**Shipped features (v2.2):**
- Unified 2-sheet XLSX output: "Summary" + "Analysis" (replaces 6 sheets and 4 modes)
- OutputMode system removed (enum, filter class, pipeline passthrough, frontend selector)
- Simplified UX: upload and submit, no mode selection

**Shipped features (v2.1):**
- Repository restructured: monolith split into `apps/api/`, `apps/worker/`, `apps/frontend/`
- Standalone packages: `packages/parser/` (10 modules), `packages/shared-python/` (46 modules)
- Render services properly named: vip30-api, vip30-frontend, vip30-worker

**Shipped features (v2.0):**
- Methodology analysis (O&P, depreciation, scope alignment, data provenance)
- Rules engine with 3 severity tiers, 6 alert types, structural pattern detection
- 5 quality gates (hedge, judgment, quantification, evidence grounding, methodology neutrality)

**Shipped features (v1.2):**
- Enterprise B2B landing page with Xactimate-focused messaging
- Trust footer with Privacy Policy, Terms of Service, and Security pages
- User dropdown, credit balance display, structured logging, health endpoints

**Shipped features (v1.1):**
- PostgreSQL database with workspace-scoped schema
- Email OTP authentication with rate limiting and JWT cookies
- Job state machine, ledger-style credits, real-time polling, history UI

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
- ✓ Monolith split into apps/api + apps/worker — v2.1
- ✓ Standalone parser and shared-python packages — v2.1
- ✓ Frontend renamed from vipclaims-saas — v2.1
- ✓ Render services properly named and configured — v2.1
- ✓ All Python imports resolve with new package structure — v2.1
- ✓ Unified 2-sheet XLSX output (Summary + Analysis) — v2.2
- ✓ OutputMode system removed (enum, filter, pipeline, frontend) — v2.2
- ✓ No mode selection in UX — v2.2
- ✓ LLM pipeline unchanged, all content flows to output — v2.2

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
| Unified 2-sheet output over 4 modes | Modes were presentation filters, not generation variants. Simpler UX, same LLM cost. | ✓ Good |

## Tech Debt

| Item | Severity | Notes |
|------|----------|-------|
| `POST /render/upload-url` unauthenticated | Low | Works, but any client can request URLs |
| `datetime.utcnow()` deprecated | Low | Python 3.12+ compatibility warning |
| JWT_SECRET has default value | Low | Should enforce in production |
| `output_mode` DB column still exists | Low | Nullable, not written — preserves historical data |

---
*Last updated: 2026-02-18 after v2.2 milestone completion*
