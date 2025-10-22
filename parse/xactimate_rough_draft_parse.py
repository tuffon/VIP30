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
TABLE_HEADER_CONTINUATION = r'^CONTINUED\s*-\s*.+'  # continuation banner
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
AREA_SUMMARY_LABELS = [
    ("Surface Area", "surface_area"),
    ("Number of Squares", "number_of_squares"),
    ("Total Perimeter Length", "total_perimeter_length"),
    ("Total Perimeter", "total_perimeter"),
    ("Perimeter Length", "perimeter_length"),
]
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
SUMMARY_KV_ROW  = r'^(Line Item Total|California Lumber Assessment Fee|Material Sales Tax|Subtotal|Overhead|Profit|Replacement Cost Value|Net Claim|Less Deductible|Less Amount Over Limit\(s\))\s+\$?([\d,]+\.[\d]+)$'
SUMMARY_NET_CLAIM_ROW = r'^Net\s+Claim\s+\$?([\d,]+\.[\d]+)\s*$'

# recap
RECAP_TAX_OP_HDR = r'^Recap\s+of\s+Taxes,\s+Overhead\s+and\s+Profit\s*$'
RECAP_TAX_OP_TOTAL_ROW = r'^Total\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)$'
RECAP_BY_ROOM_HDR = r'^Recap\s+by\s+Room\s*$'
RECAP_BY_CATEGORY_HDR = r'^Recap\s+by\s+Category\s*$'
RECAP_LINE_PATTERN = r'^([A-Za-z0-9/_\-\.\s\(\),&\']+?)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$'
RECAP_COVERAGE_SPLIT = r'^Coverage:\s+(.+?)\s+@?\s*(\d{1,3}\.\d{2})%?\s*=\s*([\d,]+\.\d+)$'
RECAP_SUBTOTAL_PATTERN = r'^(?:Area\s+Subtotal:|O&P Items Subtotal|Non-O&P Items Subtotal|Subtotal of Areas|Total)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$'

class HeaderType(Enum):
    STATEFARM = "statefarm"
    APEX = "apex"

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


def _format_metric_number(value: str) -> str:
    try:
        num = float((value or '').replace(',', ''))
    except (TypeError, ValueError):
        return (value or '').strip()
    if abs(num - round(num)) < 1e-6:
        return f"{int(round(num)):,d}"
    return f"{num:,.2f}"


def _is_footer_line(line: str) -> bool:
    if not line:
        return False
    s = line.lower()
    return any(keyword in s for keyword in [
        "apex public adjusters",
        "suite",
        "brand blvd",
        "www.",
        "phone",
        "fax",
        "claim number",
        "policy number"
    ])

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
        # full text (once)
        full_lines = self._get_full_text_lines()

        # pre-pass recap-by-category (non-sequential), and skip mask
        recap_cat, recap_cat_spans = self._prepass_recap_by_category(full_lines)
        skip_mask = self._build_skip_mask(len(full_lines), recap_cat_spans)

        # sequential parse using full_lines and skip_mask
        sections, _ = self._parse_document_from_lines(full_lines, skip_mask=skip_mask)

        # front-page metadata
        case_md = self._parse_case_metadata_first_page(self.input_file)

        # end-of-doc structured (but we will not clobber recap_by_category if prepass found it)
        end = self._parse_end_structured(full_lines)
        if recap_cat and (recap_cat.get("subtotals") or any(k for k in recap_cat.keys() if k != "subtotals")):
            end["recap_by_category"] = recap_cat

        # per-section validations
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

        # doc-level validations
        doc_validations = self._validate_doc(end, sections)

        # writes
        self._write_raw_lines(full_lines)

        # ------- ONLY CHANGE: build recaps_and_summaries and conditionally add trade_summary -------
        recaps = {
            "summaries_by_coverage": end.get("summaries_by_coverage", {}),
            "recap_tax_op": end.get("recap_tax_op"),
            "recap_by_room": end.get("recap_by_room"),
            "recap_by_category": end.get("recap_by_category") or recap_cat or {"subtotals": []},
        }
        if end.get("trade_summary"):
            recaps["trade_summary"] = end["trade_summary"]
        # -------------------------------------------------------------------------------------------

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
            "recaps_and_summaries": recaps,
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

    def _write_raw_lines(self, lines: List[str]) -> None:
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

    def detect_table_header(self, lines, i):
        """
        Detect a table header at index i.
        Returns: (HeaderType|None, consumed_lines:int, profile:dict|None)
        profile = {
            "type": "statefarm" | "apex",
            "columns": [...],                        # exact column names on header, left->right
            "apex_flags": TableColumns(...) or None  # for APEX only, to feed _parse_line_item_calc/_parse_totals_line
        }
        """
        n = len(lines)
        cur = (lines[i] or "").strip()
        nxt = (lines[i+1] or "").strip() if i+1 < n else ""

        # --- State Farm single-line header ---
        sf_header = r"^DESCRIPTION\s+QUANTITY\s+UNIT\s+PRICE\s+TAX\s+RCV$"
        if re.match(sf_header, cur, re.IGNORECASE):
            return (
                HeaderType.STATEFARM,
                1,
                {"type": "statefarm", "columns": ["DESCRIPTION","QUANTITY","UNIT","PRICE","TAX","RCV"], "apex_flags": None}
            )

        # --- Apex/Rough Draft header (1-2 lines) ---
        # First line (required)
        if re.match(r"^CAT\s+SEL\s+ACT\s+DESCRIPTION\s*$", cur, re.IGNORECASE):
            # Second line may include various combos, but must contain at least QTY and TOTAL somewhere
            combined = nxt if nxt else ""
            cols_line2 = []
            if nxt:
                # Assemble second-line columns by scanning canonical tokens in order of appearance
                tokens = [
                    ("CALC", r"\bCALC\b"),
                    ("QTY", r"\bQTY\b"),
                    ("RESET", r"\bRESET\b"),
                    ("REMOVE", r"\bREMOVE\b"),
                    ("REPLACE", r"\bREPLACE\b"),
                    ("TAX", r"\bTAX\b"),
                    ("O&P", r"\bO\s*&\s*P\b|\bO&P\b"),
                    ("TOTAL", r"\bTOTAL\b"),
                ]
                posmap = []
                low = nxt.upper()
                for name, pat in tokens:
                    m = re.search(pat, nxt, re.IGNORECASE)
                    if m:
                        posmap.append((m.start(), name))
                posmap.sort(key=lambda x: x[0])
                cols_line2 = [name for _, name in posmap]

            # Require at least QTY and TOTAL in the second line to consider it a real table start
            if "QTY" in cols_line2 and "TOTAL" in cols_line2:
                flags = TableColumns(
                    has_reset=("RESET" in cols_line2),
                    has_tax=("TAX" in cols_line2),
                    has_op=("O&P" in cols_line2 or "O & P" in cols_line2),
                )
                profile = {
                    "type": "apex",
                    "columns": ["CAT","SEL","ACT","DESCRIPTION"] + cols_line2,
                    "apex_flags": flags
                }
                return (HeaderType.APEX, 2, profile)

            # Some Apex PDFs compress second line; accept single-line variant with QTY/TOTAL seen in the same row
            if re.search(r"\bQTY\b", cur, re.IGNORECASE) and re.search(r"\bTOTAL\b", cur, re.IGNORECASE):
                flags = TableColumns(has_reset=("RESET" in cur),
                                    has_tax=("TAX" in cur),
                                    has_op=("O&P" in cur or "O & P" in cur))
                profile = {
                    "type": "apex",
                    "columns": re.findall(r"[A-Z&\.]+", cur),
                    "apex_flags": flags
                }
                return (HeaderType.APEX, 1, profile)

        return (None, 0, None)

    def backtrack_section_context(self, lines, header_idx):
        """
        Walk upward from header_idx-1 to collect:
        - area (sticky across sections)
        - section_name (+ optional height)
        - metadata (doors/walls/areas via _extract_metadata_from_line)
        - subrooms [{subroom_name, metadata{height,...}}]
        Returns:
        {
            "area": str|None,
            "section_name": str,
            "height": str|None,
            "metadata": dict,
            "subrooms": list,
            "scan_start_idx": int
        }
        """
        i = header_idx - 1
        area = None
        section_name = None
        height = None
        metadata = {}
        subrooms = []

        # simple helpers
        def clean(s): 
            return re.sub(r"\s+", " ", (s or "").replace("\u00A0"," ").strip())

        def looks_like_stop(s):
            if not s: 
                return False
            s2 = clean(s)
            if re.match(r"^\s*Totals?:", s2, re.IGNORECASE): 
                return True
            if re.search(r"^\s*(Summary\s+for|Recap\s+|Coverage\s+|Grand\s+Total\s+Areas)\b", s2, re.IGNORECASE): 
                return True
            if re.match(r"^\d{1,4}$", s2): 
                return True
            if "Page:" in s2 or "Date:" in s2: 
                return True
            # another header above would also be a stop (handled by main loop via detect_table_header)
            return False

        # we will accumulate lines upward until a big gap/stop
        scan_start_idx = max(0, header_idx - 30)  # reasonable cap
        last_seen_section_line = None
        pending_subroom = None

        while i >= 0 and i >= scan_start_idx:
            raw = lines[i] or ""
            s = clean(raw)

            # NOTE: use module-level helpers (no self.)
            if looks_like_stop(s) or is_page_header(s, []):
                break
            if is_diagram_artifact(s):
                i -= 1
                continue

            # Subroom lines (captured while scanning up)
            is_sub, sub_name, sub_h = is_subroom_header(s)
            if is_sub:
                if pending_subroom:
                    subrooms.append(pending_subroom)
                pending_subroom = {"subroom_name": sub_name, "metadata": {"height": sub_h}}
                i -= 1
                continue

            # Section name with optional Height
            msec = re.match(r"^(.+?)\s+Height:\s*(.+?)\s*$", s, re.IGNORECASE)
            if msec and section_name is None:
                section_name = msec.group(1).strip()
                height = msec.group(2).strip()
                last_seen_section_line = s
                i -= 1
                continue

            # Plain section name (no height) – prefer the closest good title-like line
            if section_name is None:
                # Filter out obvious non-titles
                if not re.match(r"^(CAT\s+SEL\s+ACT|DESCRIPTION\s+QUANTITY\s+UNIT)", s, re.IGNORECASE) \
                and not s.lower().startswith("continued -") \
                and not s.lower().startswith("source -") \
                and not s.lower().startswith("estimate:") \
                and not s.lower().startswith("summary"):
                    # Heuristic: shortish, title-cased or underscored area/room names
                    if len(s) <= 50 and not re.search(r"\$\d|Totals?:", s, re.IGNORECASE):
                        section_name = s
                        last_seen_section_line = s
                        i -= 1
                        continue

            # Area: a title-like line above the section name (distinct)
            if section_name and area is None:
                if s and s != last_seen_section_line:
                    if len(s) <= 40 and not re.search(r"(Height:|Totals?:|CAT\s+SEL|DESCRIPTION\s+QUANTITY)", s, re.IGNORECASE):
                        # avoid summary/coverage
                        if not re.search(r"(Summary|Coverage|Recap|Trade\s+Summary)", s, re.IGNORECASE):
                            area = s

            # Metadata (doors/walls/areas)
            md = self._extract_metadata_from_line(s)
            if md:
                metadata = self._merge_metadata(metadata, md)
                if area is None and metadata.get('area'):
                    area = metadata.get('area')

            i -= 1

        # flush pending subroom (if we saw any while scanning upward)
        if pending_subroom:
            subrooms.append(pending_subroom)

        # defaults
        if not section_name:
            section_name = "Unknown Section"

        return {
            "area": area,
            "section_name": section_name,
            "height": height,
            "metadata": metadata,
            "subrooms": list(reversed(subrooms)),  # keep natural order (top→down)
            "scan_start_idx": i+1
        }

    def parse_statefarm_row(self, line, profile):
        """
        Parse a State Farm row according to the profile columns.
        Expected format (canonical):
        [index.] DESCRIPTION <...>   QUANTITY(unit-suffixed like 4,354.00SF)  UNIT  PRICE  TAX  RCV
        We will accept:
        - optional leading index like '1.' (we strip it)
        - quantity as "<number><UNIT>" or "<number> <UNIT>"
        Returns: dict or None
        """
        s = re.sub(r"\s+", " ", (line or "").replace("\u00A0"," ").strip())
        # Strip leading "n." index if present
        s = re.sub(r"^\d+\.\s+", "", s)

        # The safest approach: capture from right to left the last 3 numeric fields (PRICE, TAX, RCV)
        m = re.search(r"\s(?P<price>[\d,]+\.\d{2})\s+(?P<tax>[\d,]+\.\d{2})\s+(?P<rcv>[\d,]+\.\d{2})\s*$", s)
        if not m:
            return None

        price = m.group("price")
        tax = m.group("tax")
        rcv = m.group("rcv")
        left = s[:m.start()].rstrip()

        # Now split left into DESCRIPTION + QUANTITY (with unit)
        # quantity at the right end as "<num><unit>" or "<num> <unit>"
        mq = re.search(r"(?P<num>[\d,]+(?:\.\d+)?)[ ]?(?P<unit>[A-Z]{2,})\s*$", left)
        if not mq:
            return None

        qty = mq.group("num")
        unit = mq.group("unit")
        description = left[:mq.start()].rstrip()

        try:
            qty_val = float(qty.replace(",", ""))
        except Exception:
            qty_val = 0.0

        return {
            "type": "line_item",
            "line_number": None,
            "cat": None, "sel": None, "act": None,
            "description": description,
            "calc": "",
            "qty": qty_val,
            "unit": unit,
            "price": format_dollar_amount(_money_to_float(price)),
            "item_codes": [],
            "reset": None, "remove": None, "replace": None,
            "tax": format_dollar_amount(_money_to_float(tax)) if "TAX" in (profile.get("columns") or []) else None,
            "op": None,
            "total": format_dollar_amount(_money_to_float(rcv)),   # RCV is the line total in SF
            "total_note": None,
            "notes": ""
        }

    def map_totals_from_line(self, profile, totals_line, section_name_hint=None):
        """
        Convert a Totals line into {'tax':..., 'op':..., 'total':...} using the profile columns.
        For STATEFARM the last number is RCV (section total). If TAX column exists, the penultimate number is tax.
        For APEX, delegate to existing _parse_totals_line using synthesized TableColumns flags from profile['apex_flags'].
        """
        s = (totals_line or "").strip()

        if profile["type"] == "statefarm":
            # Typical: "Totals: <name> <tax> <rcv>" or "Totals: <name> <rcv>"
            nums = re.findall(r"([\d,]+\.\d{2})", s)
            if not nums:
                return {"tax": None, "op": None, "total": "0.00"}
            # last is total (RCV)
            total = format_dollar_amount(_money_to_float(nums[-1]))
            tax = None
            if "TAX" in profile.get("columns", []) and len(nums) >= 2:
                tax = format_dollar_amount(_money_to_float(nums[-2]))
            return {"tax": tax, "op": None, "total": total}

        # APEX: use your existing logic but with the flags from profile
        flags = profile.get("apex_flags") or TableColumns(False, False, False)
        # Reuse your existing _parse_totals_line by faking a TableColumns instance
        return self._parse_totals_line(s, flags)

    def _normalize_line_item_keys(self, item: dict, columns: List[str]) -> dict:
        if not item:
            return item
        if not columns:
            return dict(item)

        normalized: Dict[str, object] = {}
        synonyms = {
            'quantity': ['qty'],
            'qty': ['quantity'],
            'total': ['rcv'],
            'rcv': ['total'],
            'oandp': ['op'],
        }

        for column in columns:
            key = column.lower().replace("&", "and").replace(".", "").replace(" ", "_")
            candidates = [key]
            for alias in synonyms.get(key, []):
                if alias not in candidates:
                    candidates.append(alias)

            value = None
            for cand in candidates:
                if cand in item:
                    value = item[cand]
                    break
            normalized[key] = value

        for extra_key in ('type', 'line_number'):
            if extra_key in item:
                normalized[extra_key] = item[extra_key]

        if 'unit' in item and ('unit' not in normalized or normalized['unit'] in (None, '')):
            normalized['unit'] = item['unit']

        if 'item_codes' in item and 'item_codes' not in normalized:
            normalized['item_codes'] = item['item_codes']

        if 'total_note' in item and 'total_note' not in normalized:
            normalized['total_note'] = item['total_note']

        notes_val = item.get('notes')
        if notes_val:
            normalized['notes'] = notes_val

        return normalized

    # ---------- core parsing (from provided full_lines) ----------
    def _parse_document_from_lines(self, full_lines: List[str], skip_mask: Optional[List[bool]] = None) -> tuple:
        """
        NEW: Header-anchored, totals-terminated sequential parser.
        - Opens a section only when a table header is found (STATEFARM or APEX).
        - Backtracks to assemble Area/SectionName/Height/Metadata/Subrooms.
        - Consumes page-wrapped headers as CONTINUATIONS while the section is open (until Totals).
        - Maps Totals by column names from the detected profile.
        """
        lines = full_lines
        sections: List[dict] = []

        current_section = None
        current_line_item = None
        collecting_notes = False
        current_area = None  # sticky area label across sections

        i = 0
        L = len(lines)
        while i < L:
            if skip_mask is not None and 0 <= i < len(skip_mask) and skip_mask[i]:
                i += 1
                continue

            line = (lines[i] or "").strip()
            if is_page_header(line, []):
                i += 1
                continue
            if is_diagram_artifact(line):
                i += 1
                continue

            # 1) Detect headers (always allowed)
            hdr_type, consumed, profile = self.detect_table_header(lines, i)

            if hdr_type is not None:
                # If a section is OPEN and we see another header BEFORE its Totals,
                # treat as a page-wrap/continuation: just advance and keep appending items.
                if current_section is not None:
                    prev_cols = (current_section.get("_profile") or {}).get("columns", [])
                    new_cols = profile.get("columns", [])
                    if prev_cols == new_cols:
                        # same table layout → continuation
                        i += consumed
                        # allow a few "line item header" banner rows like --- Walls --- right after wrapped header
                        while i < L:
                            t = (lines[i] or "").strip()
                            if not t or is_page_header(t, []) or is_diagram_artifact(t):
                                i += 1; continue
                            is_hdr, _txt = is_line_item_header(t)
                            if is_hdr:
                                current_section['line_items'].append({'type': 'header', 'text': _txt})
                                i += 1
                                continue
                            # stop banner window when we hit a non-header/non-noise
                            break
                        continue
                    else:
                        if current_line_item and collecting_notes:
                            columns = (current_section.get("_profile") or {}).get("columns", [])
                            normalized_item = self._normalize_line_item_keys(current_line_item, columns)
                            current_section['line_items'].append(normalized_item)
                        current_line_item = None
                        collecting_notes = False
                        current_section.pop("_profile", None)
                        sections.append(current_section)
                        current_section = None
                        # reopen with new context below

                # 2) Open a NEW section: backtrack to collect context
                ctx = self.backtrack_section_context(lines, i)
                current_area = ctx.get("area")

                current_section = {
                    "section_name": ctx["section_name"],
                    "metadata": {**ctx.get("metadata", {}), **({"height": ctx["height"]} if ctx.get("height") else {})},
                    "subrooms": ctx.get("subrooms") or [],
                    "line_items": [],
                    "section_totals": {},
                    "_profile": profile
                }
                if current_area and 'area' not in current_section["metadata"]:
                    # put area either top-level or inside metadata; here we choose metadata
                    current_section["metadata"]["area"] = current_area

                # consume header lines
                i += consumed
                # after header, optional line-item header banners (--- Walls ---)
                while i < L:
                    t = (lines[i] or "").strip()
                    if not t or is_page_header(t, []) or is_diagram_artifact(t):
                        i += 1; continue
                    is_hdr, _txt = is_line_item_header(t)
                    if is_hdr:
                        current_section['line_items'].append({'type': 'header', 'text': _txt})
                        i += 1
                        continue
                    break
                continue

            # 3) If we don't have an open section yet, advance
            if current_section is None:
                i += 1
                continue

            # 4) Inside an open section → handle Totals / line-items / notes
            s = line

            # Totals: ends the section
            if re.match(r"^Totals?:", s, re.IGNORECASE):
                # flush pending header-notes into the last item
                if current_line_item and collecting_notes:
                    columns = (current_section.get("_profile") or {}).get("columns", [])
                    normalized_item = self._normalize_line_item_keys(current_line_item, columns)
                    current_section['line_items'].append(normalized_item)
                    current_line_item = None
                    collecting_notes = False

                # profile-aware totals mapping
                totals = self.map_totals_from_line(current_section["_profile"], s, current_section.get("section_name"))
                current_section['section_totals'] = totals

                # finalize section
                current_section.pop("_profile", None)
                sections.append(current_section)
                current_section = None
                i += 1
                continue

            # Line-item header rows (--- Walls ---)
            is_hdr, _txt = is_line_item_header(s)
            if is_hdr:
                if current_line_item and collecting_notes:
                    columns = (current_section.get("_profile") or {}).get("columns", [])
                    normalized_item = self._normalize_line_item_keys(current_line_item, columns)
                    current_section['line_items'].append(normalized_item)
                    current_line_item = None
                    collecting_notes = False
                current_section['line_items'].append({'type': 'header', 'text': _txt})
                i += 1
                continue

            # Parse line items per profile
            prof = current_section.get("_profile", {})
            ptype = prof.get("type")

            parsed = None
            if ptype == "statefarm":
                parsed = self.parse_statefarm_row(s, prof)
                if parsed:
                    parsed = self._normalize_line_item_keys(parsed, prof.get("columns", []))
                    if current_line_item and collecting_notes:
                        columns = (current_section.get("_profile") or {}).get("columns", [])
                        normalized_item = self._normalize_line_item_keys(current_line_item, columns)
                        current_section['line_items'].append(normalized_item)
                        current_line_item = None
                    current_section['line_items'].append(parsed)
                    collecting_notes = True
                    current_line_item = parsed  # latest becomes the one receiving notes
                    i += 1
                    continue
            else:
                # APEX flow: use your existing detectors
                if is_line_item(s):
                    # close previous pending item
                    if current_line_item and collecting_notes:
                        columns = (current_section.get("_profile") or {}).get("columns", [])
                        normalized_item = self._normalize_line_item_keys(current_line_item, columns)
                        current_section['line_items'].append(normalized_item)
                        current_line_item = None
                        collecting_notes = False

                    m = re.match(LINE_ITEM_PATTERN, s)
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
                            'reset': None, 'remove': None, 'replace': None,
                            'tax': None, 'op': None,
                            'total': None, 'total_note': None, 'notes': ''
                        }
                        current_line_item = self._normalize_line_item_keys(current_line_item, prof.get("columns", []))
                    i += 1
                    continue

                # calc/price line (gives totals for the item)
                if current_line_item and re.search(CALC_LINE_DETECTION_PATTERN, s):
                    calc = self._parse_line_item_calc(s, prof.get("apex_flags") or TableColumns())
                    if calc:
                        current_line_item.update(calc)
                        collecting_notes = True
                        i += 1
                        continue

            # Notes accumulation for both profiles
            if current_line_item and collecting_notes:
                # skip obvious noise
                if not is_page_header(s, []) and not is_diagram_artifact(s) and not _is_footer_line(s):
                    existing_notes = current_line_item.get('notes') or ''
                    current_line_item['notes'] = (existing_notes + ' ' + s).strip()
                i += 1
                continue

            # Fallback advance
            i += 1

        # If document ends while a section is open but we never saw Totals,
        # append what we have (rare, but safer than dropping)
        if current_section is not None:
            if current_line_item and collecting_notes:
                columns = (current_section.get("_profile") or {}).get("columns", [])
                normalized_item = self._normalize_line_item_keys(current_line_item, columns)
                current_section['line_items'].append(normalized_item)
            current_section.pop("_profile", None)
            sections.append(current_section)

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
                txt = page.extract_text() or ""
                lines.extend([l.strip() for l in txt.split('\n') if l.strip()])
        return lines

    # ----- metadata helpers -----
    def _extract_area_summary(self, line: str) -> Tuple[Optional[str], Dict[str, str]]:
        cleaned = re.sub(r"\s+", " ", (line or "").replace("\u00A0", " ").strip())
        if not cleaned:
            return None, {}

        segments: List[Tuple[int, str]] = []
        values: Dict[str, str] = {}
        seen_keys = set()

        for label, key in AREA_SUMMARY_LABELS:
            pattern = rf'([0-9,]+(?:\.[0-9]+)?)\s+({re.escape(label)})'
            for match in re.finditer(pattern, cleaned, re.IGNORECASE):
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                num_str = match.group(1)
                label_text = label
                formatted = _format_metric_number(num_str)
                values[key] = formatted
                segments.append((match.start(), f"{formatted} {label_text}".strip()))

        if not segments:
            return None, values

        segments.sort(key=lambda pair: pair[0])
        summary = " ".join(seg for _, seg in segments).strip()
        return summary, values

    def _extract_metadata_from_line(self, line: str) -> dict:
        if not line:
            return {}

        lowered = line.lower()
        if any(keyword in lowered for keyword in ("totals", "recap", "summary", "coverage", "page:")):
            return {}

        md: Dict[str, object] = {}
        summary_text, summary_values = self._extract_area_summary(line)
        if summary_text:
            md['area'] = summary_text
        if summary_values:
            areas = md.setdefault('areas', {})
            for key, value in summary_values.items():
                areas[key] = value

        area_matches = []
        for key, pat in METADATA_PATTERNS.items():
            m = re.search(pat, line)
            if m:
                area_matches.append((key, format_dollar_amount(_money_to_float(m.group(1)))))

        if len(area_matches) == 1:
            key, value = area_matches[0]
            md.setdefault('areas', {})[key] = value

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
                if not isinstance(v, dict):
                    continue
                base.setdefault('areas', {})
                for area_key, value in v.items():
                    if area_key not in base['areas'] or base['areas'][area_key] != value:
                        base['areas'][area_key] = value
            elif k == 'area':
                if v and not base.get('area'):
                    base['area'] = v
            elif k in ('doors', 'missing_walls'):
                base.setdefault(k, []).extend(v)
            else:
                base[k] = v
        return base

    # ---------- Non-sequential helpers (Recap by Category pre-pass) ----------
    def _norm_line(self, s: str) -> str:
        return re.sub(r'\s+', ' ', (s or '').replace('\u00A0', ' ').strip())

    def _find_all_section_occurrences(self,
                                      all_lines: List[str],
                                      header_re: re.Pattern,
                                      stoppers: List[re.Pattern]) -> List[Tuple[int, int]]:
        n = len(all_lines)
        i = 0
        spans = []
        while i < n:
            if header_re.search(self._norm_line(all_lines[i])):
                # collapse consecutive header echoes
                j = i + 1
                while j < n and header_re.search(self._norm_line(all_lines[j])):
                    j += 1
                start = j
                # find nearest stopper after start
                k = start
                end = n
                while k < n:
                    s = self._norm_line(all_lines[k])
                    if any(p.search(s) for p in stoppers):
                        end = k
                        break
                    k += 1
                if start < end:
                    spans.append((start, end))
                    i = end
                    continue
            i += 1
        return spans

    def _build_skip_mask(self, n_lines: int, ranges: List[Tuple[int, int]]) -> List[bool]:
        mask = [False] * n_lines
        for a, b in ranges:
            a = max(0, a); b = min(n_lines, b)
            for i in range(a, b):
                mask[i] = True
        return mask

    def _prepass_recap_by_category(self, all_lines: List[str]) -> Tuple[Dict[str, object], List[Tuple[int, int]]]:
        RECAP_BY_CATEGORY_HDR_RELAXED = re.compile(r'\bRecap\s+by\s+Category\b', re.IGNORECASE)
        STOPPERS = [
            re.compile(r'^\s*Recap\s+by\s+Room\s*$', re.IGNORECASE),
            re.compile(r'^\s*Recap\s+of\s+Taxes,\s+Overhead\s+and\s+Profit\s*$', re.IGNORECASE),
            re.compile(r'^\s*Summary\s+for\s+', re.IGNORECASE),
            re.compile(r'^\s*Grand\s+Total\s+Areas\b', re.IGNORECASE),
            re.compile(r'^\s*Coverage\s+Deductible\s+Policy\s+Limit', re.IGNORECASE),
            re.compile(r'^\s*CAT\s+SEL\s+ACT\s+DESCRIPTION', re.IGNORECASE),
        ]

        spans = self._find_all_section_occurrences(all_lines, RECAP_BY_CATEGORY_HDR_RELAXED, STOPPERS)
        merged = {"subtotals": []}

        for (start, end) in spans:
            hdr_idx = start - 1
            while hdr_idx >= 0 and not RECAP_BY_CATEGORY_HDR_RELAXED.search(self._norm_line(all_lines[hdr_idx])):
                hdr_idx -= 1
            if hdr_idx < 0:
                hdr_idx = start

            block, _ = self._parse_recap_by_category_section(all_lines, hdr_idx)
            # merge
            for k, v in block.items():
                if k == "subtotals":
                    merged["subtotals"].extend(v)
                else:
                    if isinstance(v, list):
                        merged.setdefault(k, []).extend(v)
                    else:
                        merged[k] = v

        # de-dup identical subtotal rows
        if merged.get("subtotals"):
            seen = set()
            uniq = []
            for e in merged["subtotals"]:
                key = (e.get("label"), e.get("total"), e.get("pct"))
                if key not in seen:
                    seen.add(key)
                    uniq.append(e)
            merged["subtotals"] = uniq

        return merged, spans

    def _prepass_summaries(self, all_lines: List[str]) -> Tuple[Dict[str, Dict[str, str]], List[Tuple[int, int]]]:
        """
        Detect and parse ALL 'Summary for <...>' sections in the document (non-sequential).
        Each section is bounded from its header to the FIRST 'Net Claim <value>' line encountered.
        'Trade Summary' is ignored here (handled separately later).
        Returns: (summaries_by_coverage, spans)
        """
        summaries: Dict[str, Dict[str, str]] = {}
        spans: List[Tuple[int, int]] = []

        n = len(all_lines)
        i = 0
        while i < n:
            s = (all_lines[i] or "").strip()
            if s.startswith("Summary") and re.match(SUMMARY_FOR_HDR, s, re.IGNORECASE) and not s.lower().startswith("summary trade"):
                (cov, kv), j = self._parse_summary_section(all_lines, i)
                if kv:
                    summaries[cov] = {**summaries.get(cov, {}), **kv}
                spans.append((i, j))
                i = j
                continue
            i += 1

        return summaries, spans

    # ----- end-of-document parsing in structured form -----
    def _parse_recap_by_room_section(self, all_lines: List[str], start_idx: int):
        """
        Recap by Room → independent parser.
        Returns: ({"areas": {<group>: [items...]}, "subtotals": [...], "_span": (start,end)}, next_idx)

        Groups (keys in 'areas', insertion-ordered):
        - "estimate: <id>"         (lowercased prefix)
        - "<area name>"            (from "Area: <name>"), lowercased
            * If the Area header line has inline "<amt> <pct>%", it is emitted as an item with:
            item=<name> (no "Area:" prefix), total=<amt>, pct=<pct>, + captured coverage rows.

        Recognized rows:
        - Item: "<label> <amount> <pct>%"
        - Coverage: "Coverage: <label> <pct>% = <amount>"  (0..n lines after an item/special/subtotal)
        - Special (no pct): "Labor Minimums Applied <amount>"
        - Subtotals:
            "Area Subtotal: <name> <amount> <pct>%"
            "Subtotal of Areas <amount> <pct>%"
            "Total <amount> 100.00%"
        """
        import re

        # ---- helpers ----
        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").replace("\u00A0", " ").strip())

        def is_noise(s: str) -> bool:
            if not s: return True
            if "Page:" in s or re.fullmatch(r"\d{1,4}", s): return True
            if s.startswith(("Date:", "Apex ", "State Farm", "CA DOI", "www.", "Claim #", "Policy #")): return True
            if "Suite" in s or "Adjusters" in s: return True
            return False

        def money(x: str) -> str:
            return format_dollar_amount(_money_to_float(re.sub(r"\s+", "", (x or "").replace("\u00A0", " "))))

        def pct(x: str) -> float:
            return float((x or "").replace(",", ".").strip())

        def capture_coverage(k: int, n: int) -> (list, int):
            covs = []
            i2 = k
            while i2 < n:
                raw = all_lines[i2] or ""
                if is_noise(raw): i2 += 1; continue
                s2 = norm(raw)
                m = RX["COVER"].match(s2)
                if not m: break
                covs.append({"coverage": m.group("label").strip(),
                            "pct": pct(m.group("pct")),
                            "amount": money(m.group("amt"))})
                i2 += 1
            return covs, i2

        def add_item(group_key: str, label: str, amt: str, pc: str, cov_start: int, n: int):
            cov, j2 = capture_coverage(cov_start, n)
            areas.setdefault(group_key, []).append({
                "item": label, "total": money(amt), "pct": pct(pc), "coverage": cov
            })
            return j2

        def add_subtotal(label: str, amt: str, pc: str, cov_start: int, n: int):
            cov, j2 = capture_coverage(cov_start, n)
            entry = {"label": label, "total": money(amt), "pct": pct(pc)}
            if cov: entry["coverage"] = cov
            subtotals.append(entry)
            return j2

        # ---- regexes (compact & tolerant) ----
        PCT = r"%\uFF05"  # ASCII or fullwidth percent
        RX = {
            "HDR": re.compile(r"^\s*Recap\s+by\s+Room\s*$", re.IGNORECASE),
            "STOP": [
                re.compile(r"^\s*Recap\s+by\s+Category\s*$", re.IGNORECASE),
                re.compile(r"^\s*Recap\s+of\s+Taxes,\s+Overhead\s+and\s+Profit\s*$", re.IGNORECASE),
                re.compile(r"^\s*Summary\s+for\s+", re.IGNORECASE),
                re.compile(r"^\s*Grand\s+Total\s+Areas\b", re.IGNORECASE),
            ],
            "EST": re.compile(r"^\s*Estimate:\s*(?P<id>.+?)\s*$", re.IGNORECASE),
            # Area header with optional inline amount & pct
            "AREA": re.compile(
                rf"^\s*Area:\s*(?P<name>.+?)\s*(?:(?P<amt>[\d,]+(?:\.\d+)?)\s+(?P<pct>\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT}])?\s*$",
                re.IGNORECASE
            ),
            # Generic item tail "<amt> <pct>%"
            "TAIL": re.compile(rf"(?P<amt>[\d,]+(?:\.\d+)?)\s+(?P<pct>\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT}]$"),
            # Coverage line (no '@' in Room recap)
            "COVER": re.compile(r"^\s*Coverage:\s*(?P<label>.+?)\s+(?P<pct>\d{1,3}(?:\.\d{1,2})?)\s*[%\uFF05]\s*=\s*(?P<amt>[\d,]+(?:\.\d+)?)\s*$"),
            # Subtotals
            "ASUB": re.compile(rf"^\s*Area\s+Subtotal:\s*(?P<label>.+?)\s+(?P<amt>[\d,]+(?:\.\d+)?)\s+(?P<pct>\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT}]$", re.IGNORECASE),
            "SOA": re.compile(rf"^\s*Subtotal\s+of\s+Areas\s+(?P<amt>[\d,]+(?:\.\d+)?)\s+(?P<pct>\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT}]$", re.IGNORECASE),
            "TOTAL": re.compile(rf"^\s*Total\s+(?P<amt>[\d,]+(?:\.\d+)?)\s+100(?:\.00)?\s*[{PCT}]?$", re.IGNORECASE),
            # Special (no pct)
            "LABOR": re.compile(r"^\s*Labor\s+Minimums\s+Applied\s+(?P<amt>[\d,]+(?:\.\d+)?)\s*$", re.IGNORECASE),
        }

        # ---- locate section bounds & init ----
        seg_start, seg_end = self._find_section_bounds(all_lines, RX["HDR"], RX["STOP"], start_hint=start_idx)
        if seg_start == -1:
            return {"areas": {}, "subtotals": [], "_span": None}, start_idx + 1

        areas: Dict[str, List[Dict[str, object]]] = {}
        subtotals: List[Dict[str, object]] = []
        current_group: Optional[str] = None

        i, n = seg_start, seg_end
        while i < n:
            raw = all_lines[i] or ""
            if is_noise(raw): i += 1; continue
            s = norm(raw)

            # Group: Estimate
            m = RX["EST"].match(s)
            if m:
                current_group = f"estimate: {m.group('id').strip()}"
                areas.setdefault(current_group, [])
                i += 1
                continue

            # Group: Area (optional inline amt/pct)
            m = RX["AREA"].match(s)
            if m:
                area_name = m.group("name").strip()
                current_group = area_name.lower()
                areas.setdefault(current_group, [])

                amt, pc = m.group("amt"), m.group("pct")
                if amt and pc:
                    i = add_item(current_group, area_name, amt, pc, i + 1, n)
                    continue
                i += 1
                continue

            # Subtotals
            m = RX["ASUB"].match(s)
            if m:
                i = add_subtotal(f"Area Subtotal: {m.group('label').strip()}", m.group("amt"), m.group("pct"), i + 1, n)
                continue

            m = RX["SOA"].match(s)
            if m:
                i = add_subtotal("Subtotal of Areas", m.group("amt"), m.group("pct"), i + 1, n)
                continue

            m = RX["TOTAL"].match(s)
            if m:
                subtotals.append({"label": "Total", "total": money(m.group("amt")), "pct": 100.00})
                i += 1
                continue

            # Special (no pct)
            m = RX["LABOR"].match(s)
            if m:
                cov, j2 = capture_coverage(i + 1, n)
                grp = current_group or "estimate: (unknown)"
                areas.setdefault(grp, []).append({"item": "Labor Minimums Applied",
                                                "total": money(m.group("amt")),
                                                "pct": None,
                                                "coverage": cov})
                i = j2
                continue

            # Generic item "<label> <amt> <pct>%"
            mt = RX["TAIL"].search(s)
            if mt:
                label = s[:mt.start()].strip().rstrip(":")
                amt, pc = mt.group("amt"), mt.group("pct")
                grp = current_group or "estimate: (unknown)"
                i = add_item(grp, label, amt, pc, i + 1, n)
                continue

            i += 1

        return {"areas": areas, "subtotals": subtotals, "_span": (seg_start, seg_end)}, seg_end

    def _parse_recap_by_category_section(self, all_lines: List[str], start_idx: int) -> Tuple[Dict[str, object], int]:
        """
        Parses a single 'Recap by Category' block starting at start_idx (line matches RECAP_BY_CATEGORY_HDR).

        Behavior:
        - Skips page-wrap repeats of "<Category Name> Total %" unless the name actually changes.
        - Allocation rows ('Permits and Fees', 'Material Sales Tax', 'Overhead', 'Profit') go ONLY to 'subtotals'
            (with coverage) and are NOT emitted as top-level keys.
        - Bare "Subtotal <amt> <pct>%" inside an active/only group is captured and labeled "<current_key> Subtotal"
            (e.g., "Items Subtotal"), even in single-category tables.
        - Item names allow ':' (e.g., "CONT: CLEAN - GENERAL ITEMS").
        - Accepts ASCII '%' and fullwidth '％'.

        Fix for missing Items Subtotal:
        - Capture key_for_label BEFORE flush_group() and use it to emit "<key> Subtotal".
        - Fallback to last_key_seen_for_pagewrap when current_key is None at bare-subtotal time.
        """
        def gmoney(x: str) -> str:
            return format_dollar_amount(_money_to_float(x))

        # support ASCII '%' and fullwidth '％'
        PCT_CH = r"%\uFF05"

        # Headers and rows
        KEY_TOTAL_HDR = re.compile(
            rf"^([A-Za-z0-9/_\-\.\s\(\),&':]+?)\s+Total\s+(?:\d{{1,3}}(?:\.\d{{1,2}})?\s*[{PCT_CH}]|[{PCT_CH}])$",
            re.IGNORECASE
        )
        KEY_SUBTOTAL_ROW = re.compile(
            rf"^([A-Za-z0-9/_\-\.\s\(\),&':]+?)\s+Subtotal\s+([\d,]+\.\d+)\s+(\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT_CH}]$",
            re.IGNORECASE
        )
        BARE_SUBTOTAL_ROW = re.compile(
            rf"^Subtotal\s+([\d,]+\.\d+)\s+(\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT_CH}]$",
            re.IGNORECASE
        )

        # Allow ':' and fullwidth % in item lines
        RECAP_ITEM_LINE = re.compile(
            rf"^([A-Za-z0-9/_\-\.\s\(\),&':]+?)\s+([\d,]+\.\d+)\s+(\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT_CH}]$"
        )

        COVER_SPLIT = re.compile(RECAP_COVERAGE_SPLIT)
        ALLOC_LABEL_ROW = re.compile(
            rf"^(Permits and Fees|Material Sales Tax|Overhead|Profit)\s+([\d,]+\.\d+)\s+(\d{{1,3}}(?:\.\d{{1,2}})?)\s*[{PCT_CH}]$",
            re.IGNORECASE
        )
        FINAL_TOTAL_100 = re.compile(
            rf"^Total\s+([\d,]+\.\d+)\s+100(?:\.00)?\s*[{PCT_CH}]$",
            re.IGNORECASE
        )

        def is_all_caps_name(s: str) -> bool:
            return not re.search(r"[a-z]", s)

        def is_page_noise(s: str) -> bool:
            if not s: return True
            if "Page:" in s: return True
            if re.fullmatch(r"\d{1,4}", s): return True
            if s.startswith(("Date:", "Apex ", "State Farm", "CA DOI", "www.", "CHEN,", "Claim #", "Policy #")): return True
            if "Suite" in s or "Adjusters" in s: return True
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
            # de-dup by (label, total, pct)
            for e in arr:
                if e.get("label") == entry.get("label") and e.get("total") == entry.get("total") and e.get("pct") == entry.get("pct"):
                    return
            arr.append(entry)

        out = {"subtotals": []}
        i = start_idx + 1
        n = len(all_lines)
        current_key: Optional[str] = None
        pending_items: List[dict] = []

        def flush_group():
            nonlocal current_key, pending_items
            if current_key and pending_items:
                out.setdefault(current_key, []).extend(pending_items)
            current_key, pending_items = None, []

        last_key_seen_for_pagewrap: Optional[str] = None

        while i < n:
            s = (all_lines[i] or "").strip()

            # Stop on obvious new major section
            if s.startswith("Dwelling -") or s.startswith("Estimate:") or s.startswith("Summary for "):
                break

            # Group header — tolerant to page-top repeats of the SAME key
            mt = KEY_TOTAL_HDR.match(s)
            if mt:
                new_key = mt.group(1).strip()
                if current_key == new_key:
                    i += 1
                    continue
                if last_key_seen_for_pagewrap == new_key and not pending_items:
                    i += 1
                    continue
                flush_group()
                current_key = new_key
                last_key_seen_for_pagewrap = new_key
                i += 1
                continue

            # Items within active group
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

                # Labeled subtotal closes the group
                ms = KEY_SUBTOTAL_ROW.match(s)
                if ms:
                    # close items, then push labeled subtotal as-is
                    flush_group()
                    subtotals_add(out["subtotals"], {
                        "label": ms.group(1).strip(),
                        "total": gmoney(ms.group(2)),
                        "pct": float(ms.group(3)),
                    })
                    i += 1
                    continue

                # Bare "Subtotal …" — attribute to current/last key with " Subtotal" suffix (e.g., "Items Subtotal")
                bs = BARE_SUBTOTAL_ROW.match(s)
                if bs:
                    # capture the key BEFORE flushing
                    key_for_label = current_key or last_key_seen_for_pagewrap
                    flush_group()
                    if key_for_label:
                        subtotals_add(out["subtotals"], {
                            "label": f"{key_for_label} Subtotal",
                            "total": gmoney(bs.group(1)),
                            "pct": float(bs.group(2)),
                        })
                    i += 1
                    continue

            # Subtotals & allocations when no active group
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

                # Allocation rows go ONLY into 'subtotals' with coverage; no top-level keys added.
                am = ALLOC_LABEL_ROW.match(s)
                if am:
                    al_label = am.group(1).strip()
                    al_total = gmoney(am.group(2))
                    al_pct = float(am.group(3))
                    cov_list, end_k = capture_coverage(i + 1, n)
                    subtotals_add(out["subtotals"], {
                        "label": al_label, "total": al_total, "pct": al_pct, "coverage": cov_list
                    })
                    i = end_k
                    continue

                ft = FINAL_TOTAL_100.match(s)
                if ft:
                    subtotals_add(out["subtotals"], {
                        "label": "Total",
                        "total": gmoney(ft.group(1)),
                        "pct": 100.00
                    })
                    i += 1
                    continue

            # Page/header noise
            if ("Page:" in s) or re.fullmatch(r"\d{1,4}", s) or s.startswith(("Date:", "Apex ", "State Farm")):
                i += 1
                continue

            i += 1

        flush_group()
        return out, i



    def _parse_recap_tax_op_section(self, all_lines: List[str], start_idx: int) -> Tuple[Optional[Dict[str, str]], int]:
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
                break
            if s.startswith(("Summary for ", "Recap ", "Estimate:", "Grand Total Areas")):
                break
            break
        return cov, i

    def _parse_summary_block(self, all_lines: List[str], start_idx: int) -> Tuple[Tuple[str, Dict[str, str]], int]:
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

    def _parse_summary_section(self, all_lines: List[str], start_idx: int) -> Tuple[Tuple[str, Dict[str, str]], int]:
        """
        Parse a 'Summary for <Coverage>' block starting at start_idx (header line),
        consuming lines through the FIRST 'Net Claim <value>' line (inclusive).

        Returns: ((coverage_name, kv_dict), end_idx_exclusive)
        """
        def gmoney(x: str) -> str:
            return format_dollar_amount(_money_to_float(x))

        hdr = (all_lines[start_idx] or "").strip()
        m = re.match(SUMMARY_FOR_HDR, hdr)
        if not m:
            return (("unknown", {}), start_idx + 1)

        cov = m.group(1).strip()
        kv: Dict[str, str] = {}
        i, n = start_idx + 1, len(all_lines)

        while i < n:
            s = (all_lines[i] or "").strip()
            nm = re.match(SUMMARY_NET_CLAIM_ROW, s, re.IGNORECASE)
            if nm:
                kv["Net Claim"] = gmoney(nm.group(1))
                i += 1
                break

            sm = re.match(SUMMARY_KV_ROW, s, re.IGNORECASE)
            if sm:
                label, amt = sm.group(1), sm.group(2)
                kv[label] = gmoney(amt)
                i += 1
                continue

            if s == "" or s.isdigit() or "Page:" in s:
                i += 1
                continue

            if re.search(r'\bRecap\b', s) or re.search(r'\bGrand\s+Total\s+Areas\b', s) or re.search(r'^\s*Estimate:\s*', s):
                break

            i += 1

        return ((cov, kv), i)

    def _parse_trade_summary_section(self, all_lines: List[str], start_idx: int):
        """
        Parse 'Trade Summary' with strict rule: a trade ends only at 'TOTAL <trade name>'.
        Fixes:
        - Skip split two-line table headers so they don't get mis-read as trades (e.g., 'QTY TOTAL DEPREC. AMT AVAIL.').
        - Harden trade-header acceptance to avoid header terms being classified as trades.
        - Ignore duplicate headers for the same trade (page wrap) and keep appending items.
        Returns: (trade_summary_obj | None, end_idx_exclusive)
        """
        import re

        # -------- helpers --------
        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").replace("\u00A0", " ").strip())

        def gmoney(x: str) -> str:
            cleaned = re.sub(r"[^\d.\-]", "", (x or ""))
            return format_dollar_amount(_money_to_float(cleaned))

        def is_noise(s: str) -> bool:
            if not s:
                return True
            if "Page:" in s or re.fullmatch(r"\d{1,4}", s):
                return True
            if s.startswith(("Date:", "Note:", "Includes all applicable", "Trade Summary")):
                return True
            return False

        def trade_key(name: str) -> str:
            k = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
            return re.sub(r"\s+", " ", k).strip()

        def same_trade(a: str, b: str) -> bool:
            ka, kb = trade_key(a), trade_key(b)
            return bool(ka and kb) and (ka == kb or ka in kb or kb in ka)

        # -------- patterns --------
        # Table header can be printed on one line OR split across two lines.
        TABLE_HDR_ONE = re.compile(
            r"^DESCRIPTION\s+LINE\s+ITEM\s+REPL\.\s+COST\s+ACV\s+NON-REC\.\s+MAX\s+ADDL\.\s+QTY\s+TOTAL\s+DEPREC\.\s+AMT\s+AVAIL\.?$",
            re.IGNORECASE
        )
        TABLE_HDR_L1 = re.compile(
            r"^DESCRIPTION\s+LINE\s+ITEM\s+REPL\.\s+COST\s+ACV\s+NON-REC\.\s+MAX\s+ADDL\.?$",
            re.IGNORECASE
        )
        TABLE_HDR_L2 = re.compile(
            r"^QTY\s+TOTAL\s+DEPREC\.\s+AMT\s+AVAIL\.?$",
            re.IGNORECASE
        )

        TRADE_HDR = re.compile(r"^(?P<code>[A-Z]{3})\s+(?P<trade>[A-Z0-9 /&\-\.\(\)']+)$")
        # Header terms that should never appear as a "trade code" or within a real trade name
        HEADER_STOP_WORDS = {"QTY", "QTR", "TOTAL", "DEPREC", "AMT", "AVAIL", "REPL.", "REPL", "ACV", "NON-REC.", "NON-REC", "MAX", "ADDL", "ITEM", "LINE", "DESCRIPTION"}
        def looks_like_header_term(s: str) -> bool:
            tokens = re.split(r"\s+", s.strip().upper())
            return any(tok in HEADER_STOP_WORDS for tok in tokens)

        MONEY = r"\$?[\d,]+\.\d{2}"
        QTY   = r"(?P<qty>[\d,]+(?:\.\d+)?[A-Z]{2,})"
        ITEM_ROW = re.compile(
            rf"^(?P<desc>.+?)\s+{QTY}\s+(?P<repl>{MONEY})\s+(?P<acv>{MONEY})\s+(?P<nonrec>{MONEY})\s+(?P<maxaddl>{MONEY})$"
        )
        TRADE_TOTAL = re.compile(
            rf"^TOTAL\s+(?P<trade>[A-Z0-9 /&\-\.\(\)']+)\s+(?P<repl>{MONEY})\s+(?P<acv>{MONEY})\s+(?P<nonrec>{MONEY})\s+(?P<maxaddl>{MONEY})$"
        )
        GRAND_TOTALS = re.compile(
            rf"^TOTALS\s+(?P<repl>{MONEY})\s+(?P<acv>{MONEY})\s+(?P<nonrec>{MONEY})\s+(?P<maxaddl>{MONEY})$"
        )

        # -------- find 'Trade Summary' header --------
        n = len(all_lines)
        hdr_idx = -1
        for k in range(start_idx, n):
            if norm(all_lines[k] or "").lower().startswith("trade summary"):
                hdr_idx = k
                break
        if hdr_idx == -1:
            return None, start_idx + 1

        STOP = [
            re.compile(r"^\s*Summary\s+for\s+", re.IGNORECASE),
            re.compile(r"^\s*Recap\s+by\s+Room\s*$", re.IGNORECASE),
            re.compile(r"^\s*Recap\s+by\s+Category\s*$", re.IGNORECASE),
            re.compile(r"^\s*Recap\s+of\s+Taxes,\s+Overhead\s+and\s+Profit\s*$", re.IGNORECASE),
            re.compile(r"^\s*Grand\s+Total\s+Areas\b", re.IGNORECASE),
            re.compile(COVERAGE_TABLE_ROW),
            re.compile(COVERAGE_TOTAL_ROW),
            re.compile(SUMMARY_FOR_HDR, re.IGNORECASE),
        ]
        def looks_like_stop(s: str) -> bool:
            t = norm(s)
            return any(p.search(t) for p in STOP)

        # -------- parse loop --------
        out = {"totals": None, "line_items": [], "_span": None}

        current_trade = None
        current_trade_key = None

        def start_trade(code: str, name: str):
            nonlocal current_trade, current_trade_key
            current_trade = {"trade_code": code, "trade": name, "total": None, "items": []}
            current_trade_key = trade_key(name)

        def close_trade_with_totals(totals_obj: dict):
            nonlocal current_trade, current_trade_key
            if current_trade:
                current_trade["total"] = totals_obj
                out["line_items"].append(current_trade)
            current_trade = None
            current_trade_key = None

        i = hdr_idx + 1
        seg_start = hdr_idx
        seg_end = n
        pending_split_header = False  # we saw line-1 of a split table header; expect to skip line-2 next

        while i < n:
            raw = all_lines[i] or ""
            s = norm(raw)

            if looks_like_stop(s):
                break
            if is_noise(s):
                i += 1
                continue

            # -------- skip table header(s) ----------
            if TABLE_HDR_ONE.match(s):
                i += 1
                continue
            if TABLE_HDR_L1.match(s):
                pending_split_header = True
                i += 1
                continue
            if pending_split_header:
                # eat the second line if present
                if TABLE_HDR_L2.match(s):
                    i += 1
                pending_split_header = False
                continue
            if TABLE_HDR_L2.match(s):
                # stand-alone line 2 (paranoia): skip it
                i += 1
                continue

            # -------- section totals (grand) ----------
            mgt = GRAND_TOTALS.match(s)
            if mgt:
                out["totals"] = {
                    "repl_cost_total": gmoney(mgt.group("repl")),
                    "acv": gmoney(mgt.group("acv")),
                    "non_rec_deprec": gmoney(mgt.group("nonrec")),
                    "max_addl_amt_avail": gmoney(mgt.group("maxaddl")),
                }
                i += 1
                continue

            # -------- trade TOTAL (this *closes* current trade) ----------
            tt = TRADE_TOTAL.match(s)
            if tt:
                tname_total = tt.group("trade").strip()
                totals_obj = {
                    "repl_cost_total": gmoney(tt.group("repl")),
                    "acv": gmoney(tt.group("acv")),
                    "non_rec_deprec": gmoney(tt.group("nonrec")),
                    "max_addl_amt_avail": gmoney(tt.group("maxaddl")),
                }
                if current_trade and same_trade(current_trade["trade"], tname_total):
                    close_trade_with_totals(totals_obj)
                # else: ignore unmatched TOTAL rows (defensive)
                i += 1
                continue

            # -------- trade header (open/continue) ----------
            th = TRADE_HDR.match(s)
            if th:
                code = th.group("code").strip()
                tname = th.group("trade").strip()

                # Harden acceptance: reject header-ish codes or names
                if code in HEADER_STOP_WORDS or looks_like_header_term(tname):
                    i += 1
                    continue

                tkey = trade_key(tname)
                if current_trade is None:
                    start_trade(code, tname)
                else:
                    if current_trade_key and (tkey == current_trade_key or same_trade(current_trade["trade"], tname)):
                        # duplicate page-wrap header for the SAME trade: ignore
                        pass
                    else:
                        # New trade header appeared before TOTAL <old>; in well-formed docs this shouldn't happen.
                        # To avoid losing items, append the open trade (without totals) and start a new one.
                        out["line_items"].append(current_trade)
                        start_trade(code, tname)
                i += 1
                continue

            # -------- item row ----------
            ir = ITEM_ROW.match(s)
            if ir and current_trade:
                current_trade["items"].append({
                    "description": ir.group("desc").strip(),
                    "line_item_qty": ir.group("qty").strip(),
                    "repl_cost_total": gmoney(ir.group("repl")),
                    "acv": gmoney(ir.group("acv")),
                    "non_rec_deprec": gmoney(ir.group("nonrec")),
                    "max_addl_amt_avail": gmoney(ir.group("maxaddl")),
                })
                i += 1
                continue

            i += 1

        seg_end = i
        out["_span"] = (seg_start, seg_end)

        # If nothing meaningful parsed, say "not found"
        if not out["line_items"] and not out["totals"]:
            return None, seg_end

        # If a trade is still open but we never saw its TOTAL, emit it as-is (fallback)
        if current_trade and current_trade.get("items"):
            out["line_items"].append(current_trade)

        return out, seg_end

    def _parse_grand_total_areas_block(self, all_lines: List[str], start_idx: int) -> Tuple[Optional[Dict[str, str]], int]:
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
        """
        Harvests all end-of-document structured blocks (coverage table, summaries, recap by room/category, etc.)
        INDEPENDENTLY of the line-by-line sections. Also returns optional skip spans you can use to
        ignore these ranges during section parsing if desired.
        """
        def gmoney(x: str) -> str:
            return format_dollar_amount(_money_to_float(x))

        result = {
            "line_item_totals": None,
            "labor_minimums": None,
            "additional_charges": None,
            "grand_total_areas": None,
            "coverage": {"rows": [], "totals": None},
            "summaries_by_coverage": {},
            # NEW SHAPE for room recap:
            "recap_by_room": {"areas": {}, "subtotals": []},
            # Category recap remains as previously refactored
            "recap_by_category": {"subtotals": []},
            # internal: ranges to optionally skip in the line-by-line pass
            "_skip_spans": []
        }

        # --- summaries pre-pass (like recaps) ---
        summaries, sum_spans = self._prepass_summaries(all_lines)
        if summaries:
            result["summaries_by_coverage"] = summaries
        if sum_spans:
            result["_skip_spans"].extend(sum_spans)

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

            # Summary for <Coverage> (handled by _prepass_summaries). Advance cursor to avoid re-parsing.
            if re.match(SUMMARY_FOR_HDR, line):
                (_, _), i = self._parse_summary_section(all_lines, i)
                continue

            # Trade Summary (only set key if a real section is parsed)
            if re.match(r"^\s*Trade\s+Summary\s*$", line, re.IGNORECASE):
                ts_obj, i2 = self._parse_trade_summary_section(all_lines, i)
                if ts_obj:
                    # Only add the key when section truly exists
                    result["trade_summary"] = {
                        "totals": ts_obj.get("totals"),
                        "line_items": ts_obj.get("line_items"),
                    }
                    if ts_obj.get("_span"):
                        result["_skip_spans"].append(ts_obj["_span"])
                i = i2
                continue

            # Recap of Taxes, Overhead and Profit
            if re.match(RECAP_TAX_OP_HDR, line):
                result["recap_tax_op"], i = self._parse_recap_tax_op_section(all_lines, i)
                continue

            # >>> Tolerant header detection (search, not match)
            if re.search(r"\bRecap\s+by\s+Room\b", line, re.IGNORECASE):
                room_obj, i2 = self._parse_recap_by_room_section(all_lines, i)
                # adopt new structure + record skip span
                result["recap_by_room"]["areas"] = room_obj.get("areas", {})
                result["recap_by_room"]["subtotals"] = room_obj.get("subtotals", [])
                if room_obj.get("_span"):
                    result["_skip_spans"].append(room_obj["_span"])
                i = i2
                continue

            if re.search(r"\bRecap\s+by\s+Category\b", line, re.IGNORECASE):
                rbc, i2 = self._parse_recap_by_category_section(all_lines, i)
                for k, v in rbc.items():
                    if k == "subtotals":
                        result["recap_by_category"]["subtotals"].extend(v)
                    else:
                        if isinstance(v, list):
                            result["recap_by_category"].setdefault(k, []).extend(v)
                        else:
                            result["recap_by_category"][k] = v
                # best-effort span detection for category section as well
                cat_hdr = re.compile(r"^\s*Recap\s+by\s+Category\s*$", re.IGNORECASE)
                cat_stop = [
                    re.compile(r"^\s*Recap\s+by\s+Room\s*$", re.IGNORECASE),
                    re.compile(r"^\s*Recap\s+of\s+Taxes,\s+Overhead\s+and\s+Profit\s*$", re.IGNORECASE),
                    re.compile(r"^\s*Summary\s+for\s+", re.IGNORECASE),
                    re.compile(r"^\s*Grand\s+Total\s+Areas\b", re.IGNORECASE),
                ]
                s0, s1 = self._find_section_bounds(all_lines, cat_hdr, cat_stop, start_hint=i)
                if s0 != -1:
                    result["_skip_spans"].append((s0, s1))
                i = i2
                continue

            i += 1

        # If trade summary key was never set (no section found), nothing to remove.
        # If it was set but empty (shouldn't happen with parser guard), prune it just in case.
        if "trade_summary" in result:
            ts = result["trade_summary"]
            if not ts or (not ts.get("line_items") and not ts.get("totals")):
                del result["trade_summary"]

        return result


    # find section bounds used by recap-by-room
    def _find_section_bounds(self, all_lines: List[str],
                         header_re: re.Pattern,
                         stop_res: List[re.Pattern],
                         start_hint: int = 0) -> Tuple[int, int]:
        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").replace("\u00A0", " ").strip())

        n = len(all_lines)
        header_idx = -1

        for idx in range(start_hint, n):
            if header_re.search(norm(all_lines[idx] or "")):
                header_idx = idx
                break
        if header_idx == -1:
            for idx in range(0, start_hint):
                if header_re.search(norm(all_lines[idx] or "")):
                    header_idx = idx
                    break
        if header_idx == -1:
            return -1, -1

        j = header_idx + 1
        while j < n and header_re.search(norm(all_lines[j] or "")):
            j += 1
        start = j

        end = n
        for k in range(start, n):
            s = norm(all_lines[k] or "")
            for pat in stop_res:
                if pat.search(s):
                    end = k
                    return start, end
        return start, end

    # ----- validations with new layout -----
    def _validate_doc(self, end: dict, sections: List[dict]) -> dict:
        v: Dict[str, Optional[str]] = {}

        sum_sections = _round2(sum(_money_to_float(li.get('total'))
                                   for sec in sections
                                   for li in sec.get('line_items', [])
                                   if li.get('type') == 'line_item' and li.get('total')))
        v['sum_sections'] = format_dollar_amount(sum_sections)

        grand_end = None
        if end.get('line_item_totals'):
            grand_end = _money_to_float(end['line_item_totals']['grand_total'])
        elif end.get('coverage', {}).get('totals'):
            grand_end = _money_to_float(end['coverage']['totals']['item_total'])
        if grand_end is not None:
            grand_end = _round2(grand_end)
            v['end_grand_total'] = format_dollar_amount(grand_end)
            v['grand_total_vs_sections_delta'] = format_dollar_amount(_round2(grand_end - sum_sections))

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

        rbc_subtotals = (end.get('recap_by_category') or {}).get('subtotals') or []
        rbc_total_val = None
        for row in rbc_subtotals:
            if row.get('label') == 'Total':
                rbc_total_val = row.get('total')
                break
        if rbc_total_val and grand_end is not None:
            rbc_val = _round2(_money_to_float(rbc_total_val))
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
