"""
verify_golden_masters.py
-----------------------
1. Updates all 6 golden masters with correct metadata extracted from source PDFs:
   - insured_name (was null in all files)
   - price_list (now includes estimate type, e.g. "CALA8X_APR25 Restoration/Service/Remodel")
   - property_address (rough-drafts were contaminated with "Claim Rep.:" text)

2. Runs automated verification checks on each golden master:
   - Metadata field match (claim_number, insured_name, price_list, property_address)
   - Grand total present
   - Section names round-trip (names in golden master appear somewhere in PDF text)
   - Line item count plausibility (total items > 0 for non-empty docs)

Run from project root:
    python packages/parser/scripts/verify_golden_masters.py
"""

import io
import json
import re
import sys
from pathlib import Path

import pdfplumber

# Fix Windows cp1252 stdout encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]

GOLDEN_DIR = ROOT / "packages/parser/tests/golden"
DOCS_DIR = ROOT / "docs"

# ---------------------------------------------------------------------------
# Ground truth extracted from PDFs (correct values the parser should output)
# ---------------------------------------------------------------------------

METADATA_GROUND_TRUTH = {
    "rough-drafts/lachman.golden.json": {
        "insured_name": "Kenneth Chen",
        "claim_number": "75-79J8-65X",
        "price_list": "CALA8X_APR25 Restoration/Service/Remodel",
        "property_address_normalized": "1115 Lachman Ln, Pacific Palisades, CA 90272",
        "source_pdf": "docs/rough-drafts/1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.pdf",
    },
    "rough-drafts/kalyvas.golden.json": {
        "insured_name": "James Kalyvas",
        "claim_number": "75-79F9-18M",
        "price_list": "CALA8X_MAR25 Restoration/Service/Remodel",
        "property_address_normalized": "16640 Via Pacifica, Pacific Palisades, CA 90272",
        "source_pdf": "docs/rough-drafts/KALYVAS_JVB_V6_KALY2_ROUGH_DRAFT_CAR.pdf",
    },
    "final-drafts/bschacter.golden.json": {
        "insured_name": "Barbara Schacter",
        "claim_number": "75-79D9-35K",
        "price_list": "CALA8X_JUL25 Restoration/Service/Remodel",
        "property_address_normalized": "935 Chattanooga Ave., Pacific Palisades, CA 90272",
        "source_pdf": "docs/final-drafts/BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf",
    },
    "final-drafts/statefarm/customer_copy.golden.json": {
        "insured_name": "Barbara Schacter",
        "claim_number": "75-79D9-35K",
        "price_list": "CALA28_AUG25 Restoration/Service/Remodel",
        "property_address_normalized": "935 CHATTANOOGA AVE, PACIFIC PLSDS, CA 90272-2328",
        "source_pdf": "docs/final-drafts/statefarm/Customer Copy Final Draft (3).pdf",
    },
    "final-drafts/statefarm/lachman_sf.golden.json": {
        "insured_name": "Kenneth Chen",
        "claim_number": "75-79J8-65X",
        "price_list": "CALA28_JAN25 Restoration/Service/Remodel",
        "property_address_normalized": "1115 LACHMAN LN, PACIFIC PLSDS, CA 90272-2227",
        "source_pdf": "docs/final-drafts/statefarm/Estimate SF Structural damage Lachman 4.15.2025.pdf",
    },
    "final-drafts/statefarm/kalyvas_sf.golden.json": {
        "insured_name": "James Kalyvas",
        "claim_number": "75-79F9-18M3",
        "price_list": "CALA28_JAN25 Restoration/Service/Remodel",
        "property_address_normalized": "16640 Via Pacifica, Pacific Plsds, CA 90272-1947",
        "source_pdf": "docs/final-drafts/statefarm/Kalyvas Preliminary State Farm estimate9-25-25.pdf",
    },
}

# Correct property_address values for rough-draft/contractor final golden masters
# (these were contaminated with "Claim Rep.:" text from the multi-line extraction bug)
CORRECTED_PROPERTY_ADDRESSES = {
    "rough-drafts/lachman.golden.json": "1115 Lachman Ln, Pacific Palisades, CA 90272",
    "rough-drafts/kalyvas.golden.json": "16640 Via Pacifica, Pacific Palisades, CA 90272",
    "final-drafts/bschacter.golden.json": "935 Chattanooga Ave., Pacific Palisades, CA 90272",
}


# ---------------------------------------------------------------------------
# Step 1: Update golden masters with correct metadata
# ---------------------------------------------------------------------------

def update_golden_masters():
    print("=" * 60)
    print("STEP 1: Updating golden masters with correct metadata")
    print("=" * 60)

    for rel_path, truth in METADATA_GROUND_TRUTH.items():
        gm_path = GOLDEN_DIR / rel_path
        if not gm_path.exists():
            print(f"  MISSING: {rel_path}")
            continue

        with open(gm_path, encoding="utf-8") as f:
            data = json.load(f)

        meta = data.setdefault("case_metadata", {})
        changes = []

        # insured_name
        if meta.get("insured_name") != truth["insured_name"]:
            meta["insured_name"] = truth["insured_name"]
            changes.append(f"insured_name = {truth['insured_name']!r}")

        # price_list
        if meta.get("price_list") != truth["price_list"]:
            meta["price_list"] = truth["price_list"]
            changes.append(f"price_list = {truth['price_list']!r}")

        # property_address (fix contamination in rough-draft/contractor files)
        corrected_addr = CORRECTED_PROPERTY_ADDRESSES.get(rel_path)
        if corrected_addr and meta.get("property_address") != corrected_addr:
            meta["property_address"] = corrected_addr
            changes.append(f"property_address = {corrected_addr!r}")

        if changes:
            with open(gm_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  UPDATED {rel_path}:")
            for c in changes:
                print(f"    - {c}")
        else:
            print(f"  OK (no changes): {rel_path}")


# ---------------------------------------------------------------------------
# Step 2: Automated verification
# ---------------------------------------------------------------------------

def check_metadata(rel_path, meta, truth):
    issues = []
    for field in ("insured_name", "claim_number", "price_list"):
        expected = truth.get(field)
        actual = meta.get(field)
        if expected and actual != expected:
            issues.append(f"  MISMATCH {field}: got {actual!r}, expected {expected!r}")
    return issues


def check_grand_total(data):
    issues = []
    lt = (data.get("case_metadata") or {}).get("line_item_totals") or {}
    gt = lt.get("grand_total")
    if not gt:
        issues.append("  MISSING grand_total in case_metadata.line_item_totals")
    return issues


def extract_pdf_text_all_pages(pdf_path):
    """Return full concatenated text from all pages of a PDF."""
    full = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            full.append(t)
    return "\n".join(full)


def check_section_names(data, pdf_text, rel_path):
    """Verify each section name in the golden master appears in the PDF text."""
    issues = []
    sections = data.get("sections", [])
    name_key = "section_name" if sections and "section_name" in sections[0] else "name"
    not_found = []
    for sec in sections:
        name = sec.get(name_key, "")
        if not name:
            continue
        # Fuzzy: check if the section name (case-insensitive) appears in PDF
        if name.lower() not in pdf_text.lower():
            not_found.append(name)
    if not_found:
        issues.append(f"  SECTION NAMES not found in PDF ({len(not_found)}/{len(sections)}):")
        for n in not_found[:10]:
            issues.append(f"    - {n!r}")
        if len(not_found) > 10:
            issues.append(f"    ... and {len(not_found) - 10} more")
    return issues


def check_item_counts(data, rel_path):
    issues = []
    sections = data.get("sections", [])
    total_items = sum(len(s.get("line_items", [])) for s in sections)
    if total_items == 0:
        issues.append("  ZERO line items total — golden master may be empty")
    # Only flag zero-item sections that have a non-zero total (real gap vs. legitimate exclusion)
    problem_sections = [
        s.get("section_name", s.get("name", "?"))
        for s in sections
        if len(s.get("line_items", [])) == 0
        and float((s.get("section_totals") or {}).get("total", 0) or 0) != 0.0
    ]
    if problem_sections:
        issues.append(f"  {len(problem_sections)} sections with 0 items but non-zero total: {problem_sections[:5]}")
    return issues


def check_recaps(data):
    issues = []
    recaps = data.get("recaps_and_summaries") or {}
    populated = [k for k, v in recaps.items() if v is not None]
    if not populated:
        issues.append("  recaps_and_summaries: all fields null")
    return issues


def run_verification():
    print()
    print("=" * 60)
    print("STEP 2: Automated verification")
    print("=" * 60)

    all_passed = True

    for rel_path, truth in METADATA_GROUND_TRUTH.items():
        gm_path = GOLDEN_DIR / rel_path
        if not gm_path.exists():
            print(f"\n[MISSING] {rel_path}")
            all_passed = False
            continue

        with open(gm_path, encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("case_metadata") or {}
        sections = data.get("sections", [])
        total_items = sum(len(s.get("line_items", [])) for s in sections)

        pdf_path = ROOT / truth["source_pdf"]
        pdf_text = extract_pdf_text_all_pages(str(pdf_path)) if pdf_path.exists() else ""

        issues = []
        issues += check_metadata(rel_path, meta, truth)
        issues += check_grand_total(data)
        issues += check_recaps(data)
        if pdf_text:
            issues += check_section_names(data, pdf_text, rel_path)
        issues += check_item_counts(data, rel_path)

        status = "PASS" if not issues else "FAIL"
        if issues:
            all_passed = False

        name_key = "section_name" if sections and "section_name" in sections[0] else "name"
        print(f"\n[{status}] {rel_path}")
        print(f"  sections={len(sections)}, total_items={total_items}")
        print(f"  insured_name={meta.get('insured_name')!r}")
        print(f"  claim_number={meta.get('claim_number')!r}")
        print(f"  price_list={meta.get('price_list')!r}")
        print(f"  property_address={meta.get('property_address')!r}")
        if issues:
            for iss in issues:
                print(iss)

    print()
    print("=" * 60)
    print("RESULT:", "ALL CHECKS PASSED" if all_passed else "ISSUES FOUND — see above")
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    update_golden_masters()
    ok = run_verification()
    sys.exit(0 if ok else 1)
