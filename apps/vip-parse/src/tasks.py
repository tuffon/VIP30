import json
import os
import tempfile
import threading
import time
import logging
from pathlib import Path
from typing import Any, Dict

import lz4.frame

from parse.xactimate import XactimateRoughDraftParser

# Configure worker logging early so RQ shows our logs
_worker_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _worker_log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("vip-parse.worker")


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


def _run_parser_recap_only(input_path: str, out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("parser: start input=%s out_dir=%s", input_path, out_dir)
    parser = XactimateRoughDraftParser(input_path, str(out_dir), debug=False)
    t0 = time.time()
    # enforce fast recap path to reduce memory/CPU
    os.environ.setdefault("FAST_RECAP_ONLY", "1")
    parser.run()
    elapsed = int((time.time() - t0) * 1000)
    base = Path(out_dir) / Path(input_path).stem
    recap_path = base.with_suffix("")
    recap_path = Path(str(base))  # ensure string base
    recap_file = Path(f"{recap_path}.recap.json")
    if recap_file.exists():
        size = recap_file.stat().st_size
        logger.info("parser: done in %dms recap=%s size=%d bytes", elapsed, recap_file, size)
        with recap_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback to full JSON if recap file missing
    json_path = Path(f"{recap_path}.json")
    if not json_path.exists():
        logger.error("parser: missing output json: %s", json_path)
        raise FileNotFoundError(f"Expected parser output missing: {json_path}")
    size = json_path.stat().st_size
    logger.info("parser: done in %dms json=%s size=%d bytes", elapsed, json_path, size)
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
        logger.info("job start: job_id=%s", job_id)
        logger.info("job env: TMPDIR=%s", os.getenv("TMPDIR") or tempfile.gettempdir())
        # Decompress inputs
        td = time.time()
        carrier_bytes = lz4.frame.decompress(carrier_lz4)
        contractor_bytes = lz4.frame.decompress(contractor_lz4)
        logger.info("job decompress: %dms", int((time.time() - td) * 1000))
        logger.info(
            "job input: job_id=%s sizes=(carrier=%d contractor=%d) lz4_sizes=(%d,%d)",
            job_id,
            len(carrier_bytes),
            len(contractor_bytes),
            len(carrier_lz4),
            len(contractor_lz4),
        )

        # Write temp PDFs
        tw = time.time()
        carrier_path = _write_temp_pdf(carrier_bytes)
        contractor_path = _write_temp_pdf(contractor_bytes)
        logger.info("job tmpfiles: carrier=%s contractor=%s (%dms)", carrier_path, contractor_path, int((time.time() - tw) * 1000))
        tmp_dir = Path(tempfile.mkdtemp(prefix="bidcomp-"))
        logger.info("job workspace: %s", tmp_dir)

        try:
            logger.info("job parse: job_id=%s carrier_path=%s", job_id, carrier_path)
            carrier_recap_payload = _run_parser_recap_only(carrier_path, tmp_dir / "carrier")
            logger.info("job parse: job_id=%s contractor_path=%s", job_id, contractor_path)
            contractor_recap_payload = _run_parser_recap_only(contractor_path, tmp_dir / "contractor")

            recap_a = _extract_recap(carrier_recap_payload)
            recap_b = _extract_recap(contractor_recap_payload)
            logger.info(
                "job recap extracted: job_id=%s carrier_keys=%s contractor_keys=%s",
                job_id,
                list(recap_a.keys())[:5] if isinstance(recap_a, dict) else None,
                list(recap_b.keys())[:5] if isinstance(recap_b, dict) else None,
            )

            # return only what the client needs
            recap_bundle = {"carrier": recap_a, "contractor": recap_b}

            categories = _count_categories(recap_a) + _count_categories(recap_b)
            meta = {
                "elapsed_ms": int((time.time() - t0) * 1000),
                "carrier_size": len(carrier_bytes),
                "contractor_size": len(contractor_bytes),
                "categories": int(categories),
            }
            logger.info("job done: job_id=%s meta=%s", job_id, meta)
            return {"recap_by_category": recap_bundle, "meta": meta}
        finally:
            logger.info("job cleanup: removing temp files and workspace")
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


