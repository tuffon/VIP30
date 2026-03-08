"""
extract_bschacter.py

Extraction script for BSchacter contractor-final golden master.

The BSchacter PDF uses Xactimate's Restoration/Service/Remodel format:
  DESCRIPTION | QTY | RESET | REMOVE | REPLACE | TAX | O&P | TOTAL

The production parser returns 0 sections for this format (column schema mismatch).
This script extracts sections and line items from PDF text using pdfplumber, then
merges them with the existing parser audit output (which correctly captures
estimate_name, case_metadata, grand_total_areas, recaps_and_summaries).

Output: packages/parser/tests/golden/final-drafts/bschacter.golden.json
"""

import json
import os
import re
import sys

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not installed. Run: pip install pdfplumber")
    sys.exit(1)

# ─── paths ────────────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

PARSER_JSON = os.path.join(
    ROOT,
    "packages", "parser", "audit_output", "final-drafts",
    "BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.json",
)
PDF_PATH = os.path.join(
    ROOT,
    "docs", "final-drafts",
    "BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf",
)
OUTPUT_PATH = os.path.join(
    ROOT,
    "packages", "parser", "tests", "golden", "final-drafts",
    "bschacter.golden.json",
)

# ─── Known sections (from "Totals:" rows in PDF) ─────────────────────────────
# These are the 28 leaf-level sections we will extract.
# Area-level aggregates (Total: Main Level, Total: Dwelling, etc.) are NOT sections.
KNOWN_SECTIONS = {
    "Demo/Mitigtation",
    "General Items",
    "Insulation",
    "HVAC",
    "Electrical",
    "Plumbing",
    "Appliances",
    "Window and Patio Doors Replacement",
    "Main Level",      # one line item (Deodorize), total from "Total: Main Level" $2,217.22
    "Entry",
    "Kitchen",
    "Living Room",
    "Fireplace",
    "Office",
    "Office Closet",
    "Bedroom 1",
    "Bed1 Closet",
    "Hall Bathroom 1",
    "Master bathroom",
    "Master Bedroom",
    "Main Hallway",
    "Laundry Room",
    "Garage",
    "Ductwork Cavity",
    "Ext_Surfaces",
    "Hardscapes",      # items 456-463 (456-462 are before CONTINUED - Hardscapes)
    "CMU Walls",
    "Gazebos/Outside Structures",
    "Labor Minimums Applied",
    # NOTE: "Other Structures" is an AREA grouping (like "Dwelling"), NOT a leaf section.
    # Items 456-462 under the "Other Structures" header belong to "Hardscapes".
}

# ─── regex patterns ───────────────────────────────────────────────────────────

# Column header row — marks start of a section's data table
# Some pages have garbled header rows (e.g., "DESCRIPTIOEENnnttrryy QTY RESET...")
# Accept any line that starts with DESCRIPTION (even if garbled) and contains QTY RESET REMOVE
HEADER_ROW = re.compile(r'^DESCRIPTION\w*\s+QTY\s+RESET\s+REMOVE\s+REPLACE\s+TAX\s+O&P\s+TOTAL')

# Section totals (plural): "Totals: SectionName TAX O&P TOTAL"
TOTALS_ROW = re.compile(
    r'^Totals:\s+(.+?)\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s*$'
)

# Area aggregate totals (singular): "Total: AreaName TAX O&P TOTAL"
# e.g., "Total: Main Level ...", "Total: Dwelling ...", "Total: Other Structures ..."
AREA_TOTAL_ROW = re.compile(
    r'^Total:\s+(.+?)\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s*$'
)

# Continued section: "CONTINUED - SectionName"
CONTINUED_ROW = re.compile(r'^CONTINUED\s+-\s+(.+)$')

# Line item with numeric amounts: ends with TAX O&P TOTAL (3 numbers)
LINE_ITEM = re.compile(
    r'^(\d+)\.\s+(.+?)\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s*$'
)

# BID/ATTEMPT items (no amounts): ends with "PER HVC BID", "SEE BID", "ATTEMPT CLEAN"
BID_ITEM = re.compile(
    r'^(\d+)\.\s+(.+?)\s+[\d,]+\.[\d]{2}\s+\w+\s+(?:(?:PER\s+\w+\s+)?(?:SEE\s+)?BID|ATTEMPT\s+CLEAN)\s*$'
)

# Footer / header junk to skip outright
SKIP_PATTERNS = [
    re.compile(r'^\d+$'),                                    # page number only
    re.compile(r'^Office of Jared'),                         # header
    re.compile(r'^Arizona Public'),                          # header
    re.compile(r'^California Public'),                       # header
    re.compile(r'^Colorado Public'),                         # header
    re.compile(r'^Nevada Public'),                           # header
    re.compile(r'^Texas Public'),                            # header
    re.compile(r'^SCHACTER_RECON_5\s+\d'),                   # footer (with date/page)
    re.compile(r'^-----'),                                   # subsection dividers
    re.compile(r'^----'),                                    # subsection dividers
    re.compile(r'^Dwelling\s*$'),                            # area grouping
    re.compile(r'^Exterior\s*$'),                            # area grouping
    re.compile(r'^Line Item Totals:'),                       # grand total footer
    re.compile(r'^Additional Charges'),                      # charges section
]


def should_skip(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    for pat in SKIP_PATTERNS:
        if pat.match(s):
            return True
    return False


def parse_amount(s: str) -> float:
    return float(s.replace(',', ''))


def extract_sections_from_pdf(pdf_path: str) -> list:
    """
    Extract all 29 sections and their line items from the BSchacter PDF.

    Strategy:
    1. Collect all raw lines from all pages.
    2. Process line-by-line tracking:
       - CONTINUED - X  -> sets current_section to X (if X in KNOWN_SECTIONS)
       - DESCRIPTION QTY RESET... -> sets in_table = True
       - Totals: X -> stores section totals, clears current_section
       - Total: X  -> area aggregate, clears state only
       - N. Description ... TOTAL -> line item (if in_table and current_section)
       - Otherwise: check if it's a known section name acting as header
         (followed within 3 non-empty lines by DESCRIPTION QTY header)
    """
    all_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                for line in text.split('\n'):
                    all_lines.append((page_num + 1, line.rstrip()))

    sections = {}        # section_name -> {"line_items": [...], "section_totals": {...}}
    section_order = []   # preserve insertion order

    current_section = None
    in_table = False
    pending_section = None   # section name found as header, waiting for DESCRIPTION row

    i = 0
    while i < len(all_lines):
        page_num, raw_line = all_lines[i]
        line = raw_line.strip()

        if not line:
            i += 1
            continue

        if should_skip(line):
            i += 1
            continue

        # ── Area aggregate total (singular Total:) ───────────────────────────
        # Some of these are true area aggregates (Dwelling, Exterior) but some
        # (Main Level, Other Structures) are real sections in KNOWN_SECTIONS.
        m_area = AREA_TOTAL_ROW.match(line)
        if m_area:
            sec_name = m_area.group(1).strip()
            if sec_name in KNOWN_SECTIONS:
                # Only set totals if not already set (first occurrence = section total,
                # later occurrences = area aggregate in recap pages — don't overwrite)
                if sec_name not in sections:
                    sections[sec_name] = {"line_items": []}
                    section_order.append(sec_name)

                if "section_totals" not in sections[sec_name]:
                    tax = parse_amount(m_area.group(2))
                    op = parse_amount(m_area.group(3))
                    total = parse_amount(m_area.group(4))

                    computed = sum(
                        (item.get("total") or 0.0)
                        for item in sections[sec_name]["line_items"]
                    )

                    sections[sec_name]["section_totals"] = {
                        "tax": tax,
                        "op": op,
                        "total": total,
                        "computed_total": round(computed, 2),
                        "validation_delta": round(total - computed, 2),
                    }

            # Either way, reset state
            current_section = None
            in_table = False
            pending_section = None
            i += 1
            continue

        # ── Continued-section marker ──────────────────────────────────────────
        m = CONTINUED_ROW.match(line)
        if m:
            sec_name = m.group(1).strip()
            if sec_name in KNOWN_SECTIONS:
                current_section = sec_name
                if current_section not in sections:
                    sections[current_section] = {"line_items": []}
                    section_order.append(current_section)
            else:
                current_section = None
            pending_section = None
            in_table = False
            i += 1
            continue

        # ── Column header row ─────────────────────────────────────────────────
        if HEADER_ROW.match(line):
            in_table = True
            if pending_section is not None:
                current_section = pending_section
                if current_section not in sections:
                    sections[current_section] = {"line_items": []}
                    section_order.append(current_section)
                pending_section = None
            # If current_section is None here, items following will be attributed
            # to the section that owns this table (determined by Totals: row).
            # We handle this via "orphan item" logic below.
            i += 1
            continue

        # ── Section totals ────────────────────────────────────────────────────
        m = TOTALS_ROW.match(line)
        if m:
            sec_name = m.group(1).strip()
            tax = parse_amount(m.group(2))
            op = parse_amount(m.group(3))
            total = parse_amount(m.group(4))

            if sec_name not in sections:
                sections[sec_name] = {"line_items": []}
                section_order.append(sec_name)

            computed = sum(
                (item.get("total") or 0.0)
                for item in sections[sec_name]["line_items"]
            )

            sections[sec_name]["section_totals"] = {
                "tax": tax,
                "op": op,
                "total": total,
                "computed_total": round(computed, 2),
                "validation_delta": round(total - computed, 2),
            }
            current_section = None
            in_table = False
            pending_section = None
            i += 1
            continue

        # ── Line items (numeric amounts) ──────────────────────────────────────
        # Match line items regardless of in_table state — some pages have garbled
        # DESCRIPTION headers that don't match HEADER_ROW, but the line items
        # themselves are identifiable by their N. Description ... TAX O&P TOTAL pattern.
        m = LINE_ITEM.match(line)
        if m:
            item_num = int(m.group(1))
            desc_raw = m.group(2).strip()
            tax = parse_amount(m.group(3))
            op = parse_amount(m.group(4))
            total = parse_amount(m.group(5))

            target = current_section
            if target is None:
                # Orphan item: look ahead for next Totals: row to find section name
                for j in range(i + 1, min(i + 200, len(all_lines))):
                    nl = all_lines[j][1].strip()
                    tm = TOTALS_ROW.match(nl)
                    if tm:
                        target = tm.group(1).strip()
                        if target not in sections:
                            sections[target] = {"line_items": []}
                            section_order.append(target)
                        current_section = target
                        break
                    if AREA_TOTAL_ROW.match(nl):
                        break

            if target:
                if target not in sections:
                    sections[target] = {"line_items": []}
                    section_order.append(target)
                sections[target]["line_items"].append({
                    "item_number": item_num,
                    "description": desc_raw,
                    "tax": tax,
                    "op": op,
                    "total": total,
                })
            i += 1
            continue

        # ── BID/ATTEMPT items (no dollar amounts) ─────────────────────────────
        # Same as LINE_ITEM — match regardless of in_table state
        m = BID_ITEM.match(line)
        if m:
            item_num = int(m.group(1))
            desc_raw = m.group(2).strip()

            target = current_section
            if target is None:
                for j in range(i + 1, min(i + 200, len(all_lines))):
                    nl = all_lines[j][1].strip()
                    tm = TOTALS_ROW.match(nl)
                    if tm:
                        target = tm.group(1).strip()
                        if target not in sections:
                            sections[target] = {"line_items": []}
                            section_order.append(target)
                        current_section = target
                        break
                    if AREA_TOTAL_ROW.match(nl):
                        break

            if target:
                if target not in sections:
                    sections[target] = {"line_items": []}
                    section_order.append(target)
                sections[target]["line_items"].append({
                    "item_number": item_num,
                    "description": desc_raw,
                    "tax": None,
                    "op": None,
                    "total": None,
                    "_note": "Bid-priced item — amounts not in PDF",
                })
            i += 1
            continue

        # ── Section header detection ──────────────────────────────────────────
        # Accept line as section header only if it's in KNOWN_SECTIONS
        # AND the next non-empty non-skip line is the DESCRIPTION QTY header
        if not in_table and line in KNOWN_SECTIONS:
            j = i + 1
            next_line = None
            while j < len(all_lines):
                nl = all_lines[j][1].strip()
                if nl and not should_skip(nl):
                    next_line = nl
                    break
                j += 1

            if next_line and HEADER_ROW.match(next_line):
                pending_section = line
                i += 1
                continue

        i += 1

    # Build ordered section list — only include KNOWN_SECTIONS
    result = []
    for name in section_order:
        if name not in KNOWN_SECTIONS:
            continue
        sec_data = sections[name]
        entry = {
            "section_name": name,
            "section_totals": sec_data.get("section_totals", {
                "tax": None,
                "op": None,
                "total": None,
                "computed_total": None,
                "validation_delta": "N/A - no totals row found",
            }),
            "line_items": sec_data["line_items"],
        }
        result.append(entry)

    return result


def build_golden_master() -> dict:
    """Load parser audit JSON, integrate extracted sections, return golden master dict."""
    print(f"Loading parser audit JSON: {PARSER_JSON}")
    with open(PARSER_JSON, encoding='utf-8') as f:
        parser_data = json.load(f)

    print(f"Extracting sections from PDF: {PDF_PATH}")
    sections = extract_sections_from_pdf(PDF_PATH)
    print(f"  Extracted {len(sections)} sections")
    for s in sections:
        n_items = len(s["line_items"])
        total = s["section_totals"].get("total", "?")
        delta = s["section_totals"].get("validation_delta", "?")
        bid_items = sum(1 for item in s["line_items"] if item.get("total") is None)
        note = f" ({bid_items} bid/attempt-priced)" if bid_items else ""
        print(f"    - {s['section_name']}: {n_items} items{note}, total=${total}, delta={delta}")

    # Build the golden master: parser data as base, sections from PDF extraction
    golden = {
        "estimate_name": "SCHACTER_RECON_5",  # internal name from PDF text
        "case_metadata": parser_data.get("case_metadata", {}),
        "sections": sections,
        "grand_total_areas": parser_data.get("grand_total_areas", {}),
        "coverage": parser_data.get("coverage", {}),
        "recaps_and_summaries": parser_data.get("recaps_and_summaries", {}),
        "validations": parser_data.get("validations", {}),
        "_extraction_note": (
            "Sections and line items extracted from PDF text using pdfplumber "
            "(production parser returns 0 sections — column schema mismatch). "
            "Items with null tax/op/total use PER BID / SEE BID / ATTEMPT CLEAN "
            "pricing; amounts not present in the PDF text for these items. "
            "estimate_name corrected from filename fallback to internal PDF value "
            "'SCHACTER_RECON_5'. "
            "All other fields (case_metadata, grand_total_areas, coverage, "
            "recaps_and_summaries) taken from production parser audit output which "
            "correctly captures these sections."
        ),
    }

    return golden


def main():
    golden = build_golden_master()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(golden, f, indent=2, ensure_ascii=False)

    print(f"\nWrote golden master: {OUTPUT_PATH}")
    print(f"  Sections: {len(golden['sections'])}")
    total_items = sum(len(s['line_items']) for s in golden['sections'])
    print(f"  Total line items: {total_items}")

    # Quick validation
    print("\n=== Validation ===")
    print(f"estimate_name: {golden['estimate_name']}")
    print(f"grand_total from case_metadata: "
          f"{golden['case_metadata'].get('line_item_totals', {}).get('grand_total')}")
    print(f"grand_total_areas populated: {bool(golden['grand_total_areas'])}")
    print(f"recaps populated: {bool(golden['recaps_and_summaries'])}")


if __name__ == "__main__":
    main()
