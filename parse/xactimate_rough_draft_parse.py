#!/usr/bin/env python3
"""
Section Parser - Structural state machine parser for estimate documents
Refactored with dynamic column detection and RESET support
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

def parse_datetime_string(date_str: str) -> str:
    """Parse date string to ISO format."""
    if not date_str:
        return None
    
    try:
        dt = datetime.strptime(date_str, '%m/%d/%Y %I:%M %p')
        return dt.isoformat()
    except ValueError:
        try:
            dt = datetime.strptime(date_str, '%m/%d/%Y')
            return dt.isoformat()
        except ValueError:
            return date_str


def format_dollar_amount(value: float) -> str:
    """Format a dollar amount as a string with 2 decimal places."""
    return f"{value:,.2f}"


def parse_height(height_str: str) -> str:
    """Parse height string - keep original format."""
    return height_str.strip()


# ============================================================================
# PAGE HEADER DETECTION
# ============================================================================

def detect_page_header_pattern(pdf_path: str) -> list:
    """Detect repeating header lines from the first two pages."""
    header_lines = []
    
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 2:
            return header_lines
        
        page1_lines = [line.strip() for line in (pdf.pages[0].extract_text() or "").split('\n') if line.strip()]
        page2_lines = [line.strip() for line in (pdf.pages[1].extract_text() or "").split('\n') if line.strip()]
        
        for line in page1_lines[:10]:
            if line in page2_lines[:10]:
                header_lines.append(line)
        
        for line in page1_lines[:15]:
            if re.match(PAGE_NUMBER_PATTERN, line):
                header_lines.append('PAGE_NUMBER_PATTERN')
                break
    
    return header_lines


def is_page_header(line: str, header_patterns: list) -> bool:
    """Check if line matches detected header patterns."""
    if re.match(SINGLE_PAGE_NUMBER_PATTERN, line):
        return True
    
    if re.match(PAGE_NUMBER_PATTERN, line):
        return True
    
    if header_patterns and line in header_patterns:
        return True
    
    return False

def parse_item_codes(codes_str: str) -> list:
    """
    Parse abbreviated codes from bracket content.
    Codes can be single char (*, D, E, F, H, M, N, R, S) or 
    two char (RP, NR, CI, MO, ST, RS, CW, SE, SC).
    """
    if not codes_str:
        return []
    
    codes = []
    codes_str = codes_str.strip()
    
    # Known two-character codes
    two_char_codes = ['RP', 'NR', 'CI', 'MO', 'ST', 'RS', 'CW', 'SE', 'SC']
    
    i = 0
    while i < len(codes_str):
        # Skip whitespace
        if codes_str[i].isspace():
            i += 1
            continue
        
        # Check for two-character code
        if i + 1 < len(codes_str):
            two_char = codes_str[i:i+2].upper()
            if two_char in two_char_codes:
                codes.append(two_char)
                i += 2
                continue
        
        # Single character code
        if codes_str[i] in '*DEFHMNRS':
            codes.append(codes_str[i])
            i += 1
        else:
            i += 1
    
    return codes

# ============================================================================
# DIAGRAM ARTIFACT DETECTION
# ============================================================================

def is_diagram_artifact(line: str) -> bool:
    """Check if line is a diagram label or artifact that should be skipped."""
    if re.search(REPEATED_CHAR_PATTERN, line):
        return True
    
    if line in ['Door', 'Window', 'Wall']:
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

def is_table_header(line: str, next_line: str = None) -> Tuple[bool, TableColumns, bool]:
    """
    Check if line is the line items table header (may span 2 lines).
    Returns: (is_header, TableColumns, is_two_line_header)
    """
    if not re.match(TABLE_HEADER_PRIMARY, line):
        return False, TableColumns(), False
    
    # Combine current and next line to check for all columns
    combined = line
    if next_line:
        combined = line + ' ' + next_line
    
    # Detect which columns are present
    columns = TableColumns()
    columns.has_reset = 'RESET' in combined
    columns.has_tax = 'TAX' in combined
    columns.has_op = 'O&P' in combined or 'O & P' in combined
    
    # Check if next line contains the second part of header
    is_two_line_header = False
    if next_line and re.search(r'CALC\s+QTY', next_line):
        is_two_line_header = True
    
    print(f"Header detected: {columns}, two_line={is_two_line_header}")
    print(f"Header line: {line}")
    if is_two_line_header:
        print(f"Header line 2: {next_line}")
    
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


def is_totals_line(line: str, section_name: str = None) -> bool:
    """
    Check if line is a totals line.
    To avoid false positives from notes containing "Total:", verify either:
    1. The section name appears in the line, OR
    2. The line has multiple currency values (indicating it's a real totals line)
    """
    if not re.match(TOTALS_PATTERN, line):
        return False
    
    # If we have a section name, verify it appears in the totals line
    if section_name:
        # Check if section name appears in the line (case-insensitive)
        if section_name.lower() in line.lower():
            return True
    
    # Otherwise, check if line has at least 2 currency values
    # (a real totals line typically has multiple amounts like tax, O&P, total)
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
    # Debug logging
    with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
        debug_file.write(f"\n{'='*80}\n")
        debug_file.write(f"calc_line: '{calc_line}'\n")
        debug_file.write(f"columns: {columns}\n")

    # ------------------------------------------------------------------------------
    # 1) Explicit SEE handler
    # ------------------------------------------------------------------------------
    see_pattern = (
        CALC_PREFIX_PATTERN +
        QTY_UNIT_PATTERN +
        BRACKETS_PATTERN +
        SEE_PATTERN
    )
    see_match = re.search(see_pattern, calc_line, re.IGNORECASE)
    if see_match:
        codes_str = see_match.group(4) or ''
        result = {
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
        with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
            debug_file.write(f"SEE pattern matched. Result: {result}\n")
        return result

    # ------------------------------------------------------------------------------
    # 2) Priced formats - Build pattern dynamically based on columns
    # ------------------------------------------------------------------------------
    base_pattern = (
        CALC_PREFIX_PATTERN +
        QTY_UNIT_PATTERN +
        BRACKETS_PATTERN
    )
    
    # When RESET column exists in header, we have TWO possible priced formats:
    # Format A: RESET REMOVE + REPLACE = (all three values present)
    # Format B: REMOVE + REPLACE = (RESET omitted entirely for this line item)
    
    if columns.has_reset:
        # Try Format A first (RESET REMOVE + REPLACE = with all values)
        pattern_a = base_pattern + CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*'
        
        # Build tail for Format A
        if columns.has_tax and columns.has_op:
            tail_pattern_a = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        elif columns.has_tax:
            tail_pattern_a = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        elif columns.has_op:
            tail_pattern_a = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        else:
            tail_pattern_a = r'(?:' + CURRENCY_PATTERN + r'\s+)*' + CURRENCY_PATTERN + r'\s*$'
        
        full_pattern_a = pattern_a + tail_pattern_a
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
            idx += 4  # Skip calc, qty, unit, item_codes
            
            # Parse RESET, REMOVE, REPLACE
            result['reset'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            result['remove'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            result['replace'] = format_dollar_amount(float(groups[idx + 2].replace(',', '')))
            idx += 3
            
            # Parse TAX and O&P based on what columns exist
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

            with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
                debug_file.write(f"RESET Format A matched (RESET REMOVE + REPLACE). Result: {result}\n")
            return result
        
        # Try Format B (RESET omitted entirely for this line item)
        # Standard pattern: REMOVE + REPLACE =
        pattern_b = base_pattern + CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*'
        
        # Build tail for Format B (same as standard format)
        if columns.has_tax and columns.has_op:
            tail_pattern_b = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        elif columns.has_tax:
            tail_pattern_b = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        elif columns.has_op:
            tail_pattern_b = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        else:
            tail_pattern_b = r'(?:' + CURRENCY_PATTERN + r'\s+)*' + CURRENCY_PATTERN + r'\s*$'
        
        full_pattern_b = pattern_b + tail_pattern_b
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
                'reset': None,  # RESET omitted for this line item
            }
            idx += 4  # Skip calc, qty, unit, item_codes
            
            # Parse REMOVE and REPLACE
            result['remove'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            result['replace'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            idx += 2
            
            # Parse TAX and O&P based on what columns exist
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

            with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
                debug_file.write(f"Format B matched (REMOVE + REPLACE, RESET omitted). Result: {result}\n")
            return result
    
    else:
        # No RESET column - standard format: REMOVE + REPLACE =
        pattern = base_pattern + CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*'
        
        # Build the tail pattern based on which columns are present
        if columns.has_tax and columns.has_op:
            tail_pattern = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        elif columns.has_tax:
            tail_pattern = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        elif columns.has_op:
            tail_pattern = CURRENCY_PATTERN + r'\s+' + CURRENCY_PATTERN + r'\s*$'
        else:
            tail_pattern = r'(?:' + CURRENCY_PATTERN + r'\s+)*' + CURRENCY_PATTERN + r'\s*$'
        
        full_pattern = pattern + tail_pattern
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
            idx += 4  # Skip calc, qty, unit, item_codes
            
            # Parse REMOVE and REPLACE
            result['remove'] = format_dollar_amount(float(groups[idx].replace(',', '')))
            result['replace'] = format_dollar_amount(float(groups[idx + 1].replace(',', '')))
            idx += 2
            
            # Parse TAX and O&P based on what columns exist
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

            with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
                debug_file.write(f"Standard format matched. Result: {result}\n")
            return result

    # ------------------------------------------------------------------------------
    # 3) Terminal status fallback
    # ------------------------------------------------------------------------------
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
                
                # Check if the line contains "SEE" before the terminal status
                note_text = match2.group(5).strip().upper()
                if 'SEE' in calc_line.upper() and not note_text.startswith('SEE'):
                    note_text = 'SEE ' + note_text
                
                result = {
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
                with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
                    debug_file.write(f"Terminal status matched. Result: {result}\n")
                return result

    with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
        debug_file.write(f"No pattern matched\n")
    return {}


# ============================================================================
# TOTALS PARSING
# ============================================================================

def parse_totals(totals_line: str, columns: TableColumns) -> dict:
    """
    Parse totals line with dynamic column detection. Supports 'Total:' and 'Totals:'.
    Note: Totals never include RESET values - only TAX, O&P, and TOTAL.
    """
    
    # Build pattern based on columns present (but NEVER include RESET in totals)
    if columns.has_tax and columns.has_op:
        # Format: Totals: TAX O&P TOTAL
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
        # Format: Totals: TAX TOTAL
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
        # Format: Totals: O&P TOTAL
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
        # Format: Totals: TOTAL
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

    # Fallback: infer from currency numbers found
    nums = re.findall(r'[\d,]+\.\d+', totals_line)
    if nums:
        amounts = [format_dollar_amount(float(n.replace(',', ''))) for n in nums]
        n = len(amounts)

        result = {'tax': None, 'op': None, 'total': '0.00'}
        
        # Work backwards from the end (NEVER include RESET)
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
    metadata = {}
    
    areas = {}
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
            if 'areas' not in base:
                base['areas'] = {}
            base['areas'].update(value)
        elif key == 'doors':
            if 'doors' not in base:
                base['doors'] = []
            base['doors'].extend(value)
        elif key == 'missing_walls':
            if 'missing_walls' not in base:
                base['missing_walls'] = []
            base['missing_walls'].extend(value)
        else:
            base[key] = value
    return base


# ============================================================================
# DOCUMENT PARSING
# ============================================================================

def parse_document(pdf_path: str) -> tuple:
    """Parse entire document using state machine."""
    header_patterns = detect_page_header_pattern(pdf_path)
    
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split('\n'):
                stripped = line.strip()
                if stripped and not is_page_header(stripped, header_patterns):
                    lines.append(stripped)
    
    state = ParseState.LOOKING_FOR_SECTION
    sections = []
    current_section = None
    current_subroom = None
    current_line_item = None
    collecting_notes = False
    columns = TableColumns()
    pending_header_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        next_line = lines[i+1] if i+1 < len(lines) else None
        
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
                if i > 0 and not is_page_header(lines[i-1], header_patterns):
                    section_name = lines[i-1].strip()
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
            if meta:
                current_subroom['metadata'] = merge_metadata(current_subroom['metadata'], meta)
            
            i += 1
            continue
        
        elif state == ParseState.IN_LINE_ITEMS:
            if is_table_continuation(line):
                pending_header_lines = []
                i += 1
                
                if i < len(lines):
                    next_line_after = lines[i+1] if i+1 < len(lines) else None
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

def parse_case_metadata(lines: list) -> dict:
    """Extract case metadata from the first ~50 lines."""
    metadata = {}
    # Increase to 50 lines to ensure we capture all metadata
    text = '\n'.join(lines[:50])
    
    # Debug: Write the text we're searching to a file
    with open('debug_metadata.log', 'w', encoding='utf-8') as f:
        f.write("=== TEXT BEING SEARCHED ===\n")
        f.write(text)
        f.write("\n=== END TEXT ===\n")
    
    # Parse Claim Number, Policy Number, Loss Type
    line1_match = re.search(CASE_LINE1_PATTERN, text, re.IGNORECASE)
    if line1_match:
        claim = line1_match.group(1).strip()
        policy = line1_match.group(2).strip()
        loss_type = line1_match.group(3).strip()
        
        metadata['claim_number'] = claim if claim else None
        metadata['policy_number'] = policy if policy else None
        metadata['loss_type'] = loss_type if (loss_type and not loss_type.startswith('Coverage')) else None
    else:
        metadata['claim_number'] = None
        metadata['policy_number'] = None
        metadata['loss_type'] = None
    
    # Parse Coverage Table (with improved pattern)
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
    
    metadata['coverage'] = coverage_table if coverage_table else None
    
    # Parse Property Address
    property_match = re.search(PROPERTY_ADDRESS_PATTERN, text, re.DOTALL)
    if property_match:
        address_text = property_match.group(1).strip()
        metadata['property_address'] = ' '.join(address_text.split()) if address_text else None
    else:
        metadata['property_address'] = None
    
    # Parse Dates (Line 1)
    date_line1 = re.search(DATE_LINE1_PATTERN, text, re.IGNORECASE)
    if date_line1:
        dol = date_line1.group(1).strip()
        dr = date_line1.group(2).strip()
        metadata['date_of_loss'] = parse_datetime_string(dol) if (dol and re.match(r'\d+/\d+/\d+', dol)) else None
        metadata['date_received'] = parse_datetime_string(dr) if (dr and re.match(r'\d+/\d+/\d+', dr)) else None
    else:
        metadata['date_of_loss'] = None
        metadata['date_received'] = None
    
    # Parse Dates (Line 2)
    date_line2 = re.search(DATE_LINE2_PATTERN, text, re.IGNORECASE)
    if date_line2:
        di = date_line2.group(1).strip()
        de = date_line2.group(2).strip()
        metadata['date_inspected'] = parse_datetime_string(di) if (di and re.match(r'\d+/\d+/\d+', di)) else None
        metadata['date_entered'] = parse_datetime_string(de) if (de and re.match(r'\d+/\d+/\d+', de)) else None
    else:
        metadata['date_inspected'] = None
        metadata['date_entered'] = None
    
    # Parse Price List and Depreciation Options (Line 1)
    price_line = re.search(PRICE_LIST_PATTERN, text, re.IGNORECASE)
    if price_line:
        metadata['price_list'] = price_line.group(1).strip()
        metadata['depreciate_material'] = (price_line.group(2).strip().upper() == 'YES')
        metadata['depreciate_op'] = (price_line.group(3).strip().upper() == 'YES')
        with open('debug_metadata.log', 'a', encoding='utf-8') as f:
            f.write(f"Price list matched: {price_line.group(0)}\n")
    else:
        metadata['price_list'] = None
        metadata['depreciate_material'] = None
        metadata['depreciate_op'] = None
        with open('debug_metadata.log', 'a', encoding='utf-8') as f:
            f.write(f"Price list pattern FAILED\n")
            f.write(f"Pattern: {PRICE_LIST_PATTERN}\n")
    
    # Parse Depreciation Options (Line 2)
    deprec_line2 = re.search(DEPREC_LINE2_PATTERN, text, re.IGNORECASE)
    if deprec_line2:
        metadata['depreciate_non_material'] = (deprec_line2.group(1).strip().upper() == 'YES')
        metadata['depreciate_taxes'] = (deprec_line2.group(2).strip().upper() == 'YES')
        with open('debug_metadata.log', 'a', encoding='utf-8') as f:
            f.write(f"Deprec line 2 matched: {deprec_line2.group(0)}\n")
    else:
        metadata['depreciate_non_material'] = None
        metadata['depreciate_taxes'] = None
        with open('debug_metadata.log', 'a', encoding='utf-8') as f:
            f.write(f"Deprec line 2 pattern FAILED\n")
            f.write(f"Pattern: {DEPREC_LINE2_PATTERN}\n")
    
    # Parse Estimate Name and Depreciate Removal
    estimate_line = re.search(ESTIMATE_LINE_PATTERN, text, re.IGNORECASE)
    if estimate_line:
        metadata['estimate_name'] = estimate_line.group(1).strip()
        metadata['depreciate_removal'] = (estimate_line.group(2).strip().upper() == 'YES')
        with open('debug_metadata.log', 'a', encoding='utf-8') as f:
            f.write(f"Estimate matched: {estimate_line.group(0)}\n")
    else:
        metadata['estimate_name'] = None
        metadata['depreciate_removal'] = None
        with open('debug_metadata.log', 'a', encoding='utf-8') as f:
            f.write(f"Estimate pattern FAILED\n")
            f.write(f"Pattern: {ESTIMATE_LINE_PATTERN}\n")
    
    # Derive region from price list
    if metadata.get('price_list') and metadata['price_list'].upper().startswith('CALA'):
        metadata['region'] = 'California'
    else:
        metadata['region'] = None
    
    # Building type placeholder
    metadata['building_type'] = None
    
    return metadata


# ============================================================================
# MAIN
# ============================================================================

def main():
    with open('debug_calc.log', 'w', encoding='utf-8') as debug_file:
        debug_file.write("Debug log started\n")
    
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
    
    for pdf_file in pdfs:
        pdf_path = os.path.join(input_dir, pdf_file)
        base_name = os.path.splitext(pdf_file)[0]
        
        print(f"\nProcessing: {pdf_file}")
        
        sections, all_lines = parse_document(pdf_path)
        
        lines = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend([l.strip() for l in text.split('\n') if l.strip()])
                break
        
        case_metadata = parse_case_metadata(lines)
        
        for section in sections:
            computed_total = sum(
                float(item['total'].replace(',', '')) 
                for item in section['line_items'] 
                if item.get('type') == 'line_item' and item.get('total') is not None
            )
            declared_total_str = section['section_totals'].get('total', '0.00')
            if declared_total_str:
                declared_total = float(declared_total_str.replace(',', ''))
            else:
                declared_total = 0.0
            delta = declared_total - computed_total
            # Handle floating point precision - treat tiny differences as zero
            if abs(delta) < 0.005:
                delta = 0.0
            section['section_totals']['validation_delta'] = format_dollar_amount(delta)
        
        output = {
            'case_metadata': case_metadata,
            'sections': sections
        }
        
        out_path = os.path.join(output_dir, f"{base_name}.out")
        json_path = os.path.join(output_dir, f"{base_name}.json")
        
        with open(out_path, 'w', encoding='utf-8') as f:
            for line in all_lines:
                f.write(line + '\n')
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"Found {len(sections)} sections:")
        for section in sections:
            items = sum(1 for item in section['line_items'] if item.get('type') == 'line_item')
            headers = sum(1 for item in section['line_items'] if item.get('type') == 'header')
            total = section['section_totals'].get('total', '0.00')
            subrooms_count = len(section['subrooms'])
            print(f"  - {section['section_name']}: {items} items, {headers} header(s), ${total}, {subrooms_count} subroom(s)")
            for subroom in section['subrooms']:
                print(f"      └─ {subroom['subroom_name']}")
        
        print(f"\n✓ Output written to:")
        print(f"  - {out_path}")
        print(f"  - {json_path}")


if __name__ == "__main__":
    main()