# Golden Masters

Golden masters are the ground-truth expected output for each document type that
the VIP30 parser supports. The Phase 25 coverage harness diffs live parser
output against these files to measure coverage and catch regressions.

---

## Purpose

When the parser produces output for a known PDF, that output can be captured and
saved as the "golden master" for that document. Future parser runs are then
compared field-by-field against the golden master to detect:

- Regressions (fields that previously parsed correctly and now fail)
- Coverage improvements (fields that were previously null and now populate)
- Count changes (more or fewer sections or line items than expected)

The rough-draft golden masters were created from Phase 23 audit output, which
confirmed zero validation delta across all sections — making that output suitable
as production-quality ground truth.

---

## File Naming Convention

| File path | Document |
|-----------|----------|
| `rough-drafts/lachman.golden.json` | Lachman APEX 2 rough draft |
| `rough-drafts/kalyvas.golden.json` | Kalyvas JVB V6 rough draft |
| `final-drafts/bschacter.golden.json` | BSchacter contractor final (v2.5 scope) |
| `final-drafts/statefarm/customer_copy.golden.json` | StateFarm Customer Copy (v2.5 scope) |
| `final-drafts/statefarm/lachman_sf.golden.json` | StateFarm Lachman structural (v2.5 scope) |
| `final-drafts/statefarm/kalyvas_sf.golden.json` | StateFarm Kalyvas preliminary (v2.5 scope) |

Files marked "v2.5 scope" do not yet exist — they will be created once the
corresponding document-type parsers are production-quality.

---

## Schema

Golden master files use the same schema as `vip_parser.xactimate` output.
Top-level fields:

| Field | Type | Description |
|-------|------|-------------|
| `estimate_name` | string | Identifier derived from the source filename |
| `case_metadata` | object | Insured, claim number, policy number, dates, adjuster |
| `sections` | array | Trade sections — each has a `name` and `line_items` array |
| `grand_total_areas` | object | Total areas (roof, walls, floor, etc.) |
| `coverage` | object | Coverage type and deductible information |
| `recaps_and_summaries` | object | Depreciation, overhead, profit, totals |
| `validations` | object | Per-section validation delta (should be 0.00 for rough drafts) |

Each element in `sections` has:

```json
{
  "name": "INTERIOR",
  "line_items": [
    {
      "description": "...",
      "quantity": "...",
      "unit": "...",
      "unit_price": "...",
      "total": "..."
    }
  ]
}
```

---

## How to Update a Golden Master

1. Run the parser on the source PDF:
   ```bash
   cd packages/parser
   python -m vip_parser.xactimate path/to/source.pdf --output output.json
   ```
2. Verify output quality manually against the PDF. Check:
   - Section count matches expected
   - Line item counts match expected
   - Validation delta is 0.00 on all sections
   - Key metadata fields are populated (claim number, dates, insured name)
3. Replace the golden master file with the new output:
   ```bash
   cp output.json tests/golden/rough-drafts/<name>.golden.json
   ```
4. Human-verify: open the new golden master and spot-check 3-5 sections
   against the source PDF.
5. Commit the updated file with a message explaining what changed and why.

Never update a golden master without human verification. Automated replacement
without review defeats the purpose of having a regression baseline.

---

## Source PDFs

Source PDFs are stored in the project `docs/` directory:

| Golden master | Source PDF location |
|---------------|---------------------|
| `rough-drafts/lachman.golden.json` | `docs/rough-drafts/1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.pdf` |
| `rough-drafts/kalyvas.golden.json` | `docs/rough-drafts/KALYVAS_JVB_V6_KALY2_ROUGH_DRAFT_CAR.pdf` |
| `final-drafts/bschacter.golden.json` | `docs/final-drafts/BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf` |
| `final-drafts/statefarm/customer_copy.golden.json` | `docs/final-drafts/statefarm/Customer Copy Final Draft (3).pdf` |
| `final-drafts/statefarm/lachman_sf.golden.json` | `docs/final-drafts/statefarm/Estimate SF Structural damage Lachman 4.15.2025.pdf` |
| `final-drafts/statefarm/kalyvas_sf.golden.json` | `docs/final-drafts/statefarm/Kalyvas Preliminary State Farm estimate9-25-25.pdf` |

Source PDFs are not committed to the repository (large binary files). They are
stored locally and referenced by path only.
