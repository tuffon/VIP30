# Roadmap: v1.0 Professional Adjuster Narratives

**Milestone:** v1.0 Professional Adjuster Narratives
**Created:** 2026-01-18
**Phases:** 8

## Overview

Transform bid comparison narrative output from generic AI-sounding text to professional adjuster memo tone using a three-pass LLM pipeline (Analysis → Writer → Conditional Compliance Rewrite) with deterministic quality gating.

## Phases

### Phase 1: Data Contracts
**Goal:** Define Pydantic models for all pipeline data structures

Foundation phase establishing typed contracts between pipeline passes. All subsequent phases depend on these data structures.

**Requirements covered:**
- DATA-01: Pydantic models define pass outputs (AnalysisResult, DraftNarrative, FinalNarrative)
- DATA-02: Schema validation ensures pass outputs conform before forwarding

**Success criteria:**
- [ ] AnalysisResult model defined with category_analyses, scope_gaps, confidence fields
- [ ] DraftNarrative model defined with overview, key_drivers, scope_observations fields
- [ ] FinalNarrative model defined (extends DraftNarrative with quality_report)
- [ ] PipelineState container holds all intermediate results
- [ ] QualityReport model captures gate results
- [ ] All models have unit tests for validation

---

### Phase 2: Quality Gates (Deterministic)
**Goal:** Implement measurable quality checks that run without LLM calls

Build deterministic validators that provide pass/fail signals for the conditional compliance rewrite decision.

**Requirements covered:**
- GATE-01: Hedging threshold check (≤3 soft qualifiers per section)
- GATE-02: Trade verbosity check (≤2 sentences per trade, avg ≤40 words)
- GATE-03: Valuation link check (every trade ties to dollar amount or delta)
- GATE-04: Summary length check (bullets ≤30 words, ≤6 total bullets)

**Success criteria:**
- [ ] HedgingChecker counts hedge words (may, might, appears, suggests, etc.)
- [ ] VerbosityChecker validates sentence count and word averages using textstat
- [ ] ValuationLinkChecker detects dollar amounts or delta references via regex
- [ ] SummaryLengthChecker validates bullet constraints
- [ ] QualityEvaluator aggregates all checks into QualityReport
- [ ] Tests with known-passing and known-failing narrative samples

---

### Phase 3: Quality Gates (Pattern-Based)
**Goal:** Implement pattern detection for analyst tone and GPT-isms

Extend quality checking with banned phrase detection to catch AI-sounding language.

**Requirements covered:**
- GATE-05: Analyst tone detection (ban "suggests", "appears", "may indicate", "likely due to")
- GATE-06: Slop/GPT-ism detection (ban "it's worth noting", "delve", "comprehensive", etc.)

**Success criteria:**
- [ ] AnalystToneChecker detects hedging phrases specific to analyst writing
- [ ] SlopChecker detects GPT-ism phrases (tapestry, delve, it's worth noting, etc.)
- [ ] Both checkers integrated into QualityEvaluator
- [ ] Banned phrase lists configurable via settings
- [ ] Tests with real LLM output samples showing detection accuracy

---

### Phase 4: Analysis Pass
**Goal:** Implement first LLM pass for structured delta extraction

Create the analysis pass that extracts structured comparison data from raw estimates, reducing token count from 100k+ to ~5-10k.

**Requirements covered:**
- PIPE-01: Analysis pass extracts structured category deltas with supporting line items

**Success criteria:**
- [ ] analysis_pass_v1 prompt template created in TemplateRegistry
- [ ] Line item sampling logic reduces token count (top 5 items per category by amount)
- [ ] run_analysis_pass() function returns validated AnalysisResult
- [ ] Handles empty categories, missing data gracefully
- [ ] Integration test with real estimate pairs

---

### Phase 5: Writer Pass
**Goal:** Implement second LLM pass with adjuster tone control

Create the writer pass that transforms structured analysis into professional adjuster narratives using few-shot examples and terminology glossary.

**Requirements covered:**
- PIPE-02: Writer pass generates adjuster-tone narratives from analysis output
- STYLE-01: Writer pass includes 3-5 real adjuster memo examples (few-shot)
- STYLE-02: Terminology glossary injected into writer prompt (PWI, MEP, ELE, PNT, SF, O&P)

**Success criteria:**
- [ ] writer_pass_v1 prompt template with adjuster memo examples
- [ ] Terminology glossary (PWI, MEP, ELE, PNT, SF, O&P) injected into system prompt
- [ ] 3-5 real adjuster memo excerpts as few-shot examples
- [ ] run_writer_pass() function returns validated DraftNarrative
- [ ] Output matches adjuster tone characteristics (short, declarative, numbers present)
- [ ] Integration test: analysis → writer flow

---

### Phase 6: Pipeline Orchestration
**Goal:** Wire passes together with conditional compliance rewrite

Create NarrativePipeline orchestrator that runs passes in sequence and triggers compliance rewrite only when quality gates fail.

**Requirements covered:**
- PIPE-03: Compliance rewrite pass triggers only when quality gates fail

**Success criteria:**
- [ ] NarrativePipeline class orchestrates pass sequence
- [ ] Quality gates run after writer pass
- [ ] Compliance rewrite skipped when quality passes (logged as compliance_skipped)
- [ ] Compliance rewrite triggered when quality fails
- [ ] compliance_rewrite_v1 prompt template with failed checks injection
- [ ] Max 2 rewrite iterations (prevent infinite loops)
- [ ] Error handling with fallbacks per pass
- [ ] Timing and logging per pass
- [ ] End-to-end integration test

---

### Phase 7: Caching & Integration
**Goal:** Add Redis caching and integrate pipeline into BidComp

Complete the pipeline with pass-level caching and production integration.

**Requirements covered:**
- PIPE-04: Pass-level caching via Redis avoids redundant LLM calls

**Success criteria:**
- [ ] PipelineCache wrapper for Redis with TTL support
- [ ] Analysis pass cached (1 hour TTL) - same estimates produce same analysis
- [ ] Writer pass cached (30 min TTL) - same analysis + style = same draft
- [ ] Compliance pass NOT cached (quality gates may change)
- [ ] Cache keys based on content hash of inputs
- [ ] BidComp._generate_narrative replaced with NarrativePipeline.run()
- [ ] End-to-end test through RQ worker
- [ ] Performance comparison: single-pass vs multi-pass latency

---

### Phase 8: Narrative Regression Fixes
**Goal:** Fix regressions in narrative output where category delta values are missing and narrative quality needs improvement

Addresses issues discovered during v1.0 testing:
- Missing numeric values in key drivers (primary_total, comparison_total, delta)
- Narrative structure needs two sentences (delta assessment + cause analysis)
- Overview too brief (needs 2-3 sentences on delta, causes, reasoning)
- Estimate ID names need consistent display

**Requirements covered:**
- REGR-01: Key drivers display numeric values for Primary, Comparison, and Delta
- REGR-02: Driver narratives have two sentences (delta + cause)
- REGR-03: Overview has 2-3 sentences with cause analysis
- REGR-04: Estimate names prominently displayed

**Success criteria:**
- [ ] Key drivers show Primary value, Comparison value, and Delta (all numeric)
- [ ] Each driver narrative has two sentences (delta assessment + cause assessment)
- [ ] Overview is 2-3 sentences with delta direction, primary causes, and reasoning
- [ ] Estimate names are prominently displayed and used in comparative framing
- [ ] All existing tests continue to pass

---

## Dependency Graph

```
Phase 1 (Data Contracts)
    ↓
Phase 2 (Deterministic Gates) ← Phase 3 (Pattern Gates)
    ↓
Phase 4 (Analysis Pass)
    ↓
Phase 5 (Writer Pass)
    ↓
Phase 6 (Pipeline Orchestration)
    ↓
Phase 7 (Caching & Integration)
    ↓
Phase 8 (Narrative Regression Fixes)
```

## Requirement Coverage

| Requirement | Phase | Description |
|-------------|-------|-------------|
| DATA-01 | 1 | Pydantic models for pass outputs |
| DATA-02 | 1 | Schema validation for pass outputs |
| GATE-01 | 2 | Hedging threshold (≤3) |
| GATE-02 | 2 | Trade verbosity (≤2 sentences, ≤40 words) |
| GATE-03 | 2 | Valuation link check |
| GATE-04 | 2 | Summary length (≤30 words, ≤6 bullets) |
| GATE-05 | 3 | Analyst tone detection |
| GATE-06 | 3 | Slop/GPT-ism detection |
| PIPE-01 | 4 | Analysis pass extracts deltas |
| PIPE-02 | 5 | Writer pass generates narratives |
| STYLE-01 | 5 | Few-shot adjuster examples |
| STYLE-02 | 5 | Terminology glossary |
| PIPE-03 | 6 | Conditional compliance rewrite |
| PIPE-04 | 7 | Redis pass-level caching |
| REGR-01 | 8 | Key drivers display numeric values |
| REGR-02 | 8 | Driver narratives have two sentences |
| REGR-03 | 8 | Overview has 2-3 sentences with cause analysis |
| REGR-04 | 8 | Estimate names prominently displayed |

**Coverage:** 18/18 requirements mapped (100%)

---

*Roadmap created: 2026-01-18*
*Based on: ARCHITECTURE.md build order, FEATURES.md recommendations, STACK.md tooling*
