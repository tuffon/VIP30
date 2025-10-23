"""Reusable helpers for the Xactimate rough draft parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pdfplumber

from .constants import (
    BRACKETS_PATTERN,
    CALC_LINE_DETECTION_PATTERN,
    CALC_PREFIX_PATTERN,
    HEADER_VARIANTS,
    DOOR_PATTERN,
    LINE_ITEM_HEADER_PATTERN,
    LINE_ITEM_PATTERN,
    METADATA_PATTERNS,
    MISSING_WALL_PATTERN,
    PAGE_NUMBER_PATTERN,
    QUOTE_PATTERN,
    REPEATED_CHAR_PATTERN,
    SECTION_HEIGHT_PATTERN,
    SECTION_NAME_EXTRACTION,
    SEE_PATTERN,
    SINGLE_PAGE_NUMBER_PATTERN,
    SUBROOM_PATTERN,
    TABLE_HEADER_CONTINUATION,
    TERMINAL_STATUS_PATTERN,
    TOTALS_PATTERN,
)


@dataclass
class TableColumns:
    family: Optional[str] = None
    headers_norm: List[str] = field(default_factory=list)
    has_reset: bool = False
    has_tax: bool = False
    has_op: bool = False

    def __repr__(self) -> str:  # pragma: no cover - repr for debugging convenience
        cols = []
        if self.has_reset:
            cols.append("RESET")
        if self.has_tax:
            cols.append("TAX")
        if self.has_op:
            cols.append("O&P")
        fam = f"family={self.family}" if self.family else "family=?"
        hdrs = f"headers={self.headers_norm}" if self.headers_norm else "headers=[]"
        extras = ', '.join(cols) if cols else 'base only'
        return f"TableColumns({fam}, {hdrs}, {extras})"


def normalize_header_label(s: str) -> Optional[str]:
    def norm(val: Optional[str]) -> str:
        return re.sub(r'[\s\.&/]+', ' ', (val or '').upper()).strip()

    t = norm(s)
    if not t:
        return None
    for canon, variants in HEADER_VARIANTS.items():
        for variant in variants:
            if t == norm(variant):
                return canon
    return None


class ParseState(Enum):
    LOOKING_FOR_SECTION = 1
    IN_SECTION_METADATA = 2
    IN_SUBROOM_METADATA = 3
    IN_LINE_ITEMS = 4


# ---- formatting helpers -------------------------------------------------

def money_to_float(value: str) -> float:
    if not value:
        return 0.0
    return float(str(value).replace(',', ''))


def format_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def round2(value: float) -> float:
    return round(value + 1e-7, 2)


def format_dollar_amount(value: float) -> str:
    return f"{value:,.2f}"


def parse_datetime_string(date_str: str) -> Optional[str]:
    if not date_str:
        return None
    for fmt in ('%m/%d/%Y %I:%M %p', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).isoformat()
        except ValueError:
            continue
    return date_str


def parse_item_codes(codes_str: Optional[str]) -> List[str]:
    if not codes_str:
        return []
    codes: List[str] = []
    cs = codes_str.strip()
    two = {'RP', 'NR', 'CI', 'MO', 'ST', 'RS', 'CW', 'SE', 'SC'}
    i = 0
    while i < len(cs):
        if cs[i].isspace():
            i += 1
            continue
        if i + 1 < len(cs) and cs[i:i + 2].upper() in two:
            codes.append(cs[i:i + 2].upper())
            i += 2
            continue
        if cs[i].upper() in '*DEFHMNRS':
            codes.append(cs[i].upper())
        i += 1
    return codes


# ---- heuristics ---------------------------------------------------------

def is_diagram_artifact(line: str) -> bool:
    if re.search(REPEATED_CHAR_PATTERN, line):
        return True
    if line in {'Door', 'Window', 'Wall'}:
        return True
    if len(line) < 15 and re.search(QUOTE_PATTERN, line):
        return True
    special = sum(1 for c in line if c in '\"\'.-_|/\\')
    return len(line) > 0 and special / len(line) > 0.4


def is_page_header(line: str, header_patterns: List[str]) -> bool:
    if re.match(SINGLE_PAGE_NUMBER_PATTERN, line):
        return True
    if re.match(PAGE_NUMBER_PATTERN, line):
        return True
    return bool(header_patterns and line in header_patterns)


def detect_page_header_pattern(pdf_path: str) -> List[str]:
    header_lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 2:
            return header_lines
        p1 = [l.strip() for l in (pdf.pages[0].extract_text() or '').split('\n') if l.strip()]
        p2 = [l.strip() for l in (pdf.pages[1].extract_text() or '').split('\n') if l.strip()]
        for line in p1[:10]:
            if line in p2[:10]:
                header_lines.append(line)
        for line in p1[:15]:
            if re.match(PAGE_NUMBER_PATTERN, line):
                header_lines.append('PAGE_NUMBER_PATTERN')
                break
    return header_lines


def is_table_header(line: str, next_line: Optional[str]) -> Tuple[bool, TableColumns, bool]:
    def extract_tokens(raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        stripped = raw.strip()
        if not stripped:
            return []
        chunks = [c.strip() for c in re.split(r'\s{2,}|\t+', stripped) if c.strip()]
        tokens: List[str] = []
        for chunk in chunks:
            norm = normalize_header_label(chunk)
            if norm:
                tokens.append(norm)
        if tokens:
            return tokens
        words = [w for w in stripped.split() if w]
        i, n = 0, len(words)
        while i < n:
            single = normalize_header_label(words[i])
            if single:
                tokens.append(single)
                i += 1
                continue
            matched = False
            for j in range(n, i, -1):
                candidate = ' '.join(words[i:j])
                norm = normalize_header_label(candidate)
                if norm:
                    tokens.append(norm)
                    i = j
                    matched = True
                    break
            if not matched:
                i += 1
        return tokens

    top_tokens = extract_tokens(line)
    bottom_tokens = extract_tokens(next_line)

    layout_b_required = {"CAT", "SEL", "ACT", "DESCRIPTION"}
    bottom_allowed = {"CALC", "QTY", "RESET", "REMOVE", "REPLACE", "TAX", "O&P", "TOTAL"}
    if layout_b_required.issubset(set(top_tokens)) and bottom_tokens and all(t in bottom_allowed for t in bottom_tokens):
        cols = TableColumns(
            family='B',
            headers_norm=top_tokens + bottom_tokens,
            has_reset='RESET' in bottom_tokens,
            has_tax='TAX' in bottom_tokens,
            has_op='O&P' in bottom_tokens,
        )
        return True, cols, True

    layout_a_candidates = {"DESCRIPTION", "QUANTITY", "UNIT", "PRICE", "TAX", "RCV"}
    top_filtered = [t for t in top_tokens if t in layout_a_candidates]
    if len(top_filtered) >= 4 and "DESCRIPTION" in top_filtered and "RCV" in top_filtered:
        cols = TableColumns(
            family='A',
            headers_norm=top_filtered,
            has_reset=False,
            has_tax='TAX' in top_filtered,
            has_op=False,
        )
        return True, cols, False

    return False, TableColumns(), False


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
    if not re.match(TOTALS_PATTERN, line):
        return False
    if section_name and section_name.lower() in line.lower():
        return True
    return len(re.findall(r'[\d,]+\.\d{2}', line)) >= 2


# ---- metadata helpers ---------------------------------------------------

def extract_metadata_from_line(line: str) -> Dict[str, object]:
    md: Dict[str, object] = {}
    areas: Dict[str, str] = {}
    for key, pat in METADATA_PATTERNS.items():
        m = re.search(pat, line)
        if m:
            areas[key] = format_dollar_amount(money_to_float(m.group(1)))
    if areas:
        md['areas'] = areas

    doors = [
        {'dimensions': m.group(1).strip(), 'opens_into': m.group(2).strip()}
        for m in re.finditer(DOOR_PATTERN, line, re.IGNORECASE)
    ]
    if doors:
        md['doors'] = doors

    walls = [
        {'dimensions': m.group(1).strip(), 'opens_into': m.group(2).strip()}
        for m in re.finditer(MISSING_WALL_PATTERN, line, re.IGNORECASE)
    ]
    if walls:
        md['missing_walls'] = walls

    return md


def merge_metadata(base: Dict[str, object], new: Dict[str, object]) -> Dict[str, object]:
    for k, v in new.items():
        if k == 'areas':
            base.setdefault('areas', {}).update(v)
        elif k in ('doors', 'missing_walls'):
            base.setdefault(k, []).extend(v)
        else:
            base[k] = v
    return base


__all__ = [
    'TableColumns',
    'ParseState',
    'money_to_float',
    'format_money',
    'format_dollar_amount',
    'round2',
    'parse_datetime_string',
    'parse_item_codes',
    'is_diagram_artifact',
    'is_page_header',
    'detect_page_header_pattern',
    'is_table_header',
    'is_table_continuation',
    'is_subroom_header',
    'is_line_item',
    'is_line_item_header',
    'is_totals_line',
    'extract_metadata_from_line',
    'merge_metadata',
]
