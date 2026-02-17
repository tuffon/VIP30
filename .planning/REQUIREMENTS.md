# Requirements: VIP30 v2.0 Analytical Intelligence

**Defined:** 2026-02-17
**Core Value:** Reliable end-to-end bid comparison that produces actionable output

## v2.0 Requirements

Requirements for v2.0 release. Each maps to roadmap phases.

### Data Foundation

- [x] **DATA-01**: System compares estimates at line-item level, matching items by Xactimate activity codes or description similarity
- [x] **DATA-02**: System detects O&P structure in each estimate (general O&P, per-line O&P, inclusion/exclusion)
- [x] **DATA-03**: System detects depreciation methodology in each estimate (ACV vs RCV, percentage vs amount)
- [x] **DATA-04**: System produces scope alignment matrix showing items present in one estimate but absent from the other
- [x] **DATA-05**: System calculates total delta with breakdown sorted by absolute magnitude
- [x] **DATA-06**: System produces consistent analytical findings for identical inputs (deterministic pre-LLM analysis, cached LLM results)
- [x] **DATA-07**: System tracks data provenance — every analytical claim links to specific parsed data, with granularity field preventing fabricated evidence

### Narrative Quality

- [x] **NARR-01**: All narratives use quantified differences (dollar amounts and percentages) instead of qualitative language
- [x] **NARR-02**: All narratives use neutral, observation-based language that withstands litigation scrutiny (zero hedge words, zero judgment adjectives)
- [x] **NARR-03**: Every factual claim in narrative output traces to specific line items, quantities, or calculations in source data

### Intelligence Layer

- [x] **INTL-01**: System produces methodology analysis block comparing O&P treatment, depreciation approach, unit pricing source, and locality factors
- [x] **INTL-02**: System produces ranked impact table with categories sorted by delta magnitude and percentage of total variance
- [x] **INTL-03**: Rules engine flags top variance drivers (top 20%), scope gaps, missing O&P, depreciation mismatches, and large unspecified categories with max 3 severity tiers
- [x] **INTL-04**: System detects structural patterns (partial vs full restoration, systematic pricing differences, code compliance omissions)
- [x] **INTL-05**: System generates diagnostic follow-ups tied to detected variances (actionable next steps, not recommendations)

### Output Modes

- [ ] **MODE-01**: System supports 4 output modes (Executive, Carrier Negotiation, Litigation, Internal Estimator) from the same underlying analysis
- [ ] **MODE-02**: Executive mode produces 1-page compressed view with total delta, top 3 drivers, and structural flags
- [ ] **MODE-03**: All modes share identical analytical findings — modes filter content and adjust tone, never change conclusions
- [ ] **MODE-04**: Litigation mode enforces strictest neutral tone with zero hedge words and full evidence citations

### Visual Hierarchy

- [ ] **XLSX-01**: Enhanced XLSX with conditional formatting (color scales for variance, data bars for impact, colored fills for flags)
- [ ] **XLSX-02**: Multi-sheet structure: Executive Summary, Ranked Impact, Methodology, Scope Alignment, Category Detail
- [ ] **XLSX-03**: Executive Summary sheet is self-contained — decision-maker can act from sheet 1 alone
- [ ] **XLSX-04**: Output includes audit trail metadata (comparison parameters, data extraction timestamps, input file hashes)

### Quality Gates

- [x] **GATE-01**: Expanded hedge word detection including insurance-litigation-specific terms
- [x] **GATE-02**: Judgment language detection (evaluative adjectives: excessive, inadequate, inflated, etc.)
- [x] **GATE-03**: Quantification enforcement — every narrative sentence referencing a delta includes dollar amount and percentage
- [x] **GATE-04**: Evidence grounding check — narrative claims cannot exceed specificity of parsed input data
- [x] **GATE-05**: Methodology neutrality check — no comparative adjectives or standard-referencing in methodology section

## v2.1+ Requirements

Deferred to future release. Tracked but not in current roadmap.

### Configuration & Tuning

- **DEFER-01**: User-configurable rule thresholds per claim type
- **DEFER-02**: Category name normalization across Xactimate versions
- **DEFER-03**: Template-driven litigation output (minimal LLM text) for maximum reproducibility
- **DEFER-04**: Claim-size-aware rule sensitivity tiers (small/medium/large)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| "Which estimate is better" verdicts (AF-1) | Makes tool an advocate, disqualifiable in litigation |
| Recommendation language (AF-2) | Creates liability exposure |
| Emotional terminology (AF-3) | Destroys neutrality |
| Automated fraud indicators (AF-4) | Defamatory without investigation |
| Confidence scores (AF-5) | False precision, indefensible methodology |
| Side-picking output modes (AF-6) | Credibility collapses if discovered in litigation |
| Editorializing narratives (AF-7) | Hallucination liability in legal contexts |
| Settlement predictions (AF-8) | Dangerous without claims history data |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 9 | Completed |
| DATA-02 | Phase 9 | Completed |
| DATA-03 | Phase 9 | Completed |
| DATA-04 | Phase 9 | Completed |
| DATA-05 | Phase 9 | Completed |
| DATA-06 | Phase 9 | Completed |
| DATA-07 | Phase 9 | Completed |
| INTL-01 | Phase 9 | Completed |
| INTL-02 | Phase 10 | Completed |
| INTL-03 | Phase 10 | Completed |
| INTL-04 | Phase 10 | Completed |
| INTL-05 | Phase 10 | Completed |
| NARR-01 | Phase 11 | Completed |
| NARR-02 | Phase 11 | Completed |
| NARR-03 | Phase 11 | Completed |
| GATE-01 | Phase 11 | Completed |
| GATE-02 | Phase 11 | Completed |
| GATE-03 | Phase 11 | Completed |
| GATE-04 | Phase 11 | Completed |
| GATE-05 | Phase 11 | Completed |
| MODE-01 | Phase 12 | Pending |
| MODE-02 | Phase 12 | Pending |
| MODE-03 | Phase 12 | Pending |
| MODE-04 | Phase 12 | Pending |
| XLSX-01 | Phase 12 | Pending |
| XLSX-02 | Phase 12 | Pending |
| XLSX-03 | Phase 12 | Pending |
| XLSX-04 | Phase 12 | Pending |

**Coverage:**
- v2.0 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17 after roadmap creation*
