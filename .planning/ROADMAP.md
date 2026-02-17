# Roadmap: VIP30

## Milestones

- ✅ **v1.0.1 Professional Adjuster Narratives** - Phases 1-8 (shipped 2026-02-09)
- ✅ **v1.1 MVP Launch** - Phases 1-4 (shipped 2026-02-14)
- ✅ **v1.2 Launch Ready** - Phases 5-8 (shipped 2026-02-17)
- 🚧 **v2.0 Analytical Intelligence** - Phases 9-12 (in progress)

## Phases

- [x] **Phase 9: Data Foundation & Methodology** - Line-item comparison, O&P/depreciation detection, scope alignment, data provenance
- [ ] **Phase 10: Rules Engine & Intelligence** - Emphasis flags, alert tags, ranked impact, pattern detection, diagnostic follow-ups
  - Plans: 10-01 (models + engine, Wave 1), 10-02 (pipeline integration, Wave 2)
- [ ] **Phase 11: Narrative Quality & Quality Gates** - Evidence-based narratives, neutral tone, expanded quality gate system
- [ ] **Phase 12: Output Modes & Enhanced XLSX** - Four audience modes, multi-sheet XLSX, conditional formatting, audit trail
  - Plans: 12-01 (mode model + filter + XLSX rewrite, Wave 1), 12-02 (full stack wiring + frontend, Wave 2)

## Phase Details

### 🚧 v2.0 Analytical Intelligence

**Milestone Goal:** Transform output from spreadsheet-heavy comparison to structured signal extraction with defensible framing — executive-ready, carrier-ready, litigation-ready reports.

### Phase 9: Data Foundation & Methodology
**Goal**: Reliable data extraction with methodology comparison and evidence provenance tracking
**Depends on**: v1.2 (existing pipeline)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, INTL-01
**Success Criteria** (what must be TRUE):
  1. System matches line items between two estimates by Xactimate activity code or description similarity
  2. O&P structure detected and compared between estimates (general O&P, per-line O&P, inclusion/exclusion)
  3. Depreciation methodology detected and compared (ACV vs RCV, percentage vs amount)
  4. Scope alignment matrix shows items present in one estimate but absent from the other
  5. Every analytical claim tracks data provenance — granularity field prevents fabricated evidence
**Research**: Likely (line-item matching algorithm, O&P/depreciation extraction depth from Xactimate PDFs)
**Research topics**: Line-item matching strategy (fuzzy vs activity codes), O&P parameter extraction from PDF output, OpenAI Structured Outputs migration
**Plans**: 09-01 (models + analyzers, Wave 1), 09-02 (integration + structured outputs, Wave 2)

### Phase 10: Rules Engine & Intelligence
**Goal**: Automated emphasis, alerting, pattern detection, and diagnostic follow-ups
**Depends on**: Phase 9 (MethodologyResult + category data)
**Requirements**: INTL-02, INTL-03, INTL-04, INTL-05
**Success Criteria** (what must be TRUE):
  1. Ranked impact table produced with categories sorted by delta magnitude and % of total variance
  2. Top variance drivers (top 20%) flagged with exactly 3 severity tiers (critical/notable/informational)
  3. Alert tags fire for missing O&P, scope imbalance, depreciation mismatches, large unspecified categories
  4. Structural patterns detected (partial vs full restoration, systematic pricing differences)
  5. Diagnostic follow-ups generated for each flagged variance (actionable next steps, not recommendations)
**Research**: Unlikely (pure Python rules engine, established patterns)
**Plans**: 10-01 (models + engine, Wave 1), 10-02 (pipeline integration, Wave 2)

### Phase 11: Narrative Quality & Quality Gates
**Goal**: Evidence-based, neutral-tone narratives with expanded quality gate system
**Depends on**: Phase 10 (SignalBundle feeds into LLM pipeline)
**Requirements**: NARR-01, NARR-02, NARR-03, GATE-01, GATE-02, GATE-03, GATE-04, GATE-05
**Success Criteria** (what must be TRUE):
  1. All narratives contain dollar amounts and percentages for every referenced delta
  2. Zero hedge words or judgment adjectives appear in any output
  3. Every factual claim in narrative traces to specific line items, quantities, or calculations in source data
  4. Five quality gates operational: hedge detection, judgment language, quantification enforcement, evidence grounding, methodology neutrality
**Research**: Done (11-RESEARCH.md — gate designs, word lists, patterns)
**Plans**: 11-01 (word lists + gate checkers, Wave 1), 11-02 (prompts + pipeline integration, Wave 2)

### Phase 12: Output Modes & Enhanced XLSX
**Goal**: Four audience-specific output modes with enhanced multi-sheet XLSX and audit trail
**Depends on**: Phase 11 (full enriched PipelineState)
**Requirements**: MODE-01, MODE-02, MODE-03, MODE-04, XLSX-01, XLSX-02, XLSX-03, XLSX-04
**Success Criteria** (what must be TRUE):
  1. User can select output mode (Executive/Carrier/Litigation/Internal) before job submission
  2. Executive mode produces 1-page compressed view with total delta, top 3 drivers, and structural flags
  3. All four modes produce identical analytical findings — modes filter content and adjust tone only
  4. XLSX has conditional formatting, multi-sheet structure, and self-contained executive summary sheet
  5. Output includes audit trail metadata (comparison parameters, timestamps, input file hashes)
**Research**: Unlikely (openpyxl conditional formatting documented, internal wiring)
**Plans**: 12-01 (mode model + filter + XLSX rewrite, Wave 1), 12-02 (full stack wiring + frontend, Wave 2)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 9. Data Foundation & Methodology | 2/2 | Completed | 2026-02-17 |
| 10. Rules Engine & Intelligence | 0/2 | Planned | - |
| 11. Narrative Quality & Quality Gates | 0/2 | Planned | - |
| 12. Output Modes & Enhanced XLSX | 0/2 | Planned | - |

---
*Last updated: 2026-02-17 — Phase 12 planned (2 plans in 2 waves)*
