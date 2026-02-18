# Project Milestones: VIP30

## v2.2 Unified Output (Shipped: 2026-02-18)

**Delivered:** Single unified 2-sheet XLSX report replacing 4 output modes. Simpler UX with no mode selection.

**Phases completed:** 16-17 (executed directly)

**Key accomplishments:**
- XLSX restructured from 6 sheets to 2: "Summary" + "Analysis"
- `OutputMode` enum, `OutputModeFilter` class, and `output_modes.py` deleted
- Mode selector removed from frontend bid comp page
- `output_mode` removed from API `CreateJobRequest`
- Worker backward-compatible (ignores mode param from queued jobs)
- DB column made nullable, historical values preserved

**Stats:**
- 11 files changed
- 235 insertions, 450 deletions (net reduction)
- 2 phases
- Same day

**Git range:** `1582e01` → `3264734`

**What's next:** TBD — discuss next milestone

---

## v2.1 Repository Restructure (Shipped: 2026-02-18)

**Delivered:** Clean repository structure with monolith split into separate apps and packages, proper service naming on Render.

**Phases completed:** 13-15 (2 formal plans + direct execution)

**Key accomplishments:**
- Extracted `packages/parser/` as standalone Python package (10 modules, zero business logic deps)
- Extracted `packages/shared-python/` with 46 modules (bid_comp, pipeline, rules, methodology, etc.)
- Split `apps/vip-parse/` monolith into `apps/api/` (FastAPI) and `apps/worker/` (RQ)
- Renamed `apps/vipclaims-saas/` to `apps/frontend/`
- Updated render.yaml with correct service names (vip30-api, vip30-frontend, vip30-worker)
- Removed dead preflight code

**Stats:**
- 191 files created/modified
- 1,691 insertions, 1,391 deletions
- 3 phases, 2 plans
- 1 day from start to ship

**Git range:** `ec35399` → `4a1f829`

**What's next:** v2.2 — Unified 2-sheet output, remove output mode system

---

## v2.0 Analytical Intelligence (Shipped: 2026-02-17)

**Delivered:** Full analytical intelligence layer with methodology analysis, rules engine, quality gates, and output modes.

**Phases completed:** 9-12 (8 plans total)

**Key accomplishments:**
- Methodology analysis (O&P, depreciation, scope alignment, data provenance)
- Rules engine with 3 severity tiers, 6 alert types, structural pattern detection
- 5 quality gates (hedge, judgment, quantification, evidence grounding, methodology neutrality)
- 4 output modes (executive, carrier, litigation, internal)
- Enhanced multi-sheet XLSX with conditional formatting and audit trail

**Stats:**
- 4 phases, 8 plans
- 1 day from start to ship

**Git range:** `0e4ef27` → `2597518`

**What's next:** v2.1 — Repository restructure

---

## v1.2 Launch Ready (Shipped: 2026-02-17)

**Delivered:** Launch-ready product with enterprise B2B landing page, trust elements, polished app experience, and production observability.

**Phases completed:** 5-8 (6 plans total)

**Key accomplishments:**
- Landing page redesigned with Xactimate-focused B2B messaging and enterprise aesthetic
- Trust footer with Privacy Policy, Terms of Service, and Security pages
- User dropdown component with session persistence via localStorage
- Credit balance display with visual states in Bid Comp UI
- Structured JSON logging with request ID middleware
- Health endpoints for Render monitoring

**Stats:**
- 42 files created/modified
- 2,932 lines TypeScript, 35,261 lines Python
- 4 phases, 6 plans
- 1 day from start to ship

**Git range:** `5751cc9` → `c4e4fab`

**Tech debt incurred:**
- DESIGN-05: Using placeholder screenshots (replace before launch)
- Build verification: Local `.next` permission issue needs CI/deploy verification

**What's next:** v2 — pricing page, demo video, date filtering

---

## v1.1 MVP Launch (Shipped: 2026-02-14)

**Delivered:** Production-ready customer validation loop with email OTP auth, credit-based usage tracking, job state machine, and complete frontend experience.

**Phases completed:** 1-4 (8 plans total)

**Key accomplishments:**
- PostgreSQL database with workspace-scoped schema (users, workspaces, jobs, credits)
- Email OTP authentication with rate limiting, JWT cookies, and automatic workspace creation
- Job state machine (queued → parsing → analyzing → writing → completed|failed) with progress tracking
- Ledger-style credit system with idempotent consumption on job success only
- Complete frontend auth flow (/login → OTP verify → cookie-based sessions)
- Job progress and history UI with real-time polling and pagination

**Stats:**
- 51 files created/modified
- 9,319 lines of Python, 1,907 lines TypeScript
- 4 phases, 8 plans
- 2 days from start to ship

**Git range:** `7f4df34` → `de0007f`

**What's next:** v1.2 — date filtering, internal naming cleanup, production hardening

---

## v1.0.1 Professional Adjuster Narratives (Shipped: 2026-02-09)

**Delivered:** Three-pass LLM pipeline with quality gating that produces professional adjuster-tone narratives from bid comparison data.

**Phases completed:** 1-8 (8 plans total)

**Key accomplishments:**
- Three-pass LLM pipeline (Analysis → Writer → Compliance) reducing token count from 100k+ to ~5-10k
- Deterministic quality gates: 6 measurable checks (hedging, verbosity, valuation links, summary length, analyst tone, GPT-isms)
- Adjuster tone control via few-shot examples from real memos + terminology glossary
- Pass-level Redis caching with content-hash keys (1hr analysis, 30min writer TTL)
- Production integration into BidComp with legacy fallback preserved
- Regression fixes: numeric key_driver values, two-sentence narratives, expanded overview structure

**Stats:**
- 68 files created/modified
- 2,591 lines of Python (pipeline module)
- 8 phases, 8 plans
- 5 days from start to ship

**Git range:** `cab57c1` → `3233fbd`

**What's next:** TBD — discuss next milestone goals

---
