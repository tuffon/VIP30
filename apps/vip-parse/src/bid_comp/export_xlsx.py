from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter


def export_xlsx(
    *,
    pair,
    narrative,
    category_rows: List[Dict[str, Any]],
    recap_rows: List[Dict[str, Any]],
) -> bytes:
    wb = Workbook()
    ws_summary = wb.active
    ws_summary.title = "Narrative Summary"
    header_font = Font(bold=True)

    ws_summary["A1"] = "Bid Comparison Summary"
    ws_summary["A1"].font = Font(bold=True, size=14)

    ws_summary["A3"] = "Bid A"
    ws_summary["B3"] = pair.bid_a.estimate_name
    ws_summary["C3"] = pair.bid_a.totals.grand_total
    ws_summary["A4"] = "Bid B"
    ws_summary["B4"] = pair.bid_b.estimate_name
    ws_summary["C4"] = pair.bid_b.totals.grand_total
    for cell_ref in ("C3", "C4"):
        cell = ws_summary[cell_ref]
        if isinstance(cell.value, (int, float)):
            cell.number_format = "$#,##0.00"

    ws_summary["A6"] = "Executive Summary"
    ws_summary["A6"].font = header_font
    ws_summary.merge_cells(start_row=6, start_column=2, end_row=6, end_column=5)
    exec_cell = ws_summary.cell(row=6, column=2, value=narrative.executive_summary)
    exec_cell.alignment = Alignment(wrap_text=True, vertical="top")

    current_row = 8
    ws_summary.cell(row=current_row, column=1, value="Largest Deltas").font = header_font
    current_row += 1
    delta_headers = ["Driver", f"{pair.bid_a.estimate_name} ($)", f"{pair.bid_b.estimate_name} ($)", "Delta ($)", "Insight"]
    for col_idx, header in enumerate(delta_headers, start=1):
        ws_summary.cell(row=current_row, column=col_idx, value=header).font = header_font
    current_row += 1
    for entry in narrative.largest_deltas:
        ws_summary.cell(row=current_row, column=1, value=entry.get("title") or entry.get("category"))
        ws_summary.cell(row=current_row, column=2, value=entry.get("bid_a_total"))
        ws_summary.cell(row=current_row, column=3, value=entry.get("bid_b_total"))
        ws_summary.cell(row=current_row, column=4, value=entry.get("delta"))
        ws_summary.cell(row=current_row, column=5, value=entry.get("insight"))
        current_row += 1
    for col_idx in (2, 3, 4):
        col_letter = get_column_letter(col_idx)
        for cell in ws_summary[col_letter]:
            if isinstance(cell.value, (int, float)):
                cell.number_format = "$#,##0.00"

    current_row += 1
    ws_summary.cell(row=current_row, column=1, value="Contextual Drivers").font = header_font
    current_row += 1
    for note in narrative.contextual_drivers:
        ws_summary.cell(row=current_row, column=2, value=f"- {note}").alignment = Alignment(wrap_text=True, vertical="top")
        current_row += 1

    current_row += 1
    ws_summary.cell(row=current_row, column=1, value="Follow-up Actions").font = header_font
    current_row += 1
    for action in narrative.follow_up_actions:
        ws_summary.cell(row=current_row, column=2, value=f"- {action}").alignment = Alignment(wrap_text=True, vertical="top")
        current_row += 1

    _autosize(ws_summary)

    # Sheet 2: category matrix
    ws_categories = wb.create_sheet("Verisk Categories")
    cat_headers = [
        "Category",
        f"{pair.bid_a.estimate_name} ($)",
        f"{pair.bid_b.estimate_name} ($)",
        "Delta ($)",
        "Delta (% of Bid A)",
    ]
    ws_categories.append(cat_headers)
    for col_idx in range(1, len(cat_headers) + 1):
        ws_categories.cell(row=1, column=col_idx).font = header_font
    for row in category_rows:
        ws_categories.append(
            [
                row["category"],
                row.get("bid_a_total"),
                row.get("bid_b_total"),
                row.get("delta"),
                row.get("delta_pct"),
            ]
        )
    for col_idx in (2, 3, 4):
        col_letter = get_column_letter(col_idx)
        for cell in ws_categories[col_letter]:
            if isinstance(cell.value, (int, float)):
                cell.number_format = "$#,##0.00"
    pct_column = get_column_letter(5)
    for cell in ws_categories[pct_column]:
        if isinstance(cell.value, (int, float)):
            cell.number_format = "0.00%"
    ws_categories.freeze_panes = "A2"
    _autosize(ws_categories)

    # Sheet 3: raw recap
    ws_recap = wb.create_sheet("Original Recap")
    recap_headers = ["Estimate", "Group", "Item", "Total ($)"]
    ws_recap.append(recap_headers)
    for col_idx in range(1, len(recap_headers) + 1):
        ws_recap.cell(row=1, column=col_idx).font = header_font
    for entry in recap_rows:
        ws_recap.append(
            [
                entry.get("estimate"),
                entry.get("group"),
                entry.get("item"),
                entry.get("total"),
            ]
        )
    total_col = get_column_letter(4)
    for cell in ws_recap[total_col]:
        if isinstance(cell.value, (int, float)):
            cell.number_format = "$#,##0.00"
    ws_recap.freeze_panes = "A2"
    _autosize(ws_recap)

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _autosize(ws) -> None:
    for column_cells in ws.columns:
        letter = column_cells[0].column_letter
        max_len = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=0)
        ws.column_dimensions[letter].width = min(max(12, max_len + 2), 80)
