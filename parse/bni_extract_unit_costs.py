#!/usr/bin/env python3
"""
extract_unit_costs.py

A utility script that extracts all four sheets from the
"2025 BNi SQUARE FOOT COSTBOOK PLUS.xlsx" workbook and serializes them
into structured JSON files.

The resulting JSON files will be written to the data/costbook/ directory.

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
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
COSTBOOK_PATH = REPO_ROOT / "documents" / "costbook" / "2025 BNi SQUARE FOOT COSTBOOK PLUS.xlsx"
OUTPUT_DIR = REPO_ROOT / "data" / "costbook"

# Sheet configurations
SHEETS = {
    "PROJECTS": {
        "source_type": "bni_projects",
        "skip_rows": 1,
    },
    "UNIT COSTS1": {
        "source_type": "bni_unit_costs", 
        "skip_rows": 1,
    },
    "LOCATIONS": {
        "source_type": "bni_locations",
        "skip_rows": 1,
    }
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def normalize_column_names(columns: List[str]) -> List[str]:
    """Normalize column names to lowercase snake_case."""
    return [
        str(col).strip().lower().replace(" ", "_").replace("-", "_")
        for col in columns
    ]


def is_project_header(row: pd.Series) -> bool:
    """Check if a row is a project header (e.g., 'Fire Station', 'Church')."""
    # Look for project names in the first few columns
    for col in row.iloc[:3]:
        if pd.notna(col) and isinstance(col, str):
            col_str = str(col).strip()
            # Check if it looks like a project type (not a code or division)
            if (len(col_str) > 3 and 
                not col_str.isdigit() and 
                not col_str.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')) and
                col_str not in ['Code', 'Division Name', 'FILE 1']):
                return True
    return False


def is_header_row(row: pd.Series) -> bool:
    """Check if a row is a header row (contains only division/subdivision/classification)."""
    # Check if unit_cost is NaN and description is NaN or looks like a header
    unit_cost = row.get('unit_cost', row.get('total_cost'))
    description = row.get('description', row.get('short_description'))
    
    if pd.isna(unit_cost):
        # Check if description looks like a header (short, all caps, or contains keywords)
        if pd.notna(description):
            desc_str = str(description).strip()
            if (len(desc_str) < 50 and 
                (desc_str.isupper() or 
                 any(keyword in desc_str.upper() for keyword in ['GENERAL', 'REQUIREMENTS', 'DIVISION']))):
                return True
    return False


# ---------------------------------------------------------------------------
# Sheet-specific parsers
# ---------------------------------------------------------------------------

def parse_projects_sheet(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Parse the PROJECTS sheet with project header detection."""
    records = []
    current_project_type = None
    
    # The PROJECTS sheet has a specific structure where:
    # - Row 0: "FILE 1" and project name (e.g., "FIRE STATION")
    # - Row 1: "Code" and "Division Name" headers
    # - Subsequent rows: division codes and names with percentages
    
    # Extract project type from the first row
    if len(df) > 0:
        first_row = df.iloc[0]
        for col in first_row.iloc[1:4]:  # Check columns 1-3 for project name
            if pd.notna(col) and isinstance(col, str):
                col_str = str(col).strip()
                if (len(col_str) > 3 and 
                    not col_str.isdigit() and 
                    col_str not in ['Code', 'Division Name', 'FILE 1']):
                    current_project_type = col_str
                    break
    
    # Process data rows (skip header row)
    for i, row in df.iterrows():
        if i == 0:  # Skip the project header row
            continue
            
        # Get division code and name
        division_code = row.iloc[0] if len(row) > 0 else None
        division_name = row.iloc[1] if len(row) > 1 else None
        
        # Look for percentage in the data
        percent_breakdown = None
        for col_idx in range(2, min(len(row), 8)):  # Check columns 2-7 for percentage
            val = row.iloc[col_idx]
            if pd.notna(val):
                try:
                    percent_breakdown = float(val)
                    break
                except (ValueError, TypeError):
                    continue
        
        # Skip rows without meaningful data
        if pd.isna(division_code) or pd.isna(division_name) or percent_breakdown is None:
            continue
            
        # Create record
        record = {
            "project_type": current_project_type or "",
            "division": str(division_name).strip(),
            "percent_breakdown": percent_breakdown,
            "national_avg_cost_sf": 0.0,  # Not available in this sheet
            "local_cost_sf": 0.0,  # Not available in this sheet
            "projected_cost_total": 0.0,  # Not available in this sheet
            "local_cost_total": 0.0,  # Not available in this sheet
            "sheet_name": "PROJECTS",
            "source_type": "bni_projects",
            "version": "2025"
        }
        
        records.append(record)
    
    return records


def parse_unit_costs_sheet(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Parse the UNIT COSTS1 sheet with comprehensive schema combining best features."""
    # Normalize column names
    df.columns = normalize_column_names(df.columns)
    
    # Map columns to expected schema
    if "bn2m_no2" in df.columns:
        df = df.rename(columns={"bn2m_no2": "code"})
    elif "bn2m_no" in df.columns:
        df = df.rename(columns={"bn2m_no": "code"})
    
    if "total_cost" in df.columns and "unit_cost" not in df.columns:
        df = df.rename(columns={"total_cost": "unit_cost"})
    
    # Required columns
    required_cols = [
        "main_division",
        "subdivision", 
        "major_classification",
        "description",
        "unit",
        "unit_cost",
    ]
    
    # Check for missing columns
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"Warning: Missing columns in UNIT COSTS: {missing}")
        # Use available columns
        available_cols = [c for c in required_cols if c in df.columns]
        df = df[available_cols + (["code"] if "code" in df.columns else [])]
    else:
        # Include code if available
        export_cols = required_cols.copy()
        if "code" in df.columns:
            export_cols.insert(0, "code")
        df = df[export_cols]
    
    # Drop rows missing key data
    df = df.dropna(subset=["description", "unit_cost"])
    
    # Fill NaN values
    if "major_classification" in df.columns:
        df["major_classification"] = df["major_classification"].fillna("")
    
    # Convert to records with comprehensive schema
    records = df.to_dict(orient="records")
    for rec in records:
        # Create a comprehensive schema that combines the best of both approaches
        rec["sheet_name"] = "UNIT COSTS"
        rec["source_type"] = "bni_unit_costs"
        rec["version"] = "2025"
        
        # Add short_description field (derived from description for consistency)
        if "description" in rec:
            desc = str(rec["description"])
            # Extract short description (first part before comma, or first few words)
            if "," in desc:
                rec["short_description"] = desc.split(",")[0].strip()
            else:
                # Take first 3-4 words as short description
                words = desc.split()[:4]
                rec["short_description"] = " ".join(words)
        else:
            rec["short_description"] = ""
    
    return records




def parse_locations_sheet(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Parse the LOCATIONS sheet for region multipliers."""
    records = []
    
    # The locations sheet has a simple structure: region code and multiplier
    for _, row in df.iterrows():
        # Get the first column (region code) and second column (multiplier)
        region_code = row.iloc[0] if len(row) > 0 else None
        multiplier = row.iloc[1] if len(row) > 1 else None
        
        if pd.notna(region_code) and pd.notna(multiplier):
            # Parse region code to extract city and state
            region_str = str(region_code).strip()
            if ' - ' in region_str:
                state_code, city = region_str.split(' - ', 1)
                state_code = state_code.strip()
                city = city.strip()
            else:
                state_code = region_str
                city = ""
            
            record = {
                "region_code": region_str,
                "city": city,
                "state": state_code,
                "multiplier": float(multiplier),
                "sheet_name": "LOCATIONS",
                "source_type": "bni_locations",
                "version": "2025"
            }
            
            records.append(record)
    
    return records


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------

def main() -> None:
    """Main function to extract all sheets from the costbook."""
    if not COSTBOOK_PATH.exists():
        sys.exit(f"❌ Expected costbook not found: {COSTBOOK_PATH}")
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    summary = {}
    
    for sheet_name, config in SHEETS.items():
        print(f"📊 Processing {sheet_name} sheet...")
        
        try:
            # Load the sheet
            df = pd.read_excel(COSTBOOK_PATH, sheet_name=sheet_name, skiprows=config["skip_rows"])
            
            # Parse based on sheet type
            if sheet_name == "PROJECTS":
                records = parse_projects_sheet(df)
            elif sheet_name == "UNIT COSTS1":
                records = parse_unit_costs_sheet(df)
            elif sheet_name == "LOCATIONS":
                records = parse_locations_sheet(df)
            else:
                print(f"⚠️  Unknown sheet: {sheet_name}")
                continue
            
            # Save to JSON file
            if sheet_name == "UNIT COSTS1":
                output_file = OUTPUT_DIR / "unit_costs.json"
            else:
                output_file = OUTPUT_DIR / f"{sheet_name.lower().replace(' ', '_')}.json"
            with output_file.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            
            summary[sheet_name] = len(records)
            print(f"✅ Exported {len(records)} records to {output_file.relative_to(REPO_ROOT)}")
            
        except Exception as e:
            print(f"❌ Error processing {sheet_name}: {e}")
            summary[sheet_name] = 0
    
    # Print summary
    print("\n📋 Summary:")
    print("=" * 50)
    for sheet_name, count in summary.items():
        print(f"{sheet_name:20} {count:6} records")
    print("=" * 50)
    total_records = sum(summary.values())
    print(f"{'TOTAL':20} {total_records:6} records")


if __name__ == "__main__":
    main()
