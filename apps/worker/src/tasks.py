from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
import gc
import hashlib
import httpx
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from redis import Redis
from rq.job import Job

from vip_shared.bid_comp import BidComp
from vip_shared.bid_comp.identity import ensure_estimate_identity
from vip_shared.db import async_session_maker
from vip_shared.integrations.sendgrid_client import SendGridClient
from vip_shared.llm import OpenAIChatAdapter
from vip_shared.methodology.analyzer import MethodologyAnalyzer
from vip_shared.rules.engine import RulesEngine
from vip_shared.services.jobs import JobService
from vip_shared.utils.s3_client import get_s3, get_bucket

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
_ASYNC_LOOP: asyncio.AbstractEventLoop | None = None
_ASYNC_LOOP_THREAD: threading.Thread | None = None
_ASYNC_LOOP_LOCK = threading.Lock()
_ASYNC_OP_TIMEOUT_SEC = int(os.getenv("WORKER_ASYNC_OP_TIMEOUT_SEC", "20"))
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


def _safe_filename(value: Optional[str], fallback: str = "estimate.pdf") -> str:
    """
    Return a safe basename to store a downloaded estimate without leaking path separators.
    """
    if not value:
        return fallback
    base = Path(str(value)).name.strip()
    if not base:
        return fallback
    base = re.sub(r"[\\/]+", "_", base)
    return base


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
    logger.info(
        "identity: job=%s role=%s original=%s estimate=%s fallback=%s",
        job_id,
        role,
        original,
        resolved,
        json.dumps(_identity_snapshot(payload), ensure_ascii=False),
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
    from vip_parser.xactimate import XactimateRoughDraftParser
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
    from vip_parser.xactimate import XactimateRoughDraftParser

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


def _run_loop_forever(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_async_loop() -> asyncio.AbstractEventLoop:
    global _ASYNC_LOOP, _ASYNC_LOOP_THREAD
    with _ASYNC_LOOP_LOCK:
        if _ASYNC_LOOP and not _ASYNC_LOOP.is_closed():
            return _ASYNC_LOOP

        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=_run_loop_forever,
            args=(loop,),
            daemon=True,
            name="vip-parse-worker-async-loop",
        )
        thread.start()
        _ASYNC_LOOP = loop
        _ASYNC_LOOP_THREAD = thread
        return loop


def _run_async(coro):
    """
    Run async coroutine from sync worker context on a single persistent event loop.
    This avoids cross-loop asyncpg/sqlalchemy pool errors when called repeatedly.
    """
    loop = _get_async_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=_ASYNC_OP_TIMEOUT_SEC)
    except FutureTimeoutError:
        future.cancel()
        raise TimeoutError(
            f"async worker operation timed out after {_ASYNC_OP_TIMEOUT_SEC}s"
        ) from None


def _update_job_progress(
    db_job_id: Optional[str],
    state: Optional[str],
    progress: int,
    step: Optional[str] = None,
) -> None:
    if not db_job_id:
        return

    async def _update():
        async with async_session_maker() as db:
            job_uuid = uuid.UUID(db_job_id)
            job = await JobService.get_job(db, job_uuid)
            if not job:
                return
            if state and job.state != state and job.state not in JobService.TERMINAL_STATES:
                await JobService.transition_state(db, job_uuid, state)
            await JobService.update_progress(db, job_uuid, progress, step)

    try:
        _run_async(_update())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to update job progress for db_job_id=%s: %s", db_job_id, exc)


def run_bid_comp_keys(
    job_id: str,
    carrier_key: str,
    contractor_key: str,
    template: str | None = None,
    carrier_filename: str | None = None,
    contractor_filename: str | None = None,
    notify_email: str | None = None,
    db_job_id: str | None = None,
    *,
    output_mode: str = "internal",
) -> Dict[str, Any]:
    t0 = time.time()
    _ = output_mode  # Backward compatibility for queued jobs that still pass this kwarg.
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

        work_dir = Path(tempfile.mkdtemp(prefix="bidcomp-input-"))
        carrier_original = carrier_filename or Path(carrier_key).name
        contractor_original = contractor_filename or Path(contractor_key).name
        carrier_path = work_dir / _safe_filename(carrier_original, fallback="carrier.pdf")
        contractor_path = work_dir / _safe_filename(contractor_original, fallback="contractor.pdf")
        s3.download_file(bucket, carrier_key, str(carrier_path))
        s3.download_file(bucket, contractor_key, str(contractor_path))
        carrier_hash = hashlib.sha256(carrier_path.read_bytes()).hexdigest()
        contractor_hash = hashlib.sha256(contractor_path.read_bytes()).hexdigest()
        logger.info(
            "job download complete: job_id=%s carrier_tmp=%s contractor_tmp=%s carrier_original=%s contractor_original=%s",
            job_id,
            carrier_path,
            contractor_path,
            carrier_original,
            contractor_original,
        )
        _update_job_progress(db_job_id, JobService.PARSING, 15, "Downloaded files")

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

            _update_job_progress(db_job_id, JobService.PARSING, 20, "Parsing primary estimate")
            carrier_payload = _parse_full(carrier_path)
            _update_job_progress(db_job_id, JobService.PARSING, 35, "Primary estimate parsed")

            _update_job_progress(db_job_id, JobService.PARSING, 40, "Parsing comparison estimate")
            contractor_payload = _parse_full(contractor_path)
            _update_job_progress(db_job_id, JobService.ANALYZING, 55, "Comparison estimate parsed")
            carrier_parser_name = Path(carrier_path).name
            contractor_parser_name = Path(contractor_path).name

            logger.info(
                "job payload parsed: job_id=%s carrier_has_name=%s contractor_has_name=%s",
                job_id,
                bool(isinstance(carrier_payload, dict) and carrier_payload.get("estimate_name")),
                bool(isinstance(contractor_payload, dict) and contractor_payload.get("estimate_name")),
            )

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

            methodology_result = None
            _update_job_progress(db_job_id, JobService.ANALYZING, 62, "Running methodology analysis")
            try:
                analyzer = MethodologyAnalyzer()
                methodology_result = analyzer.analyze(
                    primary_payload=carrier_payload,
                    comparison_payload=contractor_payload,
                )
                logger.info(
                    "methodology analysis complete: job_id=%s op_differs=%s depr_differs=%s granularity=%s",
                    job_id,
                    methodology_result.op_treatment_differs,
                    methodology_result.depreciation_approach_differs,
                    methodology_result.data_granularity.value,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("methodology analysis failed (non-fatal): job_id=%s error=%s", job_id, exc)

            signal_bundle = None
            if methodology_result is not None:
                _update_job_progress(db_job_id, JobService.ANALYZING, 66, "Running intelligence rules")
                try:
                    rules_engine = RulesEngine()
                    signal_bundle = rules_engine.evaluate(methodology_result)
                    logger.info(
                        "rules engine complete: job_id=%s flags=%d alerts=%d patterns=%d followups=%d",
                        job_id,
                        len(signal_bundle.emphasis_flags),
                        len(signal_bundle.alert_tags),
                        len(signal_bundle.structural_patterns),
                        len(signal_bundle.diagnostic_followups),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("rules engine failed (non-fatal): job_id=%s error=%s", job_id, exc)

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
                "methodology": methodology_result,
                "signals": signal_bundle,
            }
            logger.info(
                "job bid-context ready: job_id=%s primary=%s comparison=%s primary_src=%s comparison_src=%s",
                job_id,
                primary_name,
                comparison_name,
                carrier_original,
                contractor_original,
            )
            _update_job_progress(db_job_id, JobService.ANALYZING, 68, "Analyzing estimate deltas")

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
            llm_stats: Dict[str, Any] = {"total_calls": 0, "successful_calls": 0, "failed_calls": 0, "disabled_reason": None}
            llm_had_output = False
            xlsx_tmp = ""
            xlsx_key = f"results/{job_id}/bid-comp.xlsx"
            try:
                llm = None
                if os.getenv("OPENAI_API_KEY"):
                    try:
                        llm = OpenAIChatAdapter(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
                    except Exception:
                        llm = None
                comp = BidComp(llm_adapter=llm)
                logger.info("job bid-comp run starting: job_id=%s", job_id)
                _update_job_progress(db_job_id, JobService.WRITING, 78, "Generating narratives")
                xlsx_bytes = comp.run(
                    bid_context,
                    job_id,
                )
                _update_job_progress(db_job_id, JobService.WRITING, 88, "Generating XLSX report")
                llm_stats = llm.stats() if llm else {"total_calls": 0, "successful_calls": 0, "failed_calls": 0, "disabled_reason": None}
                llm_had_output = bool(llm_stats.get("successful_calls", 0) > 0)
                logger.info(
                    "job bid-comp run finished: job_id=%s xlsx_bytes=%d llm_enabled=%s llm_successful_calls=%s llm_failed_calls=%s llm_disabled_reason=%s",
                    job_id,
                    len(xlsx_bytes),
                    bool(llm),
                    llm_stats.get("successful_calls"),
                    llm_stats.get("failed_calls"),
                    llm_stats.get("disabled_reason"),
                )
                xlsx_tmp = tempfile.mktemp(suffix=".xlsx")
                with open(xlsx_tmp, "wb") as xf:
                    xf.write(xlsx_bytes)
                xlsx_key = f"results/{job_id}/bid-comp.xlsx"
                s3.upload_file(xlsx_tmp, bucket, xlsx_key)
                _update_job_progress(db_job_id, JobService.WRITING, 96, "Uploading final results")
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
                        "llm_successful_calls": llm_stats.get("successful_calls", 0),
                        "llm_failed_calls": llm_stats.get("failed_calls", 0),
                        "llm_disabled_reason": llm_stats.get("disabled_reason"),
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

            if db_job_id:
                narrative_key = (result.get("result_keys") or {}).get("narrative")
                if not llm_had_output:
                    logger.warning(
                        "job completed without successful LLM output; skipping credit charge: job_id=%s",
                        job_id,
                    )

                async def _complete():
                    async with async_session_maker() as db:
                        await JobService.complete_job(
                            db,
                            uuid.UUID(db_job_id),
                            result_s3_key=xlsx_key,
                            narrative_s3_key=narrative_key,
                            consume_credit=llm_had_output,
                        )

                try:
                    _run_async(_complete())
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to mark job completed for db_job_id=%s: %s", db_job_id, exc)

            logger.info("job done (r2 keys): job_id=%s", job_id)
            return result
        except Exception as exc:  # noqa: BLE001
            if db_job_id:
                async def _fail():
                    async with async_session_maker() as db:
                        await JobService.fail_job(
                            db,
                            uuid.UUID(db_job_id),
                            error_code=exc.__class__.__name__,
                            error_message=str(exc),
                        )

                try:
                    _run_async(_fail())
                except Exception as fail_exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to mark job failed for db_job_id=%s: %s",
                        db_job_id,
                        fail_exc,
                    )
            raise
        finally:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass



# removed full-parse worker per product decision; recap-only flow remains
