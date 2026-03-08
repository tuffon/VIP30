---
phase: 23-parser-audit
plan: "02"
subsystem: testing
tags: [xactimate, parser, audit, pdf, json, gap-analysis]

requires:
  - phase: 23-01
    provides: "Parser JSON outputs for all 6 PDFs in audit_output/; run_log.json with parse results"

provides:
  - "AUDIT-REPORT.md: 255-line structured gap analysis covering all 3 doc types"
  - "Per-field coverage table: what parser captures vs misses for rough-draft, contractor-final, StateFarm"
  - "10-item prioritized gap list for v2.5 parser fixes"
  - "Root-cause identification: contractor-final column schema mismatch; StateFarm item-per-section under-extraction"

affects:
  - "24-golden-masters — this report defines what perfect output should look like per doc type"
  - "25-parser-fixes (v2.5) — gap priority table is the direct input for fix scoping"

tech-stack:
  added: []
  patterns:
    - "Gap analysis structured as: field coverage table + amount accuracy + root cause — per doc type"
    - "Validation delta as signal for item extraction completeness (declared total - computed total)"

key-files:
  created:
    - "packages/parser/audit_output/AUDIT-REPORT.md"
  modified: []

key-decisions:
  - "6 PDFs audited (not 7 — plan text said 7, actual corpus is 6; note updated in STATE.md in 23-01)"
  - "BSchacter contractor final: root cause is column schema mismatch (RESET/REMOVE/REPLACE/TAX/O&P columns), not a text extraction failure — PDF text is readable and metadata parses correctly"
  - "StateFarm Customer Copy under-extraction: likely summary/grouped layout rather than row-per-item; further investigation needed before fix attempt"
  - "Rough-draft parser is production-quality baseline — zero validation delta, all fields captured"

patterns-established:
  - "Audit structure: Executive Summary > Doc Types table > Per-doc-type findings > Cross-doc patterns > Gap priority table"
  - "Field status documented as: Captured / Partial / Missing / Fallback-only — with specific example values"

duration: 35min
completed: 2026-03-07
---

# Phase 23 Plan 02: Parser Audit Gap Analysis Summary

**Structured parser coverage audit identifying 10 gaps across 3 doc types: contractor-final column schema mismatch causes total section failure; StateFarm Customer Copy captures 1 item per section where many exist; rough-draft parser achieves perfect accuracy baseline**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-03-07T (session start)
- **Completed:** 2026-03-07
- **Tasks:** 2 of 2
- **Files modified:** 1 created (AUDIT-REPORT.md)

## Accomplishments

- Read and analyzed all 6 parser JSON outputs from plan 23-01 using Python extraction scripts
- Documented field-by-field coverage for every JSON key (case_metadata, sections, grand_total_areas, coverage, recaps_and_summaries) per doc type
- Identified root causes for both critical gaps: contractor-final column schema mismatch and StateFarm line-item under-extraction pattern
- Produced 255-line AUDIT-REPORT.md with no placeholder sections — all data from actual parser outputs

## Task Commits

1. **Task 1 + Task 2: Analyze outputs and write AUDIT-REPORT.md** — `4d98cd3` (feat)

## Files Created/Modified

- `packages/parser/audit_output/AUDIT-REPORT.md` — 255-line structured gap analysis covering all 3 doc types, 10-item gap priority table for v2.5

## Decisions Made

- BSchacter contractor final: root cause is column schema mismatch — the parser's line-item regex expects rough-draft column layout (unit cost + quantity) but contractor finals use RESET/REMOVE/REPLACE/TAX/O&P columns. Metadata header and recap tables parse fine; only section/line-item extraction fails.
- StateFarm Customer Copy: 31 sections detected but 29 of 31 have non-zero validation delta totaling $165K. Most sections contain 0 or 1 line item where the declared total implies many more. Pattern suggests a summary/grouped row layout that the parser's item regex does not match.
- Rough-draft baseline is solid: zero validation delta across all 72 sections (32+40), all major fields captured, suitable as v2.5 regression baseline.

## Deviations from Plan

None — plan executed exactly as written. The only factual adjustment was noting 6 PDFs audited (not 7 as plan text stated), consistent with the 23-01 decision already recorded in STATE.md.

## Issues Encountered

- JSON output files are large (>256KB for rough drafts) and could not be read directly with the Read tool. Used Python extraction scripts to pull specific fields and compute statistics — faster and more reliable than attempting partial reads.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 24 (golden masters) has a clear brief: AUDIT-REPORT.md documents per-doc-type field coverage and identifies 10 gaps. Golden master files should represent perfect output for each of the 3 doc types.
- P1 for v2.5: contractor-final line-item parser (new column schema)
- P2 for v2.5: StateFarm Customer Copy item extraction (grouped vs itemized row detection)
- P3 for v2.5: StateFarm header metadata regex (all metadata fields null for StateFarm)
- Rough-draft parser requires no changes — use as regression baseline

---
*Phase: 23-parser-audit*
*Completed: 2026-03-07*
