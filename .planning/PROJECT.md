# VIP30

## What This Is

A SaaS application for insurance adjusters to compare Xactimate bid estimates. Users upload two PDF estimates, the system parses them, compares line items, and generates an XLSX report with narrative analysis explaining the differences.

## Core Value

Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report.

## Requirements

### Validated

- ✓ Xactimate PDF parsing extracts structured data — existing
- ✓ Job queue processes long-running tasks asynchronously — existing
- ✓ Presigned URL pattern for secure file upload/download — existing
- ✓ XLSX report generation with comparison data — existing
- ✓ LLM-powered narrative generation for bid differences — existing
- ✓ Frontend upload flow with job polling — existing

### Active

- [ ] Frontend uses environment variable for backend URL (not hardcoded localhost)
- [ ] End-to-end flow works in production deployment
- [ ] Output format is consistent and reliable
- [ ] Narrative structure is clear and useful

### Out of Scope

- Multi-tenant user management — focus on core comparison first
- Additional document types beyond Xactimate — scope to known format

## Context

Brownfield codebase with functional bid comparison locally. Turborepo monorepo with Next.js frontend (`apps/vipclaims-saas`), FastAPI backend (`apps/vip-parse`), and RQ worker for async processing. Deployed to Render with auto-deploy on push.

Current blocker: frontend hardcoded to localhost prevents production testing. Once fixed, can validate full flow and identify output quality issues.

## Constraints

- **Deployment:** Render.com — frontend, API, worker, Redis all managed there
- **Storage:** Cloudflare R2 via S3-compatible API
- **LLM:** OpenAI API (gpt-4o-mini default)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Xactimate-only parsing | Known format, proven parser exists | ✓ Good |
| RQ for job queue | Simple Redis-based queue, fits Render deployment | ✓ Good |
| XLSX output format | Industry standard, adjusters expect spreadsheets | — Pending |

---
*Last updated: 2026-01-15 after initialization*
