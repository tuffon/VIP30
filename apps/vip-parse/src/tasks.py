import json
import os
import tempfile
import threading
import time
import logging
from pathlib import Path
import subprocess
import sys
import gc
import httpx
from src.utils.s3_client import get_s3, get_bucket
from typing import Any, Dict
from rq.job import Job

from redis import Redis
from src.bid_comp import BidComp
from src.bid_comp.identity import ensure_estimate_identity
from src.llm import OpenAIChatAdapter

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
    # Lazy import heavy parser
    from parse.xactimate import XactimateRoughDraftParser
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


def _run_parser_full(input_path: str, out_dir: Path) -> Dict[str, Any]:
    """
    Run full Xactimate parser (sections + recaps) with FAST_RECAP_ONLY disabled.
    Returns the complete JSON payload written by the parser.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("parser(full): start input=%s out_dir=%s", input_path, out_dir)
    from parse.xactimate import XactimateRoughDraftParser

    # Ensure full parse, not recap-only
    os.environ["FAST_RECAP_ONLY"] = "0"
    parser = XactimateRoughDraftParser(input_path, str(out_dir), debug=False)
    t0 = time.time()
    parser.run()
    elapsed = int((time.time() - t0) * 1000)
    base = Path(out_dir) / Path(input_path).stem
    json_path = Path(f"{base}.json")
    if not json_path.exists():
        logger.error("parser(full): missing json output: %s", json_path)
        raise FileNotFoundError(f"Expected full parser output missing: {json_path}")
    size = json_path.stat().st_size
    logger.info("parser(full): done in %dms json=%s size=%d bytes", elapsed, json_path, size)
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


def run_bid_comp_keys(job_id: str, carrier_key: str, contractor_key: str, template: str | None = None) -> Dict[str, Any]:
    t0 = time.time()
    with _SEM:
        logger.info("job start (r2 keys): job_id=%s", job_id)
        s3 = get_s3()
        bucket = get_bucket()

        # Download to temp
        carrier_path = tempfile.mktemp(suffix=".pdf")
        contractor_path = tempfile.mktemp(suffix=".pdf")
        s3.download_file(bucket, carrier_key, carrier_path)
        s3.download_file(bucket, contractor_key, contractor_path)

        try:
            def _parse_full(pdf_path: str) -> Dict[str, Any]:
                """
                Run the full parser for a single PDF and return the complete JSON payload.
                """
                out_dir = Path(tempfile.mkdtemp(prefix="bidcomp-r2-full-"))
                try:
                    return _run_parser_full(pdf_path, out_dir)
                finally:
                    try:
                        for root, _dirs, files in os.walk(out_dir, topdown=False):
                            for name in files:
                                try:
                                    os.remove(Path(root) / name)
                                except OSError:
                                    pass
                        os.removedirs(out_dir)
                    except OSError:
                        pass

            carrier_payload = _parse_full(carrier_path)
            contractor_payload = _parse_full(contractor_path)

            bid_a_name = ensure_estimate_identity(carrier_payload, Path(carrier_key).name)
            bid_b_name = ensure_estimate_identity(contractor_payload, Path(contractor_key).name)

            # recaps derived from full JSON; used for summary rows and checks
            recap_a = _extract_recap(carrier_payload)
            recap_b = _extract_recap(contractor_payload)
            recap_bundle = {
                "estimates": [
                    {"estimate_name": bid_a_name, "recap": recap_a},
                    {"estimate_name": bid_b_name, "recap": recap_b},
                ],
                "carrier": recap_a,
                "contractor": recap_b,
            }

            # full-context input for BidComp: full JSON, not recap-only
            bid_context = {
                "estimates": [
                    {"role": "BID_A", "estimate_name": bid_a_name, "payload": carrier_payload},
                    {"role": "BID_B", "estimate_name": bid_b_name, "payload": contractor_payload},
                ],
                "carrier": carrier_payload,
                "contractor": contractor_payload,
            }

            # Persist JSON payloads alongside XLS output for debugging
            json_prefix = f"results/{job_id}"
            try:
                carrier_json_key = f"{json_prefix}/bid-a-context.json"
                contractor_json_key = f"{json_prefix}/bid-b-context.json"
                s3.put_object(
                    Bucket=bucket,
                    Key=carrier_json_key,
                    Body=json.dumps(carrier_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                    ContentType="application/json",
                )
                s3.put_object(
                    Bucket=bucket,
                    Key=contractor_json_key,
                    Body=json.dumps(contractor_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                    ContentType="application/json",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to upload bid comp JSON artifacts: %s", exc)

            # Generate XLSX using deterministic BidComp; include LLM notes if OPENAI_API_KEY present
            try:
                llm = None
                if os.getenv("OPENAI_API_KEY"):
                    try:
                        llm = OpenAIChatAdapter(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
                    except Exception:
                        llm = None
                xlsx_bytes = BidComp(llm_adapter=llm).run(bid_context, job_id)
                xlsx_tmp = tempfile.mktemp(suffix=".xlsx")
                with open(xlsx_tmp, "wb") as xf:
                    xf.write(xlsx_bytes)
                xlsx_key = f"results/{job_id}/bid-comp.xlsx"
                s3.upload_file(xlsx_tmp, bucket, xlsx_key)
            finally:
                try:
                    os.remove(xlsx_tmp)
                except Exception:
                    pass

            result: Dict[str, Any] = {
                "recap_by_category": recap_bundle,
                "meta": {
                    "elapsed_ms": int((time.time() - t0) * 1000),
                },
                "result_keys": {"xlsx": xlsx_key},
            }

            # Optional downstream API call
            ds_url = os.getenv("DOWNSTREAM_API_URL")
            if ds_url:
                body: Dict[str, Any] = {"context": recap_bundle}
                if template is not None:
                    body["template"] = template
                headers = {}
                token = os.getenv("DOWNSTREAM_API_KEY")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                try:
                    with httpx.Client(timeout=60) as client:
                        resp = client.post(ds_url, json=body, headers=headers)
                        api_obj: Dict[str, Any] = {"status": resp.status_code}
                        try:
                            api_obj["json"] = resp.json()
                        except Exception:
                            api_obj["text"] = resp.text
                        result["api"] = api_obj
                except Exception as e:  # noqa: BLE001
                    logger.warning("downstream api call failed: %s", e)
                    result["api"] = {"error": str(e)}

            logger.info("job done (r2 keys): job_id=%s", job_id)
            return result
        finally:
            for p in (carrier_path, contractor_path):
                try:
                    os.remove(p)
                except OSError:
                    pass



# removed full-parse worker per product decision; recap-only flow remains
