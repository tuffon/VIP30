"""
extract_statefarm.py

Extraction script for StateFarm golden masters.

Produces three golden master JSON files:
  - packages/parser/tests/golden/final-drafts/statefarm/customer_copy.golden.json
  - packages/parser/tests/golden/final-drafts/statefarm/lachman_sf.golden.json
  - packages/parser/tests/golden/final-drafts/statefarm/kalyvas_sf.golden.json

Strategy:
- Start from parser audit output (which correctly captures section structure)
- Use pdfplumber to extract missing line items for delta sections
- For sections the parser already extracted correctly: keep parser line_items as-is
- When extracted count < parser count: keep parser items (they cover more of the section)
- Document extraction gaps in _extraction_note fields
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

PARSER_DIR = os.path.join(ROOT, "packages", "parser", "audit_output", "final-drafts", "statefarm")
PDF_DIR = os.path.join(ROOT, "docs", "final-drafts", "statefarm")
OUTPUT_DIR = os.path.join(ROOT, "packages", "parser", "tests", "golden", "final-drafts", "statefarm")

FILES = {
    "customer_copy": {
        "parser_json": os.path.join(PARSER_DIR, "Customer Copy Final Draft (3).json"),
        "pdf": os.path.join(PDF_DIR, "Customer Copy Final Draft (3).pdf"),
        "output": os.path.join(OUTPUT_DIR, "customer_copy.golden.json"),
        "expected_sections": 31,
        "col_format": "3col",   # DESCRIPTION QUANTITY UNIT PRICE TAX GCO&P RCV
    },
    "lachman_sf": {
        "parser_json": os.path.join(PARSER_DIR, "Estimate SF Structural damage Lachman 4.15.2025.json"),
        "pdf": os.path.join(PDF_DIR, "Estimate SF Structural damage Lachman 4.15.2025.pdf"),
        "output": os.path.join(OUTPUT_DIR, "lachman_sf.golden.json"),
        "expected_sections": 34,
        "col_format": "2col",   # DESCRIPTION QUANTITY UNIT PRICE TAX RCV
    },
    "kalyvas_sf": {
        "parser_json": os.path.join(PARSER_DIR, "Kalyvas Preliminary State Farm estimate9-25-25.json"),
        "pdf": os.path.join(PDF_DIR, "Kalyvas Preliminary State Farm estimate9-25-25.pdf"),
        "output": os.path.join(OUTPUT_DIR, "kalyvas_sf.golden.json"),
        "expected_sections": 36,
        "col_format": "3col",   # DESCRIPTION QUANTITY UNIT PRICE TAX GCO&P RCV
    },
}

# Delta sections that need PDF extraction (parser output is incorrect/incomplete).
# For customer_copy: None = try all sections with delta > 0.
DELTA_SECTIONS = {
    "lachman_sf": ["Office Bath", "Master Bathroom", "Linen Closet", "PRC RESTORATION INC."],
    "kalyvas_sf": ["Guest Bedroom", "ROOF1", "Ext_Surfaces", "Hardscapes and walkways"],
    "customer_copy": None,
}

# ─── regex patterns ───────────────────────────────────────────────────────────

HEADER_ROW_ANY = re.compile(r'^DESCRIPTION\w*\s+QUANTITY\s+UNIT\s+PRICE')

TOTALS_3 = re.compile(
    r'^Totals:\s+(.+?)\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s*$'
)
TOTALS_2 = re.compile(
    r'^Totals:\s+(.+?)\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s*$'
)

CONTINUED_ROW = re.compile(r'^CONTINUED\s+-\s+(.+)$')

# Area total (singular) — used to end sections that use "Total:" instead of "Totals:"
AREA_TOTAL = re.compile(
    r'^Total:\s+(.+?)\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s*$'
)

# All StateFarm PDFs have 3 trailing numbers (PRICE/TAX/GCO&P then RCV — last one is always RCV).
# Pattern: "N. Description ... NUM NUM NUM" (last 3 numbers, capturing all 3)
# Handles asterisk prices (33.92*) and EN-suffixed amounts (14,137.76*EN)
LINE_ITEM_3 = re.compile(
    r'^(\d+)\.\s+(.+?)\s+([\d,]+\.[\d]{2}[\w*]*)\s+([\d,]+\.[\d]{2})\s+([\d,]+\.[\d]{2})\s*$'
)

# Also try a simpler pattern: just needs to end with one clean number (the RCV)
# For items where only one trailing number is visible (edge cases)
LINE_ITEM_1 = re.compile(
    r'^(\d+)\.\s+(.+?)\s+([\d,]+\.[\d]{2})\s*$'
)

# Garbled text (doubled characters from floor plan diagrams)
GARBLED = re.compile(r'([A-Za-z])\1([A-Za-z])\2')

SKIP_PATTERNS = [
    re.compile(r'^\d+$'),
    re.compile(r'^State Farm$'),
    re.compile(r'^Date:\s+\d'),
    re.compile(r'^Area Totals:'),
    re.compile(r'^Total:\s+'),
]


def should_skip(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    for pat in SKIP_PATTERNS:
        if pat.match(s):
            return True
    # Skip garbled floor plan text
    if GARBLED.search(s) and len(s) > 10:
        return True
    return False


def parse_amount(s: str) -> float:
    cleaned = re.sub(r'[*ENen]', '', s).replace(',', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def extract_all_lines(pdf_path: str) -> list:
    """Extract all (page_num, line) tuples from PDF."""
    all_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                for line in text.split('\n'):
                    all_lines.append((page_num + 1, line.rstrip()))
    return all_lines


def extract_section_items(all_lines: list, section_name: str, col_format: str,
                          occurrence: int = 0) -> list:
    """
    Extract line items for a specific section from PDF.

    Searches CONTINUED markers and section headers for the given section_name.
    Returns list of item dicts, deduplicated by item number within the occurrence.

    col_format is accepted for API compatibility but all StateFarm PDFs use
    LINE_ITEM_3 (3 trailing numbers, last = RCV).

    occurrence: 1-based index selecting which occurrence of the section to extract.
                0 (default) means extract all occurrences combined.
    """
    items_by_num = {}   # item_number -> dict
    item_order = []

    in_section = False
    occurrence_count = 0   # how many times we've entered this section

    i = 0
    while i < len(all_lines):
        page_num, raw_line = all_lines[i]
        line = raw_line.strip()

        if not line:
            i += 1
            continue

        # Check for end of this section (Totals: or Total: for this section only)
        tm3 = TOTALS_3.match(line)
        tm2 = TOTALS_2.match(line)
        area_m = AREA_TOTAL.match(line)
        totals_m = tm3 or tm2 or area_m
        if totals_m and in_section:
            sec = totals_m.group(1).strip()
            if sec == section_name:
                in_section = False
                # If we were targeting a specific occurrence and we've found it,
                # we can stop scanning early.
                if occurrence > 0 and occurrence_count == occurrence:
                    break
                i += 1
                continue

        # CONTINUED marker
        cont_m = CONTINUED_ROW.match(line)
        if cont_m and cont_m.group(1).strip() == section_name:
            in_section = True
            i += 1
            continue

        # Section header (just the name) — only detect if NOT garbled
        if not in_section and line.strip() == section_name and not GARBLED.search(line):
            # Look ahead for DESCRIPTION header.
            # Window is large (100 lines) to handle pages with many annotations between
            # the section header and the DESCRIPTION row (e.g. Ext_Surfaces in Kalyvas).
            j = i + 1
            found_header = False
            while j < len(all_lines) and j < i + 100:
                nl = all_lines[j][1].strip()
                if nl and HEADER_ROW_ANY.match(nl):
                    found_header = True
                    break
                if nl:
                    # Stop looking if we hit a section-terminating pattern
                    if TOTALS_3.match(nl) or TOTALS_2.match(nl) or AREA_TOTAL.match(nl):
                        break
                    if CONTINUED_ROW.match(nl):
                        # The section continues on this page via CONTINUED marker — let
                        # the main loop handle it; do NOT enter section here.
                        break
                j += 1
            if found_header:
                occurrence_count += 1
                # If targeting specific occurrence, skip this occurrence entirely.
                # Scan forward to the Totals:/Total: end-of-section marker so the
                # main loop doesn't re-fire on duplicate section-name lines that
                # immediately follow (StateFarm often prints the section name twice).
                if occurrence > 0 and occurrence_count != occurrence:
                    # Advance i past the end of this section
                    k = i + 1
                    while k < len(all_lines):
                        nl = all_lines[k][1].strip()
                        tm3k = TOTALS_3.match(nl)
                        tm2k = TOTALS_2.match(nl)
                        atk = AREA_TOTAL.match(nl)
                        end_m = tm3k or tm2k or atk
                        if end_m and end_m.group(1).strip() == section_name:
                            i = k  # position just BEFORE the end line; main loop will advance
                            break
                        k += 1
                    else:
                        i += 1   # fallback if no end found
                    continue
                in_section = True
                i += 1
                continue

        # Column header — skip (just advance)
        if in_section and HEADER_ROW_ANY.match(line):
            i += 1
            continue

        # Line item matching — LINE_ITEM_3 for all StateFarm formats.
        # All SF PDFs have 3 trailing numbers; last one is always RCV.
        if in_section:
            m = LINE_ITEM_3.match(line)
            if m:
                item_num = int(m.group(1))
                desc = m.group(2).strip()

                # Groups 3, 4, 5 are the last three numbers on the line.
                # For 3-col (GCO&P) PDFs: TAX, GCO&P, RCV
                # For 2-col PDFs:         PRICE, TAX, RCV
                # In both cases group 5 = RCV (total).
                tax = parse_amount(m.group(3))
                op = parse_amount(m.group(4))
                total = parse_amount(m.group(5))

                if item_num not in items_by_num:
                    items_by_num[item_num] = {
                        "item_number": item_num,
                        "description": desc,
                        "tax": tax,
                        "op": op,
                        "total": total,
                    }
                    item_order.append(item_num)

        i += 1

    return [items_by_num[n] for n in item_order]


def _item_key(item: dict) -> int:
    """
    Return the canonical item number for a line item dict.

    Parser items use 'line_number' (int); PDF-extracted items use 'item_number' (int).
    Both refer to the same sequence number printed on the estimate line.
    """
    n = item.get("item_number")
    if n is not None:
        return int(n)
    n = item.get("line_number")
    if n is not None:
        return int(n)
    return id(item)  # fallback for header/non-line-item parser records


def merge_items(parser_items: list, pdf_items: list) -> tuple:
    """
    Merge parser items and PDF-extracted items, deduplicating by item number.
    Returns (merged_list, source_description).

    Parser items may include header/subheader dicts (no item number) from the
    Xactimate parser — these are passed through as-is.

    Deduplication: parser line_items and PDF items are matched by their shared
    sequence number (parser['line_number'] == pdf['item_number']).  When both
    cover the same item number the PDF version wins (has qty/unit in description).

    The merged list always starts with the full parser item list (preserving
    headers and non-line-item rows), then appends PDF-only items at the end.
    """
    if not pdf_items:
        return parser_items, "parser only"

    if not parser_items:
        return pdf_items, "pdf only"

    # Build a set of item numbers covered by PDF extraction
    pdf_by_num = {}
    for item in pdf_items:
        n = _item_key(item)
        pdf_by_num[n] = item

    # Walk parser items; replace each line item that PDF also covers
    merged = []
    parser_line_nums = set()
    for item in parser_items:
        if item.get("type") in ("line_item",) or "line_number" in item:
            n = _item_key(item)
            parser_line_nums.add(n)
            if n in pdf_by_num:
                merged.append(pdf_by_num[n])   # PDF version wins
            else:
                merged.append(item)
        else:
            # Header / sub-header rows — pass through unchanged
            merged.append(item)

    # Append PDF items whose item numbers weren't in the parser list
    for item in pdf_items:
        n = _item_key(item)
        if n not in parser_line_nums:
            merged.append(item)

    # Count only true line items for source description
    n_pdf_lines = len(pdf_items)
    n_parser_lines = len([it for it in parser_items if "line_number" in it or it.get("type") == "line_item"])

    if n_pdf_lines >= n_parser_lines:
        src = f"pdf ({n_pdf_lines}) >= parser ({n_parser_lines}) — merged, PDF wins"
    else:
        src = f"pdf ({n_pdf_lines}) < parser ({n_parser_lines}) — merged, parser base"

    return merged, src


def build_sf_golden(file_key: str, cfg: dict) -> dict:
    """Build a StateFarm golden master for the given file."""
    print(f"\n{'='*60}")
    print(f"Building: {file_key}")

    with open(cfg["parser_json"], encoding='utf-8') as f:
        parser_data = json.load(f)

    sections = [dict(s) for s in parser_data.get("sections", [])]
    col_format = cfg["col_format"]
    delta_sections = DELTA_SECTIONS.get(file_key)

    all_lines = extract_all_lines(cfg["pdf"])
    print(f"  Parser: {len(sections)} sections, col_format={col_format}")

    extraction_gaps = []
    extraction_results = {}

    if delta_sections is None:
        # Customer Copy: try all sections with delta > 0.5
        target_sections = []
        for sec in sections:
            totals = sec.get("section_totals", {})
            delta = totals.get("validation_delta", 0)
            try:
                delta_f = abs(float(str(delta).replace(',', '')))
            except Exception:
                delta_f = 0.0
            if delta_f > 0.5:
                target_sections.append(sec["section_name"])
    else:
        target_sections = delta_sections

    # Track which section names have been processed (for duplicates)
    processed_sections = {}  # section_name -> count of occurrences processed

    for sec in sections:
        name = sec["section_name"]
        processed_sections[name] = processed_sections.get(name, 0) + 1
        occurrence = processed_sections[name]

        if name in target_sections:
            parser_items = sec.get("line_items", [])
            pdf_items = extract_section_items(all_lines, name, col_format,
                                              occurrence=occurrence)

            merged, src = merge_items(parser_items, pdf_items)

            if len(merged) > len(parser_items):
                sec["line_items"] = merged
                extraction_results[f"{name}#{occurrence}"] = (
                    f"{len(merged)} items ({src})"
                )
                print(f"  + {name}#{occurrence}: {len(parser_items)}->{len(merged)} ({src})")
            elif len(merged) == len(parser_items) and pdf_items:
                # Same count — still merge to pick up PDF quality descriptions
                sec["line_items"] = merged
                print(f"  ~ {name}#{occurrence}: {len(merged)} items (merged, same count)")
            else:
                extraction_gaps.append(f"{name}#{occurrence}")
                print(f"  - {name}#{occurrence}: kept {len(parser_items)} parser items "
                      f"(pdf got {len(pdf_items)})")
        else:
            n_items = len(sec.get("line_items", []))
            if n_items > 0:
                print(f"  = {name}#{occurrence}: {n_items} parser items kept (no delta)")

    # Build note
    if extraction_gaps:
        note = (
            f"StateFarm golden master ({file_key}). "
            f"Section structure from parser output. "
            f"Line items supplemented via pdfplumber for delta sections where possible. "
            f"Sections still requiring v2.5 parser fix: {extraction_gaps}. "
            f"Sections improved: {list(extraction_results.keys())}."
        )
    else:
        note = (
            f"StateFarm golden master ({file_key}). "
            f"Section structure from parser output. "
            f"All delta sections supplemented via pdfplumber extraction."
        )

    golden = {
        "estimate_name": parser_data.get("estimate_name", ""),
        "case_metadata": parser_data.get("case_metadata", {}),
        "sections": sections,
        "grand_total_areas": parser_data.get("grand_total_areas", {}),
        "coverage": parser_data.get("coverage", {}),
        "recaps_and_summaries": parser_data.get("recaps_and_summaries", {}),
        "validations": parser_data.get("validations", {}),
        "_extraction_note": note,
    }

    return golden


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for file_key, cfg in FILES.items():
        golden = build_sf_golden(file_key, cfg)

        with open(cfg["output"], 'w', encoding='utf-8') as f:
            json.dump(golden, f, indent=2, ensure_ascii=False)

        secs = golden["sections"]
        total_items = sum(len(s.get("line_items", [])) for s in secs)
        print(f"\nWrote: {cfg['output']}")
        print(f"  Sections: {len(secs)} (expected {cfg['expected_sections']})")
        print(f"  Total items: {total_items}")

    # Final verification
    print("\n=== Final Verification ===")
    expected_counts = {
        "customer_copy.golden.json": 31,
        "lachman_sf.golden.json": 34,
        "kalyvas_sf.golden.json": 36,
    }
    for fname, exp_sec in expected_counts.items():
        fpath = os.path.join(OUTPUT_DIR, fname)
        with open(fpath, encoding='utf-8') as f:
            d = json.load(f)
        sec = len(d.get("sections", []))
        items = sum(len(s.get("line_items", [])) for s in d.get("sections", []))
        status = "OK" if sec == exp_sec else f"MISMATCH (expected {exp_sec})"
        print(f"  {fname}: sections={sec} [{status}], items={items}")


if __name__ == "__main__":
    main()
