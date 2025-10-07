#!/usr/bin/env python3
"""
Section Parser - Structural state machine parser for estimate documents
Refactored: debug logs removed, regex constants centralized, safe cleanups only.
"""

import os
import sys
import json
import re
import pdfplumber
from enum import Enum
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple


# ============================================================================
# REGEX PATTERNS - Global Constants
# ============================================================================

# Page header patterns
PAGE_NUMBER_PATTERN = r'.*\d+/\d+/\d+\s+Page:\s*\d+'
SINGLE_PAGE_NUMBER_PATTERN = r'^\d{1,3}$'

# Section and room patterns
SECTION_HEIGHT_PATTERN = r'^(.+?)\s+Height:\s*(.+)'
SECTION_NAME_EXTRACTION = r'([A-Z][A-Za-z\s\.\(\)/]+(?:\s+\d+)?)\s*$'
SUBROOM_PATTERN = r'^Subroom:\s+(.+?)\s+Height:\s*(.+)'

# Table header patterns
TABLE_HEADER_PRIMARY = r'CAT\s+SEL\s+ACT\s+DESCRIPTION'
TABLE_HEADER_CONTINUATION = r'^CONTINUED\s*-\s*.+'
TABLE_HEADER_SECOND_LINE_FRAGMENT = r'CALC\s+QTY'

# Line item patterns
LINE_ITEM_PATTERN = r'^(\d+)\.\s+([A-Z]{3,})\s+([A-Z0-9<>+\-/]+)\s+(\S)\s+(.*)$'
LINE_ITEM_HEADER_PATTERN = r'^([-*=~_]{2,})\s*(.+?)\s*([-*=~_]{2,})\s*:?\s*$'

# Calculation line patterns
CALC_PREFIX_PATTERN = r'(?:([0-9*+\-./\s]+?)\s+)?'
CALC_LINE_DETECTION_PATTERN = r'[0-9.]+\s*[A-Z]{2,}\s*(?:\[[^\]]+\]|\bSEE\b|[0-9,]+\.[0-9]+)'
QTY_UNIT_PATTERN = r'([0-9]+(?:\.[0-9]+)?)\s*([A-Z]{2,})\s*'
BRACKETS_PATTERN = r'(?:\[([^\]]+)\])?\s*'
CURRENCY_PATTERN = r'([0-9,]+\.[0-9]+)'
SEE_PATTERN = r'(?:SEE|SEE:)\s+([A-Z0-9][A-Z0-9._/\- ]+?)\s*$'

# Terminal status fallback
TERMINAL_STATUS_PATTERN = r'\b([A-Z0-9]+(?:[._/\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+(?:[._/\-][A-Z0-9]+)*)*)\s*$'

# Metadata extraction patterns
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

# Totals pattern
TOTALS_PATTERN = r'^Totals?:'

# Case metadata patterns
CASE_LINE1_PATTERN = r'Claim\s+Number:\s*(\S*)\s+Policy\s+Number:\s*(\S*)\s+Type\s+of\s+Loss:\s*([^\n]*)'
COVERAGE_SECTION_PATTERN = r'Coverage\s+Deductible\s+Policy\s+Limit\s*\n((?:.*?\$[\d,]+\.[\d]{2}.*?\n?)+)'
COVERAGE_ROW_PATTERN = r'^\s*([A-Za-z\s,&\-]+?)\s+\$?([\d,]+\.[\d]{2})\s+\$?([\d,]+\.[\d]{2})'
PROPERTY_ADDRESS_PATTERN = r'Property:\s*(.+?)(?=\n[A-Za-z\s]+:|\Z)'
DATE_LINE1_PATTERN = r'Date\s+of\s+Loss:\s*([^\n]*?)\s*Date\s+Received:\s*([^\n]*?)(?=\n|$)'
DATE_LINE2_PATTERN = r'Date\s+Inspected:\s*([^\n]*?)\s*Date\s+Entered:\s*([^\n]+?)(?=\n|$)'
PRICE_LIST_PATTERN = r'Price\s+List:\s*([^\s]+)\s+Depreciate\s+Material:\s*(Yes|No)\s+Depreciate\s+O&P:\s*(Yes|No)'
DEPREC_LINE2_PATTERN = r'(?:.*?\s+)?Depreciate\s+Non-material:\s*(Yes|No)\s+Depreciate\s+Taxes:\s*(Yes|No)'
ESTIMATE_LINE_PATTERN = r'Estimate:\s*([^\s]+)\s+Depreciate\s+Removal:\s*(Yes|No)'

# Diagram artifact detection
REPEATED_CHAR_PATTERN = r'([A-Z])\1{2,}'
QUOTE_PATTERN = r'[\"\']{2,}'


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class TableColumns:
    """Configuration for which columns are present in the line items table"""
    has_reset: bool = False
    has_tax: bool = False
    has_op: bool = False
    
    def __repr__(self):
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


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def parse_datetime_string(date_str: str) -> Optional[str]:
    """Parse date string to ISO format."""
    if not date_str:
        return None
    for fmt in ('%m/%d/%Y %I:%M %p', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).isoformat()
        except ValueError:
            continue
    return date_str  # fallback to original text if unparsable


def format_dollar_amount(value: float) -> str:
    """Format a dollar amount as a string with 2 decimal places."""
    return f"{value:,.2f}"


def parse_height(height_str: str) -> str:
    """Parse height string - keep original format."""
    return height_str.strip()


# ============================================================================
# PAGE HEADER DETECTION
# ============================================================================

def detect_page_header_pattern(pdf_path: str) -> List[str]:
    """Detect repeating header lines from the first two pages."""
    header_lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 2:
            return header_lines
        page1_lines = [l.strip() for l in (pdf.pages[0].extract_text() or "").split('\n') if l.strip()]
        page2_lines = [l.strip() for l in (pdf.pages[1].extract_text() or "").split('\n') if l.strip()]
        for line in page1_lines[:10]:
            if line in page2_lines[:10]:
                header_lines.append(line)
        for line in page1_lines[:15]:
            if re.match(PAGE_NUMBER_PATTERN, line):
                header_lines.append('PAGE_NUMBER_PATTERN')
                break
    return header_lines


def is_page_header(line: str, header_patterns: List[str]) -> bool:
    """Check if line matches detected header patterns."""
    if re.match(SINGLE_PAGE_NUMBER_PATTERN, line):
        return True
    if re.match(PAGE_NUMBER_PATTERN, line):
        return True
    if header_patterns and line in header_patterns:
        return True
    return False


def parse_item_codes(codes_str: Optional[str]) -> List[str]:
    """
    Parse abbreviated codes from bracket content.
    Codes can be single char (*, D, E, F, H, M, N, R, S) or
    two char (RP, NR, CI, MO, ST, RS, CW, SE, SC).
    """
    if not codes_str:
        return []
    codes: List[str] = []
    codes_str = codes_str.strip()
    two_char_codes = {'RP', 'NR', 'CI', 'MO', 'ST', 'RS', 'CW', 'SE', 'SC'}
    i = 0
    while i < len(codes_str):
        if codes_str[i].isspace():
            i += 1
            continue
        if i + 1 < len(codes_str):
            two_char = codes_str[i:i+2].upper()
            if two_char in two_char_codes:
                codes.append(two_char)
                i += 2
                continue
        if codes_str[i].upper() in '*DEFHMNRS':
            codes.append(codes_str[i].upper())
        i += 1
    return codes


# ============================================================================
# DIAGRAM ARTIFACT DETECTION
# ============================================================================

def is_diagram_artifact(line: str) -> bool:
    """Check if line is a diagram label or artifact that should be skipped."""
    if re.search(REPEATED_CHAR_PATTERN, line):
        return True
    if line in {'Door', 'Window', 'Wall'}:
        return True
    if len(line) < 15 and re.search(QUOTE_PATTERN, line):
        return True
    special_char_count = sum(1 for c in line if c in '\"\'.-_|/\\')
    if len(line) > 0 and special_char_count / len(line) > 0.4:
        return True
    return False


# ============================================================================
# TABLE HEADER DETECTION
# ============================================================================

def is_table_header(line: str, next_line: Optional[str] = None) -> Tuple[bool, TableColumns, bool]:
    """
    Check if line is the line items table header (may span 2 lines).
    Returns: (is_header, TableColumns, is_two_line_header)
    """
    if not re.match(TABLE_HEADER_PRIMARY, line):
        return False, TableColumns(), False

    combined = f"{line} {next_line}" if next_line else line
    columns = TableColumns()
    columns.has_reset = 'RESET' in combined
    columns.has_tax = 'TAX' in combined
    columns.has_op = 'O&P' in combined or 'O & P' in combined

    is_two_line_header = bool(next_line and re.search(TABLE_HEADER_SECOND_LINE_FRAGMENT, next_line))
    return True, columns, is_two_line_header


def is_table_continuation(line: str) -> bool:
    """Check if line indicates a table continuation on new page."""
    return bool(re.match(TABLE_HEADER_CONTINUATION, line, re.IGNORECASE))


# ============================================================================
# SECTION AND SUBROOM DETECTION
# ============================================================================

def is_subroom_header(line: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Check if line is a subroom header."""
    match = re.match(SUBROOM_PATTERN, line, re.IGNORECASE)
    if match:
        return True, match.group(1).strip(), match.group(2).strip()
    return False, None, None


# ============================================================================
# LINE ITEM DETECTION
# ============================================================================

def is_line_item(line: str) -> bool:
    """Check if line is a line item."""
    return bool(re.match(LINE_ITEM_PATTERN, line))


def is_line_item_header(line: str) -> Tuple[bool, Optional[str]]:
    """
    Check if line is a line item header with delimiters.
    Returns (is_header, header_text)
    """
    match = re.match(LINE_ITEM_HEADER_PATTERN, line)
    if match:
        header_text = match.group(2).strip().rstrip(':')
        return True, header_text
    return False, None


def is_totals_line(line: str, section_name: Optional[str] = None) -> bool:
    """
    Check if line is a totals line.
    To avoid false positives from notes containing "Total:", verify either:
    1. The section name appears in the line, OR
    2. The line has multiple currency values (indicating it's a real totals line)
    """
    if not re.match(TOTALS_PATTERN, line):
        return False
    if section_name and section_name.lower() in line.lower():
        return True
    currency_matches = re.findall(r'[\d,]+\.\d{2}', line)
    return len(currency_matches) >= 2


# ============================================================================
# LINE ITEM CALCULATION PARSING
# ============================================================================

def parse_line_item_calc(calc_line: str, columns: TableColumns) -> dict:
    """
    Parse calculation line for line item with dynamic column detection.
    Supports:
      1) Priced lines with RESET: RESET REMOVE + REPLACE = [TAX] [O&P] TOTAL
      2) Priced lines without RESET: REMOVE + REPLACE = [TAX] [O&P] TOTAL
      3) Price-less directive lines: QTY UNIT SEE X3.BUILD -> total=0.00, total_note
      4) Generic terminal-status fallback
    Also captures abbreviated item codes in brackets after quantity (e.g., [*F]).
    """
    # 1) Explicit SEE handler
    see_pattern = (
        CALC_PREFIX_PATTERN +
        QTY_UNIT_PATTERN +
        BRACKETS_PATTERN +
        SEE_PATTERN
    )
    see_match = re.search(see_pattern, calc_line, re.IGNORECASE)
    if see_match:
        codes_str = see_match.group(4) or ''
        return {
            'calc': (see_match.group(1) or '').strip(),
            'qty': float(see_match.group(2)),
            'unit': see_match.group(3).upper(),
            'item_codes': parse_item_codes(codes_str),
            'reset': None,
            'remove': None,
            'replace': None,
            'tax': None,
            'op': None,
            'total': '0.00',
            'total_note': 'SEE ' + see_match.group(5).strip().upper()
        }

    # 2) Priced formats
    base_pattern = CALC_PREFIX_PATTERN + QTY_UNIT_PATTERN + BRACKETS_PATTERN

    def build_tail(has_tax: bool, has_op: bool) -> str:
        if has_tax and has_op:
            return CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        if has_tax:
            return CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        if has_op:
            return CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        return r'(?:' + CURRENCY_PATTERN + r'\s+)*' + CURRENCY_PATTERN + r'\s*$'

    if columns.has_reset:
        # Format A: RESET REMOVE + REPLACE = [TAX] [O&P] TOTAL
        full_pattern_a = (
            base_pattern +
            CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*' +
            build_tail(columns.has_tax, columns.has_op)
        )
        match = re.search(full_pattern_a, calc_line)
        if match:
            groups = match.groups()
            idx = 0
            codes_str = groups[3] or ''
            result = {
                'calc': (groups[idx] or '').strip(),
                'qty': float(groups[idx + 1]),
                'unit': groups[idx + 2],
                'item_codes': parse_item_codes(codes_str),
            }
            idx += 4
            result['reset'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            result['remove'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            result['replace'] = format_dollar_amount(float(groups[idx + 2].replace(',', '')))
            idx += 3
            if columns.has_tax and columns.has_op:
                result['tax'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['op'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
                result['total'] = format_dollar_amount(float(groups[idx + 2].replace(',', '')))
            elif columns.has_tax:
                result['tax'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['op'] = None
                result['total'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            elif columns.has_op:
                result['tax'] = None
                result['op'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['total'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            else:
                result['tax'] = None
                result['op'] = None
                result['total'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            return result

        # Format B: (no RESET value on this row) REMOVE + REPLACE =
        full_pattern_b = (
            base_pattern +
            CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*' +
            build_tail(columns.has_tax, columns.has_op)
        )
        match = re.search(full_pattern_b, calc_line)
        if match:
            groups = match.groups()
            idx = 0
            codes_str = groups[3] or ''
            result = {
                'calc': (groups[idx] or '').strip(),
                'qty': float(groups[idx + 1]),
                'unit': groups[idx + 2],
                'item_codes': parse_item_codes(codes_str),
                'reset': None,
            }
            idx += 4
            result['remove'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            result['replace'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            idx += 2
            if columns.has_tax and columns.has_op:
                result['tax'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['op'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
                result['total'] = format_dollar_amount(float(groups[idx + 2].replace(',', '')))
            elif columns.has_tax:
                result['tax'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['op'] = None
                result['total'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            elif columns.has_op:
                result['tax'] = None
                result['op'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['total'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            else:
                result['tax'] = None
                result['op'] = None
                result['total'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            return result
    else:
        # No RESET column: standard REMOVE + REPLACE =
        full_pattern = (
            base_pattern +
            CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*' +
            build_tail(columns.has_tax, columns.has_op)
        )
        match = re.search(full_pattern, calc_line)
        if match:
            groups = match.groups()
            idx = 0
            codes_str = groups[3] or ''
            result = {
                'calc': (groups[idx] or '').strip(),
                'qty': float(groups[idx + 1]),
                'unit': groups[idx + 2],
                'item_codes': parse_item_codes(codes_str),
                'reset': None,
            }
            idx += 4
            result['remove'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            result['replace'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            idx += 2
            if columns.has_tax and columns.has_op:
                result['tax'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['op'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
                result['total'] = format_dollar_amount(float(groups[idx + 2].replace(',', '')))
            elif columns.has_tax:
                result['tax'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['op'] = None
                result['total'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            elif columns.has_op:
                result['tax'] = None
                result['op'] = format_dollar_amount(float(groups[idx].replace(',', '')))
                result['total'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            else:
                result['tax'] = None
                result['op'] = None
                result['total'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            return result

    # 3) Terminal status fallback
    terminal_status_match = re.search(TERMINAL_STATUS_PATTERN, calc_line, re.IGNORECASE)
    qty_unit_base = CALC_PREFIX_PATTERN + QTY_UNIT_PATTERN + BRACKETS_PATTERN
    if terminal_status_match:
        terminal_status = terminal_status_match.group(1).strip()
        if re.search(qty_unit_base + re.escape(terminal_status) + r'\s*$', calc_line, re.IGNORECASE):
            match2 = re.search(
                qty_unit_base +
                r'([A-Z0-9]+(?:[._/\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+(?:[._/\-][A-Z0-9]+)*)*)\s*$',
                calc_line,
                re.IGNORECASE
            )
            if match2:
                codes_str = match2.group(4) or ''
                note_text = match2.group(5).strip().upper()
                if 'SEE' in calc_line.upper() and not note_text.startswith('SEE'):
                    note_text = 'SEE ' + note_text
                return {
                    'calc': (match2.group(1) or '').strip(),
                    'qty': float(match2.group(2)),
                    'unit': match2.group(3),
                    'item_codes': parse_item_codes(codes_str),
                    'reset': None,
                    'remove': None,
                    'replace': None,
                    'tax': None,
                    'op': None,
                    'total': '0.00',
                    'total_note': note_text
                }
    return {}


# ============================================================================
# TOTALS PARSING
# ============================================================================

def parse_totals(totals_line: str, columns: TableColumns) -> dict:
    """
    Parse totals line with dynamic column detection. Supports 'Total:' and 'Totals:'.
    Note: Totals never include RESET values - only TAX, O&P, and TOTAL.
    """
    if columns.has_tax and columns.has_op:
        match = re.search(
            r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$',
            totals_line,
            re.IGNORECASE
        )
        if match:
            return {
                'tax': format_dollar_amount(float(match.group(1).replace(',', ''))),
                'op': format_dollar_amount(float(match.group(2).replace(',', ''))),
                'total': format_dollar_amount(float(match.group(3).replace(',', '')))
            }
    elif columns.has_tax:
        match = re.search(
            r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$',
            totals_line,
            re.IGNORECASE
        )
        if match:
            return {
                'tax': format_dollar_amount(float(match.group(1).replace(',', ''))),
                'op': None,
                'total': format_dollar_amount(float(match.group(2).replace(',', '')))
            }
    elif columns.has_op:
        match = re.search(
            r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$',
            totals_line,
            re.IGNORECASE
        )
        if match:
            return {
                'tax': None,
                'op': format_dollar_amount(float(match.group(1).replace(',', ''))),
                'total': format_dollar_amount(float(match.group(2).replace(',', '')))
            }
    else:
        match = re.search(
            r'Totals?:.*?([\d,]+\.\d+)\s*$',
            totals_line,
            re.IGNORECASE
        )
        if match:
            return {
                'tax': None,
                'op': None,
                'total': format_dollar_amount(float(match.group(1).replace(',', '')))
            }

    # Fallback inference
    nums = re.findall(r'[\d,]+\.\d+', totals_line)
    if nums:
        amounts = [format_dollar_amount(float(n.replace(',', ''))) for n in nums]
        n = len(amounts)
        result = {'tax': None, 'op': None, 'total': '0.00'}
        if n >= 1:
            result['total'] = amounts[-1]
        if columns.has_op and n >= 2:
            result['op'] = amounts[-2]
        if columns.has_tax and n >= (3 if columns.has_op else 2):
            idx = -3 if columns.has_op else -2
            result['tax'] = amounts[idx]
        return result

    return {'tax': None, 'op': None, 'total': '0.00'}


# ============================================================================
# METADATA EXTRACTION
# ============================================================================

def extract_metadata_from_line(line: str) -> dict:
    """Extract all metadata fields from a single line."""
    metadata: Dict[str, object] = {}

    areas: Dict[str, str] = {}
    for key, pattern in METADATA_PATTERNS.items():
        match = re.search(pattern, line)
        if match:
            areas[key] = format_dollar_amount(float(match.group(1).replace(',', '')))
    if areas:
        metadata['areas'] = areas

    doors = []
    for match in re.finditer(DOOR_PATTERN, line, re.IGNORECASE):
        doors.append({
            'dimensions': match.group(1).strip(),
            'opens_into': match.group(2).strip()
        })
    if doors:
        metadata['doors'] = doors

    walls = []
    for match in re.finditer(MISSING_WALL_PATTERN, line, re.IGNORECASE):
        walls.append({
            'dimensions': match.group(1).strip(),
            'opens_into': match.group(2).strip()
        })
    if walls:
        metadata['missing_walls'] = walls

    return metadata


def merge_metadata(base: dict, new: dict) -> dict:
    """Merge new metadata into base metadata."""
    for key, value in new.items():
        if key == 'areas':
            base.setdefault('areas', {}).update(value)
        elif key == 'doors':
            base.setdefault('doors', []).extend(value)
        elif key == 'missing_walls':
            base.setdefault('missing_walls', []).extend(value)
        else:
            base[key] = value
    return base


# ============================================================================
# DOCUMENT PARSING
# ============================================================================

def parse_document(pdf_path: str) -> tuple:
    """Parse entire document using state machine."""
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
            if is_diagram_artifact(line):
                i += 1
                continue

            if 'Height:' in line and 'Subroom:' not in line:
                match = re.match(SECTION_HEIGHT_PATTERN, line)
                if match:
                    raw_section_name = match.group(1).strip()
                    height = match.group(2).strip()
                    section_name_match = re.search(SECTION_NAME_EXTRACTION, raw_section_name)
                    section_name = section_name_match.group(1).strip() if section_name_match else raw_section_name
                    current_section = {
                        'section_name': section_name,
                        'metadata': {'height': parse_height(height)},
                        'subrooms': [],
                        'line_items': [],
                        'section_totals': {}
                    }
                    state = ParseState.IN_SECTION_METADATA
                    i += 1
                    continue

            is_header, detected_columns, is_two_line = is_table_header(line, next_line)
            if is_header:
                section_name = "Unknown Section"
                if i > 0 and not is_page_header(lines[i - 1], header_patterns):
                    section_name = lines[i - 1].strip()
                    name_match = re.search(SECTION_NAME_EXTRACTION, section_name)
                    if name_match:
                        section_name = name_match.group(1).strip()

                current_section = {
                    'section_name': section_name,
                    'metadata': {},
                    'subrooms': [],
                    'line_items': [],
                    'section_totals': {}
                }
                columns = detected_columns
                state = ParseState.IN_LINE_ITEMS
                i += 2 if is_two_line else 1
                continue

            i += 1
            continue

        elif state == ParseState.IN_SECTION_METADATA:
            is_sub, sub_name, sub_height = is_subroom_header(line)
            if is_sub:
                current_subroom = {
                    'subroom_name': sub_name,
                    'metadata': {'height': parse_height(sub_height)}
                }
                state = ParseState.IN_SUBROOM_METADATA
                i += 1
                continue

            is_header, detected_columns, is_two_line = is_table_header(line, next_line)
            if is_header:
                columns = detected_columns
                state = ParseState.IN_LINE_ITEMS
                i += 2 if is_two_line else 1
                continue

            meta = extract_metadata_from_line(line)
            if meta:
                current_section['metadata'] = merge_metadata(current_section['metadata'], meta)

            i += 1
            continue

        elif state == ParseState.IN_SUBROOM_METADATA:
            is_sub, sub_name, sub_height = is_subroom_header(line)
            if is_sub:
                current_section['subrooms'].append(current_subroom)
                current_subroom = {
                    'subroom_name': sub_name,
                    'metadata': {'height': parse_height(sub_height)}
                }
                i += 1
                continue

            is_header, detected_columns, is_two_line = is_table_header(line, next_line)
            if is_header:
                current_section['subrooms'].append(current_subroom)
                current_subroom = None
                columns = detected_columns
                state = ParseState.IN_LINE_ITEMS
                i += 2 if is_two_line else 1
                continue

            meta = extract_metadata_from_line(line)
            if meta and current_subroom is not None:
                current_subroom['metadata'] = merge_metadata(current_subroom['metadata'], meta)

            i += 1
            continue

        elif state == ParseState.IN_LINE_ITEMS:
            if is_table_continuation(line):
                pending_header_lines = []
                i += 1
                if i < len(lines):
                    next_line_after = lines[i + 1] if i + 1 < len(lines) else None
                    is_header, new_columns, is_two_line = is_table_header(lines[i], next_line_after)
                    if is_header:
                        columns = new_columns
                        i += 2 if is_two_line else 1
                continue

            if is_totals_line(line, current_section['section_name'] if current_section else None):
                if pending_header_lines and current_line_item:
                    note_text = ' '.join(pending_header_lines)
                    if current_line_item['notes']:
                        current_line_item['notes'] += ' ' + note_text
                    else:
                        current_line_item['notes'] = note_text
                    pending_header_lines = []

                if collecting_notes and current_line_item:
                    current_section['line_items'].append(current_line_item)
                    current_line_item = None
                    collecting_notes = False

                current_section['section_totals'] = parse_totals(line, columns)
                sections.append(current_section)
                current_section = None
                columns = TableColumns()
                state = ParseState.LOOKING_FOR_SECTION
                i += 1
                continue

            is_header_line, header_text = is_line_item_header(line)
            if is_header_line:
                if pending_header_lines and current_line_item:
                    note_text = ' '.join(pending_header_lines)
                    if current_line_item['notes']:
                        current_line_item['notes'] += ' ' + note_text
                    else:
                        current_line_item['notes'] = note_text
                    pending_header_lines = []

                if collecting_notes and current_line_item:
                    current_section['line_items'].append(current_line_item)
                    current_line_item = None
                    collecting_notes = False

                current_section['line_items'].append({
                    'type': 'header',
                    'text': header_text
                })
                i += 1
                continue

            if is_line_item(line):
                if pending_header_lines and current_line_item:
                    note_text = ' '.join(pending_header_lines)
                    if current_line_item['notes']:
                        current_line_item['notes'] += ' ' + note_text
                    else:
                        current_line_item['notes'] = note_text
                    pending_header_lines = []

                if current_line_item:
                    current_section['line_items'].append(current_line_item)
                    current_line_item = None
                    collecting_notes = False

                match = re.match(LINE_ITEM_PATTERN, line)
                if match:
                    current_line_item = {
                        'type': 'line_item',
                        'line_number': int(match.group(1)),
                        'cat': match.group(2),
                        'sel': match.group(3),
                        'act': match.group(4),
                        'description': match.group(5).strip(),
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
                i += 1
                continue

            if current_line_item and re.search(CALC_LINE_DETECTION_PATTERN, line):
                calc = parse_line_item_calc(line, columns)
                if calc:
                    current_line_item.update(calc)
                    collecting_notes = True
                    i += 1
                    continue

            if collecting_notes and current_line_item:
                pending_header_lines.append(line)
                i += 1
                continue

            i += 1
            continue

        i += 1

    return sections, lines


# ============================================================================
# CASE METADATA PARSING
# ============================================================================

def parse_case_metadata(lines: List[str]) -> dict:
    """Extract case metadata from the first ~50 lines."""
    metadata: Dict[str, object] = {}
    text = '\n'.join(lines[:50])

    # Claim / Policy / Loss Type
    line1_match = re.search(CASE_LINE1_PATTERN, text, re.IGNORECASE)
    if line1_match:
        claim = line1_match.group(1).strip()
        policy = line1_match.group(2).strip()
        loss_type = line1_match.group(3).strip()
        metadata['claim_number'] = claim or None
        metadata['policy_number'] = policy or None
        metadata['loss_type'] = loss_type if (loss_type and not loss_type.startswith('Coverage')) else None
    else:
        metadata['claim_number'] = None
        metadata['policy_number'] = None
        metadata['loss_type'] = None

    # Coverage Table
    coverage_table = []
    coverage_section = re.search(COVERAGE_SECTION_PATTERN, text, re.IGNORECASE)
    if coverage_section:
        table_rows = coverage_section.group(1).strip().split('\n')
        for row in table_rows:
            row_match = re.match(COVERAGE_ROW_PATTERN, row)
            if row_match:
                coverage_table.append({
                    'coverage_type': row_match.group(1).strip(),
                    'deductible': format_dollar_amount(float(row_match.group(2).replace(',', ''))),
                    'policy_limit': format_dollar_amount(float(row_match.group(3).replace(',', '')))
                })
    metadata['coverage'] = coverage_table or None

    # Property Address
    property_match = re.search(PROPERTY_ADDRESS_PATTERN, text, re.DOTALL)
    if property_match:
        address_text = property_match.group(1).strip()
        metadata['property_address'] = ' '.join(address_text.split()) if address_text else None
    else:
        metadata['property_address'] = None

    # Dates
    date_line1 = re.search(DATE_LINE1_PATTERN, text, re.IGNORECASE)
    if date_line1:
        dol = date_line1.group(1).strip()
        dr = date_line1.group(2).strip()
        metadata['date_of_loss'] = parse_datetime_string(dol) if (dol and re.match(r'\d+/\d+/\d+', dol)) else None
        metadata['date_received'] = parse_datetime_string(dr) if (dr and re.match(r'\d+/\d+/\d+', dr)) else None
    else:
        metadata['date_of_loss'] = None
        metadata['date_received'] = None

    date_line2 = re.search(DATE_LINE2_PATTERN, text, re.IGNORECASE)
    if date_line2:
        di = date_line2.group(1).strip()
        de = date_line2.group(2).strip()
        metadata['date_inspected'] = parse_datetime_string(di) if (di and re.match(r'\d+/\d+/\d+', di)) else None
        metadata['date_entered'] = parse_datetime_string(de) if (de and re.match(r'\d+/\d+/\d+', de)) else None
    else:
        metadata['date_inspected'] = None
        metadata['date_entered'] = None

    # Price list / depreciation flags
    price_line = re.search(PRICE_LIST_PATTERN, text, re.IGNORECASE)
    if price_line:
        metadata['price_list'] = price_line.group(1).strip()
        metadata['depreciate_material'] = (price_line.group(2).strip().upper() == 'YES')
        metadata['depreciate_op'] = (price_line.group(3).strip().upper() == 'YES')
    else:
        metadata['price_list'] = None
        metadata['depreciate_material'] = None
        metadata['depreciate_op'] = None

    deprec_line2 = re.search(DEPREC_LINE2_PATTERN, text, re.IGNORECASE)
    if deprec_line2:
        metadata['depreciate_non_material'] = (deprec_line2.group(1).strip().upper() == 'YES')
        metadata['depreciate_taxes'] = (deprec_line2.group(2).strip().upper() == 'YES')
    else:
        metadata['depreciate_non_material'] = None
        metadata['depreciate_taxes'] = None

    estimate_line = re.search(ESTIMATE_LINE_PATTERN, text, re.IGNORECASE)
    if estimate_line:
        metadata['estimate_name'] = estimate_line.group(1).strip()
        metadata['depreciate_removal'] = (estimate_line.group(2).strip().upper() == 'YES')
    else:
        metadata['estimate_name'] = None
        metadata['depreciate_removal'] = None

    # Derived fields
    if metadata.get('price_list') and str(metadata['price_list']).upper().startswith('CALA'):
        metadata['region'] = 'California'
    else:
        metadata['region'] = None
    metadata['building_type'] = None

    return metadata


# ============================================================================
# MAIN
# ============================================================================
def _money_to_float(s: str) -> float:
    if not s:
        return 0.0
    return float(str(s).replace(',', ''))

def _section_computed_total(section: dict) -> float:
    return sum(
        _money_to_float(li.get('total'))
        for li in section.get('line_items', [])
        if li.get('type') == 'line_item' and li.get('total') is not None
    )

def _round2(x: float) -> float:
    # round-to-cents to avoid float specks; "non-zero" means != 0.00 after rounding
    return round(x + 0.0000001, 2)

def _print_doc_delta_table(pdf_file: str, rows: list, total_sections: int):
    """
    rows: list of dicts with keys: name, declared, computed, delta (all floats already rounded to 2)
    """
    print(f"\n▶ Doc: {pdf_file}")
    if not rows:
        print("  - No non-zero deltas.")
        return

    # column widths
    name_w = 42
    amt_w = 14

    def fm(v: float) -> str:
        sign = "-" if v < 0 else ""
        return f"{sign}${abs(v):,.2f}"

    # header
    print("  " + f"{'Section':{name_w}}{'Declared':>{amt_w}}{'Computed':>{amt_w}}{'Δ (Declared-Computed)':>{amt_w}}")
    print("  " + "-" * (name_w + amt_w * 3))

    # rows
    for r in rows:
        print(
            "  "
            + f"{r['name'][:name_w]:{name_w}}"
            + f"{fm(r['declared']):>{amt_w}}"
            + f"{fm(r['computed']):>{amt_w}}"
            + f"{fm(r['delta']):>{amt_w}}"
        )

    print(f"  (sections with deltas: {len(rows)} / total sections: {total_sections})")

def main():
    input_dir = "documents/historical"
    output_dir = "data/historical"

    args = sys.argv[1:]
    for a in args:
        if a.startswith("--in="):
            input_dir = a.split("=", 1)[1].strip()
        elif a.startswith("--out="):
            output_dir = a.split("=", 1)[1].strip()

    if not os.path.exists(input_dir):
        print(f"Input directory not found: {input_dir}")
        return

    pdfs = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
    if not pdfs:
        print("No PDFs found.")
        return

    os.makedirs(output_dir, exist_ok=True)

    for pdf_file in sorted(pdfs):
        pdf_path = os.path.join(input_dir, pdf_file)
        base_name = os.path.splitext(pdf_file)[0]

        # Parse whole doc
        sections, all_lines = parse_document(pdf_path)

        # First-page metadata (unchanged)
        first_page_lines: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.pages:
                txt = pdf.pages[0].extract_text() or ""
                first_page_lines.extend([l.strip() for l in txt.split('\n') if l.strip()])
        case_metadata = parse_case_metadata(first_page_lines)

        # Compute/attach totals and deltas; collect ONLY non-zero (post-rounding) deltas for the table
        table_rows = []
        for section in sections:
            computed_total = _round2(_section_computed_total(section))
            declared_total_str = section.get('section_totals', {}).get('total', '0.00')
            declared_total = _round2(_money_to_float(declared_total_str))
            delta = _round2(declared_total - computed_total)

            # persist formatted values back into JSON for traceability
            section['section_totals']['computed_total'] = format_dollar_amount(computed_total)
            section['section_totals']['validation_delta'] = format_dollar_amount(delta)

            if delta != 0.0:
                table_rows.append({
                    'name': section.get('section_name', 'Unknown Section'),
                    'declared': declared_total,
                    'computed': computed_total,
                    'delta': delta
                })

        # Write raw outputs (unchanged)
        out_path = os.path.join(output_dir, f"{base_name}.out")
        json_path = os.path.join(output_dir, f"{base_name}.json")

        with open(out_path, 'w', encoding='utf-8') as f:
            for line in all_lines:
                f.write(line + '\n')

        output = {'case_metadata': case_metadata, 'sections': sections}
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        # Pretty console table summary for THIS document (only non-zero deltas)
        _print_doc_delta_table(pdf_file, table_rows, total_sections=len(sections))


if __name__ == "__main__":
    main()
