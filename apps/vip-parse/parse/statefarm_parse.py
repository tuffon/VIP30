#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
StateFarmParser
---------------
Parses State Farm building estimate PDFs and emits a JSON payload aligned to the
Xactimate schema you’re already using. Also writes a <name>.out file (raw lines).

Key behaviors
- Skips the first two pages (front-matter) by default; also “sniffs” early pages for
  a real start when it finds "Summary for" or "Estimate:".
- Extracts case metadata, coverage summaries, per-area metrics and “Area Totals”
  blocks, and best-effort line items.
- Output:
    - case_metadata matches Xactimate keys (money as strings)
    - sections present (empty for State Farm)
    - coverage_table / summaries_by_coverage money-as-strings
    - recap_* placeholders present
    - grand_total_areas reserved (None), State Farm area totals kept in area_totals_blocks
    - writes <name>.statefarm.json and <name>.out
"""

from __future__ import annotations

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

import pdfplumber

from .xactimate.visible_text import extract_visible_lines, get_visible_text_config

# -----------------------
# Utilities
# -----------------------
_money_like = re.compile(r"\$?\(?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?")
_number_like = re.compile(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?")

def _clean_ws(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()

def _to_float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "")
    try:
        val = float(s)
        return -val if neg else val
    except ValueError:
        return None

def _fmt_money_s(val) -> Optional[str]:
    """Format to Xactimate-style money string '1,234.56' or None."""
    if val is None:
        return None
    try:
        return f"{float(val):,.2f}"
    except Exception:
        return None

def _money_from_line(line: str) -> Optional[float]:
    m = _money_like.search(line)
    return _to_float(m.group(0)) if m else None

def _ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def _resolve_output_path(in_file: str, out_path: str, suffix: str = ".json") -> str:
    r"""
    If out_path is a dir (existing or ends with sep), write <base+suffix> within it.
    Otherwise treat as a file path. Cross-platform trailing slash handling.
    """
    trailing_sep = out_path.endswith("/") or out_path.endswith('\\')
    if os.path.isdir(out_path) or trailing_sep:
        _ensure_dir(out_path)
        base = os.path.splitext(os.path.basename(in_file))[0]
        return os.path.join(out_path, base + suffix)
    parent = os.path.dirname(out_path)
    _ensure_dir(parent)
    return out_path

def _derive_json_and_out_paths(input_file: str, output_path: str) -> Tuple[str, str]:
    r"""
    Returns (json_path, out_path).
    - If output_path is a dir (or ends with / or \), use input filename + suffixes.
    - If output_path is a file, write JSON to that file (or .statefarm.json if no .json),
      and write .out next to it with the same stem.
    """
    trailing_sep = output_path.endswith("/") or output_path.endswith('\\')
    if os.path.isdir(output_path) or trailing_sep:
        _ensure_dir(output_path)
        base = os.path.splitext(os.path.basename(input_file))[0]
        return (
            os.path.join(output_path, base + ".json"),
            os.path.join(output_path, base + ".out"),
        )
    parent = os.path.dirname(output_path)
    _ensure_dir(parent)
    stem, ext = os.path.splitext(output_path)
    json_path = output_path if ext.lower() == ".json" else stem + ".statefarm.json"
    out_path = stem + ".out"
    return json_path, out_path

# -----------------------
# Parser
# -----------------------
@dataclass
class StateFarmParser:
    input_file: str
    output_path: Optional[str] = None
    debug: bool = False
    skip_header_pages: int = 2  # first two pages are headers/front-matter

    validations: Dict[str, Any] = field(default_factory=dict)

    # ---- public API ----
    def run(self) -> Dict[str, Any]:
        pages = self._extract_pages()
        start_idx = self._start_index(pages)
        core_pages = pages[start_idx:]

        case_md = self._parse_case_metadata(core_pages)
        summaries = self._parse_coverage_summaries(core_pages)
        areas, area_totals = self._parse_area_blocks(core_pages)
        line_items = self._parse_line_items(core_pages)

        # Derive compact coverage rows from summaries
        coverage_table_rows = []
        sum_rcv = 0.0
        for cov_name, kv in summaries.items():
            rcv = kv.get("replacement_cost_value")
            if isinstance(rcv, (int, float)):
                sum_rcv += rcv
            coverage_table_rows.append({
                "coverage": cov_name,
                "line_item_total": _fmt_money_s(kv.get("line_item_total")),
                "material_sales_tax": _fmt_money_s(kv.get("material_sales_tax")),
                "california_lumber_assessment_fee": _fmt_money_s(kv.get("california_lumber_assessment_fee")),
                "replacement_cost_value": _fmt_money_s(kv.get("replacement_cost_value")),
                "less_deductible": _fmt_money_s(kv.get("less_deductible")),
                "net_payment": _fmt_money_s(kv.get("net_payment")),
            })

        # --- build Xactimate-aligned case_metadata ---
        case_md_aligned = {
            "claim_number": (case_md.get("claim_number") or None),
            "policy_number": (case_md.get("policy_number") or None),
            "loss_type": (case_md.get("type_of_loss") or None),
            "coverage": [],  # SF docs typically don’t expose policy-limit table here
            "property_address": (case_md.get("property") or None),
            "date_of_loss": (case_md.get("date_of_loss") or None),
            "date_received": None,
            "date_inspected": (case_md.get("date_inspected") or None),
            "date_entered": None,
            "price_list": (case_md.get("price_list") or None),
            "depreciate_material": None,
            "depreciate_op": None,
            "depreciate_non_material": None,
            "depreciate_taxes": None,
            "estimate_name": (case_md.get("estimate_id") or None),
            "depreciate_removal": None,
            "region": None,
            "building_type": None,
            # placeholders to be filled once parsed (kept for schema parity)
            "line_item_totals": None,
            "labor_minimums": None,
            "additional_charges": None,
        }

        # --- top-level payload aligned to your Xactimate schema ---
        payload: Dict[str, Any] = {
            "source": {
                "parser": "statefarm",
                "file_name": os.path.basename(self.input_file),
                "start_page_index_used": start_idx,
            },
            "case_metadata": case_md_aligned,
            "sections": [],  # SF has no Xactimate-style sections

            "coverage_table": coverage_table_rows,
            "coverage_totals": None,
            "summaries_by_coverage": {
                k: {
                    "line_item_total": _fmt_money_s(v.get("line_item_total")),
                    "california_lumber_assessment_fee": _fmt_money_s(v.get("california_lumber_assessment_fee")),
                    "material_sales_tax": _fmt_money_s(v.get("material_sales_tax")),
                    "subtotal": _fmt_money_s(v.get("subtotal")),
                    "overhead": _fmt_money_s(v.get("overhead")),
                    "profit": _fmt_money_s(v.get("profit")),
                    "replacement_cost_value": _fmt_money_s(v.get("replacement_cost_value")),
                    "less_deductible": _fmt_money_s(v.get("less_deductible")),
                    "net_payment": _fmt_money_s(v.get("net_payment")),
                } for k, v in summaries.items()
            },
            "recap_tax_op": None,
            "recap_by_room": {"rows": [], "subtotals": []},
            "recap_by_category": {"op_items": [], "non_op_items": [], "allocations": {}, "totals": None},
            "grand_total_areas": None,          # Xactimate single-block slot
            "area_totals_blocks": area_totals,  # keep SF detailed blocks
            "line_items": line_items,           # best-effort list
        }

        if self.debug:
            payload["validations"] = {"coverage": {"sum_rcv_across_coverages": round(sum_rcv, 2)}}

        est_name = case_md_aligned.get("estimate_name") or Path(self.input_file).stem
        payload["estimate_name"] = est_name
        if isinstance(payload.get("case_metadata"), dict) and not payload["case_metadata"].get("estimate_name"):
            payload["case_metadata"]["estimate_name"] = est_name

        # --- WRITE OUTPUTS: JSON + .out ---
        if self.output_path:
            json_path, out_path = _derive_json_and_out_paths(self.input_file, self.output_path)

            # JSON
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            # .out (raw lines as parsed)
            with open(out_path, "w", encoding="utf-8") as f:
                for p in pages:
                    for ln in p.split("\n"):
                        f.write(ln + "\n")

            if self.debug:
                print(f"[debug] wrote: {json_path}")
                print(f"[debug] wrote: {out_path}")

        return payload

    # ---- extraction helpers ----
    def _extract_pages(self) -> List[str]:
        pages: List[str] = []
        with pdfplumber.open(self.input_file) as pdf:
            config = get_visible_text_config()
            for idx, page in enumerate(pdf.pages):
                lines = extract_visible_lines(
                    page,
                    config=config,
                    debug_page_number=idx + 1,
                )
                pages.append("\n".join(lines))
        return pages

    def _start_index(self, pages: List[str]) -> int:
        # Honor explicit skip; if we detect a summary earlier, we won't go before it.
        idx = min(self.skip_header_pages, max(0, len(pages) - 1))
        # If any of the first 3 pages contain a clear "Summary for" or "Estimate:", start there.
        for i in range(min(3, len(pages))):
            sniff = pages[i]
            if "Summary for" in sniff or "Estimate:" in sniff:
                idx = max(idx, i)
        return idx

    def _parse_case_metadata(self, pages: List[str]) -> Dict[str, Any]:
        meta = {
            "estimate_id": None,
            "claim_number": None,
            "policy_number": None,
            "price_list": None,
            "type_of_loss": None,
            "deductible": None,
            "date_of_loss": None,
            "date_inspected": None,
            "insured": None,
            "property": None,
        }
        # Use the first core page with "Estimate:" if present
        first = None
        for p in pages[:5]:
            if "Estimate:" in p:
                first = p
                break
        if first is None and pages:
            first = pages[0]

        for ln in first.splitlines():
            t = _clean_ws(ln)
            if t.startswith("Estimate:"):
                meta["estimate_id"] = t.split("Estimate:", 1)[1].strip()
            elif t.startswith("Claim Number:"):
                meta["claim_number"] = t.split("Claim Number:", 1)[1].strip()
            elif t.startswith("Policy Number:"):
                meta["policy_number"] = t.split("Policy Number:", 1)[1].strip()
            elif t.startswith("Price List:"):
                meta["price_list"] = t.split("Price List:", 1)[1].strip()
            elif t.startswith("Type of Loss:"):
                meta["type_of_loss"] = t.split("Type of Loss:", 1)[1].strip()
            elif t.startswith("Deductible:"):
                meta["deductible"] = _to_float(t.split("Deductible:", 1)[1])
            elif t.startswith("Date of Loss:"):
                meta["date_of_loss"] = t.split("Date of Loss:", 1)[1].strip()
            elif t.startswith("Date Inspected:"):
                meta["date_inspected"] = t.split("Date Inspected:", 1)[1].strip()
            elif t.startswith("Insured:"):
                meta["insured"] = t.split("Insured:", 1)[1].strip()
            elif t.startswith("Property:"):
                meta["property"] = t.split("Property:", 1)[1].strip()

        return meta

    def _parse_coverage_summaries(self, pages: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Blocks look like:
            Summary for Coverage A - Dwelling - <peril/notes>
            Line Item Total 69,914.45
            California Lumber Assessment Fee 11.59
            Material Sales Tax 674.52
            Subtotal 70,600.00
            Overhead 3,530.00
            Profit 3,530.00
            Replacement Cost Value 77,660.00
            Less Deductible (0.00)
            Net Payment $77,660.00
        """
        summaries: Dict[str, Dict[str, Any]] = {}
        joined = "\n\n".join(pages)

        blocks = re.split(r"\n(?=Summary for )", joined)
        for blk in blocks:
            if not blk.strip().startswith("Summary for "):
                continue
            header = blk.splitlines()[0].strip()
            cov_name = header.replace("Summary for ", "").strip()

            data = {
                "line_item_total": None,
                "california_lumber_assessment_fee": None,
                "material_sales_tax": None,
                "subtotal": None,
                "overhead": None,
                "profit": None,
                "replacement_cost_value": None,
                "less_deductible": None,
                "net_payment": None,
            }

            for ln in blk.splitlines()[1:30]:
                t = _clean_ws(ln)
                low = t.lower()
                if low.startswith("line item total"):
                    data["line_item_total"] = _money_from_line(t)
                elif low.startswith("california lumber assessment fee"):
                    data["california_lumber_assessment_fee"] = _money_from_line(t)
                elif low.startswith("material sales tax"):
                    data["material_sales_tax"] = _money_from_line(t)
                elif low.startswith("subtotal"):
                    data["subtotal"] = _money_from_line(t)
                elif low.startswith("overhead") or low.startswith("general contractor overhead"):
                    data["overhead"] = _money_from_line(t)
                elif low.startswith("profit") or low.startswith("general contractor profit"):
                    data["profit"] = _money_from_line(t)
                elif low.startswith("replacement cost value"):
                    data["replacement_cost_value"] = _money_from_line(t)
                elif low.startswith("less deductible"):
                    data["less_deductible"] = _money_from_line(t)
                elif low.startswith("net payment") or low.startswith("net claim"):
                    data["net_payment"] = _money_from_line(t)

            summaries[cov_name] = data

        return summaries

    def _parse_area_blocks(self, pages: List[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract per-area metrics and "Area Totals:" aggregates.
        Returns (areas, area_totals_blocks)
        """
        areas: List[Dict[str, Any]] = []
        totals: List[Dict[str, Any]] = []

        metric_map = {
            "sf walls": "sf_walls",
            "sf ceiling": "sf_ceiling",
            "sf walls and ceiling": "sf_walls_and_ceiling",
            "sf floor": "sf_floor",
            "sy flooring": "sy_flooring",
            "lf floor perimeter": "lf_floor_perimeter",
            "sf long wall": "sf_long_wall",
            "sf short wall": "sf_short_wall",
            "lf ceil. perimeter": "lf_ceil_perimeter",
            "floor area": "floor_area",
            "total area": "total_area",
            "interior wall area": "interior_wall_area",
            "exterior wall area": "exterior_wall_area",
            "exterior perimeter of walls": "exterior_perimeter_of_walls",
            "surface area": "surface_area",
            "number of squares": "number_of_squares",
            "total perimeter length": "total_perimeter_length",
            "total ridge length": "total_ridge_length",
            "total hip length": "total_hip_length",
        }
        val = r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
        label_union = "|".join(map(re.escape, metric_map.keys()))
        metric_re = re.compile(fr"{val}\s+({label_union})", re.IGNORECASE)

        for p in pages:
            lines = [ln for ln in p.splitlines() if ln.strip()]
            text = re.sub(r"\s+", " ", p)

            if "Area Totals:" in p:
                header_line = next((ln for ln in lines if ln.strip().startswith("Area Totals:")), None)
                area_name = header_line.split("Area Totals:", 1)[1].strip() if header_line else "Unknown"
                metrics: Dict[str, float] = {}
                for m in metric_re.finditer(text):
                    key = metric_map[m.group(2).lower()]
                    metrics[key] = _to_float(m.group(1))
                tot_line = next((ln for ln in lines if ln.strip().startswith("Total ")), "")
                tots = _number_like.findall(tot_line)
                rcv_total = _to_float(tots[-1]) if tots else None
                totals.append({"area": area_name, "metrics": metrics, "total_rcv": rcv_total})
                continue

            if "Height:" in p and not p.strip().startswith("CONTINUED -"):
                area_header = None
                for i, ln in enumerate(lines):
                    if "Height:" in ln:
                        area_header = lines[i-1] if i > 0 else ln
                        break
                area_name = _clean_ws(area_header or "Area")
                metrics: Dict[str, float] = {}
                for m in metric_re.finditer(text):
                    key = metric_map[m.group(2).lower()]
                    metrics[key] = _to_float(m.group(1))
                if metrics:
                    areas.append({"area": area_name, "metrics": metrics})

        return areas, totals

    def _parse_line_items(self, pages: List[str]) -> List[Dict[str, Any]]:
        """
        Best-effort parsing of numbered line items:
          15. Description ... 284.71 SF 0.81 ... $230.62
        Returns flat list; includes 'area' context when detected.
        """
        items: List[Dict[str, Any]] = []
        area_ctx: Optional[str] = None

        area_hdr = re.compile(r"^(?:Subroom:\s*)?([A-Za-z][A-Za-z0-9 _\-/#]+)\s+Height:", re.IGNORECASE)
        line_re = re.compile(
            r"^\s*\*?\s*(\d+)\.\s+(?P<desc>.+?)\s+(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s+([A-Z]{2}|EA|HR|SF|LF|SY)\s+(\d{1,3}(?:,\d{3})*(?:\.\d+)?)",
            re.IGNORECASE
        )

        for p in pages:
            m_area = area_hdr.search(p)
            if m_area:
                area_ctx = _clean_ws(m_area.group(1))

            for ln in p.splitlines():
                t = _clean_ws(ln)
                m = line_re.match(t)
                if not m:
                    continue
                desc = _clean_ws(m.group("desc"))
                qty = _to_float(m.group(3))
                unit = m.group(4)
                unit_price = _to_float(m.group(5))
                monies = _money_like.findall(t)
                rcv = _to_float(monies[-1]) if monies else None
                tax = None
                if "TAX" in t.upper() and len(monies) >= 2:
                    tax = _to_float(monies[-2])

                items.append({
                    "area": area_ctx,
                    "line_no": int(m.group(1)),
                    "description": desc,
                    "qty": qty,
                    "unit": unit,
                    "unit_price": unit_price,
                    "tax": tax,
                    "rcv": rcv
                })

        return items
