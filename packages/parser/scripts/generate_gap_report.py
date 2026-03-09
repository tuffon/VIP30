"""
generate_gap_report.py
----------------------
Run all 6 golden master comparisons and write GAP-REPORT.md.

Produces the v2.5 gap analysis: per-doc coverage%, missing sections, metadata
gaps, and cross-document pattern summary.

Run from project root:
    python packages/parser/scripts/generate_gap_report.py
"""

import io
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = ROOT / "packages/parser/tests/golden"
REPORT_PATH = ROOT / "packages/parser/tests/GAP-REPORT.md"

DOCUMENTS = [
    (
        "rough-drafts/lachman.golden.json",
        "docs/rough-drafts/1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.pdf",
        "rough-draft",
        "lachman",
    ),
    (
        "rough-drafts/kalyvas.golden.json",
        "docs/rough-drafts/KALYVAS_JVB_V6_KALY2_ROUGH_DRAFT_CAR.pdf",
        "rough-draft",
        "kalyvas",
    ),
    (
        "final-drafts/bschacter.golden.json",
        "docs/final-drafts/BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf",
        "contractor-final",
        "bschacter",
    ),
    (
        "final-drafts/statefarm/SF_BSchacter.golden.json",
        "docs/final-drafts/statefarm/SF_BSchacter.pdf",
        "statefarm",
        "sf_bschacter",
    ),
    (
        "final-drafts/statefarm/lachman_sf.golden.json",
        "docs/final-drafts/statefarm/Estimate SF Structural damage Lachman 4.15.2025.pdf",
        "statefarm",
        "lachman_sf",
    ),
    (
        "final-drafts/statefarm/kalyvas_sf.golden.json",
        "docs/final-drafts/statefarm/Kalyvas Preliminary State Farm estimate9-25-25.pdf",
        "statefarm",
        "kalyvas_sf",
    ),
]

METADATA_FIELDS = ["claim_number", "insured_name", "price_list", "property_address"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_golden(rel_path: str) -> dict:
    path = GOLDEN_DIR / rel_path
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_parser(pdf_rel: str) -> dict | None:
    from vip_parser.xactimate import XactimateRoughDraftParser  # noqa: PLC0415

    pdf_path = ROOT / pdf_rel
    if not pdf_path.exists():
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            parser = XactimateRoughDraftParser(str(pdf_path), tmpdir)
            parser.run()
            json_path = Path(tmpdir) / f"{pdf_path.stem}.json"
            if not json_path.exists():
                return None
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            return None


def section_name_of(sec: dict) -> str:
    return sec.get("section_name") or sec.get("name") or ""


def section_total_of(sec: dict) -> float:
    totals = sec.get("section_totals") or {}
    raw = totals.get("total", "0")
    try:
        return float(str(raw).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def meta_diff(golden: dict, parsed: dict | None) -> list[tuple[str, str, str]]:
    """Return list of (field, parser_val, golden_val) for mismatched metadata fields."""
    g_meta = golden.get("case_metadata") or {}
    p_meta = (parsed.get("case_metadata") or {}) if parsed else {}
    return [
        (field, repr(p_meta.get(field)), repr(g_meta.get(field)))
        for field in METADATA_FIELDS
        if g_meta.get(field) != p_meta.get(field)
    ]


def section_analysis(golden: dict, parsed: dict | None) -> dict:
    """
    Compare sections. Returns:
      {
        g_count, p_count,
        matched: [name, ...],
        missing: [(name, g_items, g_total), ...],
        partial: [(name, p_items, g_items, item_delta, p_total, g_total, total_delta), ...],
        coverage_pct: float,
        non_excl_count: int,
      }
    """
    g_secs = golden.get("sections") or []
    p_secs = (parsed.get("sections") or []) if parsed else []

    p_by_name = {section_name_of(s): s for s in p_secs if section_name_of(s)}

    matched = []
    missing = []
    partial = []

    non_excl = 0
    for g_sec in g_secs:
        g_name = section_name_of(g_sec)
        g_items = len(g_sec.get("line_items") or [])
        g_total = section_total_of(g_sec)

        if g_total == 0.0 and g_items == 0:
            continue  # legitimately excluded
        non_excl += 1

        p_sec = p_by_name.get(g_name)
        if p_sec is None:
            missing.append((g_name, g_items, g_total))
        else:
            p_items = len(p_sec.get("line_items") or [])
            p_total = section_total_of(p_sec)
            item_delta = p_items - g_items
            total_delta = p_total - g_total
            if abs(item_delta) > 0 or abs(total_delta) > 0.05:
                partial.append((g_name, p_items, g_items, item_delta, p_total, g_total, total_delta))
            else:
                matched.append(g_name)

    coverage_pct = len(matched) / non_excl * 100 if non_excl else 100.0
    return {
        "g_count": len(g_secs),
        "p_count": len(p_secs),
        "matched": matched,
        "missing": missing,
        "partial": partial,
        "coverage_pct": coverage_pct,
        "non_excl_count": non_excl,
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def build_report(results: list[dict]) -> str:
    lines = []
    today = date.today().isoformat()

    lines.append("# Coverage Gap Report — Phase 25")
    lines.append("")
    lines.append(f"Generated: {today}")
    lines.append("")
    lines.append("This report is the v2.5 parser-fix input. Rough-draft documents are the")
    lines.append("regression baseline; final-draft gaps are the v2.5 fix targets.")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Document | Doc Type | Sections (parser/golden) | Coverage | Metadata |")
    lines.append("|----------|----------|--------------------------|----------|----------|")
    for r in results:
        sa = r["section_analysis"]
        meta_ok = "PASS" if not r["meta_diffs"] else f"{len(r['meta_diffs'])} gaps"
        pdf_status = " (PDF missing)" if not r["pdf_found"] else ""
        lines.append(
            f"| {r['name']} | {r['doc_type']} | "
            f"{sa['p_count']}/{sa['g_count']} | "
            f"{sa['coverage_pct']:.0f}% ({len(sa['matched'])}/{sa['non_excl_count']}) | "
            f"{meta_ok}{pdf_status} |"
        )

    lines.append("")

    # Per-document analysis
    lines.append("## Per-Document Analysis")
    lines.append("")

    for r in results:
        lines.append(f"### {r['golden_rel']}")
        lines.append("")
        lines.append(f"**Doc type:** {r['doc_type']}")
        if not r["pdf_found"]:
            lines.append("")
            lines.append("> **PDF not found** — parser could not run. Gaps estimated from golden master only.")
            lines.append("")

        sa = r["section_analysis"]
        lines.append(f"**Sections:** parser={sa['p_count']}  golden={sa['g_count']}  "
                     f"coverage={sa['coverage_pct']:.0f}% ({len(sa['matched'])}/{sa['non_excl_count']} non-excluded)")
        lines.append("")

        # Metadata
        if r["meta_diffs"]:
            lines.append("**Metadata gaps:**")
            for field, p_val, g_val in r["meta_diffs"]:
                lines.append(f"- `{field}`: parser={p_val}  golden={g_val}")
            lines.append("")
        else:
            lines.append("**Metadata:** all fields match")
            lines.append("")

        # Missing sections
        if sa["missing"]:
            lines.append(f"**Missing sections ({len(sa['missing'])}):**")
            for name, g_items, g_total in sa["missing"]:
                lines.append(f"- {name}: {g_items} items, ${g_total:,.2f}")
            lines.append("")

        # Partial sections
        if sa["partial"]:
            lines.append(f"**Partial sections ({len(sa['partial'])}):**")
            for name, p_items, g_items, item_delta, p_total, g_total, total_delta in sa["partial"]:
                lines.append(
                    f"- {name}: items {p_items}/{g_items} ({item_delta:+d})  "
                    f"total ${p_total:,.2f}/${g_total:,.2f} ({total_delta:+,.2f})"
                )
            lines.append("")

        if not sa["missing"] and not sa["partial"]:
            lines.append("**All sections matched.** ✓")
            lines.append("")

    # Cross-document patterns
    lines.append("## Cross-Document Patterns")
    lines.append("")

    # Sections missing in ALL final drafts
    final_results = [r for r in results if r["doc_type"] != "rough-draft"]
    if final_results:
        # Sections missing in ≥2 final drafts
        from collections import Counter
        missing_counts: Counter = Counter()
        for r in final_results:
            for name, _, _ in r["section_analysis"]["missing"]:
                missing_counts[name] += 1

        always_missing = sorted(
            [(name, cnt) for name, cnt in missing_counts.items() if cnt >= 2],
            key=lambda x: -x[1],
        )
        if always_missing:
            lines.append(f"### Sections missing in ≥2 final-draft documents ({len(always_missing)} total)")
            lines.append("")
            for name, cnt in always_missing:
                lines.append(f"- **{name}** — missing in {cnt}/{len(final_results)} final-draft docs")
            lines.append("")

        # Metadata fields missing in all final drafts
        meta_missing: Counter = Counter()
        for r in final_results:
            for field, _, _ in r["meta_diffs"]:
                meta_missing[field] += 1
        always_meta = [(f, c) for f, c in meta_missing.items() if c == len(final_results)]
        if always_meta:
            lines.append("### Metadata fields null in ALL final-draft documents")
            lines.append("")
            for field, _ in always_meta:
                lines.append(f"- `{field}`")
            lines.append("")

    lines.append("### v2.5 Fix Priority")
    lines.append("")
    lines.append("Ordered by impact (document coverage % gain):")
    lines.append("")
    # Rough-draft issues first (regressions), then final-draft by coverage gap
    rough = [r for r in results if r["doc_type"] == "rough-draft" and r["section_analysis"]["coverage_pct"] < 100]
    if rough:
        lines.append("**REGRESSIONS (rough-draft, must fix first):**")
        for r in rough:
            lines.append(f"- {r['name']}: {r['section_analysis']['coverage_pct']:.0f}% coverage")
        lines.append("")

    lines.append("**Final-draft gaps (v2.5 scope):**")
    finals_sorted = sorted(
        [r for r in results if r["doc_type"] != "rough-draft"],
        key=lambda r: r["section_analysis"]["coverage_pct"],
    )
    for r in finals_sorted:
        sa = r["section_analysis"]
        lines.append(
            f"- **{r['doc_type']} / {r['name']}**: "
            f"{sa['coverage_pct']:.0f}% coverage — "
            f"{len(sa['missing'])} missing, {len(sa['partial'])} partial"
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("Phase 25 Gap Report Generator")
    print("=" * 65)

    results = []
    for golden_rel, pdf_rel, doc_type, name in DOCUMENTS:
        print(f"\n  [{doc_type}] {name} ...", end=" ", flush=True)
        golden = load_golden(golden_rel)
        pdf_found = (ROOT / pdf_rel).exists()
        parsed = run_parser(pdf_rel) if pdf_found else None
        if not pdf_found:
            print("PDF missing", end=" ")
        elif parsed is None:
            print("parse failed", end=" ")
        sa = section_analysis(golden, parsed)
        md = meta_diff(golden, parsed)
        print(f"coverage={sa['coverage_pct']:.0f}% ({len(sa['matched'])}/{sa['non_excl_count']})")
        results.append({
            "name": name,
            "golden_rel": golden_rel,
            "pdf_rel": pdf_rel,
            "doc_type": doc_type,
            "pdf_found": pdf_found,
            "parsed": parsed is not None,
            "section_analysis": sa,
            "meta_diffs": md,
        })

    report = build_report(results)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nWrote: {REPORT_PATH.relative_to(ROOT)}")
    print(f"Lines: {len(report.splitlines())}")

    # Quick summary
    rough = [r for r in results if r["doc_type"] == "rough-draft"]
    finals = [r for r in results if r["doc_type"] != "rough-draft"]
    rough_pass = all(r["section_analysis"]["coverage_pct"] >= 99.0 for r in rough)
    print()
    print(f"  Rough-draft baseline: {'PASS' if rough_pass else 'REGRESSION DETECTED'}")
    for r in finals:
        sa = r["section_analysis"]
        print(f"  {r['doc_type']:20} {r['name']:20} {sa['coverage_pct']:5.0f}% coverage")


if __name__ == "__main__":
    main()
