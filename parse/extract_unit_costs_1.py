#!/usr/bin/env python3
"""
extract_unit_costs.py

A utility script that extracts the "UNIT COSTS1" sheet from the
"2025 BNi SQUARE FOOT COSTBOOK PLUS.xlsx" workbook shipped with this repository
and serialises it into a structured JSON file.

The resulting JSON file, ``unit_costs1_structured.json``, will be written to the
same directory as this script.

Run it with:

    python parse/extract_unit_costs.py

or (from the repository root):

    python -m parse.extract_unit_costs

The script will attempt to install its Python runtime dependencies (``pandas``
and ``openpyxl``) automatically if they are not already available in the
current environment.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency handling – make sure ``pandas`` is available.
# ---------------------------------------------------------------------------
try:
    import pandas as pd  # type: ignore  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover – executed only when missing
    print("⚠️   pandas not found. Installing required dependencies (pandas, openpyxl)…")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "openpyxl"])
    import pandas as pd  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
COSTBOOK_PATH = REPO_ROOT / "CSI Manuals" / "2025 BNi SQUARE FOOT COSTBOOK PLUS.xlsx"
SHEET_NAME = "UNIT COSTS1"
OUTPUT_FILE = Path(__file__).with_name("unit_costs1_structured.json")


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------

def main() -> None:
    if not COSTBOOK_PATH.exists():
        sys.exit(f"❌ Expected costbook not found: {COSTBOOK_PATH}")

    # Load the sheet, skipping the top notice/info row so that the first sheet
    # row becomes our header row directly.
    df = pd.read_excel(COSTBOOK_PATH, sheet_name=SHEET_NAME, skiprows=1)

    # -------------------------------------------------------------------
    # Normalise column names for easier downstream handling.
    # We turn them into lowercase snake-case with spaces trimmed.
    # Example: "MAJOR CLASSIFICATION" -> "major_classification".
    # -------------------------------------------------------------------
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )

    # Some versions label the cost column "total_cost"; we standardise to
    # "unit_cost" for consistency.
    if "total_cost" in df.columns and "unit_cost" not in df.columns:
        df = df.rename(columns={"total_cost": "unit_cost"})

    # Map the sheet's CSI code column (BN2M_NO2) to a clearer name.
    # After normalisation the header becomes "bn2m_no2".
    if "bn2m_no2" in df.columns:
        df = df.rename(columns={"bn2m_no2": "code"})
    elif "bn2m_no" in df.columns:
        df = df.rename(columns={"bn2m_no": "code"})

    # Detect whether the CSI column is present – it's optional but, if found,
    # we want to include it in the exported JSON.
    has_csi = "code" in df.columns

    # We expect the following canonical columns.
    required_cols = [
        "main_division",
        "subdivision",
        "major_classification",
        "description",
        "unit",
        "unit_cost",
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(
            "Expected columns missing after normalisation: " + ", ".join(missing)
        )

    # Retain only the relevant columns in the desired order (+ CSI code if it exists).
    export_cols = required_cols.copy()
    if has_csi:
        export_cols.insert(0, "code")  # put CSI code first

    df = df[export_cols]

    # Drop rows missing key data and normalise optional fields.
    df = df.dropna(subset=["description", "unit_cost"])  # type: ignore[arg-type]

    # Replace NaNs in the optional *major_classification* column with empty string
    # so that the JSON output never contains null/NaN for this field.
    if "major_classification" in df.columns:
        df["major_classification"] = df["major_classification"].fillna("")

    # Convert to JSON-friendly dicts and tag each record with its source
    records = df.to_dict(orient="records")
    for rec in records:
        rec["source_type"] = "bni_csi"

    # Write out the JSON file
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print(f"✅ Exported {len(records)} records to {OUTPUT_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main() 