---
phase: 26-contractor-final-parser
verified: 2026-03-09T08:01:29Z
status: passed
score: 4/4 must-haves verified
must_haves:
  truths:
    - truth: XactimateRoughDraftParser on BSchacter contractor-final produces >=26 of 29 sections with line items
      status: verified
      evidence: 29/29 sections detected; 27 with items; 2 legitimately empty (HVAC total=0.00 and Main Level O&P rollup)
    - truth: Rough-draft baseline preserved -- lachman and kalyvas test_section_coverage still pass
      status: verified
      evidence: pytest -k rough -- test_section_coverage 2/2 PASSED; test_metadata 2/2 FAILED are pre-existing (Phase 25-01 decision)
    - truth: Extracted contractor-final line items have item_number, description, qty, unit, and financial fields
      status: verified
      evidence: Item keys from live parse -- line_number, description, qty, unit, reset, remove, replace, op, total. tax=None per-item is correct (section-totals level).
    - truth: Section totals extracted correctly (TAX, O&P, TOTAL from Totals line)
      status: verified
      evidence: _parse_totals_line has_tax+has_op branch extracts 3-amount pattern; confirmed 26/29 sections delta=0.00
  artifacts:
    - path: packages/parser/vip_parser/xactimate/constants.py
      status: verified
      evidence: CFINAL_ITEM_PATTERN lines 19-30 defined; in __all__ at line 121. 165 lines total.
    - path: packages/parser/vip_parser/xactimate/helpers.py
      status: verified
      evidence: family=C assignment lines 235-251; inserted between family B (line 233) and family A (line 253).
    - path: packages/parser/vip_parser/xactimate/parser.py
      status: verified
      evidence: _parse_cfinal_line method lines 806-855; dispatch in _try_start_line_item lines 727-729.
  key_links:
    - from: parser.py:_try_start_line_item
      to: parser.py:_parse_cfinal_line
      via: columns.family == C branch
      status: verified
      evidence: Lines 727-729 confirmed by grep; branch present and wired after family A, before family B/default
    - from: helpers.py:is_table_header
      to: family C detection
      via: _cfinal_required.issubset check with DESCRIPTION+RESET+REMOVE+REPLACE
      status: verified
      evidence: Lines 239-251 confirmed; required set + allowed-set guard correctly isolates contractor-final headers
---

# Phase 26: Contractor-Final Parser Verification Report

**Phase Goal:** Fix the contractor-final parser so BSchacter produces >=26 of 29 sections with extracted line items using the RESET/REMOVE/REPLACE/TAX/O&P column schema.
**Verified:** 2026-03-09T08:01:29Z
**Status:** PASSED
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                              | Status   | Evidence                                                                    |
| --- | ---------------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------- |
| 1   | BSchacter parser produces >=26 of 29 sections with line items                     | VERIFIED | 29/29 sections; 27 with items; 2 legitimately empty (HVAC, Main Level)     |
| 2   | Rough-draft baseline preserved -- test_section_coverage passes                    | VERIFIED | test_section_coverage 2/2 PASSED; test_metadata failures are pre-existing   |
| 3   | Line items have item_number, description, qty, unit, and financial fields          | VERIFIED | All required fields present from live parse; tax=None per-item is correct   |
| 4   | Section totals extracted correctly (TAX, O&P, TOTAL from Totals line)             | VERIFIED | _parse_totals_line 3-amount branch confirmed; 26/29 sections delta=0.00     |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact                                                            | Expected                      | Status   | Details                                                                          |
| ------------------------------------------------------------------- | ----------------------------- | -------- | -------------------------------------------------------------------------------- |
| packages/parser/vip_parser/xactimate/constants.py                  | Contains CFINAL_ITEM_PATTERN  | VERIFIED | Lines 19-30; in __all__ at line 121. 165 lines, no stubs.                        |
| packages/parser/vip_parser/xactimate/helpers.py                    | Contains family=C assignment  | VERIFIED | Lines 235-251; placed between family B and family A checks.                      |
| packages/parser/vip_parser/xactimate/parser.py                     | Contains _parse_cfinal_line   | VERIFIED | Lines 806-855 method; lines 727-729 dispatch in _try_start_line_item.            |

### Key Link Verification

| From                             | To                         | Via                                | Status   | Details                                                              |
| -------------------------------- | -------------------------- | ---------------------------------- | -------- | -------------------------------------------------------------------- |
| parser.py:_try_start_line_item   | _parse_cfinal_line         | columns.family == C branch         | WIRED    | Lines 727-729; dispatches and returns (item, True)                  |
| helpers.py:is_table_header       | Family C detection         | _cfinal_required.issubset          | WIRED    | Lines 239-251; DESCRIPTION+RESET+REMOVE+REPLACE required set guard  |
| Family C cols (has_tax, has_op)  | _parse_totals_line         | has_tax=True and has_op=True flags | WIRED    | Family C sets both flags; totals method picks TAX/O&P/TOTAL branch  |

### Requirements Coverage

| Requirement                                                               | Status    | Notes                                                                              |
| ------------------------------------------------------------------------- | --------- | ---------------------------------------------------------------------------------- |
| CFINAL-01: Line items map to RESET/REMOVE/REPLACE/TAX/O&P schema          | SATISFIED | reset/remove/replace/op/total per item; tax at section-totals level.               |
| CFINAL-02: BSchacter produces >=26 of 29 sections with line items         | SATISFIED | 29/29 sections; 27 with items; 2 empty are legitimate (HVAC, Main Level rollup).   |
| VALID-01: Rough-draft baseline preserved                                   | SATISFIED | test_section_coverage 2/2 PASSED for lachman and kalyvas.                          |

### Anti-Patterns Found

| File       | Line | Pattern | Severity | Impact |
| ---------- | ---- | ------- | -------- | ------ |
| None found | --   | --      | --       | --     |

No TODO/FIXME/placeholder stubs found in the three modified files. All implementations are substantive.

### Detailed Verification Notes

**Truth 1 -- Section Count (live parse)**

Run against BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf:

```
BSchacter sections: 29/29
Sections with line items: 27
  [ 1 items] Demo/Mitigtation: total=120,000.00
  [15 items] General Items: total=62,013.93
  [ 1 items] Insulation: total=4,872.63
  [ 0 items] HVAC: total=0.00             <- legitimately empty (no HVAC work)
  [15 items] Electrical: total=28,391.81
  [ 2 items] Plumbing: total=868.16
  [ 8 items] Appliances: total=25,439.62
  [ 0 items] Main Level: total=2,217.22   <- O&P rollup, no explicit line items in PDF
  [33 items] Entry: total=7,205.94
  [39 items] Kitchen: total=22,704.73
  ... 17 more sections with items
```

27 sections with items exceeds the >=26 threshold. The 2 empty sections are both legitimate per
STATE.md Phase 26-01 decision: HVAC has no work in this bid; Main Level is an O&P rollup section
without explicit line items in the PDF.

**Truth 2 -- Regression Test Output**

```
pytest tests/test_coverage.py -k rough -v
PASSED  test_section_coverage[rough-drafts/lachman.golden.json-...]
PASSED  test_section_coverage[rough-drafts/kalyvas.golden.json-...]
FAILED  test_metadata[rough-drafts/lachman.golden.json-...]   <- pre-existing
FAILED  test_metadata[rough-drafts/kalyvas.golden.json-...]   <- pre-existing
2 failed, 2 passed in 197.93s
```

The test_metadata failures are pre-existing and documented in STATE.md Phase 25-01 decision:
Rough-draft test_metadata failures are informative gap documentation, not regressions -- golden
master metadata values represent ideal v2.5 target output; parser currently returns raw/truncated
values; test_section_coverage passes 100% confirming structural parser is production-quality.
The phase plan also explicitly documented this in the Deviations from Plan section.

**Truth 3 -- Item Field Structure (Demo/Mitigtation, item 1, from live parse)**

```json
{
  "type": "line_item",
  "line_number": 1,
  "description": "General Demolition (Bid Item)",
  "qty": 1.0,
  "unit": "EA",
  "reset": "100,000.00",
  "remove": "0.00",
  "replace": "0.00",
  "op": "20,000.00",
  "total": "120,000.00"
}
```

tax is None for bid items and stripped by _finalize_line_item (removes None values from output dict).
The contractor-final format reports tax at the section-totals level, not per line item. All required
fields (line_number/item_number, description, qty, unit, reset, remove, replace, op, total) present.

**Truth 4 -- Section Totals Extraction**

_parse_totals_line at parser.py line 883 with columns.has_tax=True and columns.has_op=True (set by
family C detection) picks the 3-amount TAX/O&P/TOTAL branch (line 884). Confirmed:

```
Demo/Mitigtation: tax=0.00,   op=20,000.00, total=120,000.00, delta=0.00
General Items:    tax=49.95,  op=10,335.66, total=62,013.93,  delta=0.00
Insulation:       tax=176.86, op=812.12,    total=4,872.63,   delta=0.00
HVAC:             tax=0.00,   op=0.00,      total=0.00,        delta=0.00
Electrical:       tax=642.55, op=4,731.98,  total=28,391.81,  delta=0.00
```

3 sections with non-zero delta (Main Level $2,217.22; Entry $295.23; Master bathroom $367.27)
are pre-existing document characteristics noted in STATE.md decisions.

**Key Link -- parser.py _try_start_line_item dispatch (confirmed by grep)**

```python
# parser.py lines 723-729
def _try_start_line_item(self, line, columns):
    if columns.family == "A":
        item = self._parse_layout_a_line(line, columns)
        return (item, True) if item else (None, False)
    if columns.family == "C":
        item = self._parse_cfinal_line(line, columns)
        return (item, True) if item else (None, False)
    m = re.match(LINE_ITEM_PATTERN, line)   # family B / default
```

**Key Link -- helpers.py family C detection (confirmed by code read)**

```python
# helpers.py lines 235-251
_cfinal_required = {"DESCRIPTION", "RESET", "REMOVE", "REPLACE"}
_cfinal_allowed = {"DESCRIPTION", "QTY", "CALC", "RESET", "REMOVE", "REPLACE", "TAX", "O&P", "TOTAL"}
if (_cfinal_required.issubset(set(top_tokens))
        and all(t in _cfinal_allowed for t in top_tokens)
        and len(top_tokens) >= 4):
    cols = TableColumns(family="C", has_reset=True, has_tax=True, has_op=True)
    return True, cols, False   # is_two=False (single-line header)
```

### Human Verification Required

None. All must-haves verified programmatically via live parse and pytest execution.

## Gaps Summary

No gaps found. All 4 truths verified.

**Notable outstanding item (not a gap, out of scope for this phase):**
bschacter.golden.json in .planning/golden-masters/final-drafts/ is the Phase 24-02 version
(0 sections, 477 manually-extracted items). This needs updating with Phase 26 parser output
before the coverage harness can validate BSchacter final-drafts. Documented in STATE.md
blockers/concerns.

---

_Verified: 2026-03-09T08:01:29Z_
_Verifier: Claude (gsd-verifier)_