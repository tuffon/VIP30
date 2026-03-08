# Xactimate Parser Coverage Audit — v2.4

**Date:** 2026-03-07
**Parser:** XactimateRoughDraftParser (packages/parser)
**Documents audited:** 6 PDFs across 3 doc types
**Parser changes:** NONE — this is a baseline audit only

---

## Executive Summary

The parser achieves near-perfect coverage on rough-draft contractor PDFs: both rough-draft files parse with 100% section accuracy, zero validation delta, and all major fields populated. Contractor final-draft PDFs (Xactimate "Restoration/Service/Remodel" format) fail completely at the section level — BSchacter produces 0 sections and 0 line items despite readable text, because the column schema differs from rough drafts. StateFarm final-draft PDFs parse sections successfully but suffer severe line-item under-extraction: sections detect correctly but items-per-section is often 1 or 0, and validation deltas reach $103,723 per section. For v2.5, the two priority gaps are: (1) contractor final-draft support (currently zero extraction), and (2) StateFarm line-item completeness per section (currently captures ~1 item where many exist).

---

## Document Types Audited

| Doc Type | Files | Parser Result | Sections | Line Items |
|----------|-------|---------------|----------|------------|
| Rough Draft (contractor) | 2 | Success | 32 / 40 | 525 / 887 |
| Final Draft (contractor) | 1 | Critical fail — 0 sections | 0 | 0 |
| StateFarm Final Draft | 3 | Partial — sections ok, items incomplete | 31–36 | 32–518 |

---

## Per-Document-Type Findings

### Rough Draft (Contractor)

**Files:**
- `docs/rough-drafts/1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.pdf`
- `docs/rough-drafts/KALYVAS_JVB_V6_KALY2_ROUGH_DRAFT_CAR.pdf`

**Parser status:** Success — 32 sections / 525 items (Lachman); 40 sections / 887 items (Kalyvas)

**Captured fields:**

| Field | Status | Notes |
|-------|--------|-------|
| `estimate_name` | Captured | Internal Xactimate name (e.g., `1115_LACHMAN_APEX_2`) — not filename |
| `case_metadata.claim_number` | Captured | `75-79J8-65X`, `75-79F9-18M` |
| `case_metadata.policy_number` | Captured | Both populated |
| `case_metadata.loss_type` | Captured | Fire / WildFire |
| `case_metadata.coverage` | Captured | Coverage types with deductibles and policy limits |
| `case_metadata.property_address` | Captured | Full address + claim rep contact embedded |
| `case_metadata.date_of_loss` | Captured | ISO datetime |
| `case_metadata.date_received` | Partial | Lachman: null; Kalyvas: populated |
| `case_metadata.date_inspected` | Partial | Lachman: null; Kalyvas: populated |
| `case_metadata.date_entered` | Captured | Both populated |
| `case_metadata.price_list` | Captured | `CALA8X_APR25`, `CALA8X_MAR25` |
| `case_metadata.building_type` | Missing | Always null across both files |
| `case_metadata.line_item_totals` | Captured | Grand total, O&P, sales tax all present |
| `case_metadata.labor_minimums` | Captured | Lachman: populated; Kalyvas: null |
| `case_metadata.additional_charges` | Captured | California Lumber Assessment Fee |
| `sections` | Captured | All sections with names, line items, section totals |
| `grand_total_areas` | Captured | All 18 measurement fields present (sf_walls through total_hip_length) |
| `coverage` | Captured | Rows with per-coverage totals and percentages |
| `recaps_and_summaries.summaries_by_coverage` | Captured | Dwelling, Other Structures, Trees/Plants/Shrubs |
| `recaps_and_summaries.recap_tax_op` | Captured | Overhead, profit, material sales tax, storage rental tax |
| `recaps_and_summaries.recap_by_room` | Captured | Populated |
| `recaps_and_summaries.recap_by_category` | Captured | Populated |
| `recaps_and_summaries.trade_summary` | Not present | Field does not appear in rough-draft output (not a gap — not expected) |

**Amount accuracy:**
- Sections with non-zero validation_delta: **0/32** (Lachman), **0/40** (Kalyvas)
- Max delta observed: **$0.00** — perfect section-level accuracy for this doc type
- Document-level recap_vs_end_grand_delta: $81.05 (Lachman), $75.92 (Kalyvas)
  - These small recap discrepancies are rounding artifacts from the recap tables, not section extraction errors

**Section errors (minor):**
- Lachman: `Other Structures` — section name not found above table at line 1683 (parser warning, section still extracted)
- Kalyvas: `Hardscapes and walkways` — same pattern (section still extracted with 0 items)

**Gaps identified:**
- `case_metadata.building_type`: always null (field exists in schema but not detected in PDF text)
- `case_metadata.date_received` / `date_inspected`: null when PDF leaves dates blank (expected behavior)
- `case_metadata.property_address`: claim rep contact info is appended in same string — not separated
- Section name detection warning for sections lacking explicit header text above the table; these sections still parse but may produce 0 items if the table boundary is misidentified

---

### Final Draft (Contractor)

**Files:**
- `docs/final-drafts/BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf`

**Parser status:** Critical failure — 0 sections, 0 line items

**Root cause:** The BSchacter PDF uses Xactimate's "Restoration/Service/Remodel" output format, which has a different column layout than rough drafts:
- Rough draft columns: `DESCRIPTION | UNIT COST | QUANTITY | TOTAL`
- Contractor final columns: `DESCRIPTION | QTY | RESET | REMOVE | REPLACE | TAX | O&P | TOTAL`

The parser's line-item regex is tuned for the rough-draft column schema and does not match any rows in the contractor final format. Section headers also appear without the indentation or prefix pattern the parser expects.

**What was captured despite 0 sections:**

| Field | Status | Notes |
|-------|--------|-------|
| `estimate_name` | Fallback only | Filename used as fallback (`BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf`), not internal name. Internal name is `SCHACTER_RECON_5` — visible in PDF text but not extracted |
| `case_metadata.claim_number` | Captured | `75-79D9-35K` |
| `case_metadata.policy_number` | Captured | `71-GF-E601-0` |
| `case_metadata.loss_type` | Captured | WildFire |
| `case_metadata.property_address` | Captured | Full address |
| `case_metadata.date_of_loss` | Missing | PDF shows blank date field — parser correctly returns null |
| `case_metadata.price_list` | Missing | `CALA8X_JUL25` is in the PDF text but not captured (null) |
| `case_metadata.line_item_totals` | Captured | Grand total $809,462.41, O&P $98,050.84, sales tax $10,686.51 (from footer) |
| `grand_total_areas` | Captured | All 18 measurement fields present — area tables parse successfully |
| `coverage` | Captured | 8 coverage rows with item totals and percentages |
| `recaps_and_summaries.summaries_by_coverage` | Captured | Dwelling, Other Structures |
| `recaps_and_summaries.recap_by_room` | Captured | Populated |
| `recaps_and_summaries.recap_by_category` | Captured | Populated |
| `recaps_and_summaries.recap_tax_op` | **Missing** | null — footer tax/O&P table not extracted |
| `sections` | **Failed** | 0 sections, 0 line items |

**Validation (document level):**
- `grand_total_vs_sections_delta`: $809,462.41 — full grand total unaccounted for by sections (expected: 0 sections)
- `recap_vs_end_grand_delta`: $2.42 — very small, recap tables parsed accurately

**Gaps identified:**
- Complete section and line-item extraction failure — no line-item data recoverable
- Internal estimate name (`SCHACTER_RECON_5`) not captured (filename used as fallback)
- `price_list` field not extracted (`CALA8X_JUL25` is in text but parser regex doesn't match contractor final header format)
- `recap_tax_op` not extracted
- `case_metadata.depreciate_*` flags all null (format difference)

---

### StateFarm Final Draft

**Files:**
- `docs/final-drafts/statefarm/Customer Copy Final Draft (3).pdf`
- `docs/final-drafts/statefarm/Estimate SF Structural damage Lachman 4.15.2025.pdf`
- `docs/final-drafts/statefarm/Kalyvas Preliminary State Farm estimate9-25-25.pdf`

**Parser status:** Partial — sections detected, but line-item extraction is critically incomplete per-section

**Section and item counts:**

| File | Sections | Line Items | Expected ratio |
|------|----------|------------|----------------|
| Customer Copy Final Draft (3) | 31 | 32 | ~1 item/section (critical gap) |
| Estimate SF Structural damage Lachman | 34 | 367 | ~11 items/section (reasonable) |
| Kalyvas Preliminary State Farm | 36 | 518 | ~14 items/section (reasonable) |

**Pattern:** Customer Copy Final Draft has a different internal layout — section totals appear but most items are not captured. Lachman and Kalyvas StateFarm files extract more items but still show large per-section deltas.

**Captured fields (per all 3 StateFarm files):**

| Field | Status | Notes |
|-------|--------|-------|
| `estimate_name` | Fallback only | Filename used (e.g., `Customer Copy Final Draft (3).pdf`); internal claim number used as estimate name in line_item_totals (`75-79D9-35K`, `75-79F9-18M3`) |
| `case_metadata.claim_number` | **Missing** | null across all 3 StateFarm files |
| `case_metadata.policy_number` | **Missing** | null across all 3 StateFarm files |
| `case_metadata.loss_type` | **Missing** | null across all 3 StateFarm files |
| `case_metadata.coverage` (metadata) | **Missing** | null across all 3 StateFarm files |
| `case_metadata.property_address` | **Missing** | null across all 3 StateFarm files |
| `case_metadata.date_of_loss` | **Missing** | null across all 3 StateFarm files |
| `case_metadata.date_entered` | **Missing** | null across all 3 StateFarm files |
| `case_metadata.price_list` | **Missing** | null across all 3 StateFarm files |
| `case_metadata.depreciate_*` | **Missing** | All null across all 3 StateFarm files |
| `case_metadata.line_item_totals` | Partial | Lachman: null; Customer Copy and Kalyvas: populated with grand total |
| `sections` | Partial | Sections detected, line items severely under-extracted in Customer Copy |
| `grand_total_areas` | Mostly captured | 13–14 of 18 rough-draft fields present; missing: `sy_flooring`, `sf_long_wall`, `sf_short_wall`, `total_perimeter_length` (Kalyvas); also `total_hip_length` (Customer Copy, Lachman) |
| `coverage.rows` | **Missing** | 0 coverage rows across all 3 StateFarm files (rows array empty) |
| `coverage.totals` | Captured | Totals present even where rows are empty |
| `recaps_and_summaries.summaries_by_coverage` | Captured | All 3 populated — StateFarm format uses different coverage label ("Dwelling Estimated cost to repair or replace") |
| `recaps_and_summaries.recap_tax_op` | Captured | All 3 populated |
| `recaps_and_summaries.recap_by_room` | Captured | All 3 populated |
| `recaps_and_summaries.recap_by_category` | Partial | Column header differs ("General Contractor O&P Items" vs "O&P Items") — parsed but may have structural differences |
| `recaps_and_summaries.trade_summary` | Present (2/3) | Lachman and Kalyvas have trade_summary; Customer Copy does not |

**Amount accuracy (validation_delta per section):**

| File | Non-zero delta sections | Max single delta | Sum of all deltas |
|------|------------------------|------------------|-------------------|
| Customer Copy Final Draft (3) | 29/31 | $50,743.85 | $165,492.81 |
| Estimate SF Structural damage Lachman | 4/34 | $14,137.76 | $15,346.95 |
| Kalyvas Preliminary State Farm | 4/36 | $103,723.10 | $141,628.84 |

**Customer Copy delta root cause:** Most sections detect 0 or 1 line items but have large declared totals. For example, "Trees, Shrubs and Landscaping" has 0 items extracted and a $50,743.85 delta; "General Items" has 0 items and a $16,876.12 delta. The section boundaries are found but the line-item rows within the section are not matched, likely because the Customer Copy format uses a summary-style layout with totals printed inline rather than itemized row-by-row.

**Kalyvas Ext_Surfaces delta ($103,723.10):** Section has 5 items extracted but the declared section total is much larger — many items in that section are not captured.

**Section errors:**
- SF Kalyvas: `Hardscapes and walkways` — "Section name not found above table" at line 2447 (same pattern as rough-draft warning)
- SF Lachman: No section errors
- Customer Copy: No section errors

**Gaps identified:**
- All `case_metadata` header fields null (claim number, policy, address, loss type, dates, price list) — StateFarm PDF header format is different from contractor header
- `coverage.rows` always empty — StateFarm coverage table format not parsed
- `estimate_name` always falls back to filename — internal name not found in StateFarm format
- Customer Copy: systematic line-item under-extraction (likely summary/grouped format, not itemized rows)
- `grand_total_areas` missing 4–5 measurement fields vs rough draft (sy_flooring, sf_long_wall, sf_short_wall, and occasionally total_perimeter_length, total_hip_length)
- `trade_summary` absent in Customer Copy (present in Lachman and Kalyvas StateFarm)

---

## Cross-Doc-Type Patterns

**Consistently captured (all 3 doc types — even partial parses):**
- `grand_total_areas` (18 fields for rough/contractor-final, 13–14 for StateFarm)
- `recaps_and_summaries.summaries_by_coverage` — populated across all types
- `recaps_and_summaries.recap_by_room` — populated across all types
- `recaps_and_summaries.recap_by_category` — populated across all types
- `case_metadata.line_item_totals` — grand total captured from footer in all types (even when sections fail)

**Consistently missing or null (all 3 doc types):**
- `case_metadata.building_type` — never extracted (null in all 6 files)
- `case_metadata.date_received` and `date_inspected` — only populated when the PDF field is not blank
- `recaps_and_summaries.trade_summary` — only appears in 2 of 3 StateFarm files; absent in rough draft and contractor final

**Type-specific gaps:**

| Gap | Rough Draft | Contractor Final | StateFarm |
|-----|-------------|-----------------|-----------|
| Metadata header fields (claim #, policy, address) | Captured | Captured | **All null** |
| Section-level line items | Fully captured | **Total failure (0 items)** | Partial — 1 item per section in Customer Copy |
| `estimate_name` (internal) | Captured | **Fallback to filename** | **Fallback to filename** |
| `coverage.rows` | Captured (4–8 rows) | Captured (8 rows) | **Empty (0 rows)** |
| `recap_tax_op` | Captured | **Missing** | Captured |
| `grand_total_areas` completeness | All 18 fields | All 18 fields | 13–14 of 18 fields |
| Amount accuracy (validation delta) | Perfect (0.00) | N/A (no sections) | Large deltas ($103K max) |

---

## Gap Priority for v2.5

| Priority | Gap | Doc Type Affected | Impact | Root Cause |
|----------|-----|-------------------|--------|------------|
| 1 — Critical | Section and line-item extraction completely absent | Contractor Final (BSchacter) | High — $809K estimate produces no usable line-item data | Column schema mismatch: RESET/REMOVE/REPLACE/TAX/O&P columns not recognized by parser |
| 2 — Critical | Line-item under-extraction per section (1 item where many exist) | StateFarm — Customer Copy | High — 32 items extracted vs ~150+ expected; $165K validation delta | Section boundary detection finds header but item rows not matched (likely summary-grouped format) |
| 3 — High | All `case_metadata` header fields null | StateFarm (all 3 files) | High — no claim number, policy, property address, loss type for StateFarm estimates | StateFarm header layout differs from contractor header; parser regex does not match |
| 4 — High | Large per-section validation deltas in StateFarm | StateFarm — Kalyvas ($103K), Lachman ($14K) | High — extracted amounts do not match declared section totals | Items in certain section types (Ext_Surfaces, bid items) not fully captured |
| 5 — Medium | `estimate_name` falls back to filename | Contractor Final, StateFarm | Medium — internal estimate name (`SCHACTER_RECON_5`, claim number) not extracted | Internal estimate name uses different label format in these PDF types |
| 6 — Medium | `coverage.rows` empty for all StateFarm files | StateFarm (all 3) | Medium — per-coverage breakdown unavailable | StateFarm coverage table format not recognized |
| 7 — Medium | `grand_total_areas` missing 4–5 fields in StateFarm | StateFarm (all 3) | Medium — sy_flooring, sf_long_wall, sf_short_wall absent | Measurement fields use different labels or positions in StateFarm output |
| 8 — Low | `recap_tax_op` missing in contractor final | Contractor Final (BSchacter) | Low — grand total still captured; tax/O&P available in line_item_totals | Tax/O&P table format differs in contractor final |
| 9 — Low | `case_metadata.building_type` always null | All types | Low — field not critical for comparison | Not consistently present in PDF header for these claim types |
| 10 — Low | Section name detection warnings (non-fatal) | Rough Draft, StateFarm | Low — section still parsed; 0-item sections result | Section header not found immediately above table in some cases |

---

## Raw Output Location

All parser JSON outputs: `packages/parser/audit_output/`
Run log: `packages/parser/audit_output/run_log.json`

Per-file outputs:
- `audit_output/rough-drafts/1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.json`
- `audit_output/rough-drafts/KALYVAS_JVB_V6_KALY2_ROUGH_DRAFT_CAR.json`
- `audit_output/final-drafts/BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.json`
- `audit_output/final-drafts/statefarm/Customer Copy Final Draft (3).json`
- `audit_output/final-drafts/statefarm/Estimate SF Structural damage Lachman 4.15.2025.json`
- `audit_output/final-drafts/statefarm/Kalyvas Preliminary State Farm estimate9-25-25.json`
