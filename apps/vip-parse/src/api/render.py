"""Bid comparison render pipeline utilities."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional
from string import Template

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile, status
import openai
from pydantic import BaseModel, Field

from parse.xactimate import XactimateRoughDraftParser


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY and not getattr(openai, "api_key", None):
    openai.api_key = OPENAI_API_KEY

# Concurrency and timeout controls (tunable via env)
PARSE_CONCURRENCY = max(1, int(os.getenv("PARSE_CONCURRENCY", "1")))
PARSE_IN_PARALLEL = os.getenv("PARSE_IN_PARALLEL", "false").strip().lower() in {"1", "true", "yes"}
PARSE_TIMEOUT_SEC = max(30, int(os.getenv("PARSE_TIMEOUT_SEC", "180")))

_parse_semaphore = None
try:
    import asyncio as _asyncio
    _parse_semaphore = _asyncio.Semaphore(PARSE_CONCURRENCY)
except Exception:
    _parse_semaphore = None


DEFAULT_SYSTEM_PROMPT = (
    "You are an estimating analyst trained on Xactimate scopes. "
    "Use the provided JSON payloads to prepare a detailed comparison."
)


DEFAULT_PROMPT_TEMPLATE = Template(
    """Goal

Generate a bid comparison CSV (Excel-compatible) using only the provided recap_by_category segments from two estimates.


Output Columns (exact order & headers):

$ROW_LABEL_HEADER,$LEFT_LABEL,$RIGHT_LABEL,Difference,Notes


$ROW_LABEL_HEADER = first column header text (e.g., KITCHEN in the sample export).


$LEFT_LABEL = label for Estimate A (e.g., APEX).


$RIGHT_LABEL = label for Estimate B (e.g., State Farm).


Currency Format: $$12,345.67


Zero/empty: $$ -


Negative: parentheses (e.g., $$ (5,541.86))


Two decimals, thousands separators.


Inputs (replace placeholders)


Estimate A label ($LEFT_LABEL) and recap JSON A:

$RECAP_A_JSON



Estimate B label ($RIGHT_LABEL) and recap JSON B:

$RECAP_B_JSON



Row label header: $ROW_LABEL_HEADER


Schema subset guaranteed (example):


recap_by_category: {
  "subtotals": [
    { "label": "O&P Items", "total": "…", "pct": … },
    { "label": "Non-O&P Items", "total": "…", "pct": … },
    { "label": "Overhead", "total": "…", "pct": … },
    { "label": "Profit", "total": "…", "pct": … },
    { "label": "Material Sales Tax", "total": "…", "pct": … },
    { "label": "Permits and Fees", "total": "…", "pct": … },
    { "label": "Total", "total": "…", "pct": … }
  ],
  "O&P Items": [ { "item": "APPLIANCES", "total": "…", "pct": …, "coverage": [...] }, ... ],
  "Non-O&P Items": [ { "item": "CLEANING", "total": "…", "pct": …, "coverage": [...] }, ... ]
}


What to Include as Rows


Top meta rows (if present in either side):


O& P Line items (if subtotals include “O&P Items” / “Non-O&P Items”)


Overhead


Profit


Material Sales Tax


Permits and Fees


Total


For each, LEFT/RIGHT = numeric from each JSON’s subtotals by matching label (case-insensitive, trim spaces). If missing on one side → $$ -.


Category rows by group:


From arrays under "O&P Items" and "Non-O&P Items".


Row label = category item (e.g., APPLIANCES, FLOOR COVERING - WOOD).


LEFT/RIGHT = category total for that group. If present only on one side, the other side is $$ -.


Keep categories distinct per group; do not merge O&P vs Non-O&P for the same name.


Normalization & Matching


Label matching: case-insensitive; trim; collapse multiple spaces; treat hyphen vs en dash as equal.


Totals: use the total strings; parse to numbers for diff; reformat to currency on output.


Duplicates: if a category item appears multiple times within a group, sum totals within that group before comparison.


Difference & Notes


Difference = $RIGHT_LABEL − $LEFT_LABEL (B minus A) values per row.


Notes guidance (only if applicable):


Category present only in $LEFT_LABEL / $RIGHT_LABEL.


O&P/Non-O&P mix differs between estimates.


Subtotal missing on $LEFT_LABEL/$RIGHT_LABEL.


Otherwise leave Notes blank.


Ordering


Block 1: meta rows in this order if present:

O& P Line items (see note below), Overhead, Profit, Material Sales Tax, Permits and Fees, Total.


“O& P Line items” rule: If subtotals include both “O&P Items” and “Non-O&P Items”, make a single row labeled exactly O& P Line items with LEFT = sum of A’s O&P + Non-O&P; RIGHT = sum of B’s O&P + Non-O&P. If only one exists on a side, use that one; if neither exists on a side, $$ -.


Block 2: categories by group. Emit all O&P Items categories first, then Non-O&P Items categories.


Within each block, sort by absolute Difference descending; ties by row label A-Z.


Validation


Headers exactly: $ROW_LABEL_HEADER,$LEFT_LABEL,$RIGHT_LABEL,Difference,Notes


Every money cell is $$ - or $$X,XXX.XX with parentheses for negatives.


No extra columns. No formulas. No trailing spaces.


Output Format


Return a single CSV with the exact header row followed by data rows.


Do not include markdown fences or extra commentary.


If your tool supports file writing, also save as bid-comp.xlsx with the same columns and values (no formulas). Otherwise, the CSV is sufficient for Excel import.


Deterministic Steps (Do This Exactly)


Parse both recap_by_category objects.


Build meta map from subtotals by normalized label.


Build group maps for "O&P Items" and "Non-O&P Items": { normalized_item -> summed_total }.


Create rows:


Meta rows (including computed O& P Line items), then O&P categories, then Non-O&P categories.


For each row, compute LEFT/RIGHT, then Difference.


Format currency cells.


Sort within blocks as specified.


Emit CSV exactly per spec.


Example header line (replace placeholders)

$ROW_LABEL_HEADER,$LEFT_LABEL,$RIGHT_LABEL,Difference,Notes
"""
)


SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/vnd.pdf",
    "application/acrobat",
    "applications/pdf",
    "text/pdf",
    "text/x-pdf",
}


class ParsedEstimate(BaseModel):
    """Representation of a parsed estimate payload."""

    filename: str
    payload: Dict[str, Any]


class OpenAIResult(BaseModel):
    """Minimal OpenAI completion payload returned to the client."""

    id: Optional[str] = None
    model: Optional[str] = None
    response_text: Optional[str] = Field(default=None, description="Aggregated textual response")
    usage: Optional[Dict[str, Any]] = None


class BidCompRenderResponse(BaseModel):
    """Response payload for the bid comparison render endpoint."""

    carrier_estimate: ParsedEstimate
    contractor_estimate: ParsedEstimate
    openai_result: Optional[OpenAIResult] = Field(default=None, description="OpenAI completion response when executed")
    openai_request_preview: Dict[str, Any]
    left_label: str = Field(description="Label used for the carrier/Estimate A side")
    right_label: str = Field(description="Label used for the contractor/Estimate B side")
    row_label_header: str = Field(description="Header used for the first column in the CSV output")


def _sanitize_filename(filename: Optional[str], fallback: str) -> str:
    name = (filename or fallback).strip()
    if not name:
        name = fallback
    # Remove any path separators
    name = Path(name).name
    # Enforce .pdf extension
    if not name.lower().endswith(".pdf"):
        name = re.sub(r"\.[^.]+$", "", name) + ".pdf"
    return name


async def _persist_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out_file:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            out_file.write(chunk)


def _run_xactimate_parser(input_path: Path, output_dir: Path, debug: bool = False) -> Dict[str, Any]:
    parser = XactimateRoughDraftParser(str(input_path), str(output_dir), debug=debug)
    parser.run()
    json_path = output_dir / f"{input_path.stem}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Expected parser output missing: {json_path}")
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_text_from_openai_content(choice: Any) -> str:
    message = getattr(choice, "message", None)
    if not message:
        return ""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and part.get("text"):
                    fragments.append(part["text"])
            else:
                text = getattr(part, "text", None)
                if text:
                    fragments.append(text)
        return "".join(fragments)
    return str(content)


def _extract_recap_by_category(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    recaps = payload.get("recaps_and_summaries") or {}
    recap = recaps.get("recap_by_category") if isinstance(recaps, dict) else None
    if recap:
        return recap
    return payload.get("recap_by_category")


def _infer_estimate_label(parsed: ParsedEstimate) -> str:
    case_md = parsed.payload.get("case_metadata") if isinstance(parsed.payload, dict) else {}
    estimate_name = (case_md or {}).get("estimate_name") if isinstance(case_md, dict) else None
    if estimate_name:
        return str(estimate_name)
    return Path(parsed.filename).stem


def _render_prompt_template(template_str: str, context: Dict[str, str]) -> str:
    try:
        return Template(template_str).substitute(context)
    except (KeyError, ValueError):
        try:
            return template_str.format_map(context)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prompt template rendering failed: {exc}",
            ) from exc


def _ensure_openai_ready() -> None:
    if not getattr(openai, "api_key", None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured",
        )


async def _call_openai(
    *,
    model: str,
    temperature: float,
    max_output_tokens: Optional[int],
    messages: list[dict],
) -> OpenAIResult:
    _ensure_openai_ready()

    def _invoke() -> OpenAIResult:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens

        try:
            response = openai.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenAI request failed: {exc}",
            ) from exc
        first_choice = response.choices[0] if response.choices else None
        text = _extract_text_from_openai_content(first_choice) if first_choice else None
        usage = None
        usage_obj = getattr(response, "usage", None)
        if usage_obj is not None:
            if hasattr(usage_obj, "model_dump"):
                usage = usage_obj.model_dump()
            elif isinstance(usage_obj, dict):
                usage = usage_obj
            else:
                usage = dict(usage_obj)
        return OpenAIResult(
            id=getattr(response, "id", None),
            model=getattr(response, "model", None),
            response_text=text,
            usage=usage,
        )

    return await asyncio.to_thread(_invoke)


async def _parse_estimate(
    *,
    upload: UploadFile,
    role_label: str,
    workspace: Path,
    debug: bool = False,
) -> ParsedEstimate:
    content_type = (upload.content_type or "").lower()
    if content_type and content_type not in SUPPORTED_CONTENT_TYPES:
        if not (upload.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"{role_label} must be a PDF document",
            )

    safe_name = _sanitize_filename(upload.filename, f"{role_label}.pdf")
    input_path = workspace / "inputs" / safe_name
    output_dir = workspace / "outputs" / role_label

    await _persist_upload(upload, input_path)

    print(f"[bid-comp] Starting parse for {role_label} file '{safe_name}'")
    try:
        payload = await asyncio.wait_for(
            asyncio.to_thread(_run_xactimate_parser, input_path, output_dir, debug),
            timeout=PARSE_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError as te:  # noqa: F821
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Parser timeout") from te
    print(f"[bid-comp] Completed parse for {role_label} file '{safe_name}'")

    return ParsedEstimate(filename=safe_name, payload=payload)


async def process_bid_comp_render(
    *,
    carrier_estimate: UploadFile,
    contractor_estimate: UploadFile,
    prompt_template: Optional[str],
    left_label_override: Optional[str],
    right_label_override: Optional[str],
    row_label_header: Optional[str],
    model: str,
    temperature: float,
    max_output_tokens: Optional[int],
    debug_parser: bool = False,
) -> BidCompRenderResponse:
    if temperature < 0 or temperature > 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Temperature must be between 0 and 2")

    with TemporaryDirectory(prefix="bid-comp-") as tmp:
        workspace = Path(tmp)
        (workspace / "inputs").mkdir(parents=True, exist_ok=True)
        (workspace / "outputs").mkdir(parents=True, exist_ok=True)

        # Concurrency guard across requests
        if _parse_semaphore is not None:
            print(f"[bid-comp] Waiting on parse semaphore (limit={PARSE_CONCURRENCY})")
            await _parse_semaphore.acquire()
            print("[bid-comp] Acquired parse semaphore")
        try:
            if PARSE_IN_PARALLEL:
                carrier_task = _parse_estimate(
                    upload=carrier_estimate,
                    role_label="carrier",
                    workspace=workspace,
                    debug=debug_parser,
                )
                contractor_task = _parse_estimate(
                    upload=contractor_estimate,
                    role_label="contractor",
                    workspace=workspace,
                    debug=debug_parser,
                )
                try:
                    carrier_parsed, contractor_parsed = await asyncio.gather(carrier_task, contractor_task)
                    print("[bid-comp] Both parses completed successfully (parallel)")
                finally:
                    await asyncio.gather(carrier_estimate.close(), contractor_estimate.close())
            else:
                # Sequential to reduce CPU/memory pressure
                try:
                    carrier_parsed = await _parse_estimate(
                        upload=carrier_estimate,
                        role_label="carrier",
                        workspace=workspace,
                        debug=debug_parser,
                    )
                finally:
                    await carrier_estimate.close()

                try:
                    contractor_parsed = await _parse_estimate(
                        upload=contractor_estimate,
                        role_label="contractor",
                        workspace=workspace,
                        debug=debug_parser,
                    )
                finally:
                    await contractor_estimate.close()
                print("[bid-comp] Both parses completed successfully (sequential)")
        except Exception as parse_err:  # noqa: BLE001
            print("[bid-comp] Parser failure:", repr(parse_err))
            raise HTTPException(status_code=500, detail=f"Parser failure: {parse_err}") from parse_err
        finally:
            if _parse_semaphore is not None:
                _parse_semaphore.release()
                print("[bid-comp] Released parse semaphore")

        left_label = (left_label_override or _infer_estimate_label(carrier_parsed)).strip()
        right_label = (right_label_override or _infer_estimate_label(contractor_parsed)).strip()
        row_header = (row_label_header or "Category").strip() or "Category"

        recap_a = _extract_recap_by_category(carrier_parsed.payload) or {}
        recap_b = _extract_recap_by_category(contractor_parsed.payload) or {}

        context = {
            "LEFT_LABEL": left_label,
            "RIGHT_LABEL": right_label,
            "ROW_LABEL_HEADER": row_header,
            "RECAP_A_JSON": json.dumps(recap_a, ensure_ascii=False, indent=2),
            "RECAP_B_JSON": json.dumps(recap_b, ensure_ascii=False, indent=2),
        }

        template_source = prompt_template or DEFAULT_PROMPT_TEMPLATE.template
        prompt_body = _render_prompt_template(template_source, context)

        messages = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_body},
        ]

        openai_request_preview = {
            "model": model,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "messages": messages,
        }

        openai_result: Optional[OpenAIResult] = None

    return BidCompRenderResponse(
        carrier_estimate=carrier_parsed,
        contractor_estimate=contractor_parsed,
        openai_request_preview=openai_request_preview,
        openai_result=openai_result,
        left_label=left_label,
        right_label=right_label,
        row_label_header=row_header,
    )


__all__ = [
    "BidCompRenderResponse",
    "OpenAIResult",
    "ParsedEstimate",
    "process_bid_comp_render",
]


