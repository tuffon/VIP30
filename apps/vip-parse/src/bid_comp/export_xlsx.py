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

    sections = narrative.sections or {}
    overview_text = _resolve_overview_text(narrative)
    scope_items = sections.get("scope_observations") or []
    followup_items = sections.get("suggested_followups") or []
    driver_rows = narrative.key_drivers or [
        {
            "category": row.get("category"),
            "primary_total": row.get("primary_total"),
            "comparison_total": row.get("comparison_total"),
            "delta_total": row.get("delta"),
            "narrative": "",
        }
        for row in (narrative.delta_rows or [])
    ]

    current_row = 6
    current_row = _write_text_section(ws_summary, current_row, "Overview of Estimates", overview_text, header_font)
    current_row = _write_key_driver_section(
        ws_summary,
        current_row,
        pair,
        driver_rows,
        header_font,
    )
    current_row = _write_list_section(ws_summary, current_row, "Scope Observations", scope_items, header_font)
    current_row = _write_list_section(ws_summary, current_row, "Suggested Follow-ups", followup_items, header_font)

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


def _write_text_section(ws, start_row: int, title: str, body: str, header_font: Font) -> int:
    ws.cell(row=start_row, column=1, value=title).font = header_font
    body_row = start_row + 1
    ws.merge_cells(start_row=body_row, start_column=1, end_row=body_row, end_column=5)
    body_cell = ws.cell(row=body_row, column=1, value=body or "No narrative available.")
    body_cell.alignment = Alignment(wrap_text=True, vertical="top")
    return body_row + 2


def _write_list_section(ws, start_row: int, title: str, items: List[str], header_font: Font) -> int:
    ws.cell(row=start_row, column=1, value=title).font = header_font
    row = start_row + 1
    if not items:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        cell = ws.cell(row=row, column=1, value="No items provided.")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        return row + 2
    for item in items:
        ws.cell(row=row, column=1, value="•")
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
        text_cell = ws.cell(row=row, column=2, value=item)
        text_cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1
    return row + 1


def _write_key_driver_section(ws, start_row: int, pair, drivers: List[Dict[str, Any]], header_font: Font) -> int:
    ws.cell(row=start_row, column=1, value="Key Cost Drivers").font = header_font
    row = start_row + 1
    headers = [
        "Category",
        f"{pair.primary.estimate_name} ($)",
        f"{pair.comparison.estimate_name} ($)",
        "Delta ($)",
        "Narrative",
    ]
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=row, column=col_idx, value=header).font = header_font
    row += 1
    if not drivers:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        cell = ws.cell(row=row, column=1, value="No driver data provided.")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        return row + 2
    for driver in drivers:
        primary_val = driver.get("primary_total")
        comparison_val = driver.get("comparison_total")
        delta_val = driver.get("delta_total")
        if delta_val is None and isinstance(primary_val, (int, float)) and isinstance(comparison_val, (int, float)):
            delta_val = round((comparison_val or 0) - (primary_val or 0), 2)
        ws.cell(row=row, column=1, value=driver.get("category"))
        primary_cell = ws.cell(row=row, column=2, value=primary_val)
        comparison_cell = ws.cell(row=row, column=3, value=comparison_val)
        delta_cell = ws.cell(row=row, column=4, value=delta_val)
        narrative_cell = ws.cell(row=row, column=5, value=driver.get("narrative") or "")
        for cell in (primary_cell, comparison_cell, delta_cell):
            if isinstance(cell.value, (int, float)):
                cell.number_format = "$#,##0.00"
        narrative_cell.alignment = Alignment(wrap_text=True, vertical="top")
        row += 1
    return row + 1


def _resolve_overview_text(narrative) -> str:
    sections = narrative.sections or {}
    overview = (sections.get("overview_of_estimates") or "").strip()
    if overview:
        return overview
    return _extract_first_paragraph(narrative.blocks) or "No narrative available."


def _extract_first_paragraph(blocks: List[Any]) -> str:
    for block in blocks:
        kind = getattr(block, "kind", None)
        text = getattr(block, "text", "")
        if kind in {"paragraph", "heading"} and text:
            return text
    return ""
