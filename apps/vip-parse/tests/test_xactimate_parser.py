import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vip_parser.xactimate.helpers import TableColumns, is_table_header, money_to_float
from vip_parser.xactimate.parser import XactimateRoughDraftParser


def test_layout_a_header_detection():
    header = "DESCRIPTION QUANTITY UNIT PRICE TAX RCV"
    is_hdr, columns, is_two = is_table_header(header, None)
    assert is_hdr
    assert not is_two
    assert columns.family == 'A'
    assert columns.has_tax is True
    assert columns.headers_norm == ['DESCRIPTION', 'QUANTITY', 'UNIT', 'PRICE', 'TAX', 'RCV']


def test_layout_b_header_detection():
    top = "CAT SEL ACT DESCRIPTION"
    bottom = "CALC QTY RESET REMOVE REPLACE TAX O&P TOTAL"
    is_hdr, columns, is_two = is_table_header(top, bottom)
    assert is_hdr
    assert is_two
    assert columns.family == 'B'
    assert columns.has_reset is True
    assert columns.has_tax is True
    assert columns.has_op is True
    assert columns.headers_norm == [
        'CAT', 'SEL', 'ACT', 'DESCRIPTION', 'CALC', 'QTY',
        'RESET', 'REMOVE', 'REPLACE', 'TAX', 'O&P', 'TOTAL'
    ]


def test_layout_b_header_without_optional_columns():
    top = "CAT SEL ACT DESCRIPTION"
    bottom = "CALC QTY REMOVE REPLACE TAX TOTAL"
    is_hdr, columns, is_two = is_table_header(top, bottom)
    assert is_hdr
    assert is_two
    assert columns.family == 'B'
    assert columns.has_reset is False
    assert columns.has_op is False
    assert columns.has_tax is True


def _make_parser() -> XactimateRoughDraftParser:
    return XactimateRoughDraftParser.__new__(XactimateRoughDraftParser)


def test_total_note_from_see_reference():
    parser = _make_parser()
    columns = TableColumns(family='B', headers_norm=[], has_tax=True)
    calc_line = "6*6*8 288.00HR [CI] SEE LINE 7"
    result = parser._parse_line_item_calc(calc_line, columns)
    assert result['total'] == '0.00'
    assert result['total_note'] == 'SEE LINE 7'


def test_total_note_from_terminal_status():
    parser = _make_parser()
    columns = TableColumns(family='B', headers_norm=[], has_tax=False)
    calc_line = "2*2 4.00EA [NC] NO CHARGE"
    result = parser._parse_line_item_calc(calc_line, columns)
    assert result['total'] == '0.00'
    assert result['total_note'] == 'NO CHARGE'


def test_integration_headers_and_totals():
    parser = _make_parser()
    lines = [
        "Room A Height: 8'",
        "CAT SEL ACT DESCRIPTION",
        "CALC QTY REMOVE REPLACE TAX TOTAL",
        "1. ABC DEF + First item",
        "1*1 1.00EA 0.00+ 10.00 = 0.00 10.00",
        "---- Flooring ----",
        "2. ABC DEF + Second item",
        "2*1 1.00EA 0.00+ 5.00 = 0.00 5.00",
        "Prime before paint",
        "Totals: Room A 0.00 15.00",
        "Room B Height: 9'",
        "DESCRIPTION QUANTITY UNIT PRICE RCV",
        "1. Paint walls 10.00SF 1.00 10.00",
        "Add accent color",
        "Totals: Room B 10.00",
    ]

    sections, _ = parser._parse_document_from_lines(lines)
    assert len(sections) == 2

    first_section = sections[0]
    items = first_section['line_items']
    assert items[1] == {'type': 'header', 'text': 'Flooring'}
    first_line = items[0]
    second_line = items[2]
    assert 'op' not in first_line
    assert second_line['notes'] == 'Prime before paint'
    totals_sum = sum(money_to_float(li['total']) for li in items if li['type'] == 'line_item')
    assert math.isclose(totals_sum, 15.00, abs_tol=1e-6)
    assert first_section['section_totals']['total'] == '15.00'

    second_section = sections[1]
    assert len(second_section['line_items']) == 1
    layout_a_item = second_section['line_items'][0]
    assert layout_a_item['description'] == 'Paint walls'
    assert layout_a_item['qty'] == pytest.approx(10.0)
    assert layout_a_item['unit'] == 'SF'
    assert 'tax' not in layout_a_item
    assert layout_a_item['notes'] == 'Add accent color'
    assert second_section['section_totals']['total'] == '10.00'

    total_sections_sum = sum(
        money_to_float(li['total'])
        for section in sections
        for li in section['line_items']
        if li['type'] == 'line_item'
    )
    declared = sum(money_to_float(sec['section_totals']['total']) for sec in sections)
    assert math.isclose(total_sections_sum, declared, abs_tol=1e-6)


def test_height_line_creates_subroom_when_name_differs():
    parser = _make_parser()
    lines = [
        "Bathroom",
        "Bathroom 1 Height: 8' 5\"",
        "CAT SEL ACT DESCRIPTION",
        "CALC QTY REMOVE REPLACE TAX TOTAL",
        "1. ABC DEF + First item",
        "1*1 1.00EA 0.00+ 5.00 = 0.00 5.00",
        "Totals: Bathroom 0.00 5.00",
    ]

    sections, _ = parser._parse_document_from_lines(lines)
    assert len(sections) == 1
    section = sections[0]

    assert section['metadata'].get('height') is None
    assert len(section['subrooms']) == 1
    assert section['subrooms'][0]['subroom_name'] == 'Bathroom 1'
    assert section['subrooms'][0]['metadata'].get('height') == "8' 5\""


def test_section_with_dimension_prefix_keeps_metadata_on_section():
    parser = _make_parser()
    lines = [
        "20' 11\" Bedroom 2 Height: Sloped",
        "Door 10' X 6' 8\" Opens into Exterior",
        "Door 3' X 7' Opens into HALLWAY",
        "Door 3' X 8' Opens into BATHROOM_1",
        "Window 3' X 5' Opens into Exterior",
        "Window 3' X 5' Opens into Exterior",
        "5' 5\" Subroom: Closet 2 (1) Height: 8'",
        "Door 3' X 7' Opens into BEDROOM_2",
        "CAT SEL ACT DESCRIPTION",
        "CALC QTY REMOVE REPLACE TAX TOTAL",
        "1. ABC DEF + First item",
        "1*1 1.00EA 0.00+ 5.00 = 0.00 5.00",
        "Totals: Bedroom 2 0.00 5.00",
    ]

    sections, _ = parser._parse_document_from_lines(lines)
    assert len(sections) == 1
    section = sections[0]

    assert section['section_name'] == 'Bedroom 2'
    metadata = section['metadata']
    assert metadata.get('height') == 'Sloped'
    assert len(metadata.get('doors', [])) == 3
    assert len(metadata.get('windows', [])) == 2
    assert len(section['subrooms']) == 1
    sub = section['subrooms'][0]
    assert sub['subroom_name'] == 'Closet 2 (1)'
    assert sub['metadata'].get('height') == "8'"
