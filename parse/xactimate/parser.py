"""Core parser implementation for the Xactimate rough draft output."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from .constants import *  # noqa: F401,F403
from .helpers import (
    ParseState,
    TableColumns,
    extract_metadata_from_line,
    format_dollar_amount,
    is_diagram_artifact,
    is_line_item,
    is_line_item_header,
    is_page_header,
    is_subroom_header,
    is_table_continuation,
    is_table_header,
    is_totals_line,
    merge_metadata,
    money_to_float,
    parse_datetime_string,
    parse_item_codes,
    round2,
)
from .io import ParserIO


class XactimateRoughDraftParser:
    def __init__(self, input_file: str, output_path: str, debug: bool = False):
        self.io = ParserIO(input_file, output_path)
        self.input_file = self.io.input_file
        self.debug = bool(debug)

    # ---------- public ----------
    def run(self) -> None:
        # full text (once)
        full_lines = self.io.read_full_text_lines()

        # pre-pass recap-by-category (non-sequential)
        recap_cat, recap_cat_spans = self._prepass_recap_by_category(full_lines)

        # end-of-doc structured (but we will not clobber recap_by_category if prepass found it)
        end = self._parse_end_structured(full_lines)

        # unified skip mask for sequential parsing
        all_spans = recap_cat_spans + (end.get("_skip_spans") or [])
        skip_mask = self._build_skip_mask(len(full_lines), all_spans)

        # sequential parse using full_lines and unified skip_mask
        sections, _ = self._parse_document_from_lines(full_lines, skip_mask=skip_mask)

        # front-page metadata
        case_md = self._parse_case_metadata(self.io.read_first_page_lines())
        if recap_cat and (recap_cat.get("subtotals") or any(k for k in recap_cat.keys() if k != "subtotals")):
            end["recap_by_category"] = recap_cat

        # per-section validations
        table_rows = []
        per_section_validations = []
        for section in sections:
            computed = round2(self._section_computed_total(section))
            declared_str = section.get('section_totals', {}).get('total', '0.00')
            declared = round2(money_to_float(declared_str))
            delta = round2(declared - computed)
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
        self.io.write_raw_lines(full_lines)

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
        self.io.write_json(payload)

        # console tables
        pdf_name = Path(self.input_file).name
        self.io.print_doc_delta_table(pdf_name, table_rows, len(sections))
        if self.debug:
            self.io.print_doc_validation_table(doc_validations)

    # ---------- internals ----------

    def _section_computed_total(self, section: dict) -> float:
        return sum(
            money_to_float(li.get('total'))
            for li in section.get('line_items', [])
            if li.get('type') == 'line_item' and li.get('total') is not None
        )

    # ---------- core parsing (from provided full_lines) ----------
    def _parse_document_from_lines(self, full_lines: List[str], skip_mask: Optional[List[bool]] = None) -> tuple:
        # header detection needs the original PDF normally; we approximate by filtering number-only and page-lines later.
        # We still try to skip page headers via simple heuristics present in helpers.
        header_patterns: List[str] = []  # unknown without page context; rely on PAGE_NUMBER_PATTERN, etc.

        lines = full_lines  # use the same list to keep indexing aligned for skip_mask
        state = ParseState.LOOKING_FOR_SECTION
        sections: List[dict] = []
        current_section = None
        current_subroom = None
        current_line_item = None
        collecting_notes = False
        columns = TableColumns()
        pending_header_lines: List[str] = []

        i = 0
        L = len(lines)
        while i < L:
            # global skips
            if skip_mask is not None and 0 <= i < len(skip_mask) and skip_mask[i]:
                i += 1
                continue
            if is_page_header(lines[i].strip(), header_patterns):
                i += 1
                continue

            line = lines[i].strip()
            next_line = lines[i + 1].strip() if i + 1 < L else None

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
                    if i > 0 and not is_page_header(lines[i-1].strip(), header_patterns):
                        prev = lines[i-1].strip()
                        nm = re.search(SECTION_NAME_EXTRACTION, prev)
                        section_name = nm.group(1).strip() if nm else prev
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
                    if i < L:
                        n2 = lines[i + 1].strip() if i + 1 < L else None
                        is_header, new_cols, is_two = is_table_header(lines[i].strip(), n2)
                        if is_header:
                            columns = new_cols
                            i += 2 if is_two else 1
                    continue

                if is_totals_line(line, current_section['section_name'] if current_section else None):
                    self._attach_pending_notes(current_line_item, pending_header_lines)
                    if collecting_notes and current_line_item:
                        current_section['line_items'].append(self._finalize_line_item(current_line_item))
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
                    self._attach_pending_notes(current_line_item, pending_header_lines)
                    if collecting_notes and current_line_item:
                        current_section['line_items'].append(self._finalize_line_item(current_line_item))
                        current_line_item = None
                    collecting_notes = False
                    current_section['line_items'].append({'type': 'header', 'text': header_text})
                    i += 1; continue

                new_line_item, start_collecting = self._try_start_line_item(line, columns)
                if new_line_item:
                    self._attach_pending_notes(current_line_item, pending_header_lines)
                    if current_line_item:
                        current_section['line_items'].append(self._finalize_line_item(current_line_item))
                        current_line_item = None
                        collecting_notes = False
                    current_line_item = new_line_item
                    collecting_notes = start_collecting
                    i += 1; continue

                if current_line_item and columns.family == 'B' and re.search(CALC_LINE_DETECTION_PATTERN, line):
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

        if current_line_item and current_section:
            self._attach_pending_notes(current_line_item, pending_header_lines)
            current_section['line_items'].append(self._finalize_line_item(current_line_item))
        if current_section:
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
                'total': format_dollar_amount(0.0), 'total_note': 'SEE ' + m.group(5).strip().upper()
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
                res['reset']   = format_dollar_amount(money_to_float(g[idx]));   res['remove'] = format_dollar_amount(money_to_float(g[idx+1])); res['replace'] = format_dollar_amount(money_to_float(g[idx+2])); idx += 3
                if columns.has_tax and columns.has_op:
                    res['tax'] = format_dollar_amount(money_to_float(g[idx])); res['op'] = format_dollar_amount(money_to_float(g[idx+1])); res['total'] = format_dollar_amount(money_to_float(g[idx+2]))
                elif columns.has_tax:
                    res['tax'] = format_dollar_amount(money_to_float(g[idx])); res['op'] = None; res['total'] = format_dollar_amount(money_to_float(g[idx+1]))
                elif columns.has_op:
                    res['tax'] = None; res['op'] = format_dollar_amount(money_to_float(g[idx])); res['total'] = format_dollar_amount(money_to_float(g[idx+1]))
                else:
                    res['tax'] = None; res['op'] = None; res['total'] = format_dollar_amount(money_to_float(g[idx]))
                return res

            full_b = base + CURRENCY_PATTERN + r'\s*\+\s*' + CURRENCY_PATTERN + r'\s*=\s*' + tail(columns.has_tax, columns.has_op)
            mb = re.search(full_b, calc_line)
            if mb:
                g, idx = mb.groups(), 0
                codes_str = g[3] or ''
                res = {'calc': (g[idx] or '').strip(), 'qty': float(g[idx+1]), 'unit': g[idx+2],
                       'item_codes': parse_item_codes(codes_str), 'reset': None}
                idx += 4
                res['remove'] = format_dollar_amount(money_to_float(g[idx])); res['replace'] = format_dollar_amount(money_to_float(g[idx+1])); idx += 2
                if columns.has_tax and columns.has_op:
                    res['tax'] = format_dollar_amount(money_to_float(g[idx])); res['op'] = format_dollar_amount(money_to_float(g[idx+1])); res['total'] = format_dollar_amount(money_to_float(g[idx+2]))
                elif columns.has_tax:
                    res['tax'] = format_dollar_amount(money_to_float(g[idx])); res['op'] = None; res['total'] = format_dollar_amount(money_to_float(g[idx+1]))
                elif columns.has_op:
                    res['tax'] = None; res['op'] = format_dollar_amount(money_to_float(g[idx])); res['total'] = format_dollar_amount(money_to_float(g[idx+1]))
                else:
                    res['tax'] = None; res['op'] = None; res['total'] = format_dollar_amount(money_to_float(g[idx]))
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
                res['remove'] = format_dollar_amount(money_to_float(g[idx])); res['replace'] = format_dollar_amount(money_to_float(g[idx+1])); idx += 2
                if columns.has_tax and columns.has_op:
                    res['tax'] = format_dollar_amount(money_to_float(g[idx])); res['op'] = format_dollar_amount(money_to_float(g[idx+1])); res['total'] = format_dollar_amount(money_to_float(g[idx+2]))
                elif columns.has_tax:
                    res['tax'] = format_dollar_amount(money_to_float(g[idx])); res['op'] = None; res['total'] = format_dollar_amount(money_to_float(g[idx+1]))
                elif columns.has_op:
                    res['tax'] = None; res['op'] = format_dollar_amount(money_to_float(g[idx])); res['total'] = format_dollar_amount(money_to_float(g[idx+1]))
                else:
                    res['tax'] = None; res['op'] = None; res['total'] = format_dollar_amount(money_to_float(g[idx]))
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
                        'total': format_dollar_amount(0.0), 'total_note': note
                    }
        return {}

    def _attach_pending_notes(self, current_line_item: Optional[dict], pending: List[str]) -> None:
        if current_line_item is None or not pending:
            return
        note_text = ' '.join(pending).strip()
        pending.clear()
        if not note_text:
            return
        existing = current_line_item.get('notes') or ''
        current_line_item['notes'] = f"{existing} {note_text}".strip() if existing else note_text

    def _try_start_line_item(self, line: str, columns: TableColumns) -> Tuple[Optional[dict], bool]:
        if columns.family == 'A':
            item = self._parse_layout_a_line(line, columns)
            return (item, True) if item else (None, False)
        m = re.match(LINE_ITEM_PATTERN, line)
        if not m:
            return None, False
        item = {
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
        return item, False

    def _parse_layout_a_line(self, line: str, columns: TableColumns) -> Optional[dict]:
        raw = line.strip()
        if not raw:
            return None
        if raw.startswith('*'):
            raw = raw[1:].strip()
        m = re.match(r'^(\d+)\.\s+(.*)$', raw)
        if not m:
            return None
        number = int(m.group(1))
        remainder = m.group(2).strip()
        if not remainder:
            return None
        tokens = remainder.split()
        if len(tokens) < 2:
            return None
        num_pattern = re.compile(r'^[\d,]+(?:\.\d+)?$')
        numeric_tokens: List[str] = []
        while tokens and num_pattern.match(tokens[-1]):
            numeric_tokens.append(tokens.pop())
        required_numeric = 3 if columns.has_tax else 2
        if len(numeric_tokens) < required_numeric:
            return None
        total_token = numeric_tokens[0]
        tax_token = numeric_tokens[1] if columns.has_tax else None
        qty_unit_token = tokens.pop() if tokens else ''
        qty_match = re.match(r'^([\d,]+(?:\.\d+)?)([A-Z%]+)$', qty_unit_token)
        if not qty_match and tokens:
            prev = tokens.pop()
            qty_match = re.match(r'^([\d,]+(?:\.\d+)?)([A-Z%]+)$', prev + qty_unit_token)
        if not qty_match:
            return None
        qty_str = qty_match.group(1)
        unit = qty_match.group(2)
        description = ' '.join(tokens).strip()
        if not description:
            return None
        item = {
            'type': 'line_item',
            'line_number': number,
            'description': description,
            'qty': float(money_to_float(qty_str)),
            'unit': unit.upper(),
            'total': format_dollar_amount(money_to_float(total_token)),
            'total_note': None,
            'notes': ''
        }
        if columns.has_tax:
            item['tax'] = format_dollar_amount(money_to_float(tax_token))
        return item

    def _finalize_line_item(self, item: dict) -> dict:
        if not item:
            return item
        if isinstance(item.get('notes'), str):
            item['notes'] = item['notes'].strip()
        cleaned: Dict[str, object] = {}
        for key, value in item.items():
            if key == 'notes':
                if isinstance(value, str) and value.strip():
                    cleaned[key] = value.strip()
                continue
            if value is None:
                continue
            if isinstance(value, str):
                trimmed = value.strip()
                if not trimmed:
                    continue
                cleaned[key] = trimmed
                continue
            if isinstance(value, list):
                if value:
                    cleaned[key] = value
                continue
            cleaned[key] = value
        return cleaned

    def _parse_totals_line(self, totals_line: str, columns: TableColumns) -> dict:
        if columns.has_tax and columns.has_op:
            m = re.search(r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$', totals_line, re.IGNORECASE)
            if m:
                return {
                    'tax': format_dollar_amount(money_to_float(m.group(1))),
                    'op': format_dollar_amount(money_to_float(m.group(2))),
                    'total': format_dollar_amount(money_to_float(m.group(3)))
                }
        elif columns.has_tax:
            m = re.search(r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$', totals_line, re.IGNORECASE)
            if m:
                return {
                    'tax': format_dollar_amount(money_to_float(m.group(1))),
                    'op': None,
                    'total': format_dollar_amount(money_to_float(m.group(2)))
                }
        elif columns.has_op:
            m = re.search(r'Totals?:.*?([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$', totals_line, re.IGNORECASE)
            if m:
                return {
                    'tax': None,
                    'op': format_dollar_amount(money_to_float(m.group(1))),
                    'total': format_dollar_amount(money_to_float(m.group(2)))
                }
        else:
            m = re.search(r'Totals?:.*?([\d,]+\.\d+)\s*$', totals_line, re.IGNORECASE)
            if m:
                return {
                    'tax': None,
                    'op': None,
                    'total': format_dollar_amount(money_to_float(m.group(1)))
                }
        # fallback inference
        nums = re.findall(r'[\d,]+\.\d+', totals_line)
        if nums:
            amounts = [format_dollar_amount(money_to_float(n)) for n in nums]
            res = {'tax': None, 'op': None, 'total': '0.00'}
            res['total'] = amounts[-1]
            if columns.has_op and len(amounts) >= 2: res['op'] = amounts[-2]
            if columns.has_tax and len(amounts) >= (3 if columns.has_op else 2):
                idx = -3 if columns.has_op else -2
                res['tax'] = amounts[idx]
            return res
        return {'tax': None, 'op': None, 'total': '0.00'}

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
        if not ranges:
            return mask

        normalized: List[Tuple[int, int]] = []
        for a, b in ranges:
            start = max(0, min(n_lines, a))
            end = max(0, min(n_lines, b))
            if start >= end:
                continue
            normalized.append((start, end))

        if not normalized:
            return mask

        normalized.sort()
        merged: List[Tuple[int, int]] = []
        for start, end in normalized:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        for start, end in merged:
            for i in range(start, end):
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
            return format_dollar_amount(money_to_float(re.sub(r"\s+", "", (x or "").replace("\u00A0", " "))))

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
            return format_dollar_amount(money_to_float(x))

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
                    "overhead": format_dollar_amount(money_to_float(tm.group(1))),
                    "profit": format_dollar_amount(money_to_float(tm.group(2))),
                    "material_sales_tax": format_dollar_amount(money_to_float(tm.group(3))),
                    "storage_rental_tax": format_dollar_amount(money_to_float(tm.group(4))),
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
                    "item_total": format_dollar_amount(money_to_float(m.group(2))),
                    "item_pct": float(m.group(3)),
                    "acv_total": format_dollar_amount(money_to_float(m.group(4))),
                    "acv_pct": float(m.group(5)),
                })
                i += 1
                continue
            m = re.match(COVERAGE_TOTAL_ROW, s)
            if m:
                cov["totals"] = {
                    "item_total": format_dollar_amount(money_to_float(m.group(1))),
                    "acv_total": format_dollar_amount(money_to_float(m.group(2))),
                }
                i += 1
                break
            if s.startswith(("Summary for ", "Recap ", "Estimate:", "Grand Total Areas")):
                break
            break
        return cov, i

    def _parse_summary_block(self, all_lines: List[str], start_idx: int) -> Tuple[Tuple[str, Dict[str, str]], int]:
        def gmoney(x: str) -> str:
            return format_dollar_amount(money_to_float(x))

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
            return format_dollar_amount(money_to_float(x))

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
            return format_dollar_amount(money_to_float(cleaned))

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
            return format_dollar_amount(money_to_float(m2.group(1))) if m2 else None

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
            return format_dollar_amount(money_to_float(x))

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

        result["_skip_spans"] = result.get("_skip_spans") or []
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

        sum_sections = round2(sum(money_to_float(li.get('total'))
                                   for sec in sections
                                   for li in sec.get('line_items', [])
                                   if li.get('type') == 'line_item' and li.get('total')))
        v['sum_sections'] = format_dollar_amount(sum_sections)

        grand_end = None
        if end.get('line_item_totals'):
            grand_end = money_to_float(end['line_item_totals']['grand_total'])
        elif end.get('coverage', {}).get('totals'):
            grand_end = money_to_float(end['coverage']['totals']['item_total'])
        if grand_end is not None:
            grand_end = round2(grand_end)
            v['end_grand_total'] = format_dollar_amount(grand_end)
            v['grand_total_vs_sections_delta'] = format_dollar_amount(round2(grand_end - sum_sections))

        summaries = end.get('summaries_by_coverage') or {}
        if summaries:
            sum_rcv = round2(sum(money_to_float(kv.get('Replacement Cost Value', '0.00'))
                                  for kv in summaries.values() if kv))
            v['sum_rcv_from_summaries'] = format_dollar_amount(sum_rcv)
            cov_tot = end.get('coverage', {}).get('totals')
            if cov_tot:
                cov_item_total = round2(money_to_float(cov_tot['item_total']))
                v['coverage_total_item'] = format_dollar_amount(cov_item_total)
                v['coverage_rcv_delta'] = format_dollar_amount(round2(cov_item_total - sum_rcv))

        rbc_subtotals = (end.get('recap_by_category') or {}).get('subtotals') or []
        rbc_total_val = None
        for row in rbc_subtotals:
            if row.get('label') == 'Total':
                rbc_total_val = row.get('total')
                break
        if rbc_total_val and grand_end is not None:
            rbc_val = round2(money_to_float(rbc_total_val))
            v['recap_category_total'] = format_dollar_amount(rbc_val)
            v['recap_vs_end_grand_delta'] = format_dollar_amount(round2(rbc_val - grand_end))

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
                        'deductible': format_dollar_amount(money_to_float(rm.group(2))),
                        'policy_limit': format_dollar_amount(money_to_float(rm.group(3))),
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
