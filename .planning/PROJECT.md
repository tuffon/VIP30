# VIP30

## What This Is

A SaaS application for insurance adjusters to compare Xactimate bid estimates. Users upload two PDF estimates, the system parses them, compares line items, and generates an XLSX report with professional adjuster-tone narrative analysis explaining the differences.

## Core Value

Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report with professional-quality narratives.

## Current State

**Version:** v1.0.1 shipped 2026-02-09

**Shipped features:**
- Three-pass LLM pipeline (Analysis → Writer → Compliance rewrite)
- 6 deterministic quality gates (hedging, verbosity, valuation links, summary length, analyst tone, GPT-isms)
- Adjuster tone control via few-shot examples + terminology glossary
- Pass-level Redis caching with content-hash keys
- Production integration in BidComp with legacy fallback

**Tech stack:** Turborepo monorepo, Next.js frontend, FastAPI backend, RQ worker, Redis caching

## Requirements

### Validated

- ✓ Xactimate PDF parsing extracts structured data — existing
- ✓ Job queue processes long-running tasks asynchronously — existing
- ✓ Presigned URL pattern for secure file upload/download — existing
- ✓ XLSX report generation with comparison data — existing
- ✓ LLM-powered narrative generation for bid differences — existing
- ✓ Frontend upload flow with job polling — existing
- ✓ Analysis pass: structured extraction of category deltas with supporting line items — v1.0.1
- ✓ Writer pass: style-controlled generation using adjuster tone reference — v1.0.1
- ✓ Quality gate: hedging threshold (≤3 soft qualifiers) — v1.0.1
- ✓ Quality gate: trade verbosity (≤2 sentences, avg ≤40 words) — v1.0.1
- ✓ Quality gate: valuation link (every trade ties to financial impact) — v1.0.1
- ✓ Quality gate: summary length (bullets ≤30 words, ≤6 total) — v1.0.1
- ✓ Quality gate: analyst tone detection (no "suggests", "appears", "may indicate") — v1.0.1
- ✓ Compliance rewrite: triggered only when quality checks fail — v1.0.1
- ✓ Pass-level Redis caching to avoid redundant LLM calls — v1.0.1
- ✓ Key drivers display numeric values (Primary, Comparison, Delta) — v1.0.1
- ✓ Driver narratives have two sentences (delta + cause) — v1.0.1
- ✓ Overview has 2-3 sentences with cause analysis — v1.0.1
- ✓ Estimate names used in comparative framing — v1.0.1

### Active

(None — planning next milestone)

### Out of Scope

- Multi-tenant user management — focus on core comparison first
- Additional document types beyond Xactimate — scope to known format
- Fine-tuning — premature optimization; few-shot sufficient
- G-Eval tone scoring — deferred to v2

## Context

Brownfield codebase with functional bid comparison. Turborepo monorepo with Next.js frontend (`apps/vipclaims-saas`), FastAPI backend (`apps/vip-parse`), and RQ worker for async processing. Deployed to Render with auto-deploy on push.

**v1.0.1 shipped:** Professional adjuster narratives via three-pass LLM pipeline with quality gating. 2,591 LOC Python in pipeline module.

## Constraints

- **Deployment:** Render.com — frontend, API, worker, Redis all managed there
- **Storage:** Cloudflare R2 via S3-compatible API
- **LLM:** OpenAI API (gpt-4o-mini default)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Xactimate-only parsing | Known format, proven parser exists | ✓ Good |
| RQ for job queue | Simple Redis-based queue, fits Render deployment | ✓ Good |
| XLSX output format | Industry standard, adjusters expect spreadsheets | ✓ Good |
| Three-pass LLM pipeline | Separation of concerns, token reduction, style control | ✓ Good |
| Pydantic v2 data contracts | Type safety, validation, serialization | ✓ Good |
| textstat for NLP metrics | Accurate sentence/word counting | ✓ Good |
| Whole-word regex for single terms | Avoids false positives in pattern matching | ✓ Good |
| Max 2 compliance rewrite iterations | Prevents infinite loops, acceptable quality | ✓ Good |
| Content-hash cache keys | Deterministic, input-based caching | ✓ Good |
| Case-insensitive category matching | Robust to LLM output variation | ✓ Good |

---
*Last updated: 2026-02-09 after v1.0.1 milestone*
