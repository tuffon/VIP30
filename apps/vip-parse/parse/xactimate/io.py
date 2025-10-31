"""I/O helpers for the Xactimate rough draft parser."""

from __future__ import annotations

import json
import os
from typing import Iterable, List

import pdfplumber

from .helpers import format_money


class ParserIO:
    """Handle file-system interactions and console output for the parser."""

    def __init__(self, input_file: str, output_path: str):
        self.input_file = os.path.abspath(input_file)
        self.output_path = output_path
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(self.input_file)
        self._resolve_outputs()

    # ---- paths ---------------------------------------------------------

    def _resolve_outputs(self) -> None:
        in_stem = os.path.splitext(os.path.basename(self.input_file))[0]
        out = self.output_path
        if os.path.isdir(out):
            base = os.path.join(out, in_stem)
            self.out_path = base + '.out'
            self.json_path = base + '.json'
        else:
            out = os.path.abspath(out)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            if os.path.splitext(out)[1] == '':
                out = out + '.json'
            self.json_path = out
            self.out_path = os.path.splitext(out)[0] + '.out'
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)

    # ---- reading -------------------------------------------------------

    def read_full_text_lines(self) -> List[str]:
        lines: List[str] = []
        with pdfplumber.open(self.input_file) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ''
                lines.extend([l.strip() for l in txt.split('\n') if l.strip()])
        return lines

    def read_first_page_lines(self) -> List[str]:
        lines: List[str] = []
        with pdfplumber.open(self.input_file) as pdf:
            if pdf.pages:
                txt = pdf.pages[0].extract_text() or ''
                lines.extend([l.strip() for l in txt.split('\n') if l.strip()])
        return lines

    # ---- writing -------------------------------------------------------

    def write_raw_lines(self, lines: Iterable[str]) -> None:
        with open(self.out_path, 'w', encoding='utf-8') as f:
            for line in lines:
                f.write(f"{line}\n")

    def write_json(self, payload: dict) -> None:
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    # ---- console output ------------------------------------------------

    def print_doc_delta_table(self, pdf_file: str, rows: List[dict], total_sections: int) -> None:
        print(f"\n▶ Doc: {pdf_file}")
        if not rows:
            print("  - No non-zero deltas.")
            print(f"  ➜ {self.json_path}")
            return
        name_w = 42
        amt_w = 16
        header = f"{'Section':{name_w}}{'Declared':>{amt_w}}{'Computed':>{amt_w}}{'Δ (Decl-Comp)':>{amt_w}}"
        print(f"  {header}")
        print("  " + "-" * (name_w + amt_w * 3))
        for row in rows:
            declared = format_money(row['declared'])
            computed = format_money(row['computed'])
            delta = format_money(row['delta'])
            print("  " + f"{row['name'][:name_w]:{name_w}}{declared:>{amt_w}}{computed:>{amt_w}}{delta:>{amt_w}}")
        print(f"  (sections with deltas: {len(rows)} / total sections: {total_sections})")
        print(f"  ➜ {self.json_path}")

    def print_doc_validation_table(self, validations: dict) -> None:
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
        for key, label in keys:
            if key in validations and validations[key] is not None:
                print("  " + f"{label:{name_w}}{validations[key]:>{val_w}}")


__all__ = ['ParserIO']
