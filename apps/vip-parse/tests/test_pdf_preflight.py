from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Iterable

import pytest

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from preflight.pdf_preflight import PDFPreflight
from preflight.ocr import OCRProcessingResult


class RecordingOCRProcessor:
    def __init__(self) -> None:
        self.calls: list[list[int]] = []

    def process(self, input_pdf: Path, output_pdf: Path, pages_to_ocr):
        self.calls.append(list(pages_to_ocr))
        shutil.copyfile(input_pdf, output_pdf)
        return OCRProcessingResult(
            backend="recording",
            pages_ocrd=list(pages_to_ocr),
            ocr_performed=bool(pages_to_ocr),
        )


@pytest.fixture
def stub_pdf(monkeypatch):
    class DummyPage:
        def __init__(self, text: str | None) -> None:
            self._text = text

        def extract_text(self, layout: bool = True):  # noqa: D401 - signature matches pdfplumber
            return self._text

    class DummyPDF:
        def __init__(self, pages: Iterable[str | None]) -> None:
            self.pages = [DummyPage(text) for text in pages]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _apply(pages: Iterable[str | None]) -> None:
        monkeypatch.setattr(pdfplumber, "open", lambda _: DummyPDF(pages))

    return _apply


def _touch_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.4\n%\xff\xff\xff\xff\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")
    return path


def test_corrupted_page_triggers_ocr(tmp_path: Path, stub_pdf):
    stub_pdf([
        "Totals: Guest Room 1.58 2,360.75",
        "TToottaallss:: GGuueesstt RRoomm",
    ])
    input_pdf = _touch_pdf(tmp_path / "input.pdf")
    processor = RecordingOCRProcessor()
    preflight = PDFPreflight(max_sample_lines=10, ocr_processor=processor)

    report_path = tmp_path / "report.json"
    preflight.process(input_pdf, report_path=report_path)

    assert processor.calls == [[2]]
    report = json.loads(report_path.read_text())
    flagged_page = next(page for page in report["page_reports"] if page["page"] == 2)
    assert "duplicate_char_runs" in flagged_page["flags"]


def test_clean_pdf_skips_ocr(tmp_path: Path, stub_pdf):
    stub_pdf([
        "Totals: Guest Room 1.58 2,360.75",
        "Grand Totals: Living Room 2.33 4,120.15",
    ])
    input_pdf = _touch_pdf(tmp_path / "input.pdf")
    processor = RecordingOCRProcessor()
    preflight = PDFPreflight(max_sample_lines=10, ocr_processor=processor)

    result = preflight.process(input_pdf)
    assert processor.calls == [[]]
    assert result.report.pages_ocrd == 0


def test_digit_burst_flag(tmp_path: Path, stub_pdf):
    stub_pdf([
        "Totals: Guest Room 1.58 2,360.75",
        "Room[[123456]] status",
    ])
    input_pdf = _touch_pdf(tmp_path / "input.pdf")
    processor = RecordingOCRProcessor()
    preflight = PDFPreflight(max_sample_lines=10, ocr_processor=processor)

    preflight.process(input_pdf)
    assert processor.calls == [[2]]


def test_blank_page_sets_no_text_flag(tmp_path: Path, stub_pdf):
    stub_pdf([
        None,
        "Totals: Guest Room 1.58 2,360.75",
    ])
    input_pdf = _touch_pdf(tmp_path / "input.pdf")
    processor = RecordingOCRProcessor()
    preflight = PDFPreflight(max_sample_lines=10, ocr_processor=processor)

    result = preflight.process(input_pdf)
    assert processor.calls == [[1]]
    first_page = result.report.page_reports[0]
    assert "no_text_layer" in first_page["flags"]


def test_cli_entry(monkeypatch, tmp_path: Path, stub_pdf):
    stub_pdf([])
    input_pdf = _touch_pdf(tmp_path / "input.pdf")

    class DummyPreflight:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def process(self, input_pdf: Path, output_pdf: Path | None = None, report_path: Path | None = None):
            report = {
                "input_pdf": str(input_pdf),
                "output_pdf": str(output_pdf or input_pdf.with_name(f"{input_pdf.stem}_preflight.pdf")),
                "pages_scanned": 0,
                "pages_re_ocrd": 0,
                "ocr_backend": "dummy",
                "ocr_performed": False,
                "page_reports": [],
            }
            out_pdf = output_pdf or input_pdf.with_name(f"{input_pdf.stem}_preflight.pdf")
            shutil.copyfile(input_pdf, out_pdf)
            report_path = report_path or out_pdf.with_suffix(".json")
            report_path.write_text(json.dumps(report))

            class Result:
                def __init__(self, output_pdf, report_path, report):
                    self.output_pdf = output_pdf
                    self.report_path = report_path
                    self.report = type("R", (), {"to_dict": lambda self: report})()

            return Result(out_pdf, report_path, report)

    from preflight import cli as preflight_cli

    monkeypatch.setattr(preflight_cli, "PDFPreflight", lambda **kwargs: DummyPreflight(**kwargs))

    out_path = tmp_path / "out.pdf"
    report_path = tmp_path / "out.json"
    rc = preflight_cli.main([str(input_pdf), "--output", str(out_path), "--report", str(report_path)])
    assert rc == 0
    assert out_path.exists()
    assert report_path.exists()
