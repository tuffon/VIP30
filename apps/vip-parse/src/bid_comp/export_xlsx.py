from __future__ import annotations

from io import BytesIO
from typing import List, Dict, Any

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.formatting.rule import CellIsRule


COLUMNS = [
    "TYPE",
    "CANONICAL GROUP",
    "NAME",
    "CARRIER TOTAL ($)",
    "CONTRACTOR TOTAL ($)",
    "Δ ($)",
    "Δ (% OF CARRIER)",
    "SOURCE GROUPS",
    "COVERAGE NOTE",
    "MATCHING NOTE",
    "FLAGS",
    "COMMENTS",
]


def build_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    return df


def export_xlsx(
    rows: List[Dict[str, Any]],
    carrier_total: float,
    contractor_total: float,
    structure_text: str,
    delta_abs_alert: float,
    delta_pct_alert: float,
) -> bytes:
    df = build_dataframe(rows)

    # Prepare writer
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        # We will prepend two summary rows manually via openpyxl after writing headers
        df.to_excel(writer, index=False, sheet_name="Bid Comp")
        wb = writer.book
        ws = writer.sheets["Bid Comp"]

        # Insert two rows at top and fill totals + structure
        ws.insert_rows(1, amount=2)
        ws.cell(row=1, column=1, value="TOTALS")
        ws.cell(row=1, column=4, value=carrier_total)
        ws.cell(row=1, column=5, value=contractor_total)
        delta_abs = (contractor_total or 0.0) - (carrier_total or 0.0)
        ws.cell(row=1, column=6, value=delta_abs)
        ws.cell(row=1, column=7, value=(delta_abs / carrier_total) if (carrier_total or 0) > 0 else None)

        ws.cell(row=2, column=1, value="STRUCTURE")
        ws.cell(row=2, column=3, value=structure_text)

        # Freeze panes below header row (header now at row 3)
        ws.freeze_panes = "A4"

        # Number formats
        for row in ws.iter_rows(min_row=1, min_col=4, max_col=6):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "$#,##0.00"
        for row in ws.iter_rows(min_row=1, min_col=7, max_col=7):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "0.00%"

        # Conditional formatting on Δ columns for data rows (from row 4)
        red_fill = PatternFill(start_color="FFF4CCCC", end_color="FFF4CCCC", fill_type="solid")
        ws.conditional_formatting.add(
            f"F4:F{ws.max_row}",
            CellIsRule(operator="greaterThanOrEqual", formula=[str(abs(delta_abs_alert))], fill=red_fill),
        )
        ws.conditional_formatting.add(
            f"F4:F{ws.max_row}",
            CellIsRule(operator="lessThanOrEqual", formula=[f"-{abs(delta_abs_alert)}"], fill=red_fill),
        )
        ws.conditional_formatting.add(
            f"G4:G{ws.max_row}",
            CellIsRule(operator="greaterThanOrEqual", formula=[str(abs(delta_pct_alert) / 100.0)], fill=red_fill),
        )
        ws.conditional_formatting.add(
            f"G4:G{ws.max_row}",
            CellIsRule(operator="lessThanOrEqual", formula=[f"-{abs(delta_pct_alert) / 100.0}"], fill=red_fill),
        )

        # Wrap text for notes columns (8–12)
        for col in range(8, 13):
            for cell in ws.iter_cols(min_col=col, max_col=col, min_row=1, max_row=ws.max_row):
                for c in cell:
                    c.alignment = Alignment(wrap_text=True, vertical="top")

        # Autosize columns
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                val = cell.value
                if val is None:
                    continue
                l = len(str(val))
                if l > max_len:
                    max_len = l
            ws.column_dimensions[col_letter].width = min(max(10, max_len + 2), 60)

        # Bold headers and summary label
        header_font = Font(bold=True)
        for cell in ws[3]:
            cell.font = header_font
        ws.cell(row=1, column=1).font = header_font
        ws.cell(row=2, column=1).font = header_font

    return bio.getvalue()


