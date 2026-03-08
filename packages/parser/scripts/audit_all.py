#!/usr/bin/env python3
"""
Audit runner — invoke XactimateRoughDraftParser on all docs PDFs.

Run from project root:
    python packages/parser/scripts/audit_all.py

Output:
    packages/parser/audit_output/<type>/<stem>.json  — parser output per PDF
    packages/parser/audit_output/run_log.json        — per-file success/failure summary
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# On Windows the default stdout encoding (cp1252) cannot represent the ▶
# character used in the parser's delta table. Reconfigure to UTF-8 so
# parser.run() does not raise UnicodeEncodeError on Windows.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
# scripts/ -> parser/ -> packages/ -> project root
PROJECT_ROOT = SCRIPT_DIR / ".." / ".." / ".."
PROJECT_ROOT = PROJECT_ROOT.resolve()

AUDIT_OUT = PROJECT_ROOT / "packages" / "parser" / "audit_output"

# ---------------------------------------------------------------------------
# Document registry
# ---------------------------------------------------------------------------

DOCS: dict[str, list[str]] = {
    "rough-drafts": [
        "docs/rough-drafts/1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.pdf",
        "docs/rough-drafts/KALYVAS_JVB_V6_KALY2_ROUGH_DRAFT_CAR.pdf",
    ],
    "final-drafts": [
        "docs/final-drafts/BSchacter-02.12.26-Est-JVB-RepairEstimate-$809,464.83.pdf",
    ],
    "final-drafts/statefarm": [
        "docs/final-drafts/statefarm/Customer Copy Final Draft (3).pdf",
        "docs/final-drafts/statefarm/Estimate SF Structural damage Lachman 4.15.2025.pdf",
        "docs/final-drafts/statefarm/Kalyvas Preliminary State Farm estimate9-25-25.pdf",
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_line_items(payload: dict) -> int:
    """Return total line item count across all sections."""
    total = 0
    sections = payload.get("sections") or []
    for section in sections:
        items = section.get("line_items") or []
        total += len(items)
    return total


def _print_summary_table(results: list[dict]) -> None:
    col_w = [50, 8, 8, 8]
    header = (
        f"{'File':<{col_w[0]}}"
        f"{'Status':>{col_w[1]}}"
        f"{'Sections':>{col_w[2]}}"
        f"{'Items':>{col_w[3]}}"
    )
    sep = "-" * sum(col_w)
    print(f"\n{'Audit Results':^{sum(col_w)}}")
    print(sep)
    print(header)
    print(sep)
    for r in results:
        fname = os.path.basename(r["file"])[:col_w[0]]
        status = r["status"]
        sections = str(r.get("sections_count", "-"))
        items = str(r.get("line_items_total", "-"))
        print(
            f"{fname:<{col_w[0]}}"
            f"{status:>{col_w[1]}}"
            f"{sections:>{col_w[2]}}"
            f"{items:>{col_w[3]}}"
        )
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        stream=sys.stderr,
    )

    # Ensure parser package is importable
    sys.path.insert(0, str(PROJECT_ROOT / "packages" / "parser"))

    from vip_parser.xactimate import XactimateRoughDraftParser  # noqa: PLC0415

    AUDIT_OUT.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    total_files = sum(len(v) for v in DOCS.values())

    for doc_type, pdf_rel_paths in DOCS.items():
        out_dir = AUDIT_OUT / doc_type
        out_dir.mkdir(parents=True, exist_ok=True)

        for rel_path in pdf_rel_paths:
            pdf_path = PROJECT_ROOT / rel_path
            file_label = rel_path

            if not pdf_path.exists():
                results.append(
                    {
                        "file": file_label,
                        "type": doc_type,
                        "status": "error",
                        "error": f"File not found: {pdf_path}",
                        "traceback": None,
                    }
                )
                print(f"  [MISSING] {file_label}")
                continue

            print(f"  [PARSE]   {file_label} ...", flush=True)
            try:
                parser = XactimateRoughDraftParser(
                    str(pdf_path), str(out_dir), debug=True
                )
                parser.run()

                # Determine output JSON path
                stem = pdf_path.stem
                json_path = out_dir / f"{stem}.json"
                json_path_str = str(json_path)

                sections_count = 0
                line_items_total = 0
                if json_path.exists():
                    try:
                        with json_path.open("r", encoding="utf-8") as f:
                            payload = json.load(f)
                        sections = payload.get("sections") or []
                        sections_count = len(sections)
                        line_items_total = _count_line_items(payload)
                    except Exception:  # noqa: BLE001
                        pass

                results.append(
                    {
                        "file": file_label,
                        "type": doc_type,
                        "status": "ok",
                        "sections_count": sections_count,
                        "line_items_total": line_items_total,
                        "json_path": json_path_str,
                    }
                )
                print(
                    f"         -> ok  sections={sections_count}  items={line_items_total}",
                    flush=True,
                )

            except Exception as exc:  # noqa: BLE001
                tb = traceback.format_exc()
                results.append(
                    {
                        "file": file_label,
                        "type": doc_type,
                        "status": "error",
                        "error": str(exc),
                        "traceback": tb,
                    }
                )
                print(f"         -> ERROR: {exc}", flush=True)

    # Write run log
    success = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "error")

    run_log = {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "total_files": total_files,
        "success": success,
        "failed": failed,
        "results": results,
    }

    log_path = AUDIT_OUT / "run_log.json"
    with log_path.open("w", encoding="utf-8") as f:
        json.dump(run_log, f, indent=2, ensure_ascii=False)

    _print_summary_table(results)
    print(f"\nRun log: {log_path}")
    print(f"Total: {total_files}  Success: {success}  Failed: {failed}\n")


if __name__ == "__main__":
    main()
