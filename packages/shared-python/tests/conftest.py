"""conftest.py -- fixtures for vip_shared pipeline tests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # project root
GOLDEN_DIR = ROOT / "packages" / "parser" / "tests" / "golden"

GOLDEN_FILES = {
    "kalyvas":      GOLDEN_DIR / "rough-drafts" / "kalyvas.golden.json",
    "lachman":      GOLDEN_DIR / "rough-drafts" / "lachman.golden.json",
    "bschacter":    GOLDEN_DIR / "final-drafts" / "bschacter.golden.json",
    "SF_BSchacter": GOLDEN_DIR / "final-drafts" / "statefarm" / "SF_BSchacter.golden.json",
    "kalyvas_sf":   GOLDEN_DIR / "final-drafts" / "statefarm" / "kalyvas_sf.golden.json",
    "lachman_sf":   GOLDEN_DIR / "final-drafts" / "statefarm" / "lachman_sf.golden.json",
}


def load_golden(name: str) -> dict:
    """Load a golden master JSON by name."""
    path = GOLDEN_FILES[name]
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_grand_total(payload: dict) -> float:
    """Extract grand total from recap subtotals."""
    recaps = payload.get("recaps_and_summaries", {})
    recap = recaps.get("recap_by_category", {})
    subtotals = recap.get("subtotals", [])
    for entry in subtotals:
        if entry.get("label") == "Total":
            val = entry.get("total", "0")
            return float(str(val).replace(",", ""))
    return 0.0
