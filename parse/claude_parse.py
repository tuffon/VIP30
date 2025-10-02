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


def is_table_header(line: str) -> bool:
    """Check if line is the line items table header."""
    return line == "CAT SEL ACT DESCRIPTION"


def is_subroom_header(line: str) -> tuple:
    """Check if line is a subroom header."""
    match = re.match(r'^Subroom:\s+(.+?)\s+Height:\s*(.+)', line, re.IGNORECASE)
    if match:
        return True, match.group(1).strip(), match.group(2).strip()
    return False, None, None


def is_line_item(line: str) -> bool:
    """Check if line is a line item."""
    return bool(re.match(r'^\d+\.\s+[A-Z]{3}\s+', line))


def is_totals_line(line: str) -> bool:
    """Check if line is a totals line."""
    return bool(re.match(r'^Totals:', line))


def parse_height(height_str: str) -> float:
    """Parse height string to float."""
    if height_str.lower() == 'tray':
        return 'Tray'
    
    height_clean = height_str.replace(' ', '')
    if "'" in height_clean:
        if '"' in height_clean:
            match = re.match(r"(\d+)'(\d+)\"", height_clean)
            if match:
                return int(match.group(1)) + int(match.group(2)) / 12.0
        else:
            return float(height_clean.replace("'", ""))
    return height_str


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
            areas[key] = float(match.group(1).replace(',', ''))
    
    if areas:
        metadata['areas'] = areas
    
    doors = []
    for match in re.finditer(r'Door\s+([\d\'\"\s]+[Xx][\d\'\"\s]+)\s+Opens\s+into\s+([A-Z_0-9]+)', line, re.IGNORECASE):
        doors.append({
            'dimensions': match.group(1).strip(),
            'opens_into': match.group(2).strip()
        })
    if doors:
        metadata['doors'] = doors
    
    walls = []
    for match in re.finditer(r'Missing\s+Wall\s+([\d\'\"\s/]+[Xx][\d\'\"\s]+)\s+Opens\s+into\s+([A-Z_0-9]+)', line, re.IGNORECASE):
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


def parse_line_item_calc(calc_line: str) -> dict:
    """Parse calculation line for line item."""
    match = re.search(
        r'(?:([0-9*+\-.\s]+?)\s+)?'
        r'([0-9]+(?:\.[0-9]+)?)\s*([A-Z]{2,4})\s+'
        r'([0-9,]+\.[0-9]+)\s*\+\s*([0-9,]+\.[0-9]+)\s*=\s*'
        r'([0-9,]+\.[0-9]+)\s+([0-9,]+\.[0-9]+)',
        calc_line
    )
    
    if match:
        return {
            'calc': (match.group(1) or '').strip(),
            'qty': float(match.group(2)),
            'unit': match.group(3),
            'remove': float(match.group(4).replace(',', '')),
            'replace': float(match.group(5).replace(',', '')),
            'tax': float(match.group(6).replace(',', '')),
            'total': float(match.group(7).replace(',', ''))
        }
    return {}


def parse_totals(totals_line: str) -> dict:
    """Parse totals line."""
    match = re.search(r'Totals:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)$', totals_line)
    if match:
        return {
            'tax': float(match.group(1).replace(',', '')),
            'total': float(match.group(2).replace(',', ''))
        }
    return {'tax': 0.0, 'total': 0.0}


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
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if state == ParseState.LOOKING_FOR_SECTION:
            if 'Height:' in line and 'Subroom:' not in line:
                match = re.match(r'^(.+?)\s+Height:\s*(.+)', line)
                if match:
                    section_name = match.group(1).strip()
                    height = match.group(2).strip()
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
            
            if i + 1 < len(lines) and is_table_header(lines[i + 1]):
                if not is_page_header(line, header_patterns):
                    current_section = {
                        'section_name': line.strip(),
                        'metadata': {},
                        'subrooms': [],
                        'line_items': [],
                        'section_totals': {}
                    }
                    state = ParseState.IN_SECTION_METADATA
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
            
            if is_table_header(line):
                state = ParseState.IN_LINE_ITEMS
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
            
            if is_table_header(line):
                current_section['subrooms'].append(current_subroom)
                current_subroom = None
                state = ParseState.IN_LINE_ITEMS
                i += 1
                continue
            
            meta = extract_metadata_from_line(line)
            if meta:
                current_subroom['metadata'] = merge_metadata(current_subroom['metadata'], meta)
            
            i += 1
            continue
        
        elif state == ParseState.IN_LINE_ITEMS:
            if is_totals_line(line):
                current_section['section_totals'] = parse_totals(line)
                sections.append(current_section)
                current_section = None
                state = ParseState.LOOKING_FOR_SECTION
                i += 1
                continue
            
            if is_line_item(line):
                match = re.match(r'^(\d+)\.\s+([A-Z]{3})\s+([A-Z0-9<>]+)\s+[\+\-]?\s*(.*)$', line)
                if match:
                    current_line_item = {
                        'line_number': int(match.group(1)),
                        'cat': match.group(2),
                        'sel': match.group(3),
                        'description': match.group(4).strip(),
                        'calc': '',
                        'qty': 0.0,
                        'unit': '',
                        'remove': 0.0,
                        'replace': 0.0,
                        'tax': 0.0,
                        'total': 0.0
                    }
                i += 1
                continue
            
            if current_line_item and re.search(r'\d+\.\d+\s*[A-Z]{2,4}\s+[\d,]+\.\d+\s*\+', line):
                calc = parse_line_item_calc(line)
                current_line_item.update(calc)
                current_section['line_items'].append(current_line_item)
                current_line_item = None
            
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
                    'deductible': float(row_match.group(2).replace(',', '')),
                    'policy_limit': float(row_match.group(3).replace(',', ''))
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
            computed_total = sum(item['total'] for item in section['line_items'])
            declared_total = section['section_totals'].get('total', 0)
            section['section_totals']['validation_delta'] = round(declared_total - computed_total, 2)
        
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
            items = len(section['line_items'])
            total = section['section_totals'].get('total', 0)
            subrooms_count = len(section['subrooms'])
            print(f"  - {section['section_name']}: {items} items, ${total:,.2f}, {subrooms_count} subroom(s)")
            for subroom in section['subrooms']:
                print(f"      └─ {subroom['subroom_name']}")
        
        print(f"\n✓ Output written to:")
        print(f"  - {out_path}")
        print(f"  - {json_path}")


if __name__ == "__main__":
    main()