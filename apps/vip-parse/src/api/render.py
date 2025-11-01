"""Bid comparison render pipeline utilities."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile, status
import openai
from pydantic import BaseModel, Field

from parse.xactimate import XactimateRoughDraftParser


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY and not getattr(openai, "api_key", None):
    openai.api_key = OPENAI_API_KEY


DEFAULT_SYSTEM_PROMPT = (
    "You are an estimating analyst trained on Xactimate scopes. "
    "Use the provided JSON payloads to prepare a detailed comparison."
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
    openai_result: OpenAIResult


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


def _ensure_openai_ready() -> None:
    if not getattr(openai, "api_key", None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured",
        )


async def _call_openai(
    *,
    prompt: str,
    model: str,
    temperature: float,
    max_output_tokens: Optional[int],
    system_prompt: str,
) -> OpenAIResult:
    _ensure_openai_ready()

    def _invoke() -> OpenAIResult:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
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

    payload = await asyncio.to_thread(_run_xactimate_parser, input_path, output_dir, debug)

    return ParsedEstimate(filename=safe_name, payload=payload)


async def process_bid_comp_render(
    *,
    carrier_estimate: UploadFile,
    contractor_estimate: UploadFile,
    prompt_template: Optional[str],
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

        carrier_parsed, contractor_parsed = await asyncio.gather(carrier_task, contractor_task)
        await asyncio.gather(carrier_estimate.close(), contractor_estimate.close())

        prompt_body = prompt_template or (
            "Provide a concise summary of key differences between these estimates.\n\n"
            f"Carrier Estimate JSON:\n{json.dumps(carrier_parsed.payload, ensure_ascii=False)}\n\n"
            f"Contractor Estimate JSON:\n{json.dumps(contractor_parsed.payload, ensure_ascii=False)}"
        )

        openai_result = await _call_openai(
            prompt=prompt_body,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
        )

    return BidCompRenderResponse(
        carrier_estimate=carrier_parsed,
        contractor_estimate=contractor_parsed,
        openai_result=openai_result,
    )


__all__ = [
    "BidCompRenderResponse",
    "OpenAIResult",
    "ParsedEstimate",
    "process_bid_comp_render",
]


