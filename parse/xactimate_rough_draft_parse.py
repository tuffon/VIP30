#!/usr/bin/env python3
"""
Xactimate Rough Draft Parser (schema v2)
- Class accepts input_file and output_path (dir or filename).
- Writes <stem>.out (raw lines) and <stem>.json (structured).
- Console prints per-document table of sections with non-zero deltas.
- Optional --debug prints doc-level validation table and includes 'validations' in JSON.

Output schema (top-level):
{
  "case_metadata": {
    ...existing fields...,
    "line_item_totals": {...},
    "labor_minimums": {...},
    "additional_charges": {...}
  },
  "sections": [...],
  "grand_total_areas": {...},
  "coverage": { "rows": [...], "totals": {...} },
  "recaps_and_summaries": {
    "summaries_by_coverage": {...},
    "recap_tax_op": {...},
    "recap_by_room": {...},
    "recap_by_category": {...}
  },
  // present only when debug=True
  "validations": {
    "per_section": [...],
    "document": {...}
  }
}
"""

import os
import re
import json
import pdfplumber
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Tuple

# =========================
# Regex (Xactimate-specific)
# =========================
PAGE_NUMBER_PATTERN = r'.*\d+/\d+/\d+\s+Page:\s*\d+'
SINGLE_PAGE_NUMBER_PATTERN = r'^\d{1,3}$'
SECTION_HEIGHT_PATTERN = r'^(.+?)\s+Height:\s*(.+)'
SECTION_NAME_EXTRACTION = r'([A-Z][A-Za-z\s\.\(\)/]+(?:\s+\d+)?)\s*$'
SUBROOM_PATTERN = r'^Subroom:\s+(.+?)\s+Height:\s*(.+)'
TABLE_HEADER_PRIMARY = r'CAT\s+SEL\s+ACT\s+DESCRIPTION'
TABLE_HEADER_CONTINUATION = r'^CONTINUED\s*-\s*.+'
TABLE_HEADER_SECOND_LINE_FRAGMENT = r'CALC\s+QTY'
LINE_ITEM_PATTERN = r'^(\d+)\.\s+([A-Z]{3,})\s+([A-Z0-9<>+\-/]+)\s+(\S)\s+(.*)$'
LINE_ITEM_HEADER_PATTERN = r'^([-*=~_]{2,})\s*(.+?)\s*([-*=~_]{2,})\s*:?\s*$'

CALC_PREFIX_PATTERN = r'(?:([0-9*+\-./\s]+?)\s+)?'
CALC_LINE_DETECTION_PATTERN = r'[0-9.]+\s*[A-Z]{2,}\s*(?:\[[^\]]+\]|\bSEE\b|[0-9,]+\.[0-9]+)'
QTY_UNIT_PATTERN = r'([0-9]+(?:\.[0-9]+)?)\s*([A-Z]{2,})\s*'
BRACKETS_PATTERN = r'(?:\[([^\]]+)\])?\s*'
CURRENCY_PATTERN = r'([0-9,]+\.[0-9]+)'
SEE_PATTERN = r'(?:SEE|SEE:)\s+([A-Z0-9][A-Z0-9._/\- ]+?)\s*$'
TERMINAL_STATUS_PATTERN = r'\b([A-Z0-9]+(?:[._/\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+(?:[._/\-][A-Z0-9]+)*)*)\s*$'

METADATA_PATTERNS = {
    'sf_walls_and_ceiling': r'([0-9,]+\.[0-9]+)\s+SF\s+Walls\s+&\s+Ceiling',
    'sf_walls': r'([0-9,]+\.[0-9]+)\s+SF\s+Walls(?!\s+&)',
    'sf_ceiling': r'([0-9,]+\.[0-9]+)\s+SF\s+Ceiling(?!\s+&)',
    'sf_floor': r'([0-9,]+\.[0-9]+)\s+SF\s+Floor(?!\s+Perimeter)',
    'sy_flooring': r'([0-9,]+\.[0-9]+)\s+SY\s+Flooring',
    'lf_floor_perimeter': r'([0-9,]+\.[0-9]+)\s+LF\s+Floor\s+Perimeter',
    'lf_ceil_perimeter': r'([0-9,]+\.[0-9]+)\s+LF\s+Ceil\.\s+Perimeter',
}
DOOR_PATTERN = r'Door\s+([\d\'\"\s]+[Xx][\d\'\"\s]+)\s+Opens\s+into\s+([A-Z_0-9]+)'
MISSING_WALL_PATTERN = r'Missing\s+Wall\s+([\d\'\"\s/]+[Xx][\d\'\"\s]+)\s+Opens\s+into\s+([A-Z_0-9]+)'
TOTALS_PATTERN = r'^Totals?:'
CASE_LINE1_PATTERN = r'Claim\s+Number:\s*(\S*)\s+Policy\s+Number:\s*(\S*)\s+Type\s+of\s+Loss:\s*([^\n]*)'
COVERAGE_SECTION_PATTERN = r'Coverage\s+Deductible\s+Policy\s+Limit\s*\n((?:.*?\$[\d,]+\.[\d]{2}.*?\n?)+)'
COVERAGE_ROW_PATTERN = r'^\s*([A-Za-z\s,&\-]+?)\s+\$?([\d,]+\.[\d]{2})\s+\$?([\d,]+\.[\d]{2})'
PROPERTY_ADDRESS_PATTERN = r'Property:\s*(.+?)(?=\n[A-Za-z\s]+:|\Z)'
DATE_LINE1_PATTERN = r'Date\s+of\s+Loss:\s*([^\n]*?)\s*Date\s+Received:\s*([^\n]*?)(?=\n|$)'
DATE_LINE2_PATTERN = r'Date\s+Inspected:\s*([^\n]*?)\s*Date\s+Entered:\s*([^\n]+?)(?=\n|$)'
PRICE_LIST_PATTERN = r'Price\s+List:\s*([^\s]+)\s+Depreciate\s+Material:\s*(Yes|No)\s+Depreciate\s+O&P:\s*(Yes|No)'
DEPREC_LINE2_PATTERN = r'(?:.*?\s+)?Depreciate\s+Non-material:\s*(Yes|No)\s+Depreciate\s+Taxes:\s*(Yes|No)'
ESTIMATE_LINE_PATTERN = r'Estimate:\s*([^\s]+)\s+Depreciate\s+Removal:\s*(Yes|No)'

REPEATED_CHAR_PATTERN = r'([A-Z])\1{2,}'
QUOTE_PATTERN = r'[\"\']{2,}'

# ----- End-of-doc tables -----
LABOR_MIN_APPLIED_PATTERN = r'^Totals?:\s*Labor\s+Minimums\s+Applied\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)'
LINE_ITEM_TOTALS_PATTERN = r'^Line\s+Item\s+Totals:\s*([A-Za-z0-9._\-]+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)'
ADD_CHARGE_ROW_PATTERN = r'^([A-Za-z].*?)\s+([\d,]+\.\d+)$'
ADD_CHARGES_HDR_PATTERN = r'^Additional\s+Charges\s+Charge\s*$'
ADD_CHARGES_TOTAL_PATTERN = r'^Additional\s+Charges\s+Total\s*\$?([\d,]+\.\d+)'

GRAND_TOTAL_AREAS_HDR = r'^Grand\s+Total\s+Areas:'

# coverage table
COVERAGE_TABLE_ROW = r'^([A-Za-z0-9][A-Za-z0-9\s,&\-\.\'/]+?)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$'
COVERAGE_TOTAL_ROW  = r'^Total\s+([\d,]+\.\d+)\s+100\.00%\s+([\d,]+\.\d+)\s+100\.00%$'

# summary pages
SUMMARY_FOR_HDR = r'^Summary\s+for\s+(.+?)\s*$'
SUMMARY_KV_ROW  = r'^(Line Item Total|California Lumber Assessment Fee|Material Sales Tax|Subtotal|Overhead|Profit|Replacement Cost Value|Net Claim|Less Deductible|Less Amount Over Limit\(s\))\s+\$?([\d,]+\.\d+)$'

# recap
RECAP_TAX_OP_HDR = r'^Recap\s+of\s+Taxes,\s+Overhead\s+and\s+Profit\s*$'
RECAP_TAX_OP_TOTAL_ROW = r'^Total\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)$'
RECAP_BY_ROOM_HDR = r'^Recap\s+by\s+Room\s*$'
RECAP_BY_CATEGORY_HDR = r'^Recap\s+by\s+Category\s*$'
RECAP_LINE_PATTERN = r'^([A-Za-z0-9/_\-\.\s\(\),&\']+?)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$'
RECAP_COVERAGE_SPLIT = r'^Coverage:\s+(.+?)\s+@?\s*(\d{1,3}\.\d{2})%?\s*=\s*([\d,]+\.\d+)$'
RECAP_SUBTOTAL_PATTERN = r'^(?:Area\s+Subtotal:|O&P Items Subtotal|Non-O&P Items Subtotal|Subtotal of Areas|Total)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$'

# =========================
# Data structures
# =========================
@dataclass
class TableColumns:
    has_reset: bool = False
    has_tax: bool = False
    has_op: bool = False
    def __repr__(self):
        cols = []
        if self.has_reset: cols.append("RESET")
        if self.has_tax: cols.append("TAX")
        if self.has_op: cols.append("O&P")
        return f"TableColumns({', '.join(cols) if cols else 'base only'})"

class ParseState(Enum):
    LOOKING_FOR_SECTION = 1
    IN_SECTION_METADATA = 2
    IN_SUBROOM_METADATA = 3
    IN_LINE_ITEMS = 4

# =========================
# Helpers
# =========================
def _money_to_float(s: str) -> float:
    if not s: return 0.0
    return float(str(s).replace(',', ''))

def _fm(val: float) -> str:
    sign = "-" if val < 0 else ""
    return f"{sign}${abs(val):,.2f}"

def _round2(x: float) -> float:
    return round(x + 1e-7, 2)

def format_dollar_amount(value: float) -> str:
    return f"{value:,.2f}"

def parse_datetime_string(date_str: str) -> Optional[str]:
    if not date_str: return None
    for fmt in ('%m/%d/%Y %I:%M %p', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).isoformat()
        except ValueError:
            continue
    return date_str

def parse_item_codes(codes_str: Optional[str]) -> List[str]:
    if not codes_str: return []
    codes, cs = [], codes_str.strip()
    two = {'RP','NR','CI','MO','ST','RS','CW','SE','SC'}
    i = 0
    while i < len(cs):
        if cs[i].isspace(): i += 1; continue
        if i+1 < len(cs) and cs[i:i+2].upper() in two:
            codes.append(cs[i:i+2].upper()); i += 2; continue
        if cs[i].upper() in '*DEFHMNRS': codes.append(cs[i].upper())
        i += 1
    return codes

def is_diagram_artifact(line: str) -> bool:
    if re.search(REPEATED_CHAR_PATTERN, line): return True
    if line in {'Door', 'Window', 'Wall'}: return True
    if len(line) < 15 and re.search(QUOTE_PATTERN, line): return True
    special = sum(1 for c in line if c in '\"\'.-_|/\\')
    return len(line) > 0 and special / len(line) > 0.4

def is_page_header(line: str, header_patterns: List[str]) -> bool:
    if re.match(SINGLE_PAGE_NUMBER_PATTERN, line): return True
    if re.match(PAGE_NUMBER_PATTERN, line): return True
    return bool(header_patterns and line in header_patterns)

def detect_page_header_pattern(pdf_path: str) -> List[str]:
    header_lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 2: return header_lines
        p1 = [l.strip() for l in (pdf.pages[0].extract_text() or "").split('\n') if l.strip()]
        p2 = [l.strip() for l in (pdf.pages[1].extract_text() or "").split('\n') if l.strip()]
        for line in p1[:10]:
            if line in p2[:10]: header_lines.append(line)
        for line in p1[:15]:
            if re.match(PAGE_NUMBER_PATTERN, line):
                header_lines.append('PAGE_NUMBER_PATTERN'); break
    return header_lines

def is_table_header(line: str, next_line: Optional[str]) -> Tuple[bool, TableColumns, bool]:
    if not re.match(TABLE_HEADER_PRIMARY, line):
        return False, TableColumns(), False
    combined = f"{line} {next_line}" if next_line else line
    cols = TableColumns(
        has_reset='RESET' in combined,
        has_tax='TAX' in combined,
        has_op=('O&P' in combined or 'O & P' in combined),
    )
    two_line = bool(next_line and re.search(TABLE_HEADER_SECOND_LINE_FRAGMENT, next_line))
    return True, cols, two_line

def is_table_continuation(line: str) -> bool:
    return bool(re.match(TABLE_HEADER_CONTINUATION, line, re.IGNORECASE))

def is_subroom_header(line: str) -> Tuple[bool, Optional[str], Optional[str]]:
    m = re.match(SUBROOM_PATTERN, line, re.IGNORECASE)
    return (True, m.group(1).strip(), m.group(2).strip()) if m else (False, None, None)

def is_line_item(line: str) -> bool:
    return bool(re.match(LINE_ITEM_PATTERN, line))

def is_line_item_header(line: str) -> Tuple[bool, Optional[str]]:
    m = re.match(LINE_ITEM_HEADER_PATTERN, line)
    return (True, m.group(2).strip().rstrip(':')) if m else (False, None)

def is_totals_line(line: str, section_name: Optional[str]) -> bool:
    if not re.match(TOTALS_PATTERN, line): return False
    if section_name and section_name.lower() in line.lower(): return True
    return len(re.findall(r'[\d,]+\.\d{2}', line)) >= 2

# =========================
# Parser Class
# =========================
class XactimateRoughDraftParser:
    def __init__(self, input_file: str, output_path: str, debug: bool = False):
        self.input_file = os.path.abspath(input_file)
        self.output_path = output_path  # dir or filename
        self.debug = bool(debug)
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(self.input_file)
        self._resolve_outputs()

    # ---------- public ----------
    def run(self) -> None:
        sections, _ = self._parse_document(self.input_file)
        case_md = self._parse_case_metadata_first_page(self.input_file)

        # end sections split per new schema
        full_lines = self._get_full_text_lines()
        end = self._parse_end_structured(full_lines)

        # attach per-section deltas + collect rows for console
        table_rows = []
        per_section_validations = []
        for section in sections:
            computed = _round2(self._section_computed_total(section))
            declared_str = section.get('section_totals', {}).get('total', '0.00')
            declared = _round2(_money_to_float(declared_str))
            delta = _round2(declared - computed)
            section['section_totals']['computed_total'] = format_dollar_amount(computed)
            section['section_totals']['validation_delta'] = format_dollar_amount(delta)
            if delta != 0.0:
                table_rows.append({
                    'name': section.get('section_name', 'Unknown Section'),
                    'declared': declared,
                    'computed': computed,
                    'delta': delta
                })
            per_section_validations.append({
                'section': section.get('section_name', 'Unknown Section'),
                'declared': format_dollar_amount(declared),
                'computed': format_dollar_amount(computed),
                'delta': format_dollar_amount(delta)
            })

        # doc-level validations using the new layout
        doc_validations = self._validate_doc(end, sections)

        # writes
        self._write_raw_lines(full_lines)
        payload = {
            "case_metadata": {
                **case_md,
                "line_item_totals": end.get("line_item_totals"),
                "labor_minimums": end.get("labor_minimums"),
                "additional_charges": end.get("additional_charges"),
            },
            "sections": sections,
            "grand_total_areas": end.get("grand_total_areas"),
            "coverage": end.get("coverage"),
            "recaps_and_summaries": {
                "summaries_by_coverage": end.get("summaries_by_coverage", {}),
                "recap_tax_op": end.get("recap_tax_op"),
                "recap_by_room": end.get("recap_by_room"),
                "recap_by_category": end.get("recap_by_category"),
            },
        }
        if self.debug:
            payload["validations"] = {
                "per_section": per_section_validations,
                "document": doc_validations
            }
        self._write_json(payload)

        # console tables
        self._print_doc_delta_table(os.path.basename(self.input_file), table_rows, len(sections), self.json_path)
        if self.debug:
            self._print_doc_validation_table(doc_validations)

    # ---------- internals ----------
    def _resolve_outputs(self):
        in_stem = os.path.splitext(os.path.basename(self.input_file))[0]
        out = self.output_path
        if os.path.isdir(out):
            base = os.path.join(out, in_stem)
            self.out_path = base + ".out"
            self.json_path = base + ".json"
        else:
            out = os.path.abspath(out)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            if os.path.splitext(out)[1] == "":
                out = out + ".json"
            self.json_path = out
            self.out_path = os.path.splitext(out)[0] + ".out"
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)

    def _write_raw_lines(self, _ignored: List[str]) -> None:
        lines = self._get_full_text_lines()
        with open(self.out_path, 'w', encoding='utf-8') as f:
            for l in lines:
                f.write(l + '\n')

    def _write_json(self, payload: dict) -> None:
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _print_doc_delta_table(self, pdf_file: str, rows: list, total_sections: int, json_path: str) -> None:
        print(f"\n▶ Doc: {pdf_file}")
        if not rows:
            print("  - No non-zero deltas.")
            print(f"  ➜ {json_path}")
            return
        name_w = 42; amt_w = 16
        print("  " + f"{'Section':{name_w}}{'Declared':>{amt_w}}{'Computed':>{amt_w}}{'Δ (Decl-Comp)':>{amt_w}}")
        print("  " + "-" * (name_w + amt_w * 3))
        for r in rows:
            print("  " + f"{r['name'][:name_w]:{name_w}}{_fm(r['declared']):>{amt_w}}{_fm(r['computed']):>{amt_w}}{_fm(r['delta']):>{amt_w}}")
        print(f"  (sections with deltas: {len(rows)} / total sections: {total_sections})")
        print(f"  ➜ {json_path}")

    def _print_doc_validation_table(self, v: dict) -> None:
        print("  Doc-level validations:")
        keys = [
            ('sum_sections', 'Sum of section items'),
            ('end_grand_total', 'End-of-doc grand total'),
            ('grand_total_vs_sections_delta', 'Δ Grand - Sections'),
            ('sum_rcv_from_summaries', 'Sum RCV (summaries)'),
            ('coverage_total_item', 'Coverage table total'),
            ('coverage_rcv_delta', 'Δ Coverage - Summaries'),
            ('recap_category_total', 'Recap-by-category total'),
            ('recap_vs_end_grand_delta', 'Δ Recap - Grand'),
        ]
        name_w, val_w = 30, 18
        print("  " + f"{'Check':{name_w}}{'Value':>{val_w}}")
        print("  " + "-" * (name_w + val_w))
        for k, label in keys:
            if k in v and v[k] is not None:
                print("  " + f"{label:{name_w}}{v[k]:>{val_w}}")

    def _section_computed_total(self, section: dict) -> float:
        return sum(
            _money_to_float(li.get('total'))
            for li in section.get('line_items', [])
            if li.get('type') == 'line_item' and li.get('total') is not None
        )

    def _parse_case_metadata_first_page(self, pdf_path: str) -> dict:
        lines: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.pages:
                txt = pdf.pages[0].extract_text() or ""
                lines.extend([l.strip() for l in txt.split('\n') if l.strip()])
        return self._parse_case_metadata(lines)

    # ---------- core parsing ----------
    def _parse_document(self, pdf_path: str) -> tuple:
        header_patterns = detect_page_header_pattern(pdf_path)
        lines: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.split('\n'):
                    stripped = line.strip()
                    if stripped and not is_page_header(stripped, header_patterns):
                        lines.append(stripped)

        state = ParseState.LOOKING_FOR_SECTION
        sections: List[dict] = []
        current_section = None
        current_subroom = None
        current_line_item = None
        collecting_notes = False
        columns = TableColumns()
        pending_header_lines: List[str] = []

        i = 0
        while i < len(lines):
            line = lines[i]
            next_line = lines[i + 1] if i + 1 < len(lines) else None

            if state == ParseState.LOOKING_FOR_SECTION:
                if is_diagram_artifact(line): i += 1; continue
                if 'Height:' in line and 'Subroom:' not in line:
                    m = re.match(SECTION_HEIGHT_PATTERN, line)
                    if m:
                        raw_name = m.group(1).strip()
                        height = m.group(2).strip()
                        name_match = re.search(SECTION_NAME_EXTRACTION, raw_name)
                        section_name = name_match.group(1).strip() if name_match else raw_name
                        current_section = {'section_name': section_name,'metadata': {'height': height.strip()},
                                           'subrooms': [], 'line_items': [], 'section_totals': {}}
                        state = ParseState.IN_SECTION_METADATA
                        i += 1; continue

                is_header, detected_cols, is_two = is_table_header(line, next_line)
                if is_header:
                    section_name = "Unknown Section"
                    if i > 0 and not is_page_header(lines[i-1], header_patterns):
                        prev = lines[i-1].strip()
                        nm = re.search(SECTION_NAME_EXTRACTION, prev)
                        section_name = nm.group(1).strip() if nm else prev
                    current_section = {'section_name': section_name, 'metadata': {}, 'subrooms': [],
                                       'line_items': [], 'section_totals': {}}
                    columns = detected_cols
                    state = ParseState.IN_LINE_ITEMS
                    i += 2 if is_two else 1
                    continue

                i += 1; continue

            elif state == ParseState.IN_SECTION_METADATA:
                is_sub, sub_name, sub_h = is_subroom_header(line)
                if is_sub:
                    current_subroom = {'subroom_name': sub_name, 'metadata': {'height': sub_h.strip()}}
                    state = ParseState.IN_SUBROOM_METADATA
                    i += 1; continue

                is_header, detected_cols, is_two = is_table_header(line, next_line)
                if is_header:
                    columns = detected_cols
                    state = ParseState.IN_LINE_ITEMS
                    i += 2 if is_two else 1
                    continue

                meta = self._extract_metadata_from_line(line)
                if meta:
                    current_section['metadata'] = self._merge_metadata(current_section['metadata'], meta)
                i += 1; continue

            elif state == ParseState.IN_SUBROOM_METADATA:
                is_sub, sub_name, sub_h = is_subroom_header(line)
                if is_sub:
                    current_section['subrooms'].append(current_subroom)
                    current_subroom = {'subroom_name': sub_name, 'metadata': {'height': sub_h.strip()}}
                    i += 1; continue

                is_header, detected_cols, is_two = is_table_header(line, next_line)
                if is_header:
                    current_section['subrooms'].append(current_subroom)
                    current_subroom = None
                    columns = detected_cols
                    state = ParseState.IN_LINE_ITEMS
                    i += 2 if is_two else 1
                    continue

                meta = self._extract_metadata_from_line(line)
                if meta and current_subroom is not None:
                    current_subroom['metadata'] = self._merge_metadata(current_subroom['metadata'], meta)
                i += 1; continue

            elif state == ParseState.IN_LINE_ITEMS:
                if is_table_continuation(line):
                    pending_header_lines = []
                    i += 1
                    if i < len(lines):
                        n2 = lines[i + 1] if i + 1 < len(lines) else None
                        is_header, new_cols, is_two = is_table_header(lines[i], n2)
                        if is_header:
                            columns = new_cols
                            i += 2 if is_two else 1
                    continue

                if is_totals_line(line, current_section['section_name'] if current_section else None):
                    if pending_header_lines and current_line_item:
                        note_text = ' '.join(pending_header_lines)
                        current_line_item['notes'] = (current_line_item['notes'] + ' ' + note_text).strip() if current_line_item['notes'] else note_text
                        pending_header_lines = []
                    if collecting_notes and current_line_item:
                        current_section['line_items'].append(current_line_item)
                        current_line_item = None
                        collecting_notes = False

                    current_section['section_totals'] = self._parse_totals_line(line, columns)
                    sections.append(current_section)
                    current_section = None
                    columns = TableColumns()
                    state = ParseState.LOOKING_FOR_SECTION
                    i += 1; continue

                is_header_line, header_text = is_line_item_header(line)
                if is_header_line:
                    if pending_header_lines and current_line_item:
                        nt = ' '.join(pending_header_lines)
                        current_line_item['notes'] = (current_line_item['notes'] + ' ' + nt).strip() if current_line_item['notes'] else nt
                        pending_header_lines = []
                    if collecting_notes and current_line_item:
                        current_section['line_items'].append(current_line_item)
                        current_line_item = None
                    collecting_notes = False
                    current_section['line_items'].append({'type': 'header', 'text': header_text})
                    i += 1; continue

                if is_line_item(line):
                    if pending_header_lines and current_line_item:
                        nt = ' '.join(pending_header_lines)
                        current_line_item['notes'] = (current_line_item['notes'] + ' ' + nt).strip() if current_line_item['notes'] else nt
                        pending_header_lines = []
                    if current_line_item:
                        current_section['line_items'].append(current_line_item)
                        current_line_item = None
                        collecting_notes = False
                    m = re.match(LINE_ITEM_PATTERN, line)
                    if m:
                        current_line_item = {
                            'type': 'line_item',
                            'line_number': int(m.group(1)),
                            'cat': m.group(2),
                            'sel': m.group(3),
                            'act': m.group(4),
                            'description': m.group(5).strip(),
                            'calc': '',
                            'qty': 0.0,
                            'unit': '',
                            'item_codes': [],
                            'reset': None,
                            'remove': None,
                            'replace': None,
                            'tax': None,
                            'op': None,
                            'total': None,
                            'total_note': None,
                            'notes': ''
                        }
                    i += 1; continue

                if current_line_item and re.search(CALC_LINE_DETECTION_PATTERN, line):
                    calc = self._parse_line_item_calc(line, columns)
                    if calc:
                        current_line_item.update(calc)
                        collecting_notes = True
                        i += 1; continue

                if collecting_notes and current_line_item:
                    pending_header_lines.append(line)
                    i += 1; continue

                i += 1; continue

            i += 1

        return sections, lines

    def _parse_line_item_calc(self, calc_line: str, columns: TableColumns) -> dict:
        # SEE handler
        see_pattern = CALC_PREFIX_PATTERN + QTY_UNIT_PATTERN + BRACKETS_PATTERN + SEE_PATTERN
        m = re.search(see_pattern, calc_line, re.IGNORECASE)
        if m:
            codes_str = m.group(4) or ''
            return {
                'calc': (m.group(1) or '').strip(),
                'qty': float(m.group(2)),
                'unit': m.group(3).upper(),
                'item_codes': parse_item_codes(codes_str),
                'reset': None, 'remove': None, 'replace': None, 'tax': None, 'op': None,
                'total': '0.00', 'total_note': 'SEE ' + m.group(5).strip().upper()
            }

        # priced formats
        base = CALC_PREFIX_PATTERN + QTY_UNIT_PATTERN + BRACKETS_PATTERN
        def tail(ht: bool, ho: bool) -> str:
            if ht and ho: return CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
            if ht: return CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
            if ho: return CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
            return r'(?:' + CURRENCY_PATTERN + r'\s+)*' + CURRENCY_PATTERN + r'\s*$'

        if columns.has_reset:
            full_a = base + CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*' + tail(columns.has_tax, columns.has_op)
            ma = re.search(full_a, calc_line)
            if ma:
                g, idx = ma.groups(), 0
                codes_str = g[3] or ''
                res = {'calc': (g[idx] or '').strip(), 'qty': float(g[idx+1]), 'unit': g[idx+2],
                       'item_codes': parse_item_codes(codes_str)}
                idx += 4
                res['reset']   = format_dollar_amount(_money_to_float(g[idx]));   res['remove'] = format_dollar_amount(_money_to_float(g[idx+1])); res['replace'] = format_dollar_amount(_money_to_float(g[idx+2])); idx += 3
                if columns.has_tax and columns.has_op:
                    res['tax'] = format_dollar_amount(_money_to_float(g[idx])); res['op'] = format_dollar_amount(_money_to_float(g[idx+1])); res['total'] = format_dollar_amount(_money_to_float(g[idx+2]))
                elif columns.has_tax:
                    res['tax'] = format_dollar_amount(_money_to_float(g[idx])); res['op'] = None; res['total'] = format_dollar_amount(_money_to_float(g[idx+1]))
                elif columns.has_op:
                    res['tax'] = None; res['op'] = format_dollar_amount(_money_to_float(g[idx])); res['total'] = format_dollar_amount(_money_to_float(g[idx+1]))
                else:
                    res['tax'] = None; res['op'] = None; res['total'] = format_dollar_amount(_money_to_float(g[idx]))
                return res

            full_b = base + CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*' + tail(columns.has_tax, columns.has_op)
            mb = re.search(full_b, calc_line)
            if mb:
                g, idx = mb.groups(), 0
                codes_str = g[3] or ''
                res = {'calc': (g[idx] or '').strip(), 'qty': float(g[idx+1]), 'unit': g[idx+2],
                       'item_codes': parse_item_codes(codes_str), 'reset': None}
                idx += 4
                res['remove'] = format_dollar_amount(_money_to_float(g[idx])); res['replace'] = format_dollar_amount(_money_to_float(g[idx+1])); idx += 2
                if columns.has_tax and columns.has_op:
                    res['tax'] = format_dollar_amount(_money_to_float(g[idx])); res['op'] = format_dollar_amount(_money_to_float(g[idx+1])); res['total'] = format_dollar_amount(_money_to_float(g[idx+2]))
                elif columns.has_tax:
                    res['tax'] = format_dollar_amount(_money_to_float(g[idx])); res['op'] = None; res['total'] = format_dollar_amount(_money_to_float(g[idx+1]))
                elif columns.has_op:
                    res['tax'] = None; res['op'] = format_dollar_amount(_money_to_float(g[idx])); res['total'] = format_dollar_amount(_money_to_float(g[idx+1]))
                else:
                    res['tax'] = None; res['op'] = None; res['total'] = format_dollar_amount(_money_to_float(g[idx]))
                return res
        else:
            full = base + CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*' + tail(columns.has_tax, columns.has_op)
            mstd = re.search(full, calc_line)
            if mstd:
                g, idx = mstd.groups(), 0
                codes_str = g[3] or ''
                res = {'calc': (g[idx] or '').strip(), 'qty': float(g[idx+1]), 'unit': g[idx+2],
                       'item_codes': parse_item_codes(codes_str), 'reset': None}
                idx += 4
                res['remove'] = format_dollar_amount(_money_to_float(g[idx])); res['replace'] = format_dollar_amount(_money_to_float(g[idx+1])); idx += 2
                if columns.has_tax and columns.has_op:
                    res['tax'] = format_dollar_amount(_money_to_float(g[idx])); res['op'] = format_dollar_amount(_money_to_float(g[idx+1])); res['total'] = format_dollar_amount(_money_to_float(g[idx+2]))
                elif columns.has_tax:
                    res['tax'] = format_dollar_amount(_money_to_float(g[idx])); res['op'] = None; res['total'] = format_dollar_amount(_money_to_float(g[idx+1]))
                elif columns.has_op:
                    res['tax'] = None; res['op'] = format_dollar_amount(_money_to_float(g[idx])); res['total'] = format_dollar_amount(_money_to_float(g[idx+1]))
                else:
                    res['tax'] = None; res['op'] = None; res['total'] = format_dollar_amount(_money_to_float(g[idx]))
                return res

        # terminal fallback
        tm = re.search(TERMINAL_STATUS_PATTERN, calc_line, re.IGNORECASE)
        qty_unit_base = CALC_PREFIX_PATTERN + QTY_UNIT_PATTERN + BRACKETS_PATTERN
        if tm:
            term = tm.group(1).strip()
            if re.search(qty_unit_base + re.escape(term) + r'\s*$', calc_line, re.IGNORECASE):
                m2 = re.search(qty_unit_base + r'([A-Z0-9]+(?:[._/\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+(?:[._/\-][A-Z0-9]+)*)*)\s*$',
                               calc_line, re.IGNORECASE)
                if m2:
                    codes_str = m2.group(4) or ''
                    note = m2.group(5).strip().upper()
                    if 'SEE' in calc_line.upper() and not note.startswith('SEE'):
                        note = 'SEE ' + note
                    return {
                        'calc': (m2.group(1) or '').strip(),
                        'qty': float(m2.group(2)),
                        'unit': m2.group(3),
                        'item_codes': parse_item_codes(codes_str),
                        'reset': None, 'remove': None, 'replace': None, 'tax': None, 'op': None,
                        'total': '0.00', 'total_note': note
                    }
        return {}

    def _parse_totals_line(self, totals_line: str, columns: TableColumns) -> dict:
        if columns.has_tax and columns.has_op:
            m = re.search(r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$', totals_line, re.IGNORECASE)
            if m:
                return {'tax': format_dollar_amount(_money_to_float(m.group(1))),
                        'op': format_dollar_amount(_money_to_float(m.group(2))),
                        'total': format_dollar_amount(_money_to_float(m.group(3)))} 
        elif columns.has_tax:
            m = re.search(r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$', totals_line, re.IGNORECASE)
            if m:
                return {'tax': format_dollar_amount(_money_to_float(m.group(1))),
                        'op': None,
                        'total': format_dollar_amount(_money_to_float(m.group(2)))} 
        elif columns.has_op:
            m = re.search(r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$', totals_line, re.IGNORECASE)
            if m:
                return {'tax': None,
                        'op': format_dollar_amount(_money_to_float(m.group(1))),
                        'total': format_dollar_amount(_money_to_float(m.group(2)))} 
        else:
            m = re.search(r'Totals?:.*?([\d,]+\.\d+)\s*$', totals_line, re.IGNORECASE)
            if m:
                return {'tax': None, 'op': None, 'total': format_dollar_amount(_money_to_float(m.group(1)))}
        # fallback inference
        nums = re.findall(r'[\d,]+\.\d+', totals_line)
        if nums:
            amounts = [format_dollar_amount(_money_to_float(n)) for n in nums]
            res = {'tax': None, 'op': None, 'total': '0.00'}
            res['total'] = amounts[-1]
            if columns.has_op and len(amounts) >= 2: res['op'] = amounts[-2]
            if columns.has_tax and len(amounts) >= (3 if columns.has_op else 2):
                idx = -3 if columns.has_op else -2
                res['tax'] = amounts[idx]
            return res
        return {'tax': None, 'op': None, 'total': '0.00'}

    def _get_full_text_lines(self) -> List[str]:
        lines: List[str] = []
        with pdfplumber.open(self.input_file) as pdf:
            for page in pdf.pages:
                txt = pdf.pages[page.page_number-1].extract_text() or ""
                lines.extend([l.strip() for l in txt.split('\n') if l.strip()])
        return lines

    # ----- metadata helpers -----
    def _extract_metadata_from_line(self, line: str) -> dict:
        md: Dict[str, object] = {}
        areas: Dict[str, str] = {}
        for key, pat in METADATA_PATTERNS.items():
            m = re.search(pat, line)
            if m: areas[key] = format_dollar_amount(_money_to_float(m.group(1)))
        if areas: md['areas'] = areas

        doors = [{'dimensions': m.group(1).strip(), 'opens_into': m.group(2).strip()}
                 for m in re.finditer(DOOR_PATTERN, line, re.IGNORECASE)]
        if doors: md['doors'] = doors

        walls = [{'dimensions': m.group(1).strip(), 'opens_into': m.group(2).strip()}
                 for m in re.finditer(MISSING_WALL_PATTERN, line, re.IGNORECASE)]
        if walls: md['missing_walls'] = walls

        return md

    def _merge_metadata(self, base: dict, new: dict) -> dict:
        for k, v in new.items():
            if k == 'areas':
                base.setdefault('areas', {}).update(v)
            elif k in ('doors', 'missing_walls'):
                base.setdefault(k, []).extend(v)
            else:
                base[k] = v
        return base

    # ----- end-of-document parsing in structured form -----
    def _find_section_bounds(self, all_lines: List[str],
                         header_re: re.Pattern,
                         stop_res: List[re.Pattern],
                         start_hint: int = 0) -> Tuple[int, int]:
        """
        Find [start, end) bounds of a section.
        - Normalizes NBSP and collapses whitespace before matching.
        - Skips over consecutive header lines (page-wrap echoes) so we don't return a zero-length slice.
        Returns (start_index_exclusive, end_index). If not found: (-1, -1).
        """

        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").replace("\u00A0", " ").strip())

        n = len(all_lines)
        header_idx = -1

        # forward scan from hint
        for idx in range(start_hint, n):
            if header_re.search(norm(all_lines[idx] or "")):
                header_idx = idx
                break
        # wrap once
        if header_idx == -1:
            for idx in range(0, start_hint):
                if header_re.search(norm(all_lines[idx] or "")):
                    header_idx = idx
                    break
        if header_idx == -1:
            return -1, -1

        # >>> NEW: collapse consecutive header lines (page-wrap echo) <<<
        j = header_idx + 1
        while j < n and header_re.search(norm(all_lines[j] or "")):
            j += 1
        start = j  # start AFTER the last consecutive header line

        # find first stopper after 'start'
        end = n
        for k in range(start, n):
            s = norm(all_lines[k] or "")
            for pat in stop_res:
                if pat.search(s):
                    end = k
                    return start, end
        return start, end

    def _parse_recap_by_room_section(self, all_lines: List[str], start_idx: int):
        """
        Recap by Room parser (group-aware):
        - Groups:
            * "Estimate: <id>"  (non-physical)
            * "Area: <name>"    (dynamic; may appear as header-only or header+item with amount/pct)
        - Items: "<label> <amount> <pct>%", followed by one-or-more coverage lines:
                "Coverage: <label> <pct>% = <amount>"  (note: no '@' in Room recap)
        - Subtotals:
            * "Area Subtotal: <name> <amount> <pct>%" (+ coverage)
            * "Subtotal of Areas <amount> <pct>%" (+ coverage)
            * "Total <amount> 100.00%"
        - Special item without pct:
            * "Labor Minimums Applied <amount>" (+ coverage)
        Returns ({ "groups": {group:[items...]}, "rows": [...], "subtotals": [...] }, next_index_after_section)
        """
        import re

        # --- Header and stoppers (IMPORTANT: 'Estimate:' is INSIDE the section, not a stopper) ---
        HDR_ROOM = re.compile(r"^\s*Recap\s+by\s+Room\s*$", re.IGNORECASE)
        STOPPERS = [
            re.compile(r"^\s*Recap\s+by\s+Category\s*$", re.IGNORECASE),
            re.compile(r"^\s*Recap\s+of\s+Taxes,\s+Overhead\s+and\s+Profit\s*$", re.IGNORECASE),
            re.compile(r"^\s*Summary\s+for\s+", re.IGNORECASE),
            re.compile(r"^\s*Grand\s+Total\s+Areas\b", re.IGNORECASE),
        ]

        seg_start, seg_end = self._find_section_bounds(all_lines, HDR_ROOM, STOPPERS, start_hint=start_idx)
        if seg_start == -1:
            return {"groups": {}, "rows": [], "subtotals": []}, start_idx + 1

        # ---------- Local helpers ----------
        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").replace("\u00A0", " ").strip())

        def is_noise(raw: str) -> bool:
            s = (raw or "").strip()
            if not s: return True
            if "Page:" in s: return True
            if re.fullmatch(r"\d{1,4}", s): return True
            if s.startswith(("Date:", "Apex ", "State Farm", "CA DOI", "www.", "Claim #", "Policy #")): return True
            if "Suite" in s or "Adjusters" in s: return True
            return False

        def gmoney(x: str) -> str:
            t = (x or "").replace("\u00A0", " ")
            t = re.sub(r"\s+", "", t)
            return format_dollar_amount(_money_to_float(t))

        def gpct(x: str) -> float:
            return float((x or "").replace(",", ".").strip())

        # Tails & recognizers
        PCT_CH = r"%\uFF05"  # ASCII % or fullwidth ％
        TAIL = re.compile(rf"([\d,]+(?:\.\d+)?)\s+(\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT_CH}]$")
        AMOUNT_ONLY_TAIL = re.compile(rf"([\d,]+(?:\.\d+)?)\s*$")
        # Headers
        EST_HDR = re.compile(r"^\s*Estimate:\s*(.+?)\s*$", re.IGNORECASE)
        AREA_HDR = re.compile(r"^\s*Area:\s*(.+?)\s*$", re.IGNORECASE)
        # Subtotals
        AREA_SUBTOTAL = re.compile(rf"^\s*Area\s+Subtotal:\s*(.+?)\s+([\d,]+(?:\.\d+)?)\s+(\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT_CH}]$", re.IGNORECASE)
        SUBTOTAL_OF_AREAS = re.compile(rf"^\s*Subtotal\s+of\s+Areas\s+([\d,]+(?:\.\d+)?)\s+(\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT_CH}]$", re.IGNORECASE)
        FINAL_TOTAL = re.compile(rf"^\s*Total\s+([\d,]+(?:\.\d+)?)\s+100(?:\.00)?\s*[{PCT_CH}]?$", re.IGNORECASE)
        # Coverage lines (ROOM variant: no '@')
        COVER_SPLIT = re.compile(r"^\s*Coverage:\s+(.+?)\s+(\d{1,3}(?:\.\d{1,2})?)\s*[%\uFF05]\s*=\s*([\d,]+(?:\.\d+)?)\s*$")
        # Special item without pct
        LABOR_MIN = re.compile(r"^\s*Labor\s+Minimums\s+Applied\s+([\d,]+(?:\.\d+)?)\s*$", re.IGNORECASE)

        def is_boundary(s: str) -> bool:
            # boundaries that end coverage collection or item recognition
            return (
                EST_HDR.match(s) or AREA_HDR.match(s) or
                AREA_SUBTOTAL.match(s) or SUBTOTAL_OF_AREAS.match(s) or
                FINAL_TOTAL.match(s) or
                TAIL.search(s)  # another item line
            )

        def capture_coverage(k: int, n: int) -> (list, int):
            covs = []
            i2 = k
            while i2 < n:
                raw = all_lines[i2] or ""
                if is_noise(raw):
                    i2 += 1
                    continue
                s = norm(raw)
                m = COVER_SPLIT.match(s)
                if not m:
                    if is_boundary(s):
                        break
                    # allow single wrapped continuation tokens to append to label (rare in Room)
                    # If needed later, add continuation logic here similar to category.
                    break
                covs.append({
                    "coverage": m.group(1).strip(),
                    "pct": gpct(m.group(2)),
                    "amount": gmoney(m.group(3)),
                })
                i2 += 1
            return covs, i2

        out_groups: dict = {}
        flat_rows: list = []
        subtotals: list = []

        current_group = None  # "Estimate: <id>" or "Area: <name>"

        i = seg_start
        n = seg_end
        while i < n:
            raw = all_lines[i] or ""
            if is_noise(raw):
                i += 1
                continue
            s = norm(raw)

            # Group headers
            m_est = EST_HDR.match(s)
            if m_est:
                current_group = f"Estimate: {m_est.group(1).strip()}"
                out_groups.setdefault(current_group, [])
                i += 1
                continue

            m_area_hdr = AREA_HDR.match(s)
            if m_area_hdr:
                # Could be header-only OR header+item if a tail is present on same line
                area_label = m_area_hdr.group(1).strip()
                current_group = f"Area: {area_label}"
                out_groups.setdefault(current_group, [])
                # If same line also has an amount/pct tail (rare), treat it as an item too
                mt = TAIL.search(s)
                if mt:
                    amount = gmoney(mt.group(1)); pct = gpct(mt.group(2))
                    # Item label should be the prefix before numeric tail; keep "Area: <name>"
                    label = s[:mt.start()].strip()
                    cov, j2 = capture_coverage(i + 1, n)
                    item = {"item": label, "total": amount, "pct": pct, "coverage": cov}
                    out_groups[current_group].append(item); flat_rows.append({k: item[k] for k in ("item","total","pct","coverage")})
                    i = j2
                    continue
                i += 1
                continue

            # Subtotals
            m_as = AREA_SUBTOTAL.match(s)
            if m_as:
                label = f"Area Subtotal: {m_as.group(1).strip()}"
                amount = gmoney(m_as.group(2)); pct = gpct(m_as.group(3))
                cov, j2 = capture_coverage(i + 1, n)
                subtotals.append({"label": label, "total": amount, "pct": pct, "coverage": cov})
                i = j2
                continue

            m_soa = SUBTOTAL_OF_AREAS.match(s)
            if m_soa:
                amount = gmoney(m_soa.group(1)); pct = gpct(m_soa.group(2))
                cov, j2 = capture_coverage(i + 1, n)
                subtotals.append({"label": "Subtotal of Areas", "total": amount, "pct": pct, "coverage": cov})
                i = j2
                continue

            m_ft = FINAL_TOTAL.match(s)
            if m_ft:
                subtotals.append({"label": "Total", "total": gmoney(m_ft.group(1)), "pct": 100.00})
                i += 1
                continue

            # Special item (no pct)
            m_lab = LABOR_MIN.match(s)
            if m_lab:
                amount = gmoney(m_lab.group(1))
                cov, j2 = capture_coverage(i + 1, n)
                label = "Labor Minimums Applied"
                # Attach to current group if set, else to a synthetic group
                grp = current_group or "Estimate: (unknown)"
                out_groups.setdefault(grp, [])
                item = {"item": label, "total": amount, "pct": None, "coverage": cov}
                out_groups[grp].append(item); flat_rows.append({k: item[k] for k in ("item","total","pct","coverage")})
                i = j2
                continue

            # Generic item with amount + pct tail
            mt = TAIL.search(s)
            if mt:
                amount = gmoney(mt.group(1)); pct = gpct(mt.group(2))
                label = s[:mt.start()].strip().rstrip(":")
                cov, j2 = capture_coverage(i + 1, n)
                grp = current_group or "Estimate: (unknown)"
                out_groups.setdefault(grp, [])
                item = {"item": label, "total": amount, "pct": pct, "coverage": cov}
                out_groups[grp].append(item); flat_rows.append({k: item[k] for k in ("item","total","pct","coverage")})
                i = j2
                continue

            # Default advance
            i += 1

        return {"groups": out_groups, "rows": flat_rows, "subtotals": subtotals}, seg_end

    def _parse_recap_by_category_section(self, all_lines: List[str], start_idx: int) -> Tuple[Dict[str, object], int]:
        """
        Parses a single 'Recap by Category' block starting at start_idx (line matches RECAP_BY_CATEGORY_HDR).
        - Dynamic groups: "<Key> Total %" or "Total <pct>%"
        Items: ALL-CAPS lines with "<amount> <pct>%"
        Coverage: one-or-more "Coverage: ..." lines with wrapped continuation lines merged.
        Group can close via "<Key> Subtotal ..." or bare "Subtotal ...".
        - 'subtotals' array: collects every subtotal (group-closing and repeated), plus allocations and final Total 100%.
        - Allocations ("Permits and Fees", "Material Sales Tax", "Overhead", "Profit") become top-level keys with coverage,
        and are mirrored into 'subtotals' with coverage.
        """
        def gmoney(x: str) -> str:
            return format_dollar_amount(_money_to_float(x))

        KEY_TOTAL_HDR = re.compile(r"^([A-Za-z0-9/_\-\.\s\(\),&']+?)\s+Total\s+(?:\d{1,3}\.\d{2}%|%)$", re.IGNORECASE)
        KEY_SUBTOTAL_ROW = re.compile(r"^([A-Za-z0-9/_\-\.\s\(\),&']+?)\s+Subtotal\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$", re.IGNORECASE)
        BARE_SUBTOTAL_ROW = re.compile(r"^Subtotal\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$", re.IGNORECASE)
        RECAP_ITEM_LINE = re.compile(RECAP_LINE_PATTERN)
        COVER_SPLIT = re.compile(RECAP_COVERAGE_SPLIT)
        ALLOC_LABEL_ROW = re.compile(r"^(Permits and Fees|Material Sales Tax|Overhead|Profit)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$", re.IGNORECASE)
        FINAL_TOTAL_100 = re.compile(r"^Total\s+([\d,]+\.\d+)\s+100\.00%$", re.IGNORECASE)

        def is_all_caps_name(s: str) -> bool:
            return not re.search(r"[a-z]", s)

        def is_page_noise(s: str) -> bool:
            if not s:
                return True
            if "Page:" in s:
                return True
            if re.fullmatch(r"\d{1,4}", s):
                return True
            if s.startswith(("Date:", "Apex ", "State Farm", "CA DOI", "www.", "CHEN,", "Claim #", "Policy #")):
                return True
            if "Suite" in s or "Adjusters" in s:
                return True
            return False

        def is_signal_boundary(s: str) -> bool:
            return (
                KEY_TOTAL_HDR.match(s) or
                KEY_SUBTOTAL_ROW.match(s) or
                BARE_SUBTOTAL_ROW.match(s) or
                ALLOC_LABEL_ROW.match(s) or
                FINAL_TOTAL_100.match(s) or
                RECAP_ITEM_LINE.match(s)
            )

        def capture_coverage(k: int, n: int) -> Tuple[List[dict], int]:
            covs: List[dict] = []
            while k < n:
                t = (all_lines[k] or "").strip()
                if is_page_noise(t):
                    k += 1
                    continue
                m = COVER_SPLIT.match(t)
                if not m:
                    break
                label = m.group(1).strip()
                pct = float(m.group(2))
                amt = gmoney(m.group(3))
                k += 1
                # absorb wrapped continuation lines into label
                while k < n:
                    t2 = (all_lines[k] or "").strip()
                    if not t2:
                        k += 1
                        continue
                    if COVER_SPLIT.match(t2) or is_signal_boundary(t2):
                        break
                    if is_page_noise(t2):
                        k += 1
                        continue
                    label = (label + " " + t2).strip()
                    k += 1
                covs.append({"coverage": label, "pct": pct, "amount": amt})
            return covs, k

        def subtotals_add(arr: List[dict], entry: dict):
            # de-dup exact (label,total,pct)
            for e in arr:
                if e.get("label") == entry.get("label") and e.get("total") == entry.get("total") and e.get("pct") == entry.get("pct"):
                    return
            arr.append(entry)

        out = {"subtotals": []}
        i = start_idx + 1
        n = len(all_lines)
        current_key = None
        pending_items: List[dict] = []

        def flush_group():
            nonlocal current_key, pending_items
            if current_key and pending_items:
                out.setdefault(current_key, []).extend(pending_items)
            current_key, pending_items = None, []

        while i < n:
            s = (all_lines[i] or "").strip()

            # Stop on obvious new major section
            if s.startswith("Dwelling -") or s.startswith("Estimate:") or s.startswith("Summary for "):
                break

            # Header
            mt = KEY_TOTAL_HDR.match(s)
            if mt:
                flush_group()
                current_key = mt.group(1).strip()
                i += 1
                continue

            # Items within a group
            if current_key:
                rm = RECAP_ITEM_LINE.match(s)
                if rm:
                    name = rm.group(1).strip()
                    if is_all_caps_name(name):
                        item_total = gmoney(rm.group(2))
                        item_pct = float(rm.group(3))
                        cov_list, end_k = capture_coverage(i + 1, n)
                        pending_items.append({
                            "item": name,
                            "total": item_total,
                            "pct": item_pct,
                            "coverage": cov_list
                        })
                        i = end_k
                        continue

                # Group-closing subtotal (labeled)
                ms = KEY_SUBTOTAL_ROW.match(s)
                if ms:
                    flush_group()
                    subtotals_add(out["subtotals"], {
                        "label": ms.group(1).strip(),
                        "total": gmoney(ms.group(2)),
                        "pct": float(ms.group(3)),
                    })
                    i += 1
                    continue

                # Bare "Subtotal …" — use current_key as label
                bs = BARE_SUBTOTAL_ROW.match(s)
                if bs:
                    flush_group()
                    if current_key:
                        subtotals_add(out["subtotals"], {
                            "label": current_key,
                            "total": gmoney(bs.group(1)),
                            "pct": float(bs.group(2)),
                        })
                    i += 1
                    continue

            # Subtotals section (no active group)
            if current_key is None:
                ms_any = KEY_SUBTOTAL_ROW.match(s)
                if ms_any:
                    subtotals_add(out["subtotals"], {
                        "label": ms_any.group(1).strip(),
                        "total": gmoney(ms_any.group(2)),
                        "pct": float(ms_any.group(3)),
                    })
                    i += 1
                    continue

                # Allocations (with coverage), also mirrored into subtotals
                am = ALLOC_LABEL_ROW.match(s)
                if am:
                    al_label = am.group(1).strip()
                    al_total = gmoney(am.group(2))
                    al_pct = float(am.group(3))
                    cov_list, end_k = capture_coverage(i + 1, n)
                    out[al_label] = {"total": al_total, "pct": al_pct, "coverage": cov_list}
                    subtotals_add(out["subtotals"], {
                        "label": al_label, "total": al_total, "pct": al_pct, "coverage": cov_list
                    })
                    i = end_k
                    continue

                # Final grand total
                ft = FINAL_TOTAL_100.match(s)
                if ft:
                    subtotals_add(out["subtotals"], {
                        "label": "Total",
                        "total": gmoney(ft.group(1)),
                        "pct": 100.00
                    })
                    i += 1
                    continue

            # Page/header noise skip
            if ("Page:" in s) or re.fullmatch(r"\d{1,4}", s) or s.startswith(("Date:", "Apex ", "State Farm")):
                i += 1
                continue

            # default
            i += 1

        flush_group()
        return out, i

    def _parse_recap_tax_op_section(self, all_lines: List[str], start_idx: int) -> Tuple[Optional[Dict[str, str]], int]:
        """
        Parses 'Recap of Taxes, Overhead and Profit' from start_idx.
        Returns (dict or None, next_index)
        """
        i, n = start_idx + 1, len(all_lines)
        total_row = None
        while i < n:
            s = (all_lines[i] or "").strip()
            tm = re.match(RECAP_TAX_OP_TOTAL_ROW, s)
            if tm:
                total_row = {
                    "overhead": format_dollar_amount(_money_to_float(tm.group(1))),
                    "profit": format_dollar_amount(_money_to_float(tm.group(2))),
                    "material_sales_tax": format_dollar_amount(_money_to_float(tm.group(3))),
                    "storage_rental_tax": format_dollar_amount(_money_to_float(tm.group(4))),
                }
                i += 1
                break
            if s.startswith("Summary for ") or re.match(RECAP_BY_ROOM_HDR, s) or re.match(RECAP_BY_CATEGORY_HDR, s):
                break
            i += 1
        return total_row, i

    def _parse_coverage_rows(self, all_lines: List[str], start_idx: int, existing_coverage: Optional[Dict[str, object]] = None) -> Tuple[Dict[str, object], int]:
        """
        Harvests a contiguous block of coverage rows and an optional 'Total' row starting at start_idx.
        Returns (coverage_dict, next_index)
        """
        cov = existing_coverage or {"rows": [], "totals": None}
        i, n = start_idx, len(all_lines)
        while i < n:
            s = (all_lines[i] or "").strip()
            m = re.match(COVERAGE_TABLE_ROW, s)
            if m:
                cov["rows"].append({
                    "name": m.group(1).strip(),
                    "item_total": format_dollar_amount(_money_to_float(m.group(2))),
                    "item_pct": float(m.group(3)),
                    "acv_total": format_dollar_amount(_money_to_float(m.group(4))),
                    "acv_pct": float(m.group(5)),
                })
                i += 1
                continue
            m = re.match(COVERAGE_TOTAL_ROW, s)
            if m:
                cov["totals"] = {
                    "item_total": format_dollar_amount(_money_to_float(m.group(1))),
                    "acv_total": format_dollar_amount(_money_to_float(m.group(2))),
                }
                i += 1
                # we often want to stop after total
                break
            # stop if we hit something that's clearly not coverage
            if s.startswith(("Summary for ", "Recap ", "Estimate:", "Grand Total Areas")):
                break
            # otherwise, exit the block gracefully
            break
        return cov, i

    def _parse_summary_block(self, all_lines: List[str], start_idx: int) -> Tuple[Tuple[str, Dict[str, str]], int]:
        """
        Parses a single 'Summary for <Coverage>' block starting at start_idx.
        Returns ((coverage_name, kv_dict), next_index).
        """
        def gmoney(x: str) -> str:
            return format_dollar_amount(_money_to_float(x))

        m = re.match(SUMMARY_FOR_HDR, (all_lines[start_idx] or "").strip())
        assert m, "Expected 'Summary for' header at start_idx"
        cov = m.group(1).strip()

        i, n = start_idx + 1, len(all_lines)
        kv = {}
        while i < n:
            s = (all_lines[i] or "").strip()
            if not s or s.startswith('Summary for ') or re.match(RECAP_TAX_OP_HDR, s) \
            or re.match(RECAP_BY_ROOM_HDR, s) or re.match(RECAP_BY_CATEGORY_HDR, s):
                break
            sm = re.match(SUMMARY_KV_ROW, s)
            if sm:
                kv[sm.group(1)] = gmoney(sm.group(2))
            i += 1
        return (cov, kv), i

    def _parse_grand_total_areas_block(self, all_lines: List[str], start_idx: int) -> Tuple[Optional[Dict[str, str]], int]:
        """
        Parses the 'Grand Total Areas:' block starting at start_idx.
        Returns (dict or None, next_index)
        """
        i, n = start_idx + 1, len(all_lines)
        block_lines = []
        while i < n:
            nxt = (all_lines[i] or "").strip()
            if not nxt:
                break
            if nxt.startswith(("Coverage ", "Summary ", "Recap ", "Estimate:")):
                break
            if "Page:" in nxt or nxt.startswith("Apex "):
                break
            block_lines.append(nxt)
            i += 1

        blob = re.sub(r"\s+", " ", " ".join(block_lines))

        def grab(pattern: str) -> Optional[str]:
            m2 = re.search(pattern, blob, re.IGNORECASE)
            return format_dollar_amount(_money_to_float(m2.group(1))) if m2 else None

        gta = {
            "sf_walls": grab(r"([\d,]+\.\d+)\s+SF\s+Walls\b"),
            "sf_ceiling": grab(r"([\d,]+\.\d+)\s+SF\s+Ceiling\b"),
            "sf_walls_and_ceiling": grab(r"([\d,]+\.\d+)\s+SF\s+Walls\s+and\s+Ceiling"),
            "sf_floor": grab(r"([\d,]+\.\d+)\s+SF\s+Floor\b"),
            "sy_flooring": grab(r"([\d,]+\.\d+)\s+SY\s+Flooring"),
            "lf_floor_perimeter": grab(r"([\d,]+\.\d+)\s+LF\s+Floor\s+Perimeter"),
            "sf_long_wall": grab(r"([\d,]+\.\d+)\s+SF\s+Long\s+Wall"),
            "sf_short_wall": grab(r"([\d,]+\.\d+)\s+SF\s+Short\s+Wall"),
            "lf_ceil_perimeter": grab(r"([\d,]+\.\d+)\s+LF\s+Ceil\.\s+Perimeter"),
            "floor_area": grab(r"([\d,]+\.\d+)\s+Floor\s+Area"),
            "total_area": grab(r"([\d,]+\.\d+)\s+Total\s+Area"),
            "interior_wall_area": grab(r"([\d,]+\.\d+)\s+Interior\s+Wall\s+Area"),
            "exterior_wall_area": grab(r"([\d,]+\.\d+)\s+Exterior\s+Wall\s+Area"),
            "exterior_perimeter_of_walls": grab(r"([\d,]+\.\d+)\s+Exterior\s+Perimeter\s+of\s+Walls"),
            "surface_area": grab(r"([\d,]+\.\d+)\s+Surface\s+Area"),
            "number_of_squares": grab(r"([\d,]+\.\d+)\s+Number\s+of\squares"),
            "total_perimeter_length": grab(r"([\d,]+\.\d+)\s+Total\s+Perimeter\s+Length"),
            "total_ridge_length": grab(r"([\d,]+\.\d+)\s+Total\s+Ridge\s+Length"),
            "total_hip_length": grab(r"([\d,]+\.\d+)\s+Total\s+Hip\s+Length"),
        }
        gta = {k: v for k, v in gta.items() if v is not None}
        return (gta or None), i

    def _parse_end_structured(self, all_lines: List[str]) -> dict:
        def gmoney(x: str) -> str:
            return format_dollar_amount(_money_to_float(x))

        result = {
            "line_item_totals": None,
            "labor_minimums": None,
            "additional_charges": None,
            "grand_total_areas": None,
            "coverage": {"rows": [], "totals": None},
            "summaries_by_coverage": {},
            "recap_tax_op": None,
            "recap_by_room": {"rows": [], "subtotals": []},
            "recap_by_category": {"subtotals": []},
        }

        i, n = 0, len(all_lines)
        while i < n:
            line = (all_lines[i] or "").strip()

            # Labor Minimums Applied
            m = re.match(LABOR_MIN_APPLIED_PATTERN, line, re.IGNORECASE)
            if m:
                result["labor_minimums"] = {
                    "labor": gmoney(m.group(1)),
                    "op_profit": gmoney(m.group(2)),
                    "total": gmoney(m.group(3)),
                }
                i += 1
                continue

            # Line Item Totals
            m = re.match(LINE_ITEM_TOTALS_PATTERN, line, re.IGNORECASE)
            if m:
                result["line_item_totals"] = {
                    "estimate": m.group(1),
                    "material_sales_tax": gmoney(m.group(2)),
                    "overhead_profit": gmoney(m.group(3)),
                    "grand_total": gmoney(m.group(4)),
                }
                i += 1
                continue

            # Additional Charges
            if re.match(ADD_CHARGES_HDR_PATTERN, line):
                items = []
                j = i + 1
                while j < n and not re.match(ADD_CHARGES_TOTAL_PATTERN, (all_lines[j] or "").strip()):
                    rm = re.match(ADD_CHARGE_ROW_PATTERN, (all_lines[j] or "").strip())
                    if rm:
                        items.append({"label": rm.group(1).strip(), "amount": gmoney(rm.group(2))})
                    j += 1
                total = None
                if j < n:
                    tm = re.match(ADD_CHARGES_TOTAL_PATTERN, (all_lines[j] or "").strip())
                    if tm:
                        total = gmoney(tm.group(1)); j += 1
                result["additional_charges"] = {"items": items, "total": total}
                i = j
                continue

            # Grand Total Areas
            if re.match(GRAND_TOTAL_AREAS_HDR, line):
                result["grand_total_areas"], i = self._parse_grand_total_areas_block(all_lines, i)
                continue

            # Coverage table rows/totals (harvest block)
            if re.match(COVERAGE_TABLE_ROW, line) or re.match(COVERAGE_TOTAL_ROW, line):
                result["coverage"], i = self._parse_coverage_rows(all_lines, i, result["coverage"])
                continue

            # Summary for <Coverage>
            m = re.match(SUMMARY_FOR_HDR, line)
            if m:
                (cov_name, kv), i = self._parse_summary_block(all_lines, i)
                result["summaries_by_coverage"][cov_name] = kv
                continue

            # Recap of Taxes, Overhead and Profit
            if re.match(RECAP_TAX_OP_HDR, line):
                result["recap_tax_op"], i = self._parse_recap_tax_op_section(all_lines, i)
                continue

            # >>> TOLERANT HEADER DETECTION (search, not match) <<<
            if re.search(r"\bRecap\s+by\s+Room\b", line, re.IGNORECASE):
                result["recap_by_room"], i = self._parse_recap_by_room_section(all_lines, i)
                continue

            if re.search(r"\bRecap\s+by\s+Category\b", line, re.IGNORECASE):
                rbc, i = self._parse_recap_by_category_section(all_lines, i)
                for k, v in rbc.items():
                    if k == "subtotals":
                        result["recap_by_category"]["subtotals"].extend(v)
                    else:
                        if isinstance(v, list):
                            result["recap_by_category"].setdefault(k, []).extend(v)
                        else:
                            result["recap_by_category"][k] = v
                continue

            i += 1

        return result


    # ----- validations with new layout -----
    def _validate_doc(self, end: dict, sections: List[dict]) -> dict:
        v: Dict[str, Optional[str]] = {}

        # sum of all section line-item totals
        sum_sections = _round2(sum(_money_to_float(li.get('total'))
                                   for sec in sections
                                   for li in sec.get('line_items', [])
                                   if li.get('type') == 'line_item' and li.get('total')))
        v['sum_sections'] = format_dollar_amount(sum_sections)

        # choose grand_end: prefer line_item_totals.grand_total, else coverage.totals.item_total
        grand_end = None
        if end.get('line_item_totals'):
            grand_end = _money_to_float(end['line_item_totals']['grand_total'])
        elif end.get('coverage', {}).get('totals'):
            grand_end = _money_to_float(end['coverage']['totals']['item_total'])
        if grand_end is not None:
            grand_end = _round2(grand_end)
            v['end_grand_total'] = format_dollar_amount(grand_end)
            v['grand_total_vs_sections_delta'] = format_dollar_amount(_round2(grand_end - sum_sections))

        # coverage totals vs sum of RCV in summaries
        summaries = end.get('summaries_by_coverage') or {}
        if summaries:
            sum_rcv = _round2(sum(_money_to_float(kv.get('Replacement Cost Value', '0.00'))
                                  for kv in summaries.values() if kv))
            v['sum_rcv_from_summaries'] = format_dollar_amount(sum_rcv)
            cov_tot = end.get('coverage', {}).get('totals')
            if cov_tot:
                cov_item_total = _round2(_money_to_float(cov_tot['item_total']))
                v['coverage_total_item'] = format_dollar_amount(cov_item_total)
                v['coverage_rcv_delta'] = format_dollar_amount(_round2(cov_item_total - sum_rcv))

        # recap-by-category total vs grand_end
        rbc_total = (end.get('recap_by_category') or {}).get('totals', {}) or {}
        rbc_val_str = rbc_total.get('grand_total')
        if rbc_val_str and grand_end is not None:
            rbc_val = _round2(_money_to_float(rbc_val_str))
            v['recap_category_total'] = format_dollar_amount(rbc_val)
            v['recap_vs_end_grand_delta'] = format_dollar_amount(_round2(rbc_val - grand_end))

        return v

    # ----- first-page case metadata -----
    def _parse_case_metadata(self, lines: List[str]) -> dict:
        md: Dict[str, object] = {}
        text = '\n'.join(lines[:50])

        m1 = re.search(CASE_LINE1_PATTERN, text, re.IGNORECASE)
        if m1:
            md['claim_number'] = (m1.group(1) or '').strip() or None
            md['policy_number'] = (m1.group(2) or '').strip() or None
            loss = (m1.group(3) or '').strip()
            md['loss_type'] = loss if (loss and not loss.startswith('Coverage')) else None
        else:
            md['claim_number'] = md['policy_number'] = md['loss_type'] = None

        table = []
        cov_sec = re.search(COVERAGE_SECTION_PATTERN, text, re.IGNORECASE)
        if cov_sec:
            for row in cov_sec.group(1).strip().split('\n'):
                rm = re.match(COVERAGE_ROW_PATTERN, row)
                if rm:
                    table.append({
                        'coverage_type': rm.group(1).strip(),
                        'deductible': format_dollar_amount(_money_to_float(rm.group(2))),
                        'policy_limit': format_dollar_amount(_money_to_float(rm.group(3))),
                    })
        md['coverage'] = table or None

        pm = re.search(PROPERTY_ADDRESS_PATTERN, text, re.DOTALL)
        md['property_address'] = ' '.join(pm.group(1).strip().split()) if pm else None

        d1 = re.search(DATE_LINE1_PATTERN, text, re.IGNORECASE)
        if d1:
            dol, dr = d1.group(1).strip(), d1.group(2).strip()
            md['date_of_loss'] = parse_datetime_string(dol) if (dol and re.match(r'\d+/\d+/\d+', dol)) else None
            md['date_received'] = parse_datetime_string(dr) if (dr and re.match(r'\d+/\d+/\d+', dr)) else None
        else:
            md['date_of_loss'] = md['date_received'] = None

        d2 = re.search(DATE_LINE2_PATTERN, text, re.IGNORECASE)
        if d2:
            di, de = d2.group(1).strip(), d2.group(2).strip()
            md['date_inspected'] = parse_datetime_string(di) if (di and re.match(r'\d+/\d+/\d+', di)) else None
            md['date_entered'] = parse_datetime_string(de) if (de and re.match(r'\d+/\d+/\d+', de)) else None
        else:
            md['date_inspected'] = md['date_entered'] = None

        pl = re.search(PRICE_LIST_PATTERN, text, re.IGNORECASE)
        if pl:
            md['price_list'] = pl.group(1).strip()
            md['depreciate_material'] = (pl.group(2).strip().upper() == 'YES')
            md['depreciate_op'] = (pl.group(3).strip().upper() == 'YES')
        else:
            md['price_list'] = md['depreciate_material'] = md['depreciate_op'] = None

        dl2 = re.search(DEPREC_LINE2_PATTERN, text, re.IGNORECASE)
        if dl2:
            md['depreciate_non_material'] = (dl2.group(1).strip().upper() == 'YES')
            md['depreciate_taxes'] = (dl2.group(2).strip().upper() == 'YES')
        else:
            md['depreciate_non_material'] = md['depreciate_taxes'] = None

        est = re.search(ESTIMATE_LINE_PATTERN, text, re.IGNORECASE)
        if est:
            md['estimate_name'] = est.group(1).strip()
            md['depreciate_removal'] = (est.group(2).strip().upper() == 'YES')
        else:
            md['estimate_name'] = md['depreciate_removal'] = None

        md['region'] = 'California' if (md.get('price_list') and str(md['price_list']).upper().startswith('CALA')) else None
        md['building_type'] = None
        return md
