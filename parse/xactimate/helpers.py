"""Reusable helpers for the Xactimate rough draft parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pdfplumber

from .constants import (
    BRAND_PAT,
    BRACKETS_PATTERN,
    CALC_LINE_DETECTION_PATTERN,
    CALC_PREFIX_PATTERN,
    DATE_STAMP_PAT,
    DOOR_PATTERN,
    LINE_ITEM_HEADER_PATTERN,
    LINE_ITEM_PATTERN,
    METADATA_PATTERNS,
    MISSING_WALL_PATTERN,
    NO_LETTERS_PAT,
    PAGE_NUMBER_PATTERN,
    PAGE_NUM_PAT,
    QUOTE_PATTERN,
    REPEATED_CHAR_PATTERN,
    SECTION_HEIGHT_PATTERN,
    SECTION_NAME_EXTRACTION,
    SEE_PATTERN,
    SINGLE_PAGE_NUMBER_PATTERN,
    SUBROOM_PATTERN,
    TABLE_HEADER_CONTINUATION,
    TABLE_HEADER_PRIMARY,
    TABLE_HEADER_SECOND_LINE_FRAGMENT,
    TERMINAL_STATUS_PATTERN,
    TOTALS_PATTERN,
    URL_PAT,
)


@dataclass
class TableColumns:
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
        return f"TableColumns({', '.join(cols) if cols else 'base only'})"


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


def _letters_ratio(text: str) -> float:
    cleaned = (text or '').strip()
    if not cleaned:
        return 0.0
    non_space = sum(1 for c in cleaned if not c.isspace())
    if non_space == 0:
        return 0.0
    letters = sum(1 for c in cleaned if c.isalpha())
    return letters / non_space if non_space else 0.0


def is_page_footer(line: str) -> bool:
    s = (line or '').strip()
    if not s:
        return False
    if PAGE_NUM_PAT.match(s):
        return True
    if DATE_STAMP_PAT.match(s):
        return True
    if URL_PAT.search(s):
        return True
    if BRAND_PAT.search(s):
        return True
    return False


def is_page_header_line(line: str) -> bool:
    s = (line or '').strip()
    if not s:
        return False
    if is_page_footer(s):
        return True
    lowered = s.lower()
    if 'claim #' in lowered or 'policy #' in lowered:
        return True
    return bool(BRAND_PAT.search(s))


def is_page_noise(line: str) -> bool:
    s = (line or '').strip()
    if not s:
        return True
    if is_page_footer(s) or is_page_header_line(s):
        return True
    if NO_LETTERS_PAT.match(s):
        return True
    if _letters_ratio(s) <= 0.25:
        return True
    lowered = s.lower()
    if 'claim #' in lowered or 'policy #' in lowered:
        return True
    return False


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
