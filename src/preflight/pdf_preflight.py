"""PDF preflight pipeline that sanitizes text layers prior to parsing."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pdfplumber

from .analysis import LineAnalysis, score_page_lines
from .ocr import AutoOCRProcessor, OCRProcessor

logger = logging.getLogger(__name__)


@dataclass
class PageAnalysisResult:
    """Outcome of analysing a single page."""

    page_number: int
    lines: List[LineAnalysis] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)

    @property
    def needs_ocr(self) -> bool:
        return bool(self.flags)


@dataclass
class PreflightReport:
    """JSON-serialisable report produced by the preflight run."""

    input_pdf: str
    output_pdf: str
    pages_scanned: int
    pages_ocrd: int
    page_reports: List[Dict[str, object]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "input_pdf": self.input_pdf,
            "output_pdf": self.output_pdf,
            "pages_scanned": self.pages_scanned,
            "pages_re_ocrd": self.pages_ocrd,
            "page_reports": self.page_reports,
        }


@dataclass
class PreflightResult:
    output_pdf: Path
    report: PreflightReport
    report_path: Optional[Path] = None


class PDFPreflight:
    """Run upstream PDF cleanup prior to invoking downstream parsers."""

    def __init__(
        self,
        *,
        max_sample_lines: int = 25,
        ocr_processor: Optional[OCRProcessor] = None,
    ) -> None:
        self.max_sample_lines = max_sample_lines
        self.ocr_processor = ocr_processor or AutoOCRProcessor()

    def process(
        self,
        input_pdf: Path,
        output_pdf: Optional[Path] = None,
        report_path: Optional[Path] = None,
    ) -> PreflightResult:
        input_pdf = Path(input_pdf)
        if output_pdf is None:
            output_pdf = input_pdf.with_name(f"{input_pdf.stem}_preflight.pdf")
        else:
            output_pdf = Path(output_pdf)

        if report_path is None:
            report_path = output_pdf.with_suffix(".json")
        else:
            report_path = Path(report_path)

        logger.info("Running PDF preflight on %s", input_pdf)
        page_results = self._scan_pdf(input_pdf)
        pages_to_ocr = [res.page_number for res in page_results if res.needs_ocr]
        logger.info("Identified %d/%d page(s) requiring OCR", len(pages_to_ocr), len(page_results))

        self.ocr_processor.process(input_pdf, output_pdf, pages_to_ocr)

        report = self._build_report(input_pdf, output_pdf, page_results)
        if report_path is not None:
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report.to_dict(), fh, indent=2)

        return PreflightResult(output_pdf=output_pdf, report=report, report_path=report_path)

    def _scan_pdf(self, input_pdf: Path) -> List[PageAnalysisResult]:
        results: List[PageAnalysisResult] = []
        with pdfplumber.open(str(input_pdf)) as pdf:
            for index, page in enumerate(pdf.pages):
                page_number = index + 1
                text = page.extract_text(layout=True) or ""
                page_result = PageAnalysisResult(page_number=page_number)

                if not text.strip():
                    page_result.flags.append("no_text_layer")
                    results.append(page_result)
                    continue

                line_results = score_page_lines(text.splitlines(), self.max_sample_lines)
                page_result.lines.extend(line_results)

                aggregated_flags: List[str] = []
                for analysis in line_results:
                    aggregated_flags.extend(analysis.flags)

                if aggregated_flags:
                    # deduplicate while preserving order
                    seen = set()
                    deduped: List[str] = []
                    for flag in aggregated_flags:
                        if flag not in seen:
                            deduped.append(flag)
                            seen.add(flag)
                    page_result.flags.extend(deduped)

                results.append(page_result)

        return results

    def _build_report(
        self,
        input_pdf: Path,
        output_pdf: Path,
        page_results: Sequence[PageAnalysisResult],
    ) -> PreflightReport:
        page_entries: List[Dict[str, object]] = []
        for result in page_results:
            page_entries.append(
                {
                    "page": result.page_number,
                    "flags": result.flags,
                    "lines": [
                        {
                            "text": analysis.metrics.line,
                            "flags": analysis.flags,
                            "metrics": {
                                "duplicate_run_ratio": analysis.metrics.duplicate_run_ratio,
                                "alpha_digit_ratio": analysis.metrics.alpha_digit_ratio,
                                "readability": analysis.metrics.readability_scores,
                            },
                        }
                        for analysis in result.lines
                    ],
                }
            )

        return PreflightReport(
            input_pdf=str(input_pdf),
            output_pdf=str(output_pdf),
            pages_scanned=len(page_results),
            pages_ocrd=sum(1 for res in page_results if res.needs_ocr),
            page_reports=page_entries,
        )
