"""CLI entry point for the PDF preflight pipeline."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from .pdf_preflight import PDFPreflight

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize PDFs ahead of parsing")
    parser.add_argument("input_pdf", type=Path, help="Input PDF to preflight")
    parser.add_argument(
        "--output",
        "-o",
        dest="output_pdf",
        type=Path,
        help="Path for the cleaned PDF (defaults to <input>_preflight.pdf)",
    )
    parser.add_argument(
        "--report",
        "-r",
        dest="report_path",
        type=Path,
        help="Optional JSON report path (defaults to alongside the output PDF)",
    )
    parser.add_argument(
        "--sample-lines",
        type=int,
        default=25,
        help="Number of lines per page to sample for corruption heuristics",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    preflight = PDFPreflight(max_sample_lines=args.sample_lines)
    result = preflight.process(
        args.input_pdf,
        output_pdf=args.output_pdf,
        report_path=args.report_path,
    )

    print(json.dumps(result.report.to_dict(), indent=2))
    if result.report_path:
        logger.info("Report written to %s", result.report_path)
    logger.info("Cleaned PDF written to %s", result.output_pdf)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
