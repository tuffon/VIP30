from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side, numbers
from openpyxl.utils import get_column_letter

from vip_shared.pipeline.output_modes import ModeFilteredOutput, OutputMode, OutputModeFilter

logger = logging.getLogger("vip-parse.bid-comp.xlsx")

_THIN_BORDER = Border(
    left=Side(style="thin", color="DDDDDD"),
    right=Side(style="thin", color="DDDDDD"),
    top=Side(style="thin", color="DDDDDD"),
    bottom=Side(style="thin", color="DDDDDD"),
)

_SEVERITY_FILLS = {
    "critical": PatternFill(fill_type="solid", fgColor="FF4444"),
    "notable": PatternFill(fill_type="solid", fgColor="FFA500"),
    "informational": PatternFill(fill_type="solid", fgColor="ADD8E6"),
}


def export_xlsx(
    *,
    pair,
    narrative,
    category_rows: List[Dict[str, Any]],
    recap_rows: Optional[List[Dict[str, Any]]] = None,
    output_mode: Optional[OutputMode] = None,
    methodology: Optional[Any] = None,
    audit_metadata: Optional[Dict[str, Any]] = None,
    signal_bundle: Optional[Any] = None,
) -> bytes:
    mode = output_mode or OutputMode.INTERNAL
    filtered = OutputModeFilter.apply(mode, narrative, methodology, signal_bundle)

    wb = Workbook()
    ws_exec = wb.active
    ws_exec.title = "Executive Summary"

    _write_executive_summary(ws_exec, pair, filtered, category_rows)
    _write_ranked_impact(wb, pair, category_rows, signal_bundle)

    if filtered.include_methodology_sheet:
        _write_methodology_sheet(wb, methodology, filtered)
    if filtered.include_scope_sheet:
        _write_scope_alignment_sheet(wb, filtered)
    if filtered.include_category_detail:
        _write_category_detail_sheet(wb, pair, category_rows, recap_rows or [])

    _write_audit_trail_sheet(wb, audit_metadata or {}, mode)

    bio = BytesIO()
    wb.save(bio)
    payload = bio.getvalue()
    logger.info("xlsx export complete mode=%s bytes=%d sheets=%d", mode.value, len(payload), len(wb.sheetnames))
    return payload


def _write_executive_summary(ws, pair, filtered: ModeFilteredOutput, category_rows: List[Dict[str, Any]]) -> None:
    title = ws["A1"]
    title.value = "Bid Comparison — Executive Summary"
    title.font = Font(bold=True, size=14)

    primary_total, comparison_total, delta_total = _totals(category_rows)

    ws["A3"] = "Primary Estimate"
    ws["B3"] = pair.primary.estimate_name
    ws["A4"] = "Comparison Estimate"
    ws["B4"] = pair.comparison.estimate_name
    ws["A5"] = "Primary Total"
    ws["B5"] = primary_total
    ws["A6"] = "Comparison Total"
    ws["B6"] = comparison_total
    ws["A7"] = "Total Delta"
    ws["B7"] = delta_total

    for row in range(3, 8):
        ws[f"A{row}"].font = Font(bold=True)
        ws[f"A{row}"].border = _THIN_BORDER
        ws[f"B{row}"].border = _THIN_BORDER
    for row in (5, 6, 7):
        ws[f"B{row}"].number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

    start_row = 9
    ws[f"A{start_row}"] = "Top Drivers"
    ws[f"A{start_row}"].font = Font(bold=True)
    start_row += 1

    headers = ["Category", "Primary ($)", "Comparison ($)", "Delta ($)", "% of Total"]
    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=idx, value=header)
        cell.font = Font(bold=True)
        cell.border = _THIN_BORDER

    ranked = _ranked_rows(category_rows)
    driver_rows = _resolve_driver_rows(filtered, ranked)
    row = start_row + 1
    for entry in driver_rows:
        ws.cell(row=row, column=1, value=entry.get("category"))
        ws.cell(row=row, column=2, value=entry.get("primary_total"))
        ws.cell(row=row, column=3, value=entry.get("comparison_total"))
        ws.cell(row=row, column=4, value=entry.get("delta"))
        ws.cell(row=row, column=5, value=entry.get("pct_of_total_variance") / 100 if entry.get("pct_of_total_variance") is not None else None)
        for col in range(1, 6):
            ws.cell(row=row, column=col).border = _THIN_BORDER
        for col in (2, 3, 4):
            ws.cell(row=row, column=col).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE
        ws.cell(row=row, column=5).number_format = "0.0%"
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Structural Flags").font = Font(bold=True)
    row += 1
    if filtered.structural_flags:
        for flag in filtered.structural_flags:
            ws.cell(row=row, column=1, value=f"- {flag}")
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
            ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True)
            row += 1
    else:
        ws.cell(row=row, column=1, value="No structural flags")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Methodology Summary").font = Font(bold=True)
    row += 1
    ws.cell(row=row, column=1, value=filtered.methodology_summary or "Methodology analysis not available")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True)

    ws.freeze_panes = "A2"
    _autosize(ws)


def _write_ranked_impact(wb: Workbook, pair, category_rows: List[Dict[str, Any]], signal_bundle: Optional[Any]) -> None:
    ws = wb.create_sheet("Ranked Impact")
    headers = ["Rank", "Category", "Primary ($)", "Comparison ($)", "Delta ($)", "% of Total Variance", "Severity"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.border = _THIN_BORDER

    ranked = _ranked_rows(category_rows)
    severity_by_category = _severity_by_category(signal_bundle)

    for idx, row in enumerate(ranked, start=1):
        severity = severity_by_category.get(row["category"], "")
        ws.append([
            idx,
            row["category"],
            row["primary_total"],
            row["comparison_total"],
            row["delta"],
            row["pct_of_total_variance"] / 100,
            severity,
        ])

    max_row = ws.max_row
    for r in range(2, max_row + 1):
        for c in range(1, 8):
            ws.cell(row=r, column=c).border = _THIN_BORDER
        for c in (3, 4, 5):
            ws.cell(row=r, column=c).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE
        ws.cell(row=r, column=6).number_format = "0.0%"

        sev = str(ws.cell(row=r, column=7).value or "").lower()
        fill = _SEVERITY_FILLS.get(sev)
        if fill is not None:
            ws.cell(row=r, column=7).fill = fill

    if max_row >= 2:
        ws.conditional_formatting.add(
            f"E2:E{max_row}",
            ColorScaleRule(
                start_type="num",
                start_value=-1,
                start_color="CC0000",
                mid_type="num",
                mid_value=0,
                mid_color="FFFFFF",
                end_type="num",
                end_value=1,
                end_color="00AA00",
            ),
        )

    ws.freeze_panes = "A2"
    _autosize(ws)


def _write_methodology_sheet(wb: Workbook, methodology: Optional[Any], filtered: ModeFilteredOutput) -> None:
    ws = wb.create_sheet("Methodology")
    ws["A1"] = "Methodology Comparison"
    ws["A1"].font = Font(bold=True, size=14)

    row = 3
    rows = [
        ("Summary", filtered.methodology_summary or "Methodology analysis not available"),
    ]

    if methodology is not None:
        rows.extend(
            [
                ("Primary O&P", methodology.primary_op.structure_type.value),
                ("Comparison O&P", methodology.comparison_op.structure_type.value),
                ("Depreciation Differs", str(methodology.depreciation_approach_differs)),
                ("Price List Differs", str(methodology.price_list_differs)),
                ("Locality Factors", methodology.locality_factors or "n/a"),
                ("Data Granularity", methodology.data_granularity.value),
            ]
        )

    for label, value in rows:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=value)
        ws.cell(row=row, column=1).border = _THIN_BORDER
        ws.cell(row=row, column=2).border = _THIN_BORDER
        ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        row += 1

    ws.freeze_panes = "A2"
    _autosize(ws)


def _write_scope_alignment_sheet(wb: Workbook, filtered: ModeFilteredOutput) -> None:
    ws = wb.create_sheet("Scope Alignment")
    ws["A1"] = "Scope Alignment"
    ws["A1"].font = Font(bold=True, size=14)

    ws["A3"] = "Scope Observations"
    ws["A3"].font = Font(bold=True)

    row = 4
    if filtered.scope_observations:
        for item in filtered.scope_observations:
            ws.cell(row=row, column=1, value=f"- {item}")
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
            ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True)
            row += 1
    else:
        ws.cell(row=row, column=1, value="No scope observations")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)

    ws.freeze_panes = "A2"
    _autosize(ws)


def _write_category_detail_sheet(
    wb: Workbook,
    pair,
    category_rows: List[Dict[str, Any]],
    recap_rows: List[Dict[str, Any]],
) -> None:
    ws = wb.create_sheet("Category Detail")
    headers = [
        "Category",
        f"{pair.primary.estimate_name} ($)",
        f"{pair.comparison.estimate_name} ($)",
        "Delta ($)",
        "Delta (% of Primary)",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.border = _THIN_BORDER

    for row in category_rows:
        ws.append([
            row.get("category"),
            row.get("primary_total"),
            row.get("comparison_total"),
            row.get("delta"),
            row.get("delta_pct"),
        ])

    max_row = ws.max_row
    for r in range(2, max_row + 1):
        for c in range(1, 6):
            ws.cell(row=r, column=c).border = _THIN_BORDER
        for c in (2, 3, 4):
            ws.cell(row=r, column=c).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE
        ws.cell(row=r, column=5).number_format = "0.00%"

    if max_row >= 2:
        ws.conditional_formatting.add(
            f"D2:D{max_row}",
            ColorScaleRule(
                start_type="num",
                start_value=-1,
                start_color="CC0000",
                mid_type="num",
                mid_value=0,
                mid_color="FFFFFF",
                end_type="num",
                end_value=1,
                end_color="00AA00",
            ),
        )
        ws.conditional_formatting.add(
            f"D2:D{max_row}",
            DataBarRule(
                start_type="num",
                start_value=0,
                end_type="max",
                end_value=0,
                color="638EC6",
                showValue=True,
            ),
        )

    if recap_rows:
        spacer = ws.max_row + 2
        ws.cell(row=spacer, column=1, value="Recap Detail (raw)").font = Font(bold=True)
        ws.cell(row=spacer + 1, column=1, value="Estimate").font = Font(bold=True)
        ws.cell(row=spacer + 1, column=2, value="Group").font = Font(bold=True)
        ws.cell(row=spacer + 1, column=3, value="Item").font = Font(bold=True)
        ws.cell(row=spacer + 1, column=4, value="Total ($)").font = Font(bold=True)
        row = spacer + 2
        for entry in recap_rows[:500]:
            ws.cell(row=row, column=1, value=entry.get("estimate"))
            ws.cell(row=row, column=2, value=entry.get("group"))
            ws.cell(row=row, column=3, value=entry.get("item"))
            ws.cell(row=row, column=4, value=entry.get("total"))
            ws.cell(row=row, column=4).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE
            row += 1

    ws.freeze_panes = "A2"
    _autosize(ws)


def _write_audit_trail_sheet(wb: Workbook, audit_metadata: Dict[str, Any], mode: OutputMode) -> None:
    ws = wb.create_sheet("Audit Trail")
    ws["A1"] = "Audit Trail"
    ws["A1"].font = Font(bold=True, size=14)

    rows = [
        ("Pipeline Version", "v2.0"),
        ("Output Mode", mode.value),
        ("Analysis Timestamp", audit_metadata.get("analysis_timestamp") or datetime.utcnow().isoformat()),
        ("Primary Filename", audit_metadata.get("primary_filename") or "n/a"),
        ("Comparison Filename", audit_metadata.get("comparison_filename") or "n/a"),
        ("Primary SHA-256", audit_metadata.get("primary_hash") or "n/a"),
        ("Comparison SHA-256", audit_metadata.get("comparison_hash") or "n/a"),
    ]

    row = 3
    for label, value in rows:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=1).border = _THIN_BORDER
        ws.cell(row=row, column=2, value=value)
        ws.cell(row=row, column=2).border = _THIN_BORDER
        row += 1

    ws.freeze_panes = "A2"
    _autosize(ws)


def _ranked_rows(category_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    total_abs = sum(abs(float(r.get("delta") or 0.0)) for r in category_rows) or 1.0
    for row in category_rows:
        delta = float(row.get("delta") or 0.0)
        ranked.append(
            {
                "category": row.get("category") or "Unknown",
                "primary_total": float(row.get("primary_total") or 0.0),
                "comparison_total": float(row.get("comparison_total") or 0.0),
                "delta": delta,
                "abs_delta": abs(delta),
                "pct_of_total_variance": round(abs(delta) / total_abs * 100.0, 2),
            }
        )
    ranked.sort(key=lambda r: (-r["abs_delta"], str(r["category"]).lower()))
    return ranked


def _resolve_driver_rows(filtered: ModeFilteredOutput, ranked_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_category = {str(r["category"]): r for r in ranked_rows}
    out: List[Dict[str, Any]] = []
    for driver in filtered.top_drivers:
        category = str(driver.get("category") or "")
        if category and category in by_category:
            out.append(by_category[category])
    if not out:
        out = ranked_rows[:3]
    return out


def _totals(category_rows: List[Dict[str, Any]]) -> tuple[float, float, float]:
    primary_total = round(sum(float(r.get("primary_total") or 0.0) for r in category_rows), 2)
    comparison_total = round(sum(float(r.get("comparison_total") or 0.0) for r in category_rows), 2)
    delta_total = round(comparison_total - primary_total, 2)
    return primary_total, comparison_total, delta_total


def _severity_by_category(signal_bundle: Optional[Any]) -> Dict[str, str]:
    if signal_bundle is None:
        return {}
    out: Dict[str, str] = {}
    for flag in getattr(signal_bundle, "emphasis_flags", []) or []:
        category = getattr(flag, "category", None)
        severity = getattr(getattr(flag, "severity", None), "value", None)
        if category and severity:
            out[str(category)] = str(severity)
    return out


def _autosize(ws) -> None:
    for column_cells in ws.columns:
        letter = get_column_letter(column_cells[0].column)
        max_len = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=0)
        ws.column_dimensions[letter].width = min(max(12, max_len + 2), 80)
