import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import lz4.frame

from parse.xactimate import XactimateRoughDraftParser


# global concurrency cap inside worker process
_SEM = threading.Semaphore(int(os.getenv("PARSE_CONCURRENCY", "1")))


def _write_temp_pdf(data: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
        return path
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise


def _run_parser(input_path: str, out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    parser = XactimateRoughDraftParser(input_path, str(out_dir), debug=False)
    parser.run()
    json_path = out_dir / f"{Path(input_path).stem}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Expected parser output missing: {json_path}")
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_recap(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    recaps = payload.get("recaps_and_summaries") or {}
    if isinstance(recaps, dict) and "recap_by_category" in recaps:
        rb = recaps.get("recap_by_category")
        return rb if isinstance(rb, dict) else {}
    rb = payload.get("recap_by_category")
    return rb if isinstance(rb, dict) else {}


def _count_categories(recap: Dict[str, Any]) -> int:
    def _collect(d: Dict[str, Any]) -> int:
        total = 0
        for group in ("O&P Items", "Non-O&P Items"):
            arr = d.get(group)
            if isinstance(arr, list):
                total += len(arr)
        return total

    if not isinstance(recap, dict):
        return 0
    return _collect(recap)


def run_bid_comp(job_id: str, carrier_lz4: bytes, contractor_lz4: bytes) -> Dict[str, Any]:
    t0 = time.time()
    with _SEM:
        carrier_bytes = lz4.frame.decompress(carrier_lz4)
        contractor_bytes = lz4.frame.decompress(contractor_lz4)

        carrier_path = _write_temp_pdf(carrier_bytes)
        contractor_path = _write_temp_pdf(contractor_bytes)
        tmp_dir = Path(tempfile.mkdtemp(prefix="bidcomp-"))

        try:
            carrier_payload = _run_parser(carrier_path, tmp_dir / "carrier")
            contractor_payload = _run_parser(contractor_path, tmp_dir / "contractor")

            recap_a = _extract_recap(carrier_payload)
            recap_b = _extract_recap(contractor_payload)

            # return only what the client needs
            recap_bundle = {"carrier": recap_a, "contractor": recap_b}

            categories = _count_categories(recap_a) + _count_categories(recap_b)
            meta = {
                "elapsed_ms": int((time.time() - t0) * 1000),
                "carrier_size": len(carrier_bytes),
                "contractor_size": len(contractor_bytes),
                "categories": int(categories),
            }
            return {"recap_by_category": recap_bundle, "meta": meta}
        finally:
            for p in (carrier_path, contractor_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
            # best-effort cleanup of temp json dir
            try:
                for root, _dirs, files in os.walk(tmp_dir, topdown=False):
                    for name in files:
                        try:
                            os.remove(Path(root) / name)
                        except OSError:
                            pass
                os.removedirs(tmp_dir)
            except OSError:
                pass


