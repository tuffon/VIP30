# VIP30

## What This Is

A SaaS application for insurance adjusters to compare Xactimate bid estimates. Users upload two PDF estimates, the system parses them, compares line items, and generates an XLSX report with professional adjuster-tone narrative analysis explaining the differences.

## Core Value

Reliable end-to-end bid comparison that produces actionable output — users upload PDFs and get a useful comparison report with professional-quality narratives.

## Current Milestone: v1.1 MVP Launch

**Goal:** Production-ready customer validation loop with auth, credits, and progress visibility.

**Target features:**
- Database setup (PostgreSQL on Render)
- Workspace model (users + credits belong to workspace, MVP = 1 user per workspace)
- Email OTP auth (one-time code, store login metadata)
- Credit system (ledger-style: credit_grants + credit_consumptions, only charge on success)
- Job state machine (queued → parsing → analyzing → writing → completed | failed)
- Clear failure handling (messaging, retry without double-charge)
- Internal naming cleanup (vip_job → comparison_job, raw_upload → bid_input)
- Rebrand to bid comparison tool
- [Stretch] Narrative enhancement (more verbose with verbosity budget guardrail)

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

- [ ] PostgreSQL database on Render for persistence
- [ ] Workspace model: users belong to workspace, credits belong to workspace
- [ ] Email OTP authentication (one-time code, not magic links)
- [ ] Login metadata: last_login_at, login_ip, login_method
- [ ] credit_grants table: source, amount, timestamp
- [ ] credit_consumptions table: job_id, amount, success, timestamp
- [ ] Configurable default credits (5 early adopters, 3 later)
- [ ] Credits only consumed on successful completion
- [ ] Job state machine: queued, parsing, analyzing, writing, completed, failed
- [ ] Job progress fields: current_state, percent/step_index, error_reason
- [ ] Clear failure messaging with retry path
- [ ] Internal naming: comparison_job, bid_input (not vip_job, raw_upload)
- [ ] Frontend rebrand to bid comparison tool positioning
- [ ] [Stretch] Narrative verbosity enhancement with budget guardrail

### Out of Scope

- OAuth login (Google/Facebook) — post-MVP, start with email OTP
- Multi-user workspaces — MVP = 1 user per workspace, architecture supports expansion
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
*Last updated: 2026-02-13 after starting v1.1 MVP Launch milestone*
