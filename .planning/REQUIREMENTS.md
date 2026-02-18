# Requirements: VIP30 v2.2 Unified Output

**Defined:** 2026-02-17
**Core Value:** Reliable end-to-end bid comparison that produces actionable output

## v2.2 Requirements

Requirements for v2.2 release. Replace 4 output modes with a single unified 2-sheet report. Simpler UX, no mode selection.

### XLSX Output

- [ ] **XLSX-01**: Report produces exactly 2 sheets: "Summary" and "Analysis"
- [ ] **XLSX-02**: Summary sheet contains total delta, top cost drivers, and key observations (merged from Executive Summary + Ranked Impact)
- [ ] **XLSX-03**: Analysis sheet contains methodology detail, scope alignment, and full category-by-category side-by-side comparison (merged from Methodology + Scope + Category Detail)
- [ ] **XLSX-04**: Audit trail sheet is removed
- [ ] **XLSX-05**: Conditional formatting preserved on new merged sheets

### Mode Removal

- [ ] **MODE-01**: `OutputMode` enum and `OutputModeFilter` class deleted
- [ ] **MODE-02**: Frontend bid comp page has no mode selector — user uploads and submits
- [ ] **MODE-03**: API `CreateJobRequest` has no `output_mode` parameter
- [ ] **MODE-04**: Worker/pipeline passes no mode parameter — always produces unified output
- [ ] **MODE-05**: `output_mode` column on `ComparisonJob` no longer written (historical values preserved)

### Pipeline

- [ ] **PIPE-01**: LLM 3-pass pipeline unchanged (same generation, same cost)
- [ ] **PIPE-02**: All generated content flows into the 2-sheet output (nothing hidden/filtered)

## Validated (v2.1 — planned, not yet executed)

v2.1 requirements preserved. See v2.1 roadmap (Phases 13-15) for details.

- [ ] DIR-01 through DIR-05: Directory restructure
- [ ] PKG-01 through PKG-05: Package structure
- [ ] IMP-01 through IMP-04: Import & reference cleanup
- [ ] REN-01 through REN-05: Render deployment

## Validated (v2.0)

All v2.0 requirements completed and shipped. See v2.0 milestone archive for details.

- [x] DATA-01 through DATA-07: Data foundation and methodology
- [x] NARR-01 through NARR-03: Narrative quality
- [x] INTL-01 through INTL-05: Intelligence layer
- [x] MODE-01 through MODE-04: Output modes (being replaced by v2.2)
- [x] XLSX-01 through XLSX-04: Visual hierarchy (being restructured by v2.2)
- [x] GATE-01 through GATE-05: Quality gates

## Deferred (v3+)

### Configuration & Tuning

- **DEFER-01**: User-configurable rule thresholds per claim type
- **DEFER-02**: Category name normalization across Xactimate versions
- **DEFER-03**: Template-driven litigation output (minimal LLM text) for maximum reproducibility
- **DEFER-04**: Claim-size-aware rule sensitivity tiers (small/medium/large)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| LLM pipeline changes | Fix output format only, generation stays the same |
| New narrative content | No new LLM prompts or passes |
| Line-item matching (TS-1) | v3+ feature, not related to output restructuring |
| Database migration to drop output_mode column | Leave column, just stop writing new values |
| "Which estimate is better" verdicts (AF-1) | Makes tool an advocate, disqualifiable in litigation |
| Recommendation language (AF-2) | Creates liability exposure |
| Emotional terminology (AF-3) | Destroys neutrality |
| Confidence scores (AF-5) | False precision, indefensible methodology |
| Editorializing narratives (AF-7) | Hallucination liability in legal contexts |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (populated by create-roadmap) | | |

**Coverage:**
- v2.2 requirements: 12 total
- Mapped to phases: 0
- Unmapped: 12 (awaiting roadmap)

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17 after v2.2 milestone creation*
