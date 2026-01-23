# VIP30

## What This Is

A SaaS application for insurance adjusters to compare Xactimate bid estimates. Users upload two PDF estimates, the system parses them, compares line items, and generates an XLSX report with narrative analysis explaining the differences.

## Core Value

Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report.

## Current Milestone: v1.0 Professional Adjuster Narratives

**Goal:** Produce bid comparison narratives that read like professional adjuster reports using a three-pass pipeline with quality gating.

**Target features:**
- Structured analysis pass extracts deltas with line-item detail
- Style-controlled writer pass generates adjuster-tone narratives
- Conditional compliance rewrite only when quality fails
- Quality gate enforces measurable criteria

## Requirements

### Validated

- ✓ Xactimate PDF parsing extracts structured data — existing
- ✓ Job queue processes long-running tasks asynchronously — existing
- ✓ Presigned URL pattern for secure file upload/download — existing
- ✓ XLSX report generation with comparison data — existing
- ✓ LLM-powered narrative generation for bid differences — existing
- ✓ Frontend upload flow with job polling — existing

### Active

- [ ] Analysis pass: structured extraction of category deltas with supporting line items
- [ ] Writer pass: style-controlled generation using adjuster tone reference
- [ ] Quality gate: hedging threshold (≤3 soft qualifiers)
- [ ] Quality gate: trade verbosity (≤2 sentences, avg ≤40 words)
- [ ] Quality gate: valuation link (every trade ties to financial impact)
- [ ] Quality gate: summary length (bullets ≤30 words, ≤6 total)
- [ ] Quality gate: analyst tone detection (no "suggests", "appears", "may indicate")
- [ ] Compliance rewrite: triggered only when quality checks fail

### Out of Scope

- Multi-tenant user management — focus on core comparison first
- Additional document types beyond Xactimate — scope to known format

## Context

Brownfield codebase with functional bid comparison. Turborepo monorepo with Next.js frontend (`apps/vipclaims-saas`), FastAPI backend (`apps/vip-parse`), and RQ worker for async processing. Deployed to Render with auto-deploy on push.

**Adjuster tone reference** (v1.0 milestone):
- Direct, no hedging — "Large Delta on Estimate cost to Mitigate" not "There appears to be a significant difference"
- Industry shorthand — PWI, MEP, ELE, PNT, SF used naturally
- Specific callouts — quantities, timeframes, unit numbers
- Action items embedded — "Need MEP Plans and ELE estimate"
- Comparative framing — "Farmers allowed for... Apex estimate includes..."
- Replacement vocabulary — "fails to include", "does not contemplate", "drives the variance"

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
*Last updated: 2026-01-18 after v1.0 milestone start*
