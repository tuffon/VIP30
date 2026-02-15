# Project Milestones: VIP30

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
