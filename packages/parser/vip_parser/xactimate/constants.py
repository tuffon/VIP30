"""Regex patterns and static configuration for the Xactimate parser."""

PAGE_NUMBER_PATTERN = r'.*\d+/\d+/\d+\s+Page:\s*\d+'
SINGLE_PAGE_NUMBER_PATTERN = r'^\d{1,3}$'
SECTION_HEIGHT_PATTERN = r'^(.+?)\s+Height:\s*(.+)'
SECTION_NAME_EXTRACTION = r'([A-Z][A-Za-z\s\.\(\)/]+(?:\s+\d+)?)\s*$'
SUBROOM_PATTERN = r'^(?:[\d\'\"\s]+)?Subroom:\s+(.+?)\s+Height:\s*(.+)'
TABLE_HEADER_PRIMARY = r'CAT\s+SEL\s+ACT\s+DESCRIPTION'
TABLE_HEADER_CONTINUATION = r'^\s*CONTINUED\s*[-:]\s*.+'
TABLE_HEADER_SECOND_LINE_FRAGMENT = r'CALC\s+QTY'
LINE_ITEM_PATTERN = r'^(\d+)\.\s+([A-Z]{3,})\s+([A-Z0-9<>+\-/]+)\s+(\S)\s+(.*)$'
LINE_ITEM_HEADER_PATTERN = r'^([-*=~_]{2,})\s*(.+?)\s*([-*=~_]{2,})\s*:?\s*$'

# Contractor-final (family C) single-line item: "{N}. {description} {QTY} {UNIT} {amounts...}"
# Description is non-greedy to stop at first decimal+unit combo.
# Groups: (1)item_num (2)description (3)qty (4)unit (5)v1 (6)v2 (7)v3 (8)v4 (9)v5
# Typically 5 amounts: RESET_unit, REMOVE_unit, REPLACE_or_TAX, O&P, TOTAL
# Minimum 1 amount required (v5 is the last captured; trailing amounts are optional).
CFINAL_ITEM_PATTERN = (
    r'^(\d+)\.\s+'           # group 1: item number
    r'(.*?)\s+'              # group 2: description (non-greedy, stops at first QTY match)
    r'([\d,]+\.\d+)\s+'     # group 3: QTY (decimal, may have commas e.g. 1,897.79)
    r'([A-Z]{1,6})\s+'      # group 4: UNIT (1-6 uppercase letters e.g. EA, MO, SF, HR)
    r'([\d,]+\.\d{2})'      # group 5: val1 (required)
    r'(?:\s+([\d,]+\.\d{2}))?'   # group 6: val2 (optional)
    r'(?:\s+([\d,]+\.\d{2}))?'   # group 7: val3 (optional)
    r'(?:\s+([\d,]+\.\d{2}))?'   # group 8: val4 (optional)
    r'(?:\s+([\d,]+\.\d{2}))?'   # group 9: val5 (optional, typically TOTAL)
    r'\s*$'
)

CALC_PREFIX_PATTERN = r'(?:([0-9*+\-./\s]+?)\s+)?'
CALC_LINE_DETECTION_PATTERN = r'[0-9.]+\s*[A-Z]{2,}\s*(?:\[[^\]]+\]|\bSEE\b|[0-9,]+\.[0-9]+)'
QTY_UNIT_PATTERN = r'([0-9]+(?:\.[0-9]+)?)\s*([A-Z]{2,})\s*'
BRACKETS_PATTERN = r'(?:\[([^\]]+)\])?\s*'
CURRENCY_PATTERN = r'([0-9,]+\.[0-9]+)'
SEE_PATTERN = r'(?:SEE|SEE:)\s+([A-Z0-9][A-Z0-9._/\- ]+?)\s*$'
TERMINAL_STATUS_PATTERN = r'\b([A-Z0-9]+(?:[._/\-][A-Z0-9]+)*(?:\s+[A-Z0-9]+(?:[._/\-][A-Z0-9]+)*)*)\s*$'

HEADER_VARIANTS = {
    # Layout A (Final Draft)
    "DESCRIPTION": {"DESCRIPTION", "DESC"},
    "QUANTITY": {"QUANTITY"},
    "UNIT": {"UNIT", "UNITS"},
    "PRICE": {"PRICE", "UNIT PRICE", "UNIT-PRICE", "UNITPRICE"},
    "TAX": {"TAX", "SALES TAX", "MATERIAL TAX"},
    "RCV": {"RCV", "REPLACEMENT COST VALUE", "REPL COST VALUE", "REPL. COST VALUE"},
    # Layout B (Rough Draft)
    "CAT": {"CAT", "CATEGORY"},
    "SEL": {"SEL", "SELECTION"},
    "ACT": {"ACT", "ACTIVITY"},
    "CALC": {"CALC", "CALCULATION"},
    "QTY": {"QTY"},
    "RESET": {"RESET", "RST"},
    "REMOVE": {"REMOVE", "RMV", "REM"},
    "REPLACE": {"REPLACE", "RPL", "R/R", "R & R", "R&R"},
    "O&P": {"O&P", "OP", "O & P", "O / P", "OVERHEAD/PROFIT", "O&P.", "GCO&P"},
    "TOTAL": {"TOTAL", "TOT"},
}

METADATA_PATTERNS = {
    'sf_walls_and_ceiling': r'([0-9,]+\.[0-9]+)\s+SF\s+Walls\s+&\s+Ceiling',
    'sf_walls': r'([0-9,]+\.[0-9]+)\s+SF\s+Walls(?!\s+&)',
    'sf_ceiling': r'([0-9,]+\.[0-9]+)\s+SF\s+Ceiling(?!\s+&)',
    'sf_floor': r'([0-9,]+\.[0-9]+)\s+SF\s+Floor(?!\s+Perimeter)',
    'sy_flooring': r'([0-9,]+\.[0-9]+)\s+SY\s+Flooring',
    'lf_floor_perimeter': r'([0-9,]+\.[0-9]+)\s+LF\s+Floor\s+Perimeter',
    'lf_ceil_perimeter': r'([0-9,]+\.[0-9]+)\s+LF\s+Ceil\.\s+Perimeter',
}
DOOR_PATTERN = r'Door\s+([\d\'\"\s/]+[Xx][\d\'\"\s/]+)\s+Opens\s+into\s+([A-Za-z0-9_]+(?:\s+[A-Za-z0-9_]+)*)'
MISSING_WALL_PATTERN = r'Missing\s+Wall\s+([\d\'\"\s/]+[Xx][\d\'\"\s/]+)\s+Opens\s+into\s+([A-Za-z0-9_]+(?:\s+[A-Za-z0-9_]+)*)'
WINDOW_PATTERN = r'Window\s+([\d\'\"\s/]+[Xx][\d\'\"\s/]+)\s+Opens\s+into\s+([A-Za-z0-9_]+(?:\s+[A-Za-z0-9_]+)*)'
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

# StateFarm two-column summary page patterns (page 3 of StateFarm PDFs).
# The summary page renders as interleaved two-column text via pdfplumber.extract_text():
#   Insured: SCHACTER, BARBARA  Estimate: 75-79D9-35K
#   Property: 935 CHATTANOOGA AVE  Claim Number: 7579D935K
#   PACIFIC PLSDS, CA 90272-2328  Policy Number: 71GFE6010
#   Cellular: 310-617-7790  Price List: CALA28_AUG25
SF_INSURED_PATTERN = r'Insured:\s+(.+?)\s+Estimate:'
SF_PRICE_LIST_PATTERN = r'Price\s+List:\s+(\S+)'
SF_PROPERTY_PATTERN = (
    r'Property:\s+(.+?)\s+Claim(?:\s+Number)?:[^\n]*\n'
    r'(.+?)\s+(?:Policy(?:\s+Number)?:|Home:|Cellular:)'
)

REPEATED_CHAR_PATTERN = r'([A-Z])\1{2,}'
QUOTE_PATTERN = r'[\"\']{2,}'

LABOR_MIN_APPLIED_PATTERN = r'^Totals?:\s*Labor\s+Minimums\s+Applied\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)'
LINE_ITEM_TOTALS_PATTERN = r'^Line\s+Item\s+Totals:\s*([A-Za-z0-9._\-]+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)'
ADD_CHARGE_ROW_PATTERN = r'^([A-Za-z].*?)\s+([\d,]+\.\d+)$'
ADD_CHARGES_HDR_PATTERN = r'^Additional\s+Charges\s+Charge\s*$'
ADD_CHARGES_TOTAL_PATTERN = r'^Additional\s+Charges\s+Total\s*\$?([\d,]+\.\d+)'

GRAND_TOTAL_AREAS_HDR = r'^Grand\s+Total\s+Areas:'

COVERAGE_TABLE_ROW = r'^([A-Za-z0-9][A-Za-z0-9\s,&\-\.\'/]+?)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$'
COVERAGE_TOTAL_ROW  = r'^Total\s+([\d,]+\.\d+)\s+100\.00%\s+([\d,]+\.\d+)\s+100\.00%$'

SUMMARY_FOR_HDR = r'^Summary\s+for\s+(.+?)\s*$'
SUMMARY_KV_ROW  = r'^(Line Item Total|California Lumber Assessment Fee|Material Sales Tax|Subtotal|Overhead|Profit|Replacement Cost Value|Net Claim|Less Deductible|Less Amount Over Limit\(s\))\s+\$?([\d,]+\.[\d]+)$'
SUMMARY_NET_CLAIM_ROW = r'^Net\s+Claim\s+\$?([\d,]+\.[\d]+)\s*$'

RECAP_TAX_OP_HDR = r'^Recap\s+of\s+Taxes,\s+Overhead\s+and\s+Profit\s*$'
RECAP_TAX_OP_TOTAL_ROW = r'^Total\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)$'
RECAP_BY_ROOM_HDR = r'^Recap\s+by\s+Room\s*$'
RECAP_BY_CATEGORY_HDR = r'^Recap\s+by\s+Category\s*$'
RECAP_LINE_PATTERN = r'^([A-Za-z0-9/_\-\.\s\(\),&\']+?)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$'
RECAP_COVERAGE_SPLIT = r'^Coverage:\s+(.+?)\s+@?\s*(\d{1,3}\.\d{2})%?\s*=\s*([\d,]+\.\d+)$'
RECAP_SUBTOTAL_PATTERN = r'^(?:Area\s+Subtotal:|O&P Items Subtotal|Non-O&P Items Subtotal|Subtotal of Areas|Total)\s+([\d,]+\.\d+)\s+(\d{1,3}\.\d{2})%$'

__all__ = [
    'PAGE_NUMBER_PATTERN',
    'SINGLE_PAGE_NUMBER_PATTERN',
    'SECTION_HEIGHT_PATTERN',
    'SECTION_NAME_EXTRACTION',
    'SUBROOM_PATTERN',
    'TABLE_HEADER_PRIMARY',
    'TABLE_HEADER_CONTINUATION',
    'TABLE_HEADER_SECOND_LINE_FRAGMENT',
    'LINE_ITEM_PATTERN',
    'LINE_ITEM_HEADER_PATTERN',
    'CFINAL_ITEM_PATTERN',
    'CALC_PREFIX_PATTERN',
    'CALC_LINE_DETECTION_PATTERN',
    'QTY_UNIT_PATTERN',
    'BRACKETS_PATTERN',
    'CURRENCY_PATTERN',
    'SEE_PATTERN',
    'TERMINAL_STATUS_PATTERN',
    'HEADER_VARIANTS',
    'METADATA_PATTERNS',
    'DOOR_PATTERN',
    'MISSING_WALL_PATTERN',
    'WINDOW_PATTERN',
    'TOTALS_PATTERN',
    'CASE_LINE1_PATTERN',
    'COVERAGE_SECTION_PATTERN',
    'COVERAGE_ROW_PATTERN',
    'PROPERTY_ADDRESS_PATTERN',
    'DATE_LINE1_PATTERN',
    'DATE_LINE2_PATTERN',
    'PRICE_LIST_PATTERN',
    'DEPREC_LINE2_PATTERN',
    'ESTIMATE_LINE_PATTERN',
    'SF_INSURED_PATTERN',
    'SF_PRICE_LIST_PATTERN',
    'SF_PROPERTY_PATTERN',
    'REPEATED_CHAR_PATTERN',
    'QUOTE_PATTERN',
    'LABOR_MIN_APPLIED_PATTERN',
    'LINE_ITEM_TOTALS_PATTERN',
    'ADD_CHARGE_ROW_PATTERN',
    'ADD_CHARGES_HDR_PATTERN',
    'ADD_CHARGES_TOTAL_PATTERN',
    'GRAND_TOTAL_AREAS_HDR',
    'COVERAGE_TABLE_ROW',
    'COVERAGE_TOTAL_ROW',
    'SUMMARY_FOR_HDR',
    'SUMMARY_KV_ROW',
    'SUMMARY_NET_CLAIM_ROW',
    'RECAP_TAX_OP_HDR',
    'RECAP_TAX_OP_TOTAL_ROW',
    'RECAP_BY_ROOM_HDR',
    'RECAP_BY_CATEGORY_HDR',
    'RECAP_LINE_PATTERN',
    'RECAP_COVERAGE_SPLIT',
    'RECAP_SUBTOTAL_PATTERN',
]
