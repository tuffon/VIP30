"""OCR backends for PDF preflight."""
from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Sequence

try:  # pragma: no cover - exercised in production when dependency available
    from pypdf import PdfReader, PdfWriter
except Exception:  # pragma: no cover
    PdfReader = PdfWriter = None

logger = logging.getLogger(__name__)


class OCRProcessor(ABC):
    """Interface for producing normalized, single-layer PDFs."""

    @abstractmethod
    def process(self, input_pdf: Path, output_pdf: Path, pages_to_ocr: Sequence[int]) -> None:
        """Create ``output_pdf`` from ``input_pdf`` applying OCR where requested."""


class PassthroughOCRProcessor(OCRProcessor):
    """Fallback OCR processor that only copies the input file."""

    def process(self, input_pdf: Path, output_pdf: Path, pages_to_ocr: Sequence[int]) -> None:
        logger.warning(
            "PassthroughOCRProcessor used; PDF will not be normalized or OCR'd."
        )
        shutil.copyfile(input_pdf, output_pdf)


class OcrmypdfProcessor(OCRProcessor):
    """OCR processor that shells out to ``ocrmypdf``."""

    def __init__(self, executable: str = "ocrmypdf") -> None:
        if shutil.which(executable) is None:
            raise RuntimeError(
                "ocrmypdf executable not found on PATH; install ocrmypdf to enable preflight OCR"
            )
        if PdfReader is None or PdfWriter is None:
            raise RuntimeError("pypdf is required for ocrmypdf integration")
        self.executable = executable

    def process(self, input_pdf: Path, output_pdf: Path, pages_to_ocr: Sequence[int]) -> None:
        input_pdf = Path(input_pdf)
        output_pdf = Path(output_pdf)
        pages = sorted(set(int(p) for p in pages_to_ocr if p >= 1))

        if not pages:
            logger.info("No pages flagged; normalizing PDF via ocrmypdf")
            self._run_ocrmypdf(
                input_pdf,
                output_pdf,
                force_ocr=False,
            )
            return

        logger.info("Re-OCR'ing %d page(s) via ocrmypdf", len(pages))
        with TemporaryWorkdir() as tmp:
            normalized_pdf = tmp / "normalized.pdf"
            self._run_ocrmypdf(input_pdf, normalized_pdf, force_ocr=False)

            base_reader = PdfReader(str(normalized_pdf))
            writer = PdfWriter()
            total_pages = len(base_reader.pages)

            for page_index in range(total_pages):
                page_number = page_index + 1
                if page_number not in pages:
                    writer.add_page(base_reader.pages[page_index])
                    continue

                single_input = tmp / f"page_{page_number}_input.pdf"
                single_output = tmp / f"page_{page_number}_ocr.pdf"
                self._write_single_page(input_pdf, page_index, single_input)
                self._run_ocrmypdf(single_input, single_output, force_ocr=True)
                ocr_reader = PdfReader(str(single_output))
                writer.add_page(ocr_reader.pages[0])

            with output_pdf.open("wb") as fh:
                writer.write(fh)

    def _write_single_page(self, input_pdf: Path, zero_index: int, output_pdf: Path) -> None:
        reader = PdfReader(str(input_pdf))
        writer = PdfWriter()
        writer.add_page(reader.pages[zero_index])
        with output_pdf.open("wb") as fh:
            writer.write(fh)

    def _run_ocrmypdf(self, input_pdf: Path, output_pdf: Path, *, force_ocr: bool) -> None:
        cmd: List[str] = [self.executable, "--quiet", "--output-type", "pdfa"]
        if force_ocr:
            cmd.append("--force-ocr")
        else:
            cmd.append("--skip-text")
        cmd.extend([str(input_pdf), str(output_pdf)])
        logger.debug("Running %s", " ".join(cmd))
        subprocess.run(cmd, check=True)


class AutoOCRProcessor(OCRProcessor):
    """Select the best available OCR processor at runtime."""

    def __init__(self) -> None:
        try:
            self._delegate: OCRProcessor = OcrmypdfProcessor()
            logger.info("Using ocrmypdf for PDF preflight normalization")
        except Exception as exc:  # pragma: no cover - exercised in production
            logger.warning("Falling back to passthrough OCR: %s", exc)
            self._delegate = PassthroughOCRProcessor()

    def process(self, input_pdf: Path, output_pdf: Path, pages_to_ocr: Sequence[int]) -> None:
        self._delegate.process(input_pdf, output_pdf, pages_to_ocr)


class TemporaryWorkdir:
    """Context manager creating a temporary working directory."""

    def __enter__(self) -> Path:
        import tempfile

        self._tmpdir = Path(tempfile.mkdtemp(prefix="pdf-preflight-"))
        return self._tmpdir

    def __exit__(self, exc_type, exc, tb) -> None:
        import shutil

        if hasattr(self, "_tmpdir") and self._tmpdir.exists():
            shutil.rmtree(self._tmpdir, ignore_errors=True)
