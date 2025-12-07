from __future__ import annotations

import gc
import httpx
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from redis import Redis
from rq.job import Job

from src.bid_comp import BidComp
from src.bid_comp.identity import ensure_estimate_identity
from src.integrations.sendgrid_client import SendGridClient
from src.llm import OpenAIChatAdapter
from src.utils.s3_client import get_s3, get_bucket

# Configure worker logging early so RQ shows our logs
_worker_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _worker_log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("vip-parse.worker")
email_client = SendGridClient()


# global concurrency cap inside worker process
_SEM = threading.Semaphore(int(os.getenv("PARSE_CONCURRENCY", "1")))
MAX_DISPLAY_NAME_LEN = 120

_FORMULA_PREFIXES = ("=", "+", "-", "@")
_INVALID_DISPLAY_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_display_name(value: Optional[str]) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = _INVALID_DISPLAY_CHARS.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if text[0] in _FORMULA_PREFIXES:
        text = f"SAFE {text}"
    if len(text) > MAX_DISPLAY_NAME_LEN:
        text = text[:MAX_DISPLAY_NAME_LEN].rstrip()
    return text


def _identity_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    case_md = payload.get("case_metadata")
    snapshot = {
        "payload.estimate_name": payload.get("estimate_name"),
        "payload.original_filename": payload.get("original_filename"),
        "case_metadata.estimate_name": (case_md or {}).get("estimate_name") if isinstance(case_md, dict) else None,
        "case_metadata.file_name": (case_md or {}).get("file_name") if isinstance(case_md, dict) else None,
        "case_metadata.original_filename": (case_md or {}).get("original_filename") if isinstance(case_md, dict) else None,
        "metadata.file_name": (payload.get("metadata") or {}).get("file_name")
        if isinstance(payload.get("metadata"), dict)
        else None,
    }
    return {k: v for k, v in snapshot.items() if v}


def _log_identity(job_id: str, role: str, original: str, resolved: str, payload: Dict[str, Any]) -> None:
    snapshot = _identity_snapshot(payload)
    logger.info(
        "identity snapshot: job_id=%s role=%s original=%s estimate_name=%s details=%s",
        job_id,
        role,
        original,
        resolved,
        json.dumps(snapshot, ensure_ascii=False) if snapshot else "{}",
    )


def _ensure_original_metadata(payload: Dict[str, Any], original_filename: str) -> None:
    if not isinstance(payload, dict):
        return
    if original_filename and not payload.get("original_filename"):
        payload["original_filename"] = original_filename
    case_md = payload.get("case_metadata")
    if isinstance(case_md, dict):
        if original_filename and not case_md.get("original_filename"):
            case_md["original_filename"] = original_filename
    elif original_filename:
        payload["case_metadata"] = {"original_filename": original_filename}


def _ensure_preferred_estimate_name(
    payload: Dict[str, Any],
    *,
    preferred_name: Optional[str],
    parser_filename: str,
) -> None:
    if not isinstance(payload, dict):
        return
    parser_basename = _sanitize_display_name(Path(parser_filename).name)
    current = (payload.get("estimate_name") or "").strip()
    current_clean = _sanitize_display_name(current)
    if current_clean and parser_basename and current_clean != parser_basename:
        return
    target = _sanitize_display_name(preferred_name)
    if not target:
        return
    payload["estimate_name"] = target
    case_md = payload.get("case_metadata")
    if isinstance(case_md, dict):
        case_md["estimate_name"] = target
    elif target:
        payload["case_metadata"] = {"estimate_name": target}


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


def run_bid_comp_keys(
    job_id: str,
    carrier_key: str,
    contractor_key: str,
    template: str | None = None,
    carrier_filename: str | None = None,
    contractor_filename: str | None = None,
    notify_email: str | None = None,
) -> Dict[str, Any]:
    t0 = time.time()
    with _SEM:
        logger.info("job start (r2 keys): job_id=%s", job_id)
        logger.info(
            "job context (r2 keys): job_id=%s carrier_key=%s contractor_key=%s carrier_filename=%s contractor_filename=%s",
            job_id,
            carrier_key,
            contractor_key,
            carrier_filename,
            contractor_filename,
        )
        s3 = get_s3()
        bucket = get_bucket()

        # Download to temp
        carrier_path = tempfile.mktemp(suffix=".pdf")
        contractor_path = tempfile.mktemp(suffix=".pdf")
        s3.download_file(bucket, carrier_key, carrier_path)
        s3.download_file(bucket, contractor_key, contractor_path)
        logger.info(
            "job download complete: job_id=%s carrier_tmp=%s contractor_tmp=%s",
            job_id,
            carrier_path,
            contractor_path,
        )

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
            carrier_parser_name = Path(carrier_path).name
            contractor_parser_name = Path(contractor_path).name

            logger.info(
                "job payload parsed: job_id=%s carrier_has_name=%s contractor_has_name=%s",
                job_id,
                bool(isinstance(carrier_payload, dict) and carrier_payload.get("estimate_name")),
                bool(isinstance(contractor_payload, dict) and contractor_payload.get("estimate_name")),
            )

            carrier_original = carrier_filename or Path(carrier_key).name
            contractor_original = contractor_filename or Path(contractor_key).name
            logger.info(
                "job originals resolved: job_id=%s carrier_original=%s contractor_original=%s",
                job_id,
                carrier_original,
                contractor_original,
            )
            _ensure_original_metadata(carrier_payload, carrier_original)
            _ensure_original_metadata(contractor_payload, contractor_original)
            _ensure_preferred_estimate_name(
                carrier_payload,
                preferred_name=carrier_original,
                parser_filename=carrier_parser_name,
            )
            _ensure_preferred_estimate_name(
                contractor_payload,
                preferred_name=contractor_original,
                parser_filename=contractor_parser_name,
            )

            primary_name = ensure_estimate_identity(
                carrier_payload,
                carrier_original,
            )
            comparison_name = ensure_estimate_identity(
                contractor_payload,
                contractor_original,
            )
            _log_identity(job_id, "carrier", carrier_original, primary_name, carrier_payload)
            _log_identity(job_id, "contractor", contractor_original, comparison_name, contractor_payload)

            # recaps derived from full JSON; used for summary rows and checks
            recap_a = _extract_recap(carrier_payload)
            recap_b = _extract_recap(contractor_payload)
            logger.info(
                "job recap snapshot: job_id=%s carrier_groups=%d contractor_groups=%d",
                job_id,
                len(recap_a or {}),
                len(recap_b or {}),
            )
            recap_bundle = {
                "estimates": [
                    {"estimate_name": primary_name, "recap": recap_a},
                    {"estimate_name": comparison_name, "recap": recap_b},
                ],
                "carrier": recap_a,
                "contractor": recap_b,
            }

            # full-context input for BidComp: full JSON, not recap-only
            bid_context = {
                "estimates": [
                    {
                        "position": "primary",
                        "estimate_name": primary_name,
                        "payload": carrier_payload,
                        "source_filename": carrier_original,
                    },
                    {
                        "position": "comparison",
                        "estimate_name": comparison_name,
                        "payload": contractor_payload,
                        "source_filename": contractor_original,
                    },
                ],
                "carrier": carrier_payload,
                "contractor": contractor_payload,
                "carrier_source_filename": carrier_original,
                "contractor_source_filename": contractor_original,
            }
            logger.info(
                "job bid-context ready: job_id=%s primary=%s comparison=%s primary_src=%s comparison_src=%s",
                job_id,
                primary_name,
                comparison_name,
                carrier_original,
                contractor_original,
            )

            # Persist JSON payloads alongside XLS output for debugging
            json_prefix = f"results/{job_id}"
            try:
                carrier_json_key = f"{json_prefix}/primary-estimate.json"
                contractor_json_key = f"{json_prefix}/comparison-estimate.json"
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
                comp = BidComp(llm_adapter=llm)
                logger.info("job bid-comp run starting: job_id=%s", job_id)
                xlsx_bytes = comp.run(bid_context, job_id)
                logger.info(
                    "job bid-comp run finished: job_id=%s xlsx_bytes=%d llm_enabled=%s",
                    job_id,
                    len(xlsx_bytes),
                    bool(llm),
                )
                xlsx_tmp = tempfile.mktemp(suffix=".xlsx")
                with open(xlsx_tmp, "wb") as xf:
                    xf.write(xlsx_bytes)
                xlsx_key = f"results/{job_id}/bid-comp.xlsx"
                s3.upload_file(xlsx_tmp, bucket, xlsx_key)
                logger.info(
                    "job xlsx uploaded: job_id=%s key=%s size_bytes=%d",
                    job_id,
                    xlsx_key,
                    len(xlsx_bytes),
                )
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
            if notify_email:
                result["notify_email"] = notify_email
            narrative_debug = getattr(comp, "last_narrative_debug", None)
            if narrative_debug:
                result["narrative_debug"] = narrative_debug
            narrative_artifact = getattr(comp, "last_narrative_artifact", None)
            if narrative_artifact:
                try:
                    narrative_key = f"{json_prefix}/narrative.json"
                    s3.put_object(
                        Bucket=bucket,
                        Key=narrative_key,
                        Body=json.dumps(narrative_artifact, ensure_ascii=False, indent=2).encode("utf-8"),
                        ContentType="application/json",
                    )
                    result["result_keys"]["narrative"] = narrative_key
                except Exception as exc:  # noqa: BLE001
                    logger.warning("failed to upload narrative artifact: %s", exc)

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

            # Email notification once we have a presigned link
            if notify_email:
                try:
                    expire = int(os.getenv("EMAIL_DOWNLOAD_EXPIRE_SEC", "86400"))
                    download_url = s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": bucket, "Key": xlsx_key},
                        ExpiresIn=expire,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to presign download for email: %s", exc)
                    download_url = None
                if download_url:
                    email_client.send_bidcomp_ready_email(
                        to_email=notify_email,
                        download_url=download_url,
                        summary=f"{primary_name} vs {comparison_name}",
                    )

            logger.info("job done (r2 keys): job_id=%s", job_id)
            return result
        finally:
            for p in (carrier_path, contractor_path):
                try:
                    os.remove(p)
                except OSError:
                    pass



# removed full-parse worker per product decision; recap-only flow remains
