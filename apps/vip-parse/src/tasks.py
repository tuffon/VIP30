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


def _split_pdf_to_chunks(src_path: str, pages_per_chunk: int = 20) -> list[str]:
    from pypdf import PdfReader, PdfWriter  # local import to avoid worker startup failures if missing
    reader = PdfReader(src_path)
    total = len(reader.pages)
    tmp_paths: list[str] = []
    for start in range(0, total, pages_per_chunk):
        end = min(start + pages_per_chunk, total)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        dst = tempfile.mktemp(suffix=f".{start+1}-{end}.pdf")
        with open(dst, "wb") as f:
            writer.write(f)
        tmp_paths.append(dst)
    return tmp_paths


def _merge_recap_dicts(recaps: list[dict]) -> dict:
    merged: dict = {}
    for recap in recaps:
        if not isinstance(recap, dict):
            continue
        for group, items in recap.items():
            if not isinstance(items, list):
                continue
            bucket = merged.setdefault(group, [])
            # map by name to sum totals
            name_to_idx: dict[str, int] = {it.get("name"): idx for idx, it in enumerate(bucket) if isinstance(it, dict) and it.get("name")}
            for it in items:
                if not isinstance(it, dict):
                    continue
                name = it.get("name")
                total = it.get("total")
                if name in name_to_idx:
                    idx = name_to_idx[name]
                    try:
                        prev = float(bucket[idx].get("total") or 0.0)
                        curr = float(total or 0.0)
                        bucket[idx]["total"] = round(prev + curr, 2)
                    except Exception:
                        # keep previous if cannot sum
                        pass
                else:
                    bucket.append({"name": name, "total": total})
                    name_to_idx[name] = len(bucket) - 1
    return merged


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


# removed full-parse helper per product decision; only recap is needed


def parse_pdf(role: str, pdf_lz4: bytes) -> Dict[str, Any]:
    """Parse a single PDF and return only recap_by_category with meta.

    Args:
        role: "carrier" or "contractor" (for logs only)
        pdf_lz4: compressed PDF bytes (lz4)
    Returns:
        { "recap_by_category": {...}, "meta": {...} }
    """
    t0 = time.time()
    with _SEM:
        logger.info("single job start: role=%s", role)
        # Lazy import lz4
        import lz4.frame
        pdf_bytes = lz4.frame.decompress(pdf_lz4)
        path = _write_temp_pdf(pdf_bytes)
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"bidcomp-{role}-"))
        try:
            payload = _run_parser_recap_only(path, tmp_dir)
            recap = _extract_recap(payload)
            meta = {
                "elapsed_ms": int((time.time() - t0) * 1000),
                "pdf_size": len(pdf_bytes),
                "role": role,
            }
            logger.info("single job done: role=%s meta=%s", role, meta)
            return {"recap_by_category": recap, "meta": meta}
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
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


def join_bid_comp(correlation_id: str, carrier_job_id: str, contractor_job_id: str) -> Dict[str, Any]:
    """Join two finished parse jobs and return merged recap structure.

    Returns:
        { "status": "succeeded", "recap_by_category": {"carrier":...,"contractor":...}, "meta": {...} }
    """
    t0 = time.time()
    # Fetch dependency results
    try:
        r = Redis.from_url(os.environ.get("REDIS_URL"), socket_connect_timeout=5, socket_timeout=5, health_check_interval=30)
        c_job = Job.fetch(carrier_job_id, connection=r)
        k_job = Job.fetch(contractor_job_id, connection=r)
    except Exception as e:  # noqa: BLE001
        logger.error("join: failed to fetch dependency jobs: %s", e)
        raise

    def _get_result(job: Job) -> Dict[str, Any]:
        if not job:
            return {}
        s = job.get_status(refresh=True)
        if s == 'failed':
            raise RuntimeError(f"dependency failed: {job.id}")
        return job.result or {}

    carrier_res = _get_result(c_job)
    contractor_res = _get_result(k_job)

    recap_a = _extract_recap(carrier_res)
    recap_b = _extract_recap(contractor_res)

    meta = {
        "elapsed_ms": int((time.time() - t0) * 1000),
        "carrier_job_id": carrier_job_id,
        "contractor_job_id": contractor_job_id,
        "correlation_id": correlation_id,
    }
    logger.info("join: done corr=%s", correlation_id)
    return {"status": "succeeded", "recap_by_category": {"carrier": recap_a, "contractor": recap_b}, "meta": meta}


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


def run_bid_comp_bytes(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Single-job entrypoint taking raw bytes for both PDFs.

    Writes bytes to /tmp, parses each via subprocess, returns recap_by_category bundle + meta.
    """
    t0 = time.time()
    with _SEM:
        logger.info("job start (bytes payload)")

        carrier_bytes = payload.get("carrier_bytes") or b""
        contractor_bytes = payload.get("contractor_bytes") or b""

        # Write temp PDFs
        tw = time.time()
        carrier_path = _write_temp_pdf(carrier_bytes)
        contractor_path = _write_temp_pdf(contractor_bytes)
        logger.info("job tmpfiles: carrier=%s contractor=%s (%dms)", carrier_path, contractor_path, int((time.time() - tw) * 1000))

        try:
            def _parse_via_subprocess(pdf_path: str) -> Dict[str, Any]:
                proc = subprocess.run(
                    [sys.executable, "-m", "src.worker_parse_helper", pdf_path],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                out = (proc.stdout or "").strip()
                if not out:
                    logger.warning("parse helper returned empty stdout for %s; stderr=%s", pdf_path, (proc.stderr or "").strip()[:300])
                    return {"recap_by_category": {}}
                try:
                    return {"recap_by_category": json.loads(out)}
                except Exception as e:  # noqa: BLE001
                    logger.warning("parse helper invalid json for %s: %s; stderr=%s", pdf_path, e, (proc.stderr or "").strip()[:300])
                    return {"recap_by_category": {}}

            logger.info("job parse (bytes): carrier=%s", carrier_path)
            carrier_payload = _parse_via_subprocess(carrier_path)
            try:
                del carrier_bytes
            except Exception:
                pass
            gc.collect()

            logger.info("job parse (bytes): contractor=%s", contractor_path)
            contractor_payload = _parse_via_subprocess(contractor_path)
            try:
                del contractor_bytes
            except Exception:
                pass
            gc.collect()

            recap_a = _extract_recap(carrier_payload)
            recap_b = _extract_recap(contractor_payload)

            recap_bundle = {"carrier": recap_a, "contractor": recap_b}
            bid_context = {"carrier": carrier_payload, "contractor": contractor_payload}
            categories = _count_categories(recap_a) + _count_categories(recap_b)
            meta = {
                "elapsed_ms": int((time.time() - t0) * 1000),
                "carrier_size": os.path.getsize(carrier_path),
                "contractor_size": os.path.getsize(contractor_path),
                "categories": int(categories),
            }
            result: Dict[str, Any] = {
                "recap_by_category": recap_bundle,
                "bid_context": bid_context,
                "meta": meta,
            }

            # Optional downstream API call with context/template
            ds_url = os.getenv("DOWNSTREAM_API_URL")
            if ds_url:
                template = payload.get("template")
                body: Dict[str, Any] = {
                    "context": recap_bundle,
                }
                if template is not None:
                    body["template"] = template
                headers = {}
                token = os.getenv("DOWNSTREAM_API_KEY")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                try:
                    with httpx.Client(timeout=30) as client:
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

            logger.info("job done (bytes): meta=%s", meta)
            return result
        finally:
            logger.info("job cleanup: removing temp files")
            for p in (carrier_path, contractor_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
def run_bid_comp(job_id: str, carrier_lz4: bytes, contractor_lz4: bytes) -> Dict[str, Any]:
    t0 = time.time()
    with _SEM:
        logger.info("job start: job_id=%s", job_id)
        logger.info("job env: TMPDIR=%s", os.getenv("TMPDIR") or tempfile.gettempdir())
        # Decompress inputs
        td = time.time()
        import lz4.frame
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
            def _parse_via_subprocess(pdf_path: str) -> Dict[str, Any]:
                # call helper in a separate process to free memory after exit
                proc = subprocess.run(
                    [sys.executable, "-m", "src.worker_parse_helper", pdf_path],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                out = (proc.stdout or "").strip()
                if not out:
                    logger.warning("parse helper returned empty stdout for %s; stderr=%s", pdf_path, (proc.stderr or "").strip()[:300])
                    return {"recap_by_category": {}}
                try:
                    return {"recap_by_category": json.loads(out)}
                except Exception as e:  # noqa: BLE001
                    logger.warning("parse helper invalid json for %s: %s; stderr=%s", pdf_path, e, (proc.stderr or "").strip()[:300])
                    return {"recap_by_category": {}}

            logger.info("job parse: job_id=%s carrier_path=%s (subprocess)", job_id, carrier_path)
            carrier_payload = _parse_via_subprocess(carrier_path)
            # free carrier temp bytes from memory aggressively
            try:
                del carrier_bytes
            except Exception:
                pass
            gc.collect()

            logger.info("job parse: job_id=%s contractor_path=%s (subprocess)", job_id, contractor_path)
            contractor_payload = _parse_via_subprocess(contractor_path)
            try:
                del contractor_bytes
            except Exception:
                pass
            gc.collect()

            recap_a = _extract_recap(carrier_payload)
            recap_b = _extract_recap(contractor_payload)
            logger.info(
                "job recap extracted: job_id=%s carrier_keys=%s contractor_keys=%s",
                job_id,
                list(recap_a.keys())[:5] if isinstance(recap_a, dict) else None,
                list(recap_b.keys())[:5] if isinstance(recap_b, dict) else None,
            )

            # return only what the client needs
            recap_bundle = {"carrier": recap_a, "contractor": recap_b}
            bid_context = {"carrier": carrier_payload, "contractor": contractor_payload}

            categories = _count_categories(recap_a) + _count_categories(recap_b)
            meta = {
                "elapsed_ms": int((time.time() - t0) * 1000),
                "carrier_size": len(carrier_bytes),
                "contractor_size": len(contractor_bytes),
                "categories": int(categories),
            }
            logger.info("job done: job_id=%s meta=%s", job_id, meta)
            return {"recap_by_category": recap_bundle, "bid_context": bid_context, "meta": meta}
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
            def _parse(pdf_path: str) -> Dict[str, Any]:
                proc = subprocess.run(
                    [sys.executable, "-m", "src.worker_parse_helper", pdf_path],
                    check=True,
                    capture_output=True,
                    text=True,
                    env={**os.environ, "HELPER_OUTDIR": tempfile.mkdtemp(prefix="helper-out-")},
                )
                out = (proc.stdout or "").strip()
                err = (proc.stderr or "").strip()
                if not out:
                    logger.error("parse helper empty stdout for %s; stderr=%s", pdf_path, err)
                    # Fallback: page-chunked parse and merge (fail if any chunk fails)
                    chunks = _split_pdf_to_chunks(pdf_path, pages_per_chunk=int(os.getenv("PAGES_PER_CHUNK", "20")))
                    try:
                        recaps: list[dict] = []
                        success = 0
                        for cp in chunks:
                            helper_out = tempfile.mkdtemp(prefix="helper-out-")
                            sub = subprocess.run(
                                [sys.executable, "-m", "src.worker_parse_helper", cp],
                                check=True,
                                capture_output=True,
                                text=True,
                                env={**os.environ, "HELPER_OUTDIR": helper_out},
                            )
                            sub_out = (sub.stdout or "").strip()
                            if not sub_out:
                                logger.error("chunk parse empty stdout: %s; stderr=%s", cp, (sub.stderr or "").strip()[:300])
                            else:
                                try:
                                    sub_recap = json.loads(sub_out)
                                    recaps.append(sub_recap if isinstance(sub_recap, dict) else {})
                                    success += 1
                                except Exception as se:  # noqa: BLE001
                                    logger.error("chunk parse invalid json: %s err=%s; stderr=%s", cp, se, (sub.stderr or "").strip()[:300])
                            # also try to read recap file from helper_out if stdout was empty
                            if not sub_out:
                                try:
                                    base = Path(helper_out) / Path(cp).stem
                                    recap_file = Path(f"{base}.recap.json")
                                    json_file = Path(f"{base}.json")
                                    if recap_file.exists():
                                        with open(recap_file, "r", encoding="utf-8") as f:
                                            r = json.load(f)
                                        if isinstance(r, dict) and "recap_by_category" in r:
                                            recaps.append(r.get("recap_by_category") or {})
                                            success += 1
                                    elif json_file.exists():
                                        with open(json_file, "r", encoding="utf-8") as f:
                                            p = json.load(f)
                                        rb = (p.get("recap_by_category") or (p.get("recaps_and_summaries") or {}).get("recap_by_category")) or {}
                                        if isinstance(rb, dict):
                                            recaps.append(rb)
                                            success += 1
                                except Exception:
                                    pass
                        if success != len(chunks):
                            raise RuntimeError(f"chunked parse incomplete: {success}/{len(chunks)} chunks succeeded")
                        merged = _merge_recap_dicts(recaps)
                        return {"recap_by_category": merged}
                    finally:
                        for cp in chunks:
                            try:
                                os.remove(cp)
                            except OSError:
                                pass
                try:
                    return {"recap_by_category": json.loads(out)}
                except Exception as e:  # noqa: BLE001
                    logger.error("parse helper invalid json for %s: %s; stderr=%s", pdf_path, e, err)
                    # Fallback: try chunked parse as above (fail if any chunk fails)
                    chunks = _split_pdf_to_chunks(pdf_path, pages_per_chunk=int(os.getenv("PAGES_PER_CHUNK", "20")))
                    try:
                        recaps: list[dict] = []
                        success = 0
                        for cp in chunks:
                            helper_out = tempfile.mkdtemp(prefix="helper-out-")
                            sub = subprocess.run(
                                [sys.executable, "-m", "src.worker_parse_helper", cp],
                                check=True,
                                capture_output=True,
                                text=True,
                                env={**os.environ, "HELPER_OUTDIR": helper_out},
                            )
                            sub_out = (sub.stdout or "").strip()
                            if not sub_out:
                                logger.error("chunk parse empty stdout: %s; stderr=%s", cp, (sub.stderr or "").strip()[:300])
                            else:
                                try:
                                    sub_recap = json.loads(sub_out)
                                    recaps.append(sub_recap if isinstance(sub_recap, dict) else {})
                                    success += 1
                                except Exception as se:  # noqa: BLE001
                                    logger.error("chunk parse invalid json: %s err=%s; stderr=%s", cp, se, (sub.stderr or "").strip()[:300])
                            if not sub_out:
                                try:
                                    base = Path(helper_out) / Path(cp).stem
                                    recap_file = Path(f"{base}.recap.json")
                                    json_file = Path(f"{base}.json")
                                    if recap_file.exists():
                                        with open(recap_file, "r", encoding="utf-8") as f:
                                            r = json.load(f)
                                        if isinstance(r, dict) and "recap_by_category" in r:
                                            recaps.append(r.get("recap_by_category") or {})
                                            success += 1
                                    elif json_file.exists():
                                        with open(json_file, "r", encoding="utf-8") as f:
                                            p = json.load(f)
                                        rb = (p.get("recap_by_category") or (p.get("recaps_and_summaries") or {}).get("recap_by_category")) or {}
                                        if isinstance(rb, dict):
                                            recaps.append(rb)
                                            success += 1
                                except Exception:
                                    pass
                        if success != len(chunks):
                            raise RuntimeError(f"chunked parse incomplete: {success}/{len(chunks)} chunks succeeded")
                        merged = _merge_recap_dicts(recaps)
                        return {"recap_by_category": merged}
                    finally:
                        for cp in chunks:
                            try:
                                os.remove(cp)
                            except OSError:
                                pass

            carrier_payload = _parse(carrier_path)
            contractor_payload = _parse(contractor_path)

            recap_a = _extract_recap(carrier_payload)
            recap_b = _extract_recap(contractor_payload)
            recap_bundle = {"carrier": recap_a, "contractor": recap_b}
            bid_context = {"carrier": carrier_payload, "contractor": contractor_payload}

            # Generate XLSX using deterministic BidComp; include LLM notes if OPENAI_API_KEY present
            try:
                llm = None
                if os.getenv("OPENAI_API_KEY"):
                    try:
                        llm = OpenAIChatAdapter(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
                    except Exception:
                        llm = None
                xlsx_bytes = BidComp(matcher_mode="hybrid", llm_adapter=llm).run(bid_context, job_id)
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
