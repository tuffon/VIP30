from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from .markdown import MarkdownBlock


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

    ws_summary["A3"] = "Estimate"
    ws_summary["B3"] = "Grand Total ($)"
    ws_summary["A4"] = pair.primary.estimate_name
    ws_summary["B4"] = pair.primary.totals.grand_total
    ws_summary["A5"] = pair.comparison.estimate_name
    ws_summary["B5"] = pair.comparison.totals.grand_total
    for cell_ref in ("B4", "B5"):
        cell = ws_summary[cell_ref]
        if isinstance(cell.value, (int, float)):
            cell.number_format = "$#,##0.00"

    ws_summary["A6"] = "Narrative"
    ws_summary["A6"].font = header_font
    current_row = _render_markdown(ws_summary, narrative.blocks, start_row=7)

    if narrative.delta_rows:
        current_row += 1
        ws_summary.cell(row=current_row, column=1, value="Key Category Deltas").font = header_font
        current_row += 1
        delta_headers = [
            "Category",
            f"{pair.primary.estimate_name} ($)",
            f"{pair.comparison.estimate_name} ($)",
            "Delta ($)",
        ]
        for col_idx, header in enumerate(delta_headers, start=1):
            ws_summary.cell(row=current_row, column=col_idx, value=header).font = header_font
        current_row += 1
        for entry in narrative.delta_rows:
            ws_summary.cell(row=current_row, column=1, value=entry.get("category"))
            ws_summary.cell(row=current_row, column=2, value=entry.get("primary_total"))
            ws_summary.cell(row=current_row, column=3, value=entry.get("comparison_total"))
            ws_summary.cell(row=current_row, column=4, value=entry.get("delta"))
            current_row += 1
        for col_idx in (2, 3, 4):
            col_letter = get_column_letter(col_idx)
            for cell in ws_summary[col_letter]:
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "$#,##0.00"

    _autosize(ws_summary)

    # Sheet 2: category matrix
    ws_categories = wb.create_sheet("Verisk Categories")
    cat_headers = [
        "Category",
        f"{pair.primary.estimate_name} ($)",
        f"{pair.comparison.estimate_name} ($)",
        "Delta ($)",
        f"Delta (% of {pair.primary.estimate_name})",
    ]
    ws_categories.append(cat_headers)
    for col_idx in range(1, len(cat_headers) + 1):
        ws_categories.cell(row=1, column=col_idx).font = header_font
    for row in category_rows:
        ws_categories.append(
            [
                row["category"],
                row.get("primary_total"),
                row.get("comparison_total"),
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


def _render_markdown(ws, blocks: List[MarkdownBlock], start_row: int) -> int:
    row = start_row
    for block in blocks:
        if block.kind == "blank":
            row += 1
            continue
        if block.kind == "heading":
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
            cell = ws.cell(row=row, column=1, value=block.text)
            font_size = max(12, 20 - (block.level * 2))
            cell.font = Font(bold=True, size=font_size)
            cell.alignment = Alignment(vertical="top")
            row += 1
            continue
        if block.kind == "paragraph":
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
            cell = ws.cell(row=row, column=1, value=block.text)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            row += 1
            continue
        if block.kind in {"bullet", "numbered"}:
            prefix = "•" if block.kind == "bullet" else f"{block.ordinal}." if block.ordinal is not None else "1."
            indent = "    " * max(0, block.level - 1)
            ws.cell(row=row, column=1, value=f"{indent}{prefix}")
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
            text_cell = ws.cell(row=row, column=2, value=block.text)
            text_cell.alignment = Alignment(wrap_text=True, vertical="top")
            row += 1
            continue
        # Fallback: treat any other block as paragraph text
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        cell = ws.cell(row=row, column=1, value=block.text)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1
    return row
