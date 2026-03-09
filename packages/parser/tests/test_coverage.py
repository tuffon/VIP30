"""
test_coverage.py — Phase 25 coverage harness.

Runs XactimateRoughDraftParser against each source PDF and diffs output
against the corresponding golden master field-by-field.

Pass/fail semantics:
  rough-draft:       PASS expected (parser IS the baseline, delta=0)
  contractor-final:  FAIL expected (0 sections — known v2.5 gap)
  statefarm:         FAIL expected (missing items/metadata — known v2.5 gaps)

Failures are informative: they show exactly what's missing, not just that
something failed. This output IS the v2.5 gap analysis input.

Run from project root:
  pip install -e packages/parser[dev]
  pytest packages/parser/tests/test_coverage.py -v
"""

import pytest
from .conftest import (
    DOCUMENTS,
    load_golden,
    run_parser,
    section_name_of,
    section_total_of,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

METADATA_FIELDS = ["claim_number", "insured_name", "price_list", "property_address"]


def _meta_diff(golden: dict, parsed: dict) -> list[str]:
    """Return list of metadata field diff strings."""
    g_meta = golden.get("case_metadata") or {}
    p_meta = parsed.get("case_metadata") or {} if parsed else {}
    diffs = []
    for field in METADATA_FIELDS:
        g_val = g_meta.get(field)
        p_val = p_meta.get(field)
        if g_val != p_val:
            diffs.append(f"  {field}: parser={p_val!r}  golden={g_val!r}")
    return diffs


def _section_diff(golden: dict, parsed: dict) -> tuple[str, float]:
    """
    Compare sections between golden and parser output.
    Returns (diff_text, coverage_pct).
    """
    g_secs = golden.get("sections") or []
    p_secs = (parsed.get("sections") or []) if parsed else []

    # Build parser section lookup by name
    p_by_name: dict[str, dict] = {}
    for sec in p_secs:
        name = section_name_of(sec)
        if name:
            p_by_name[name] = sec

    lines = []
    lines.append(f"  Section count: parser={len(p_secs)}  golden={len(g_secs)}")

    missing_secs = []
    partial_secs = []
    verified_secs = []

    for g_sec in g_secs:
        g_name = section_name_of(g_sec)
        g_items = len(g_sec.get("line_items") or [])
        g_total = section_total_of(g_sec)

        if g_total == 0.0 and g_items == 0:
            continue  # legitimately excluded section

        p_sec = p_by_name.get(g_name)
        if p_sec is None:
            missing_secs.append(f"    - {g_name} (golden: {g_items} items, ${g_total:,.2f})")
        else:
            p_items = len(p_sec.get("line_items") or [])
            p_total = section_total_of(p_sec)
            item_delta = p_items - g_items
            total_delta = p_total - g_total
            if abs(item_delta) > 0 or abs(total_delta) > 0.05:
                partial_secs.append(
                    f"    - {g_name}: items parser={p_items}/golden={g_items} (delta {item_delta:+d})"
                    f"  total parser=${p_total:,.2f}/golden=${g_total:,.2f} (delta {total_delta:+,.2f})"
                )
            else:
                verified_secs.append(g_name)

    non_excl = len(g_secs) - sum(
        1 for s in g_secs
        if section_total_of(s) == 0.0 and len(s.get("line_items") or []) == 0
    )
    matched = len(verified_secs)
    coverage = matched / non_excl * 100 if non_excl else 100.0

    lines.append(f"  Coverage: {matched}/{non_excl} sections fully matched ({coverage:.0f}%)")

    if missing_secs:
        lines.append(f"  Missing sections ({len(missing_secs)}):")
        lines.extend(missing_secs)

    if partial_secs:
        lines.append(f"  Partial sections ({len(partial_secs)}):")
        lines.extend(partial_secs)

    return "\n".join(lines), coverage


# ---------------------------------------------------------------------------
# Tests — parametrized over all 6 documents
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("golden_rel,pdf_rel,doc_type", DOCUMENTS)
class TestCoverage:

    def test_metadata(self, golden_rel, pdf_rel, doc_type):
        """Parser extracts correct metadata fields (claim_number, insured_name, price_list, address)."""
        golden = load_golden(golden_rel)
        parsed = run_parser(pdf_rel)

        diffs = _meta_diff(golden, parsed)
        if diffs:
            diff_str = "\n".join(diffs)
            pytest.fail(
                f"\n[{golden_rel}] METADATA GAPS:\n{diff_str}\n"
                f"(doc_type={doc_type})"
            )

    def test_section_coverage(self, golden_rel, pdf_rel, doc_type):
        """Parser extracts correct sections with matching item counts and totals."""
        golden = load_golden(golden_rel)
        parsed = run_parser(pdf_rel)

        diff_text, coverage_pct = _section_diff(golden, parsed)

        # Rough drafts: expect 100% coverage (parser IS the baseline)
        # Final drafts: report gaps without hard threshold (all gaps are v2.5 targets)
        threshold = 99.0 if doc_type == "rough-draft" else 0.0

        if coverage_pct < threshold or (doc_type != "rough-draft" and coverage_pct < 100.0):
            pytest.fail(
                f"\n[{golden_rel}] SECTION COVERAGE:\n{diff_text}\n"
                f"(doc_type={doc_type})"
            )
