#!/usr/bin/env python3
"""
Xactimate Rough Draft Parser
- Class accepts input_file and output_path (dir or filename).
- Writes <stem>.out (raw lines) and <stem>.json (structured).
- Prints a console table listing ONLY sections with non-zero (cent-rounded) deltas.
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

def parse_totals(totals_line: str, columns: TableColumns) -> dict:
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
        if m: return {'tax': None, 'op': None, 'total': format_dollar_amount(_money_to_float(m.group(1)))}
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

def extract_metadata_from_line(line: str) -> dict:
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

def merge_metadata(base: dict, new: dict) -> dict:
    for k, v in new.items():
        if k == 'areas':
            base.setdefault('areas', {}).update(v)
        elif k in ('doors', 'missing_walls'):
            base.setdefault(k, []).extend(v)
        else:
            base[k] = v
    return base

# =========================
# Parser Class
# =========================
class XactimateRoughDraftParser:
    def __init__(self, input_file: str, output_path: str):
        self.input_file = os.path.abspath(input_file)
        self.output_path = output_path  # dir or filename
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(self.input_file)
        self._resolve_outputs()

    # ---------- public ----------
    def run(self) -> None:
        """Parse, write .out/.json, and print delta table."""
        sections, all_lines = self._parse_document(self.input_file)
        case_md = self._parse_case_metadata_first_page(self.input_file)

        # compute totals + deltas; collect only non-zero (rounded) deltas for console table
        table_rows = []
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

        # writes
        self._write_raw_lines(all_lines)
        self._write_json({'case_metadata': case_md, 'sections': sections})

        # console table
        self._print_doc_delta_table(os.path.basename(self.input_file), table_rows, len(sections), self.json_path)

    # ---------- internals ----------
    def _resolve_outputs(self):
        in_stem = os.path.splitext(os.path.basename(self.input_file))[0]
        out = self.output_path

        if os.path.isdir(out):
            base = os.path.join(out, in_stem)
            self.out_path = base + ".out"
            self.json_path = base + ".json"
        else:
            # treat as filename (ensure dir exists)
            out = os.path.abspath(out)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            # if caller gave no extension, default to .json
            if os.path.splitext(out)[1] == "":
                out = out + ".json"
            self.json_path = out
            self.out_path = os.path.splitext(out)[0] + ".out"

        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)

    def _write_raw_lines(self, lines: List[str]) -> None:
        with pdfplumber.open(self.input_file) as pdf:
            # keep behavior: write full doc text (not just first page)
            all_lines = []
            for page in pdf.pages:
                txt = page.extract_text() or ""
                all_lines.extend([l.strip() for l in txt.split('\n') if l.strip()])
        with open(self.out_path, 'w', encoding='utf-8') as f:
            for l in all_lines:
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

        name_w = 42
        amt_w = 16
        print("  " + f"{'Section':{name_w}}{'Declared':>{amt_w}}{'Computed':>{amt_w}}{'Δ (Decl-Comp)':>{amt_w}}")
        print("  " + "-" * (name_w + amt_w * 3))
        for r in rows:
            print(
                "  "
                + f"{r['name'][:name_w]:{name_w}}"
                + f"{_fm(r['declared']):>{amt_w}}"
                + f"{_fm(r['computed']):>{amt_w}}"
                + f"{_fm(r['delta']):>{amt_w}}"
            )
        print(f"  (sections with deltas: {len(rows)} / total sections: {total_sections})")
        print(f"  ➜ {json_path}")

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

    # ---------- Xactimate-specific parsing below ----------
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
                        if nm: section_name = nm.group(1).strip()
                        else: section_name = prev
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

                meta = extract_metadata_from_line(line)
                if meta:
                    current_section['metadata'] = merge_metadata(current_section['metadata'], meta)
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

                meta = extract_metadata_from_line(line)
                if meta and current_subroom is not None:
                    current_subroom['metadata'] = merge_metadata(current_subroom['metadata'], meta)
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

    def _parse_totals_line(self, line: str, columns: TableColumns) -> dict:
        return parse_totals(line, columns)

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
