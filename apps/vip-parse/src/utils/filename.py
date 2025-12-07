from __future__ import annotations

import re

MAX_FILENAME_LENGTH = 120
_CONTROL_CHARS = re.compile(r"[\x00-\x1F\x7F]")
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9 _\-.()+]")
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _normalize_base(raw: str | None) -> str:
    """Trim, drop control characters, collapse whitespace, and replace unsafe chars."""
    if raw is None:
        return ""
    text = raw.strip()
    if not text:
        return ""
    text = _CONTROL_CHARS.sub("", text)
    text = text.replace("\\", "_").replace("/", "_")
    text = _UNSAFE_CHARS.sub("_", text)
    text = re.sub(r"_+", "_", text)
    if len(text) > MAX_FILENAME_LENGTH:
        text = text[:MAX_FILENAME_LENGTH].rstrip("_")
    return text


def sanitize_storage_name(raw: str) -> str:
    """Return a filesystem/S3-safe filename or raise ValueError if none can be derived."""
    sanitized = _normalize_base(raw)
    if not sanitized:
        raise ValueError("Filename is empty after sanitization")
    return sanitized


def sanitize_display_name(raw: str) -> str:
    """Return a display-safe filename that avoids CSV/Excel formula execution."""
    sanitized = _normalize_base(raw) or "document"
    if sanitized[0] in _FORMULA_PREFIXES:
        sanitized = f"_{sanitized}"
    return sanitized
