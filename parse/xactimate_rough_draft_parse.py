#!/usr/bin/env python3
"""
Section Parser - Structural state machine parser for estimate documents
"""

import os
import sys
import json
import re
import pdfplumber
from enum import Enum
from datetime import datetime


class ParseState(Enum):
    LOOKING_FOR_SECTION = 1
    IN_SECTION_METADATA = 2
    IN_SUBROOM_METADATA = 3
    IN_LINE_ITEMS = 4

def parse_datetime_string(date_str: str) -> str:
    """Parse date string to ISO format."""
    if not date_str:
        return None
    
    try:
        # Try parsing "M/D/YYYY H:MM AM/PM" format
        dt = datetime.strptime(date_str, '%m/%d/%Y %I:%M %p')
        return dt.isoformat()
    except ValueError:
        try:
            # Try parsing "M/D/YYYY" format (no time)
            dt = datetime.strptime(date_str, '%m/%d/%Y')
            return dt.isoformat()
        except ValueError:
            # Return original string if parsing fails
            return date_str

def detect_page_header_pattern(pdf_path: str) -> list:
    """Detect repeating header lines from the first two pages."""
    header_lines = []
    
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 2:
            return header_lines
        
        page1_lines = []
        text = pdf.pages[0].extract_text() or ""
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                page1_lines.append(stripped)
        
        page2_lines = []
        text = pdf.pages[1].extract_text() or ""
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                page2_lines.append(stripped)
        
        for line in page1_lines[:10]:
            if line in page2_lines[:10]:
                header_lines.append(line)
        
        for line in page1_lines[:15]:
            if re.match(r'.*\d+/\d+/\d+\s+Page:\s*\d+', line):
                header_lines.append('PAGE_NUMBER_PATTERN')
                break
    
    return header_lines


def is_diagram_artifact(line: str) -> bool:
    """Check if line is a diagram label or artifact that should be skipped."""
    if re.search(r'([A-Z])\1{2,}', line):
        return True
    
    if line in ['Door', 'Window', 'Wall']:
        return True
    
    if len(line) < 15 and re.search(r'[\"\']{2,}', line):
        return True
    
    special_char_count = sum(1 for c in line if c in '\"\'.-_|/\\')
    if len(line) > 0 and special_char_count / len(line) > 0.4:
        return True
    
    return False


def is_page_header(line: str, header_patterns: list) -> bool:
    """Check if line matches detected header patterns."""
    if re.match(r'^\d{1,3}$', line):
        return True
    
    if re.match(r'.*\d+/\d+/\d+\s+Page:\s*\d+', line):
        return True
    
    if header_patterns:
        for pattern in header_patterns:
            if line == pattern:
                return True
    
    return False


def is_table_header(line: str, next_line: str = None) -> tuple:
    """Check if line is the line items table header (may span 2 lines)."""
    if re.match(r'CAT\s+SEL\s+ACT\s+DESCRIPTION', line):
        # Check both current line and next line for TAX and O&P
        combined = line
        if next_line:
            combined = line + ' ' + next_line
        
        has_tax = 'TAX' in combined
        has_op = 'O&P' in combined or 'O & P' in combined
        
        # Check if next line contains the second part of header
        is_two_line_header = False
        if next_line and re.search(r'CALC\s+QTY\s+RESET', next_line):
            is_two_line_header = True
        
        # Debug output
        print(f"Header detected: has_tax={has_tax}, has_op={has_op}, two_line={is_two_line_header}")
        print(f"Header line: {line}")
        if is_two_line_header:
            print(f"Header line 2: {next_line}")
        
        return True, has_tax, has_op, is_two_line_header
    return False, False, False, False

def is_table_continuation(line: str) -> bool:
    """Check if line indicates a table continuation on new page."""
    return bool(re.match(r'^CONTINUED\s*-\s*.+', line, re.IGNORECASE))


def is_subroom_header(line: str) -> tuple:
    """Check if line is a subroom header."""
    match = re.match(r'^Subroom:\s+(.+?)\s+Height:\s*(.+)', line, re.IGNORECASE)
    if match:
        return True, match.group(1).strip(), match.group(2).strip()
    return False, None, None


def is_line_item(line: str) -> bool:
    """Check if line is a line item."""
    return bool(re.match(r'^\d+\.\s+[A-Z]{3,}\s+', line))


def is_line_item_header(line: str) -> tuple:
    """
    Check if line is a line item header with delimiters.
    Returns (is_header, header_text)
    """
    # Pattern: delimiter characters surrounding text
    # Examples: -----Text-----, ***Text***, ===Text===
    match = re.match(r'^([-*=~_]{2,})\s*(.+?)\s*([-*=~_]{2,})\s*:?\s*$', line)
    if match:
        header_text = match.group(2).strip()
        # Remove trailing colon if present
        header_text = header_text.rstrip(':')
        return True, header_text
    
    return False, None


def could_be_undelimited_header(line: str, next_line: str = None) -> tuple:
    """
    Conservative check for undelimited headers.
    Returns (is_header, header_text)
    """
    # Must be relatively short
    if len(line) > 80:
        return False, None
    
    # Must not have calculation patterns
    if re.search(r'\d+\.\d+\s*[A-Z]{2,}', line):
        return False, None
    
    # Must not be a line item itself
    if re.match(r'^\d+\.\s+[A-Z]{3,}\s+', line):
        return False, None
    
    # Must not be a table header
    if re.match(r'CAT\s+SEL\s+ACT\s+DESCRIPTION', line):
        return False, None
    
    # Must not be a continuation marker
    if re.match(r'^CONTINUED\s*-\s*.+', line, re.IGNORECASE):
        return False, None
    
    # Check if next line is a line item (strong signal this is a header)
    if next_line and re.match(r'^\d+\.\s+[A-Z]{3,}\s+', next_line):
        # Must not have many common prose words (would be a note)
        prose_words = len(re.findall(r'\b(the|and|or|of|to|for|in|on|at|with|by|that|this|from|are|was|were|been|being|have|has|had)\b', line, re.IGNORECASE))
        word_count = len(line.split())
        
        if word_count > 0 and prose_words / word_count < 0.4:
            # Title case or short capitalized phrase
            if line[0].isupper() and word_count <= 5:
                return True, line.strip()
    
    return False, None


def is_totals_line(line: str) -> bool:
    """Check if line is a totals line."""
    # Match both "Total:" and "Totals:" (singular and plural)
    return bool(re.match(r'^Totals?:', line))


def parse_height(height_str: str) -> str:
    """Parse height string - keep original format."""
    # Just return the original string, don't convert to float
    return height_str.strip()


def format_dollar_amount(value: float) -> str:
    """Format a dollar amount as a string with 2 decimal places."""
    return f"{value:,.2f}"


def extract_metadata_from_line(line: str) -> dict:
    """Extract all metadata fields from a single line."""
    metadata = {}
    
    patterns = {
        'sf_walls_and_ceiling': r'([0-9,]+\.[0-9]+)\s+SF\s+Walls\s+&\s+Ceiling',
        'sf_walls': r'([0-9,]+\.[0-9]+)\s+SF\s+Walls(?!\s+&)',
        'sf_ceiling': r'([0-9,]+\.[0-9]+)\s+SF\s+Ceiling(?!\s+&)',
        'sf_floor': r'([0-9,]+\.[0-9]+)\s+SF\s+Floor(?!\s+Perimeter)',
        'sy_flooring': r'([0-9,]+\.[0-9]+)\s+SY\s+Flooring',
        'lf_floor_perimeter': r'([0-9,]+\.[0-9]+)\s+LF\s+Floor\s+Perimeter',
        'lf_ceil_perimeter': r'([0-9,]+\.[0-9]+)\s+LF\s+Ceil\.\s+Perimeter',
    }
    
    areas = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            # Keep areas as formatted strings
            areas[key] = format_dollar_amount(float(match.group(1).replace(',', '')))
    
    if areas:
        metadata['areas'] = areas
    
    doors = []
    for match in re.finditer(r'Door\s+([\d\'\"\s]+[Xx][\d\'\"\s]+)\s+Opens\s+into\s+([A-Z_0-9]+)', line, re.IGNORECASE):
        doors.append({
            'dimensions': match.group(1).strip(),  # Keep original format
            'opens_into': match.group(2).strip()
        })
    if doors:
        metadata['doors'] = doors
    
    walls = []
    for match in re.finditer(r'Missing\s+Wall\s+([\d\'\"\s/]+[Xx][\d\'\"\s]+)\s+Opens\s+into\s+([A-Z_0-9]+)', line, re.IGNORECASE):
        walls.append({
            'dimensions': match.group(1).strip(),  # Keep original format
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


def parse_line_item_calc(calc_line: str, has_tax: bool, has_op: bool) -> dict:
    """Parse calculation line for line item with optional TAX and O&P columns.
    Supports:
      1) Priced lines like: [calc] QTY UNIT [brackets] REMOVE + REPLACE = [TAX] [O&P] TOTAL
      2) Price-less directive lines like: [calc] QTY UNIT SEE X3.BUILD  -> total=0.00, total_note
      3) Generic terminal-status fallback after QTY UNIT (e.g., SEE X3.BUILD, REF ABC-01, etc.)
    """
    # Debug logging to file
    with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
        debug_file.write(f"\n{'='*80}\n")
        debug_file.write(f"calc_line: '{calc_line}'\n")
        debug_file.write(f"has_tax: {has_tax}, has_op: {has_op}\n")

    # ------------------------------------------------------------------------------
    # 1) Explicit SEE handler
    # ------------------------------------------------------------------------------
    see_match = re.search(
        r'(?:([0-9*+\-./\s]+?)\s+)?'        # optional calc
        r'([0-9]+(?:\.[0-9]+)?)\s*'         # qty
        r'([A-Z]{2,})\s+'                   # unit
        r'(?:SEE|SEE:)\s+'                  # SEE marker
        r'([A-Z0-9][A-Z0-9._/\- ]+?)\s*$',  # note
        calc_line,
        re.IGNORECASE
    )
    if see_match:
        result = {
            'calc': (see_match.group(1) or '').strip(),
            'qty': float(see_match.group(2)),
            'unit': see_match.group(3).upper(),
            'remove': None,
            'replace': None,
            'tax': None,
            'op': None,
            'total': '0.00',
            'total_note': see_match.group(4).strip().upper()
        }
        with open('debug_calc.log', 'a', encoding='utf-8') as debug_file:
            debug_file.write(f"SEE pattern matched. Returning result: {result}\n")
        return result

    # ------------------------------------------------------------------------------
    # 2) Priced formats
    # ------------------------------------------------------------------------------
    prefix = (
        r'(?:([0-9*+\-./\s]+?)\s+)?'
        r'([0-9]+(?:\.[0-9]+)?)\s*([A-Z]{2,})\s*'
        r'(?:\[[^\]]+\])?\s*'
        r'([0-9,]+\.[0-9]+)\s*\+\s*'
        r'([0-9,]+\.[0-9]+)\s*=\s*'
    )

    if has_tax and has_op:
        pattern = prefix + r'([0-9,]+\.[0-9]+)\s+([0-9,]+\.[0-9]+)\s+([0-9,]+\.[0-9]+)\s*$'
    elif has_tax and not has_op:
        pattern = prefix + r'([0-9,]+\.[0-9]+)\s+([0-9,]+\.[0-9]+)\s*$'
    elif not has_tax and has_op:
        pattern = prefix + r'([0-9,]+\.[0-9]+)\s+([0-9,]+\.[0-9]+)\s*$'
    else:
        pattern = prefix + r'(?:[0-9,]+\.[0-9]+\s+)*([0-9,]+\.[0-9]+)\s*$'

    match = re.search(pattern, calc_line)

    if match:
        result = {
            'calc': (match.group(1) or '').strip(),
            'qty': float(match.group(2)),
            'unit': match.group(3),
            'remove': format_dollar_amount(float(match.group(4).replace(',', ''))),
            'replace': format_dollar_amount(float(match.group(5).replace(',', '')))
        }

        if has_tax and has_op:
            result['tax'] = format_dollar_amount(float(match.group(6).replace(',', '')))
            result['op'] = format_dollar_amount(float(match.group(7).replace(',', '')))
            result['total'] = format_dollar_amount(float(match.group(8).replace(',', '')))
        elif has_tax and not has_op:
            result['tax'] = format_dollar_amount(float(match.group(6).replace(',', '')))
            result['op'] = None
            result['total'] = format_dollar_amount(float(match.group(7).replace(',', '')))
        elif not has_tax and has_op:
            result['tax'] = None
            result['op'] = format_dollar_amount(float(match.group(6).replace(',', '')))
            result['total'] = format_dollar_amount(float(match.group(7).replace(',', '')))
        else:
            result['tax'] = None
            result['op'] = None
            result['total'] = format_dollar_amount(float(match.group(6).replace(',', '')))

        return result

    # ------------------------------------------------------------------------------
    # 3) Terminal status fallback
    # ------------------------------------------------------------------------------
    terminal_status_match = re.search(
        r'\b([A-Z0-9]+(?:[._/\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+(?:[._/\-][A-Z0-9]+)*)*)\s*$',
        calc_line,
        re.IGNORECASE
    )

    qty_unit_pattern = (
        r'(?:([0-9*+\-./\s]+?)\s+)?'
        r'([0-9]+(?:\.[0-9]+)?)\s*'
        r'([A-Z]{2,})\s*'
        r'(?:\[[^\]]+\])?\s+'
    )

    if terminal_status_match:
        terminal_status = terminal_status_match.group(1).strip()
        if re.search(qty_unit_pattern + re.escape(terminal_status) + r'\s*$', calc_line, re.IGNORECASE):
            match2 = re.search(
                qty_unit_pattern +
                r'([A-Z0-9]+(?:[._/\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+(?:[._/\-][A-Z0-9]+)*)*)\s*$',
                calc_line,
                re.IGNORECASE
            )
            if match2:
                return {
                    'calc': (match2.group(1) or '').strip(),
                    'qty': float(match2.group(2)),
                    'unit': match2.group(3),
                    'remove': None,
                    'replace': None,
                    'tax': None,
                    'op': None,
                    'total': '0.00',
                    'total_note': match2.group(4).strip().upper()
                }

    return {}


def parse_totals(totals_line: str, has_tax: bool, has_op: bool) -> dict:
    """Parse totals line with optional TAX and O&P. Supports 'Total:' and 'Totals:'."""
    # Primary pattern-based parsing (explicit shapes)
    if has_tax and has_op:
        # Total(s): <section> TAX O&P TOTAL
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
    elif has_tax and not has_op:
        # Total(s): <section> TAX TOTAL
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
    elif not has_tax and has_op:
        # Total(s): <section> O&P TOTAL
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
        # Total(s): <section> TOTAL
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

    # Fallback: infer from however many currency numbers we can find
    nums = re.findall(r'[\d,]+\.\d+', totals_line)
    if nums:
        # Take values from the end to avoid picking earlier incidental numbers
        amounts = [format_dollar_amount(float(n.replace(',', ''))) for n in nums]
        n = len(amounts)

        if has_tax and has_op and n >= 3:
            return {'tax': amounts[-3], 'op': amounts[-2], 'total': amounts[-1]}
        if has_tax and not has_op and n >= 2:
            return {'tax': amounts[-2], 'op': None, 'total': amounts[-1]}
        if not has_tax and has_op and n >= 2:
            return {'tax': None, 'op': amounts[-2], 'total': amounts[-1]}
        # Default: last number is total
        return {'tax': None, 'op': None, 'total': amounts[-1]}

    # If nothing matched, return zeros vs None to be explicit
    return {'tax': None, 'op': None, 'total': '0.00'}


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
    has_tax = False
    has_op = False
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
                match = re.match(r'^(.+?)\s+Height:\s*(.+)', line)
                if match:
                    raw_section_name = match.group(1).strip()
                    height = match.group(2).strip()
                    
                    section_name_match = re.search(r'([A-Z][A-Za-z\s\.\(\)/]+(?:\s+\d+)?)\s*$', raw_section_name)
                    if section_name_match:
                        section_name = section_name_match.group(1).strip()
                    else:
                        section_name = raw_section_name
                    
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
            
            # Check if current line is a table header
            is_header, header_has_tax, header_has_op, is_two_line = is_table_header(line, next_line)
            if is_header:
                # Look back for section name
                section_name = "Unknown Section"
                if i > 0 and not is_page_header(lines[i-1], header_patterns):
                    section_name = lines[i-1].strip()
                    name_match = re.search(r'([A-Z][A-Za-z\s\-/]+)\s*$', section_name)
                    if name_match:
                        section_name = name_match.group(1).strip()
                
                current_section = {
                    'section_name': section_name,
                    'metadata': {},
                    'subrooms': [],
                    'line_items': [],
                    'section_totals': {}
                }
                has_tax = header_has_tax
                has_op = header_has_op
                state = ParseState.IN_LINE_ITEMS
                
                # Skip second header line if two-line header
                if is_two_line:
                    i += 2
                else:
                    i += 1
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
            
            # Get next_line and unpack 4 values
            next_line = lines[i+1] if i+1 < len(lines) else None
            is_header, header_has_tax, header_has_op, is_two_line = is_table_header(line, next_line)
            if is_header:
                # Set has_tax and has_op here
                has_tax = header_has_tax
                has_op = header_has_op
                state = ParseState.IN_LINE_ITEMS
                # Skip second header line if two-line header
                if is_two_line:
                    i += 2
                else:
                    i += 1
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
            
            # Get next_line and unpack 4 values
            next_line = lines[i+1] if i+1 < len(lines) else None
            is_header, header_has_tax, header_has_op, is_two_line = is_table_header(line, next_line)
            if is_header:
                current_section['subrooms'].append(current_subroom)
                current_subroom = None
                # Set has_tax and has_op here
                has_tax = header_has_tax
                has_op = header_has_op
                state = ParseState.IN_LINE_ITEMS
                # Skip second header line if two-line header
                if is_two_line:
                    i += 2
                else:
                    i += 1
                continue
            
            meta = extract_metadata_from_line(line)
            if meta:
                current_subroom['metadata'] = merge_metadata(current_subroom['metadata'], meta)
            
            i += 1
            continue
        
        elif state == ParseState.IN_LINE_ITEMS:
            # Check for table continuation
            if is_table_continuation(line):
                # Clear any pending notes - continuation marks a hard break
                pending_header_lines = []
                
                # Skip continuation line
                i += 1
                
                # Read the table header that follows and update has_tax/has_op
                if i < len(lines):
                    next_line_after_continuation = lines[i+1] if i+1 < len(lines) else None
                    is_header, new_has_tax, new_has_op, is_two_line = is_table_header(lines[i], next_line_after_continuation)
                    if is_header:
                        # Update has_tax and has_op from continuation header
                        has_tax = new_has_tax
                        has_op = new_has_op
                        # Skip second header line if two-line header
                        if is_two_line:
                            i += 2
                        else:
                            i += 1
                continue
            
            # Check for totals line - end of section
            if is_totals_line(line):
                # Process any pending header lines as notes
                if pending_header_lines and current_line_item:
                    note_text = ' '.join(pending_header_lines)
                    if current_line_item['notes']:
                        current_line_item['notes'] += ' ' + note_text
                    else:
                        current_line_item['notes'] = note_text
                    pending_header_lines = []
                
                # If we were collecting notes, finalize the current line item
                if collecting_notes and current_line_item:
                    current_section['line_items'].append(current_line_item)
                    current_line_item = None
                    collecting_notes = False
                
                current_section['section_totals'] = parse_totals(line, has_tax, has_op)
                sections.append(current_section)
                current_section = None
                # Reset has_tax and has_op when section ends
                has_tax = False
                has_op = False
                state = ParseState.LOOKING_FOR_SECTION
                i += 1
                continue
            
            # Check for line item header (delimited only)
            is_header_line, header_text = is_line_item_header(line)
            if is_header_line:
                # Process pending notes first if any
                if pending_header_lines and current_line_item:
                    note_text = ' '.join(pending_header_lines)
                    if current_line_item['notes']:
                        current_line_item['notes'] += ' ' + note_text
                    else:
                        current_line_item['notes'] = note_text
                    pending_header_lines = []
                
                # Save previous line item if exists
                if collecting_notes and current_line_item:
                    current_section['line_items'].append(current_line_item)
                    current_line_item = None
                    collecting_notes = False
                
                # Add header as a special line item
                current_section['line_items'].append({
                    'type': 'header',
                    'text': header_text
                })
                i += 1
                continue
            
            # Check for new line item
            if is_line_item(line):
                # Process pending notes
                if pending_header_lines and current_line_item:
                    note_text = ' '.join(pending_header_lines)
                    if current_line_item['notes']:
                        current_line_item['notes'] += ' ' + note_text
                    else:
                        current_line_item['notes'] = note_text
                    pending_header_lines = []
                
                # FIXED: Save previous line item if it exists (regardless of collecting_notes)
                if current_line_item:
                    current_section['line_items'].append(current_line_item)
                    current_line_item = None
                    collecting_notes = False
                
                # Parse the new line item header
                # FIXED: Added + and - to SEL code character class to match codes like EVCS+, RC++, etc.
                match = re.match(r'^(\d+)\.\s+([A-Z]{3,})\s+([A-Z0-9<>+\-/]+)\s+[\+\-&]?\s*(.*)$', line)
                if match:
                    current_line_item = {
                        'type': 'line_item',
                        'line_number': int(match.group(1)),
                        'cat': match.group(2),
                        'sel': match.group(3),
                        'description': match.group(4).strip(),
                        'calc': '',
                        'qty': 0.0,
                        'unit': '',
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
            
            # Check for calculation line (only if we have a current line item)
            # Enhanced pattern to catch more calc line formats
            if current_line_item and re.search(r'[0-9.]+\s*[A-Z]{2,}\s*(?:\[[^\]]+\]|\bSEE\b|[0-9,]+\.[0-9]+\s*[+=])', line):
                calc = parse_line_item_calc(line, has_tax, has_op)
                if calc:
                    current_line_item.update(calc)
                    collecting_notes = True
                    i += 1
                    continue
            
            # Collect notes if we're in note-collecting mode
            if collecting_notes and current_line_item:
                pending_header_lines.append(line)
                i += 1
                continue
            
            i += 1
            continue
        
        i += 1
    
    return sections, lines


def parse_case_metadata(lines: list) -> dict:
    """Extract case metadata from the first ~30 lines."""
    metadata = {}
    text = '\n'.join(lines[:30])
    
    # Line 1: Claim Number: Policy Number: Type of Loss: <value>
    # Loss type must be on the same line, capture everything up to newline
    line1_match = re.search(
        r'Claim\s+Number:\s*(\S*)\s+Policy\s+Number:\s*(\S*)\s+Type\s+of\s+Loss:\s*([^\n]*)',
        text,
        re.IGNORECASE
    )
    if line1_match:
        claim = line1_match.group(1).strip()
        policy = line1_match.group(2).strip()
        loss_type = line1_match.group(3).strip()
        
        metadata['claim_number'] = claim if claim else None
        metadata['policy_number'] = policy if policy else None
        # If loss_type is empty or starts with "Coverage", set to None
        metadata['loss_type'] = loss_type if (loss_type and not loss_type.startswith('Coverage')) else None
    else:
        metadata['claim_number'] = None
        metadata['policy_number'] = None
        metadata['loss_type'] = None
    
    # Coverage table parsing
    # Table format: Coverage Deductible Policy Limit
    #               <type>    $X.XX      $Y.YY
    coverage_table = []
    coverage_section = re.search(
        r'Coverage\s+Deductible\s+Policy\s+Limit\s*\n((?:.*?\$[\d,]+\.[\d]{2}.*?\n?)+)',
        text,
        re.IGNORECASE
    )
    if coverage_section:
        table_rows = coverage_section.group(1).strip().split('\n')
        for row in table_rows:
            # Match: <coverage_type> $deductible $policy_limit
            row_match = re.match(r'^\s*([A-Za-z\s]+?)\s+\$?([\d,]+\.[\d]{2})\s+\$?([\d,]+\.[\d]{2})', row)
            if row_match:
                coverage_table.append({
                    'coverage_type': row_match.group(1).strip(),
                    'deductible': format_dollar_amount(float(row_match.group(2).replace(',', ''))),
                    'policy_limit': format_dollar_amount(float(row_match.group(3).replace(',', '')))
                })
    
    metadata['coverage'] = coverage_table if coverage_table else None
    
    # Property address (multi-line)
    property_match = re.search(r'Property:\s*(.+?)(?=\n[A-Za-z\s]+:|\Z)', text, re.DOTALL)
    if property_match:
        address_text = property_match.group(1).strip()
        metadata['property_address'] = ' '.join(address_text.split()) if address_text else None
    else:
        metadata['property_address'] = None
    
    # Date line 1: Date of Loss: <value> Date Received: <value>
    date_line1 = re.search(
        r'Date\s+of\s+Loss:\s*([^\n]*?)\s*Date\s+Received:\s*([^\n]*?)(?=\n|$)',
        text,
        re.IGNORECASE
    )
    if date_line1:
        dol = date_line1.group(1).strip()
        dr = date_line1.group(2).strip()
        metadata['date_of_loss'] = parse_datetime_string(dol) if (dol and re.match(r'\d+/\d+/\d+', dol)) else None
        metadata['date_received'] = parse_datetime_string(dr) if (dr and re.match(r'\d+/\d+/\d+', dr)) else None
    else:
        metadata['date_of_loss'] = None
        metadata['date_received'] = None
    
    # Date line 2: Date Inspected: <value> Date Entered: <value>
    date_line2 = re.search(
        r'Date\s+Inspected:\s*([^\n]*?)\s*Date\s+Entered:\s*([^\n]+?)(?=\n|$)',
        text,
        re.IGNORECASE
    )
    if date_line2:
        di = date_line2.group(1).strip()
        de = date_line2.group(2).strip()
        metadata['date_inspected'] = parse_datetime_string(di) if (di and re.match(r'\d+/\d+/\d+', di)) else None
        metadata['date_entered'] = parse_datetime_string(de) if (de and re.match(r'\d+/\d+/\d+', de)) else None
    else:
        metadata['date_inspected'] = None
        metadata['date_entered'] = None
    
    # Price List line with depreciation fields
    price_line = re.search(
        r'Price\s+List:\s*([^\s]+)\s+Depreciate\s+Material:\s*(Yes|No)\s+Depreciate\s+O&P:\s*(Yes|No)',
        text,
        re.IGNORECASE
    )
    if price_line:
        metadata['price_list'] = price_line.group(1).strip()
        metadata['depreciate_material'] = (price_line.group(2).strip().upper() == 'YES')
        metadata['depreciate_op'] = (price_line.group(3).strip().upper() == 'YES')
    else:
        metadata['price_list'] = None
        metadata['depreciate_material'] = None
        metadata['depreciate_op'] = None
    
    # Second depreciation line
    deprec_line2 = re.search(
        r'Depreciate\s+Non-material:\s*(Yes|No)\s+Depreciate\s+Taxes:\s*(Yes|No)',
        text,
        re.IGNORECASE
    )
    if deprec_line2:
        metadata['depreciate_non_material'] = (deprec_line2.group(1).strip().upper() == 'YES')
        metadata['depreciate_taxes'] = (deprec_line2.group(2).strip().upper() == 'YES')
    else:
        metadata['depreciate_non_material'] = None
        metadata['depreciate_taxes'] = None
    
    # Estimate and Depreciate Removal line
    estimate_line = re.search(
        r'Estimate:\s*([^\s]+)\s+Depreciate\s+Removal:\s*(Yes|No)',
        text,
        re.IGNORECASE
    )
    if estimate_line:
        metadata['estimate_name'] = estimate_line.group(1).strip()
        metadata['depreciate_removal'] = (estimate_line.group(2).strip().upper() == 'YES')
    else:
        metadata['estimate_name'] = None
        metadata['depreciate_removal'] = None
    
    # Derive region from price list
    if metadata.get('price_list') and metadata['price_list'].upper().startswith('CALA'):
        metadata['region'] = 'California'
    else:
        metadata['region'] = None
    
    # Building type (to be enriched later)
    metadata['building_type'] = None
    
    return metadata


def main():
    # Clear debug log at start
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
            # Convert string totals back to float for validation calculation
            # Only include line items with totals (not headers or pending items)
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
            section['section_totals']['validation_delta'] = format_dollar_amount(declared_total - computed_total)
        
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
            # Count actual line items (not headers)
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