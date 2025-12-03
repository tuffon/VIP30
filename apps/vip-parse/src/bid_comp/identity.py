from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def ensure_estimate_identity(payload: Dict[str, Any] | None, fallback: str | None = None) -> str:
    """
    Ensure the parsed payload exposes an estimate_name at the root and within case_metadata.
    Returns the resolved estimate_name so callers can label downstream artifacts consistently.
    """
    fallback_name = _sanitize_name(fallback)
    estimate_name = fallback_name

    if isinstance(payload, dict):
        raw_name = payload.get("estimate_name")
        if isinstance(raw_name, str) and raw_name.strip():
            estimate_name = raw_name.strip()
        else:
            case_md = payload.get("case_metadata")
            if isinstance(case_md, dict):
                case_name = case_md.get("estimate_name")
                if isinstance(case_name, str) and case_name.strip():
                    estimate_name = case_name.strip()
        payload["estimate_name"] = estimate_name
        case_md = payload.get("case_metadata")
        if isinstance(case_md, dict) and not case_md.get("estimate_name"):
            case_md["estimate_name"] = estimate_name

    return estimate_name


def _sanitize_name(raw: str | None) -> str:
    if not raw:
        return "Estimate"
    stem = Path(str(raw)).stem.strip()
    return stem or "Estimate"


__all__ = ["ensure_estimate_identity"]

