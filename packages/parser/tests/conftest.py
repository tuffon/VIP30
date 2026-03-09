"""
conftest.py — fixtures and helpers for the Phase 25 coverage harness.
"""
import io
import json
import sys
import tempfile
import pytest
from pathlib import Path

# Windows stdout encoding fix
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[3]        # project root
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

# Each entry: (golden_rel_path, pdf_rel_path, doc_type)
# doc_type: "rough-draft" | "contractor-final" | "statefarm"
DOCUMENTS = [
    (
        "rough-drafts/lachman.golden.json",
        "docs/rough-drafts/1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.pdf",
        "rough-draft",
    ),
    (
        "rough-drafts/kalyvas.golden.json",
        "docs/rough-drafts/KALYVAS_JVB_V6_KALY2_ROUGH_DRAFT_CAR.pdf",
        "rough-draft",
    ),
    (
        "final-drafts/bschacter.golden.json",
        "docs/final-drafts/BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf",
        "contractor-final",
    ),
    (
        "final-drafts/statefarm/SF_BSchacter.golden.json",
        "docs/final-drafts/statefarm/SF_BSchacter.pdf",
        "statefarm",
    ),
    (
        "final-drafts/statefarm/lachman_sf.golden.json",
        "docs/final-drafts/statefarm/Estimate SF Structural damage Lachman 4.15.2025.pdf",
        "statefarm",
    ),
    (
        "final-drafts/statefarm/kalyvas_sf.golden.json",
        "docs/final-drafts/statefarm/Kalyvas Preliminary State Farm estimate9-25-25.pdf",
        "statefarm",
    ),
]


def load_golden(rel_path: str) -> dict:
    """Load a golden master JSON file."""
    path = GOLDEN_DIR / rel_path
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_parser(pdf_rel: str) -> dict | None:
    """
    Invoke XactimateRoughDraftParser on the given PDF (relative to ROOT).
    Returns parsed output dict, or None if PDF not found or parse fails.
    """
    from vip_parser.xactimate import XactimateRoughDraftParser  # noqa: PLC0415

    pdf_path = ROOT / pdf_rel
    if not pdf_path.exists():
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            parser = XactimateRoughDraftParser(str(pdf_path), tmpdir)
            parser.run()
            # Parser writes {stem}.json
            json_path = Path(tmpdir) / f"{pdf_path.stem}.json"
            if not json_path.exists():
                return None
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            return None


def section_name_of(sec: dict) -> str:
    """Return section name handling both 'section_name' and 'name' keys."""
    return sec.get("section_name") or sec.get("name") or ""


def section_total_of(sec: dict) -> float:
    """Return declared section total as float."""
    totals = sec.get("section_totals") or {}
    raw = totals.get("total", "0")
    try:
        return float(str(raw).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0
