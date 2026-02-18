from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from .taxonomy import canonicalize_group, COVERAGE_ALIASES


SPACE_RE = re.compile(r"\s+")
MONEY_RE = re.compile(r"[^0-9.\-]")


def normalize_money(value: object) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.upper() in {"N/A", "NULL"}:
        return None
    cleaned = MONEY_RE.sub("", s)
    if cleaned in {"", "-", "."}:
        return None
    try:
        # round to 2 decimals deterministically
        return round(float(cleaned), 2)
    except Exception:
        return None


def normalize_label(s: str) -> str:
    if not s:
        return ""
    s2 = s.upper().replace("—", "-").replace("–", "-")
    s2 = SPACE_RE.sub(" ", s2).strip()
    return s2


def normalize_group(label: str) -> str:
    return canonicalize_group(normalize_label(label))


def normalize_coverage_label(raw: str) -> Tuple[str, Optional[str]]:
    """Return (canonical, note) where note describes cleaned noise if any."""
    if not raw:
        return "", None
    s = normalize_label(raw)
    # Remove percentages and geo-like fragments from coverage labels for canonicalization
    noise_note = None
    cleaned = re.sub(r"\b\d+\s*%\b", "", s)
    cleaned = re.sub(r"\b(UNIT|BLDG|BLD|HOUSE|APT|SUITE|LOT)\b[^|]*", "", cleaned)
    cleaned = SPACE_RE.sub(" ", cleaned).strip(" -")
    if cleaned != s:
        noise_note = f"Cleaned from '{s}'"
    canon = COVERAGE_ALIASES.get(cleaned, cleaned)
    return canon, noise_note


