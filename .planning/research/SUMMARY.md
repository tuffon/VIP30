# Project Research Summary

**Project:** VIP30 — v2.0 Analytical Intelligence
**Domain:** Insurance estimate comparison analytics
**Researched:** 2026-02-17
**Confidence:** HIGH (stack/architecture), MEDIUM (features/pitfalls)

## Executive Summary

VIP30 v2.0 adds analytical intelligence to a working bid comparison SaaS. The research reveals a clear architectural path: pre-LLM enrichment (methodology detection + rules engine) feeds into the existing 3-pass LLM pipeline, with post-LLM output mode filtering and enhanced XLSX export. The existing stack needs no new heavy dependencies — Pydantic structured outputs via the OpenAI SDK and openpyxl's untapped conditional formatting capabilities cover all v2.0 requirements.

The single most important finding across all research dimensions: **objectivity is the #1 requirement**. In insurance litigation, a report that takes sides — through hedge language, evaluative adjectives, fabricated evidence, or opinion-disguised-as-analysis — gets disqualified and destroys the user's credibility. Every architectural and implementation decision must serve defensibility first.

The highest-severity risk is **P-04: LLM fabricating line item evidence**. When the parser provides only category-level totals, the LLM will confabulate specific line items to sound authoritative. This must be solved at the data layer with provenance tracking before any intelligence or narrative features build on it.

## Key Findings

### Recommended Stack

Only one new dependency: explicit `pydantic>=2.10` (already installed via FastAPI). Upgrade `openai>=1.40` for Structured Outputs. Everything else builds on existing openpyxl 3.1.5.

**Core additions:**
- **OpenAI Structured Outputs** with Pydantic models — eliminates fragile manual JSON parsing, guarantees schema compliance
- **Custom Python rules engine** (dataclasses + pandas) — domain is ~20-50 rules on numeric data; third-party engines are abandoned or overkill
- **openpyxl conditional formatting** — CellIsRule, ColorScaleRule, DataBarRule already available but unused in current export code
- **Tone validation gates** — extend existing compliance pass with mode-specific prohibited/required term lists

**What NOT to use:** LangChain (abstraction overhead), Pydantic-AI (unnecessary wrapper), XlsxWriter (write-only, can't replace openpyxl), any third-party rules engine (abandoned or overkill).

### Expected Features

**Table stakes (must have or users lose trust):**
- Line-item level comparison (TS-1) — foundation for everything
- Quantified differences, not adjectives (TS-2) — credibility requirement
- O&P detection and comparison (TS-5) — most disputed element in estimates
- Depreciation methodology comparison (TS-6) — fundamental axis of disputes
- Scope alignment matrix (TS-4) — highest-signal finding for users
- Neutral, evidence-based language (TS-7) — litigation readiness
- Source attribution for every claim (TS-8) — every assertion must trace to data

**Differentiators (competitive advantage):**
- Methodology analysis block (D-1) — KEY differentiator; no competitor explains WHY estimates differ structurally
- Rules engine with emphasis flags (D-3) — automated expert-level flagging
- Multi-mode output (D-4) — same data, 4 audience-specific presentations
- Ranked impact table (D-2) — "where does the money live?" answered instantly

**Anti-features (must NOT build):**
- "Which estimate is better" verdicts — makes tool an advocate, disqualifiable
- Recommendation language ("you should...") — creates liability
- Emotional terminology ("lowballed", "inflated") — destroys neutrality
- Confidence scores — false precision, indefensible methodology
- Side-picking output modes — if discovered in litigation, credibility collapses

### Architecture Approach

Pre-LLM enrichment → existing LLM pipeline → post-LLM mode filtering → enhanced XLSX export. Three new module directories (`src/methodology/`, `src/rules/`, `src/output_modes/`) produce typed Pydantic models consumed by the existing pipeline. The existing `PipelineState` extends with Optional fields — backwards compatible, incremental adoption.

**Key design decisions:**
1. Methodology and rules run as pure Python BEFORE the LLM — deterministic, zero token cost, auditable
2. Output modes are post-LLM content filters on the same analysis — no 4x cost multiplication
3. New XLSX exporter (`export_xlsx_v2.py`) receives pre-filtered `ModeFilteredOutput` — clean interface, v1 fallback preserved
4. Every v2.0 addition is guarded by `if component else None` — existing pipeline continues working during incremental build

### Critical Pitfalls

1. **P-04: LLM fabricating evidence** (CRITICAL) — LLM invents line items when only category totals exist. Solve with data provenance tracking and granularity field on every analysis output.
2. **P-01: Hedge language leaking** — GPT-4o-mini defaults to epistemic hedging. Expand quality gate word list, add quantification enforcement gate.
3. **P-03: Subjective characterization** — evaluative adjectives ("excessive", "inadequate") disguised as analysis. Add judgment language gate.
4. **P-02: False emphasis hierarchy** — flagging too many items makes nothing important. Cap at 3-5 flags, use percentage-based thresholds.
5. **P-08: Output mode template proliferation** — each mode becoming a separate code path. Enforce single-pipeline-with-config-filters pattern.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Data Foundation & Methodology Detection
**Rationale:** Everything depends on reliable data extraction and methodology detection. Rules, narratives, and output modes all consume methodology results. Evidence grounding (P-04 prevention) must be solved here.
**Delivers:** MethodologyAnalyzer, data provenance tracking, PipelineState extension, OpenAI SDK migration for structured outputs
**Addresses:** TS-5 (O&P), TS-6 (depreciation), P-04, P-06, P-09 (data layer)
**Avoids:** P-04 (fabricated evidence), P-06 (inconsistent JSON)

### Phase 2: Rules Engine & Signal Extraction
**Rationale:** Consumes Phase 1 methodology output. Pure Python, independently testable. Produces the intelligence layer that narratives and export build on.
**Delivers:** RulesEngine with initial rule set, SignalBundle, emphasis flags, alert tags
**Addresses:** D-3 (rules engine), D-2 (ranked impact), TS-3 (total delta breakdown)
**Avoids:** P-02 (false hierarchy), P-05 (rigidity across claim types)

### Phase 3: Narrative Quality & Enhanced LLM Pipeline
**Rationale:** Threads Phase 1-2 outputs into the existing LLM pipeline. Enforces evidence-based reasoning, neutral tone, and quantification. This is where anti-features are actively prevented.
**Delivers:** Enhanced prompts, expanded quality gates (GATE-07 through GATE-10), mode-aware tone parameters
**Addresses:** TS-2 (quantified diffs), TS-7 (neutral language), TS-8 (source attribution), D-1 (methodology analysis narratives)
**Avoids:** P-01 (hedge language), P-03 (subjective characterization), P-09 (methodology opinion)

### Phase 4: Output Modes & Visual Hierarchy
**Rationale:** Requires full enriched pipeline state from Phase 3. Mode filter is pure Python. Executive snapshot requires classified variance types (not just magnitude ranking).
**Delivers:** OutputModeFilter (4 modes), executive snapshot with variance classification, scope alignment matrix
**Addresses:** D-4 (multi-mode), D-5 (executive snapshot), TS-4 (scope alignment), TS-10 (reproducibility)
**Avoids:** P-08 (template proliferation), P-10 (misleading simplicity)

### Phase 5: Enhanced XLSX Export
**Rationale:** Presentation layer — receives pre-filtered ModeFilteredOutput and renders multi-sheet XLSX. Must be designed for print and cross-platform compatibility.
**Delivers:** export_xlsx_v2.py with conditional formatting, multi-sheet structure, mode-specific sheet selection
**Addresses:** D-8 (enhanced XLSX), TS-9 (professional output), D-9 (audit trail)
**Avoids:** P-07 (information overload)

### Phase 6: API & Frontend Integration
**Rationale:** Backend must be complete before exposing mode selection. Minimal frontend change — dropdown for output mode.
**Delivers:** output_mode API parameter, frontend mode selector, end-to-end integration
**Addresses:** All features wired to user-facing interface

### Phase Ordering Rationale

- **Phases 1-2 can be parallelized** — they share no dependencies on each other (methodology reads EstimatePair, rules reads EstimatePair + MethodologyResult but can stub it)
- **Phase 3 requires both 1 and 2** — LLM pipeline needs methodology context AND signal emphasis
- **Phases 4-5-6 are sequential** — each consumes the output of the previous
- **Anti-features (AF-1 through AF-8) are prevented in Phase 3** via quality gates, not as a separate phase

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Line-item matching algorithm (fuzzy vs Xactimate activity codes) needs domain research
- **Phase 1:** O&P/depreciation extraction depth from PDF output needs feasibility validation
- **Phase 3:** Litigation tone calibration needs legal professional review before production

Phases with standard patterns (skip research-phase):
- **Phase 2:** Rules engine is pure Python pattern matching — well-understood
- **Phase 5:** XLSX generation with openpyxl — well-documented
- **Phase 6:** API parameter + frontend dropdown — straightforward

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Only 1 new dep; verified via PyPI/official docs |
| Features | MEDIUM | Table stakes verified via industry sources; differentiators synthesized from gap analysis |
| Architecture | HIGH | Derived from direct codebase analysis; clear dependency graph |
| Pitfalls | HIGH | Grounded in codebase analysis + domain knowledge; actionable prevention strategies |

**Overall confidence:** HIGH

### Gaps to Address

- **Line-item matching algorithm:** Fuzzy match vs Xactimate activity codes — needs domain expert input during Phase 1 planning
- **O&P extraction depth:** Can O&P parameters be reliably extracted from PDF output or only XML/ESX? Determines data completeness ceiling
- **Litigation tone legal review:** Prohibited/required term lists based on conventions, not verified against specific legal standard
- **Rule threshold calibration:** Initial values are educated guesses; need real comparison data for tuning
- **LLM reproducibility for litigation:** temperature=0 insufficient; may need template-driven output for litigation mode

## Competitor Context

- **LEVLR 3.0:** AI Xactimate comparison with color-coded line-item matching — shows WHAT differs but not WHY (VIP30's differentiator)
- **XactAnalysis QR:** Verisk's rules engine for single-estimate QA — not cross-estimate comparison
- **Manual comparison:** 2-3 hours per comparison, inconsistent, not scalable

## Sources

### Primary (HIGH confidence)
- Direct VIP30 codebase analysis (pipeline, export, quality gates, data models)
- OpenAI Structured Outputs documentation — Pydantic integration verified
- openpyxl 3.1.x official docs — conditional formatting, Table objects, NamedStyles
- Verisk/Xactimate documentation — O&P types, depreciation, QR rules engine

### Secondary (MEDIUM confidence)
- Expert witness report writing standards — neutral language requirements
- Insurance litigation credibility factors — Daubert standard, bias disqualification
- LEVLR 3.0 public materials — competitor feature analysis
- Alert fatigue research (IBM, Datadog) — threshold tuning patterns

### Tertiary (LOW confidence)
- Litigation tone patterns — based on legal writing conventions, needs professional review
- LLM structured output reliability — community reports, needs empirical measurement with VIP30 schemas

---
*Research completed: 2026-02-17*
*Ready for roadmap: yes*
