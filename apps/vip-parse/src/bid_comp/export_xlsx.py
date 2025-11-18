from __future__ import annotations

from io import BytesIO
from typing import List, Dict, Any

import pandas as pd
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter


def export_xlsx(
    rows: List[Dict[str, Any]],
    carrier_total: float,
    contractor_total: float,
    structure_text: str,
    delta_abs_alert: float,
    delta_pct_alert: float,
) -> bytes:
    """
    Export a simplified workbook modelled after the training example:

    - Sheet 'Summary '  : high-level categories with carrier/contractor totals, delta, and LLM notes.
    - Sheet 'Updated Bid Comp ' : recap-style categories with totals and deltas.

    The LLM narratives generated in BidComp (NARRATIVE field on SECTION rows)
    flow into the 'Notes' column on the Summary sheet.
    """
    df = pd.DataFrame(rows)

    # SECTION-level summaries (with optional LLM narratives)
    sec_df = df[df.get("TYPE") == "SECTION"].copy() if "TYPE" in df.columns else pd.DataFrame()
    if not sec_df.empty and "Δ ($)" in sec_df.columns:
        sec_df["__abs_delta__"] = sec_df["Δ ($)"].apply(lambda x: abs(x) if isinstance(x, (int, float)) else 0.0)
        sec_df = sec_df.sort_values("__abs_delta__", ascending=False)

    # RECAP-level summaries for the "Updated Bid Comp" sheet
    recap_df = df[df.get("TYPE") == "RECAP"].copy() if "TYPE" in df.columns else pd.DataFrame()
    if not recap_df.empty and "Δ ($)" in recap_df.columns:
        recap_df["__abs_delta__"] = recap_df["Δ ($)"].apply(lambda x: abs(x) if isinstance(x, (int, float)) else 0.0)
        recap_df = recap_df.sort_values("__abs_delta__", ascending=False)

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        wb = writer.book

        # Remove any default sheet created by openpyxl so we control ordering
        if wb.worksheets:
            wb.remove(wb.worksheets[0])

        # ----- Sheet 1: Summary -----
        ws_summary = wb.create_sheet("Summary ")
        header_font = Font(bold=True)

        # Header modelled after training file
        summary_headers = ["Trade/Category", "Carrier", "Contractor", "Difference", "Notes"]
        ws_summary.append(summary_headers)
        for col_idx in range(1, len(summary_headers) + 1):
            ws_summary.cell(row=1, column=col_idx).font = header_font

        # Optional top-level totals row
        delta_total = (contractor_total or 0.0) - (carrier_total or 0.0)
        ws_summary.append(
            [
                "TOTAL",
                carrier_total,
                contractor_total,
                delta_total,
                structure_text or "",
            ]
        )

        # Data rows from section summaries
        if not sec_df.empty:
            for _, r in sec_df.iterrows():
                ws_summary.append(
                    [
                        r.get("NAME") or r.get("CANONICAL GROUP"),
                        r.get("CARRIER TOTAL ($)"),
                        r.get("CONTRACTOR TOTAL ($)"),
                        r.get("Δ ($)"),
                        r.get("NARRATIVE") or r.get("COMMENTS"),
                    ]
                )

        # Number formatting for currency columns (Carrier, Contractor, Difference)
        for col_idx in (2, 3, 4):
            col_letter = get_column_letter(col_idx)
            for cell in ws_summary[col_letter]:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "$#,##0.00"

        # Wrap text in Notes column
        notes_col_letter = get_column_letter(5)
        for cell in ws_summary[notes_col_letter]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

        # Autosize columns on Summary sheet
        for col in ws_summary.columns:
            max_len = max((len(str(c.value)) for c in col if c.value is not None), default=0)
            ws_summary.column_dimensions[col[0].column_letter].width = min(max(10, max_len + 2), 80)

        # Freeze header row
        ws_summary.freeze_panes = "A2"

        # ----- Sheet 2: Updated Bid Comp (recap-style) -----
        if not recap_df.empty:
            ws_recap = wb.create_sheet("Updated Bid Comp ")
            recap_headers = ["Carriers O&P Items", "Carrier", "Contractor", "DELTA ", "Notes", None]
            ws_recap.append(recap_headers)
            for col_idx in range(1, len(recap_headers) + 1):
                ws_recap.cell(row=1, column=col_idx).font = header_font

            for _, r in recap_df.iterrows():
                ws_recap.append(
                    [
                        r.get("NAME"),
                        r.get("CARRIER TOTAL ($)"),
                        r.get("CONTRACTOR TOTAL ($)"),
                        r.get("Δ ($)"),
                        None,
                        None,
                    ]
                )

            # Currency formatting for recap sheet
            for col_idx in (2, 3, 4):
                col_letter = get_column_letter(col_idx)
                for cell in ws_recap[col_letter]:
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = "$#,##0.00"

            # Autosize columns
            for col in ws_recap.columns:
                max_len = max((len(str(c.value)) for c in col if c.value is not None), default=0)
                ws_recap.column_dimensions[col[0].column_letter].width = min(max(10, max_len + 2), 80)

    return bio.getvalue()
