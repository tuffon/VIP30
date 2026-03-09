"""
rebuild_sf_bschacter_golden.py
-------------------------------
Rebuilds the SF_BSchacter golden master from the source PDF with complete line item extraction.

Approach: anchor on "Totals: SectionName TAX GCO&P RCV" markers (reliable clean text),
extract line items from the block of text preceding each Totals marker.

Run from project root:
    python packages/parser/scripts/rebuild_sf_bschacter_golden.py
"""

import io
import json
import re
import sys
from pathlib import Path

import pdfplumber

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
PDF_PATH = ROOT / "docs/final-drafts/statefarm/SF_BSchacter.pdf"
OLD_GOLDEN = ROOT / "packages/parser/tests/golden/final-drafts/statefarm/SF_BSchacter.golden.json"
NEW_GOLDEN = ROOT / "packages/parser/tests/golden/final-drafts/statefarm/SF_BSchacter.golden.json"

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# End-of-section marker: "Totals: SectionName  TAX  GCO&P  RCV"
# Also matches "Total:" (singular) which some sections use instead of "Totals:"
TOTALS_RE = re.compile(
    r'Totals?:\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})'
)

# Area total markers — "Total: X" preceded by "Area Totals: X" is a roll-up, not a section total
AREA_TOTALS_PREFIX_RE = re.compile(r'Area Totals?:\s+\S')

# Standard line item line: "174. HEPA Vacuuming - 148.24SF 1.20* 0.00 35.58 213.47"
# Also handles: "* 336. Fire ... 2,049.00*E 0.00 409.80 2,458.80"
ITEM_RE = re.compile(
    r'^\*?\s*(\d+)\.\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$'
)

# REVISED / PER ESTIMATE items (no numeric total — excluded from section total)
REVISED_RE = re.compile(
    r'^\*?\s*(\d+)\.\s+(.+?)\s+(?:REVISED|PER ESTIMATE|PER EST\.?)\s*$',
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def get_full_text(pdf_path):
    """Extract all text from the PDF as a single string."""
    parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Section extraction: anchor on Totals: markers
# ---------------------------------------------------------------------------

def extract_sections(full_text):
    """
    Find all Totals: markers. For each, extract line items from the text block
    that precedes that marker (back to the previous Totals: marker or start of text).

    Returns list of dicts:
      {name, declared_tax, declared_op, declared_total, items}
    """
    # Find all Totals:/Total: positions, filtering out area roll-up totals
    totals_spans = []
    for m in TOTALS_RE.finditer(full_text):
        # Check if preceded by "Area Totals:" within 300 chars — if so, it's a roll-up
        preceding = full_text[max(0, m.start() - 300):m.start()]
        if AREA_TOTALS_PREFIX_RE.search(preceding):
            continue  # skip area roll-up totals
        totals_spans.append((m.start(), m.end(), m))

    if not totals_spans:
        return []

    sections = []

    for i, (start, end, m) in enumerate(totals_spans):
        sec_name = m.group(1).strip()
        declared_tax = m.group(2).replace(",", "")
        declared_op = m.group(3).replace(",", "")
        declared_total = m.group(4).replace(",", "")

        # Block of text preceding this Totals: marker (back to previous Totals: end)
        block_start = totals_spans[i - 1][1] if i > 0 else 0
        block = full_text[block_start:start]

        items = parse_items_from_block(block)

        sections.append({
            "name": sec_name,
            "declared_tax": declared_tax,
            "declared_op": declared_op,
            "declared_total": declared_total,
            "items": items,
        })

    return sections


def parse_items_from_block(block):
    """
    Parse line items from a text block.
    Returns list of item dicts.
    """
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
    items = []
    pending = None  # accumulates multi-line description

    for line in lines:
        # Skip table header
        if line.startswith("DESCRIPTION") and "QUANTITY" in line:
            continue
        # Skip State Farm page header lines
        if re.match(r'^(?:State Farm|SCHACTER,|Insured:|Property:|Claim |Price List:|Type of|Deductible:|Date[ :])|\d{1,2}/\d{1,2}/\d{4}', line):
            continue
        # Skip plain page numbers
        if re.match(r'^\d{1,3}$', line):
            continue
        # Skip section category headers like "**CLEANING**"
        if re.match(r'^\*{1,2}[A-Z][A-Z /&]+\*{0,2}$', line):
            continue
        # Skip "CONTINUED - ..." lines
        if re.match(r'^CONTINUED\s*[-–]', line):
            continue

        # Try to match a line item
        item_m = ITEM_RE.match(line)
        if item_m:
            # Finalize any pending multi-line item
            if pending is not None:
                items.append(pending)
            num = int(item_m.group(1))
            desc = item_m.group(2).strip()
            tax = float(item_m.group(3).replace(",", ""))
            op = float(item_m.group(4).replace(",", ""))
            total = float(item_m.group(5).replace(",", ""))
            pending = {
                "item_number": num,
                "description": desc,
                "tax": tax,
                "op": op,
                "total": total,
                "_desc_lines": [desc],
            }
            continue

        # REVISED / PER ESTIMATE
        rev_m = REVISED_RE.match(line)
        if rev_m:
            if pending is not None:
                items.append(pending)
            num = int(rev_m.group(1))
            desc = rev_m.group(2).strip()
            pending = {
                "item_number": num,
                "description": desc,
                "tax": 0.0,
                "op": 0.0,
                "total": 0.0,
                "note": "REVISED/PER ESTIMATE",
                "_desc_lines": [desc],
            }
            continue

        # Description continuation for pending item?
        if pending is not None:
            # Continuation: not a new item pattern and not noise
            # Skip noise (dimension lines, door/window specs, doubled characters)
            if re.match(r'^[\d.]+\s+(?:SF|LF|EA|CF)|^\d+[\'"]|^[A-Z]{2,}\s+[A-Z]{2,}|'
                        r'^Door|^Window|^Missing Wall|^\d+\.\d{2}\s', line):
                continue
            # Also skip doubled-character OCR artifacts (like "HHaallll")
            if re.search(r'(.)\1{2,}', line):  # 3+ repeated chars = OCR artifact
                continue
            # Looks like a real description continuation
            pending["_desc_lines"].append(line)
            pending["description"] = " ".join(pending["_desc_lines"])
            continue

    # Finalize last pending item
    if pending is not None:
        items.append(pending)

    # Clean up internal tracking field
    for item in items:
        item.pop("_desc_lines", None)

    return items


# ---------------------------------------------------------------------------
# Merge into golden master
# ---------------------------------------------------------------------------

def merge_into_golden(sections, existing_data):
    """
    Merge extracted sections into existing golden master.
    Updates line_items and recomputes validation_delta using sum(total).
    """
    # Build lookup: (name, declared_total) -> extracted section
    # Primary key includes declared_total to disambiguate duplicate section names (e.g. two "Main Level")
    extracted_by_name_total = {}
    extracted_by_name = {}  # fallback: name only
    for sec in sections:
        name = sec["name"]
        declared = sec.get("declared_total", "")
        extracted_by_name_total[(name, declared)] = sec
        # For name-only fallback, prefer the section with more items
        if name not in extracted_by_name or len(sec["items"]) > len(extracted_by_name[name]["items"]):
            extracted_by_name[name] = sec

    name_key = "section_name"
    updated_sections = []

    # Track which golden master sections we've matched
    for gm_sec in existing_data.get("sections", []):
        sec_name = gm_sec.get(name_key, gm_sec.get("name", ""))
        gm_declared = str((gm_sec.get("section_totals") or {}).get("total", "")).replace(",", "")
        # Try exact (name, declared_total) match first, then fall back to name only
        ext = extracted_by_name_total.get((sec_name, gm_declared)) or extracted_by_name.get(sec_name)

        if ext and ext["items"]:
            # Only replace if extracted has more items or better totals
            existing_items = gm_sec.get("line_items", [])
            extracted_items = ext["items"]

            # Compute sums
            existing_sum = sum(
                float(str(i.get("total", 0)).replace(",", ""))
                for i in existing_items
            )
            extracted_sum = sum(i.get("total", 0) for i in extracted_items)

            try:
                declared = float(str(
                    (gm_sec.get("section_totals") or {}).get("total", "0")
                ).replace(",", ""))
            except (ValueError, TypeError):
                declared = 0.0

            existing_delta = abs(declared - existing_sum)
            extracted_delta = abs(declared - extracted_sum)

            if extracted_delta < existing_delta or len(extracted_items) > len(existing_items):
                # Extracted is better — use it
                new_items = []
                for item in extracted_items:
                    new_items.append({
                        "item_number": item["item_number"],
                        "description": item["description"],
                        "tax": item["tax"],
                        "op": item["op"],
                        "total": item["total"],
                    })
                    if item.get("note"):
                        new_items[-1]["note"] = item["note"]
                gm_sec["line_items"] = new_items

        # Recompute validation_delta from sum(total)
        items = gm_sec.get("line_items", [])
        item_sum = 0.0
        for item in items:
            try:
                item_sum += float(str(item.get("total", 0)).replace(",", ""))
            except (ValueError, TypeError):
                pass

        totals = gm_sec.get("section_totals") or {}
        try:
            declared = float(str(totals.get("total", "0")).replace(",", ""))
        except (ValueError, TypeError):
            declared = 0.0

        delta = round(declared - item_sum, 2)
        totals["computed_total"] = round(item_sum, 2)
        totals["validation_delta"] = f"{delta:.2f}"
        gm_sec["section_totals"] = totals
        updated_sections.append(gm_sec)

    existing_data["sections"] = updated_sections
    return existing_data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("Rebuilding SF_BSchacter golden master from PDF")
    print("=" * 65)

    # Load existing golden master
    with open(OLD_GOLDEN, encoding="utf-8") as f:
        existing_data = json.load(f)

    existing_sections = existing_data.get("sections", [])
    existing_total = sum(len(s.get("line_items", [])) for s in existing_sections)
    print(f"\nExisting: {len(existing_sections)} sections, {existing_total} items")

    # Extract from PDF
    print(f"Extracting from: {PDF_PATH.name}")
    full_text = get_full_text(PDF_PATH)
    sections = extract_sections(full_text)

    print(f"\nExtracted {len(sections)} section blocks:")
    for sec in sections:
        items = sec["items"]
        item_sum = sum(i.get("total", 0) for i in items)
        try:
            declared = float(sec.get("declared_total", "0").replace(",", ""))
        except Exception:
            declared = 0.0
        delta = abs(declared - item_sum)
        status = "ok" if delta < 0.05 else f"delta={delta:,.2f}"
        print(f"  {sec['name'][:40]:40} {len(items):4} items | "
              f"sum={item_sum:>12,.2f} | declared={sec['declared_total']:>12} | {status}")

    # Merge
    print("\nMerging into golden master...")
    updated = merge_into_golden(sections, existing_data)

    new_sections = updated.get("sections", [])
    new_total = sum(len(s.get("line_items", [])) for s in new_sections)

    # Write new file
    with open(NEW_GOLDEN, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {NEW_GOLDEN.name}")
    print(f"Sections: {len(new_sections)} | Items: {new_total} (was {existing_total})")

    # Verification
    print("\n--- Section Verification ---")
    verified = gaps = excluded = 0
    for sec in new_sections:
        name = sec.get("section_name", "?")
        items = sec.get("line_items", [])
        totals = sec.get("section_totals") or {}
        delta_str = totals.get("validation_delta", "0")
        declared_str = totals.get("total", "0.00")
        try:
            delta = abs(float(str(delta_str).replace(",", "")))
            declared = float(str(declared_str).replace(",", ""))
        except (ValueError, TypeError):
            delta = 0.0
            declared = 0.0

        if declared == 0.0:
            status = "EXCLUDED"
            excluded += 1
        elif delta < 0.05:
            status = "VERIFIED"
            verified += 1
        else:
            status = f"GAP {delta:,.2f}"
            gaps += 1
        print(f"  {name[:40]:40} {len(items):4} items  {status}")

    total_non_excl = verified + gaps
    pct = verified / total_non_excl * 100 if total_non_excl else 0
    print()
    print(f"  Verified: {verified}/{total_non_excl} ({pct:.0f}%)")
    print(f"  Gaps:     {gaps}")
    print(f"  Excluded: {excluded}")
    print()
    if gaps == 0:
        print("RESULT: ALL SECTIONS VERIFIED - golden master is complete")
    else:
        print(f"RESULT: {gaps} sections still have gaps")


if __name__ == "__main__":
    main()
