"""Visible-text filtering helpers for pdfplumber pages.

This module centralizes the heuristics we use to strip invisible or overlay
text (e.g. white-on-white, text rendering mode 3, micro-font artifacts) before
the deterministic Xactimate parsers consume the text stream.  The goal is to
keep our existing parsing logic untouched while ensuring the extracted lines
match what a human sees in the PDF.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger("vip-parse.visible-text")

ColorTuple = Tuple[float, float, float]
DebugPages = Union[str, frozenset[int], None]


@dataclass
class VisibleTextConfig:
    """Tunable thresholds for visible-character filtering."""

    bg_is_white: bool = True
    drop_white_text: bool = True
    white_threshold: float = 0.97
    min_font_size: float = 2.0
    drop_invisible_render_mode: bool = True
    drop_out_of_bounds_chars: bool = True
    page_margin_tolerance: float = 1.0
    drop_small_font_overlay: bool = True
    overlay_small_font_max_size: float = 7.5
    overlay_min_chars_per_line: int = 6
    overlay_duplicate_top_tolerance: float = 0.5
    overlay_duplicate_x_tolerance: float = 0.25
    overlay_duplicate_ratio_threshold: float = 0.35
    overlay_oob_ratio_threshold: float = 0.25
    overlay_duplicate_max_x_span: float = 0.0  # 0 = disabled
    overlay_span_min_font_for_guard: float = 3.0
    drop_measurement_overlays: bool = True
    measurement_max_font_size: float = 7.5
    measurement_max_span: float = 30.0
    measurement_min_chars: int = 2
    measurement_allowed_chars: str = "0123456789'\".- /"
    debug_pages: DebugPages = None  # "all" or frozenset of 1-based page numbers
    debug_sample_lines: int = 3
    debug_log_colors: bool = False


DEFAULT_VISIBLE_TEXT_CONFIG = VisibleTextConfig()
_CACHED_CONFIG: Optional[VisibleTextConfig] = None


def get_visible_text_config() -> VisibleTextConfig:
    """Return a cached config populated from environment variables."""
    global _CACHED_CONFIG
    if _CACHED_CONFIG is None:
        _CACHED_CONFIG = load_visible_text_config_from_env(DEFAULT_VISIBLE_TEXT_CONFIG)
    return _CACHED_CONFIG


def load_visible_text_config_from_env(base: VisibleTextConfig | None = None) -> VisibleTextConfig:
    cfg = dataclasses.replace(base or DEFAULT_VISIBLE_TEXT_CONFIG)
    cfg.white_threshold = _env_float("VISIBLE_TEXT_WHITE_THRESHOLD", cfg.white_threshold)
    cfg.min_font_size = _env_float("VISIBLE_TEXT_MIN_FONT_SIZE", cfg.min_font_size)
    cfg.drop_white_text = _env_bool("VISIBLE_TEXT_DROP_WHITE", cfg.drop_white_text)
    cfg.drop_invisible_render_mode = _env_bool(
        "VISIBLE_TEXT_DROP_INVISIBLE_MODE",
        cfg.drop_invisible_render_mode,
    )
    cfg.bg_is_white = _env_bool("VISIBLE_TEXT_BG_IS_WHITE", cfg.bg_is_white)
    cfg.drop_out_of_bounds_chars = _env_bool(
        "VISIBLE_TEXT_DROP_OUT_OF_BOUNDS",
        cfg.drop_out_of_bounds_chars,
    )
    cfg.page_margin_tolerance = _env_float(
        "VISIBLE_TEXT_BOUNDARY_MARGIN",
        cfg.page_margin_tolerance,
    )
    cfg.drop_small_font_overlay = _env_bool(
        "VISIBLE_TEXT_DROP_SMALL_OVERLAY",
        cfg.drop_small_font_overlay,
    )
    cfg.overlay_small_font_max_size = _env_float(
        "VISIBLE_TEXT_OVERLAY_MAX_FONT",
        cfg.overlay_small_font_max_size,
    )
    cfg.overlay_min_chars_per_line = int(
        os.getenv("VISIBLE_TEXT_OVERLAY_MIN_CHARS", str(cfg.overlay_min_chars_per_line)).strip()
    )
    cfg.overlay_duplicate_top_tolerance = _env_float(
        "VISIBLE_TEXT_OVERLAY_TOP_TOL",
        cfg.overlay_duplicate_top_tolerance,
    )
    cfg.overlay_duplicate_x_tolerance = _env_float(
        "VISIBLE_TEXT_OVERLAY_X_TOL",
        cfg.overlay_duplicate_x_tolerance,
    )
    cfg.overlay_duplicate_ratio_threshold = _env_float(
        "VISIBLE_TEXT_OVERLAY_DUP_RATIO",
        cfg.overlay_duplicate_ratio_threshold,
    )
    cfg.overlay_oob_ratio_threshold = _env_float(
        "VISIBLE_TEXT_OVERLAY_OOB_RATIO",
        cfg.overlay_oob_ratio_threshold,
    )
    cfg.overlay_duplicate_max_x_span = _env_float(
        "VISIBLE_TEXT_OVERLAY_DUP_MAX_SPAN",
        cfg.overlay_duplicate_max_x_span,
    )
    cfg.overlay_span_min_font_for_guard = _env_float(
        "VISIBLE_TEXT_OVERLAY_SPAN_MIN_FONT",
        cfg.overlay_span_min_font_for_guard,
    )
    cfg.drop_measurement_overlays = _env_bool(
        "VISIBLE_TEXT_DROP_MEASUREMENT_OVERLAY",
        cfg.drop_measurement_overlays,
    )
    cfg.measurement_max_font_size = _env_float(
        "VISIBLE_TEXT_MEASUREMENT_MAX_FONT",
        cfg.measurement_max_font_size,
    )
    cfg.measurement_max_span = _env_float(
        "VISIBLE_TEXT_MEASUREMENT_MAX_SPAN",
        cfg.measurement_max_span,
    )
    cfg.measurement_min_chars = int(
        os.getenv("VISIBLE_TEXT_MEASUREMENT_MIN_CHARS", str(cfg.measurement_min_chars)).strip()
    )
    cfg.measurement_allowed_chars = os.getenv(
        "VISIBLE_TEXT_MEASUREMENT_ALLOWED_CHARS",
        cfg.measurement_allowed_chars,
    )
    cfg.debug_log_colors = _env_bool("VISIBLE_TEXT_DEBUG_LOG_COLORS", cfg.debug_log_colors)
    cfg.debug_sample_lines = int(
        os.getenv("VISIBLE_TEXT_DEBUG_SAMPLE_LINES", str(cfg.debug_sample_lines)).strip()
    )
    debug_pages = os.getenv("VISIBLE_TEXT_DEBUG_PAGES")
    if debug_pages:
        debug_value = debug_pages.strip().lower()
        if debug_value == "all":
            cfg.debug_pages = "all"
        else:
            selections = []
            for token in debug_value.replace(";", ",").split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    selections.append(int(token))
                except ValueError:
                    logger.warning("Ignoring invalid VISIBLE_TEXT_DEBUG_PAGES token: %s", token)
            cfg.debug_pages = frozenset(selections) if selections else None
    return cfg


def is_visible_char(
    char: Dict[str, Any],
    config: Optional[VisibleTextConfig] = None,
    *,
    page_bbox: Optional[Tuple[float, float, float, float]] = None,
) -> bool:
    """Return True if the char dict should be treated as visible."""
    config = config or get_visible_text_config()

    if (
        config.drop_out_of_bounds_chars
        and page_bbox is not None
        and _char_out_of_bounds(
            char,
            page_bbox,
            margin=config.page_margin_tolerance,
        )
    ):
        return False

    if config.drop_invisible_render_mode and int(char.get("text_rendering_mode", 0) or 0) == 3:
        return False

    size = _safe_float(char.get("size"))
    if size is not None and size < config.min_font_size:
        return False

    if config.drop_white_text and config.bg_is_white:
        color = normalize_color(char.get("non_stroking_color"))
        if color is not None and _is_color_close_to_white(color, config.white_threshold):
            return False

    return True


def normalize_color(value: Any) -> Optional[ColorTuple]:
    """Normalize pdfplumber color values into an RGB tuple in [0, 1]."""
    if value is None:
        return None

    seq: Sequence[float] | None = None
    if isinstance(value, (list, tuple)):
        seq = tuple(_clamp_unit(_safe_float(v)) for v in value if _safe_float(v) is not None)
    elif isinstance(value, (int, float)):
        normalized = _normalize_scalar_color(float(value))
        seq = (normalized,)
    elif isinstance(value, str):
        try:
            normalized = _normalize_scalar_color(float(value))
            seq = (normalized,)
        except ValueError:
            return None

    if not seq:
        return None

    if len(seq) == 1:
        c = seq[0]
        return c, c, c

    if len(seq) >= 3:
        return seq[0], seq[1], seq[2]

    return None


def filter_visible_chars(page: Any, config: Optional[VisibleTextConfig] = None) -> List[Dict[str, Any]]:
    """Return a list of visible char dicts from a pdfplumber page."""
    visible_chars, _ = _visible_chars_and_filtered_page(page, config, build_filtered_page=False)
    return visible_chars


def extract_visible_lines(
    page: Any,
    config: Optional[VisibleTextConfig] = None,
    *,
    strip_empty: bool = True,
    debug_page_number: Optional[int] = None,
    **text_kwargs: Any,
) -> List[str]:
    """Return newline-delimited lines extracted only from visible characters."""
    visible_chars, visible_page = _visible_chars_and_filtered_page(
        page,
        config,
        build_filtered_page=True,
    )
    try:
        raw_text = visible_page.extract_text(**text_kwargs) or ""
    except Exception:
        logger.exception("extract_visible_lines: page.extract_text failed; returning empty string")
        raw_text = ""
    lines = raw_text.split("\n")
    if strip_empty:
        lines = [ln.strip() for ln in lines]
        lines = [ln for ln in lines if ln]

    if _should_debug_page(config, debug_page_number):
        _log_debug_page(
            page,
            visible_chars,
            config,
            debug_page_number,
            lines[: config.debug_sample_lines],
        )

    return lines


def extract_visible_words(
    page: Any,
    config: Optional[VisibleTextConfig] = None,
    **word_kwargs: Any,
) -> List[Dict[str, Any]]:
    """Return words generated from visible characters only."""
    _, visible_page = _visible_chars_and_filtered_page(page, config, build_filtered_page=True)
    try:
        return visible_page.extract_words(**word_kwargs)
    except Exception:
        logger.exception("extract_visible_words failed; returning empty list")
        return []


def summarize_color_usage(chars: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Aggregate char counts by coarse color bucket for debugging."""
    buckets: Dict[str, int] = {}
    for char in chars:
        color = normalize_color(char.get("non_stroking_color"))
        label = _color_bucket_label(color)
        buckets[label] = buckets.get(label, 0) + 1
    return buckets


def _log_debug_page(
    original_page: Any,
    visible_chars: List[Dict[str, Any]],
    config: VisibleTextConfig,
    page_number: Optional[int],
    visible_lines_sample: List[str],
) -> None:
    raw_chars = getattr(original_page, "chars", []) or []
    total = len(raw_chars)
    kept = len(visible_chars)
    logger.info(
        "[visible-text] page=%s kept=%d/%d (%.1f%%)",
        page_number,
        kept,
        total,
        (kept / total * 100) if total else 0.0,
    )
    if config.debug_log_colors and raw_chars:
        color_summary = summarize_color_usage(raw_chars)
        logger.info("[visible-text] page=%s color summary=%s", page_number, color_summary)

    if config.debug_sample_lines > 0:
        try:
            raw_text = original_page.extract_text() or ""
        except Exception:
            raw_text = ""
        raw_lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]
        logger.info("[visible-text] page=%s raw sample=%s", page_number, raw_lines[: config.debug_sample_lines])
        logger.info(
            "[visible-text] page=%s filtered sample=%s",
            page_number,
            visible_lines_sample,
        )


def _char_out_of_bounds(
    char: Dict[str, Any],
    bbox: Tuple[float, float, float, float],
    *,
    margin: float,
) -> bool:
    page_x0, page_top, page_x1, page_bottom = bbox
    x0 = _safe_float(char.get("x0"))
    x1 = _safe_float(char.get("x1", x0))
    top = _safe_float(char.get("top"))
    bottom = _safe_float(char.get("bottom", top))

    if x1 is not None and x1 < (page_x0 - margin):
        return True
    if x0 is not None and x0 > (page_x1 + margin):
        return True
    if bottom is not None and bottom < (page_top - margin):
        return True
    if top is not None and top > (page_bottom + margin):
        return True
    return False


def _should_debug_page(config: VisibleTextConfig, page_number: Optional[int]) -> bool:
    if not config.debug_pages:
        return False
    if config.debug_pages == "all":
        return True
    if page_number is None:
        return False
    return page_number in config.debug_pages


def _is_color_close_to_white(color: ColorTuple, threshold: float) -> bool:
    return all(channel >= threshold for channel in color)


def _color_bucket_label(color: Optional[ColorTuple]) -> str:
    if color is None:
        return "unknown"
    if _is_color_close_to_white(color, 0.95):
        return "white-ish"
    if all(channel <= 0.2 for channel in color):
        return "dark"
    if color[0] > color[1] and color[0] > color[2]:
        return "red-ish"
    if color[1] >= color[0] and color[1] > color[2]:
        return "green-ish"
    if color[2] >= color[0] and color[2] >= color[1]:
        return "blue-ish"
    return "other"


def _env_bool(var: str, default: bool) -> bool:
    val = os.getenv(var)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(var: str, default: float) -> float:
    val = os.getenv(var)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        logger.warning("Invalid float for %s: %s (using %s)", var, val, default)
        return default


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_scalar_color(value: float) -> float:
    if value > 1.0:
        value = value / 255.0
    return _clamp_unit(value)


def _clamp_unit(value: Optional[float]) -> float:
    if value is None:
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _compute_small_font_overlay_drop_mask(
    chars: List[Dict[str, Any]],
    config: VisibleTextConfig,
    bbox: Optional[Tuple[float, float, float, float]],
) -> List[bool]:
    mask = [False] * len(chars)
    if not config.drop_small_font_overlay:
        return mask

    small_font_idxs: List[int] = []
    for idx, char in enumerate(chars):
        size = _safe_float(char.get("size"))
        if size is None:
            continue
        if size <= config.overlay_small_font_max_size:
            small_font_idxs.append(idx)

    if not small_font_idxs:
        return mask

    baseline_tol = max(config.overlay_duplicate_top_tolerance, 0.1)
    groups: Dict[int, List[int]] = {}
    for idx in small_font_idxs:
        top = _safe_float(chars[idx].get("top"))
        if top is None:
            continue
        bucket = int(round(top / baseline_tol))
        groups.setdefault(bucket, []).append(idx)

    for idxs in groups.values():
        measurement_flag = _is_measurement_group(chars, idxs, config)
        if measurement_flag:
            for idx in idxs:
                mask[idx] = True
            continue

        if len(idxs) < config.overlay_min_chars_per_line:
            continue

        duplicate_ratio = _duplicate_ratio(chars, idxs, config.overlay_duplicate_x_tolerance)
        oob_ratio = _oob_ratio(chars, idxs, bbox, config)
        span = _baseline_span(chars, idxs, min_font_size=config.overlay_span_min_font_for_guard)
        span_guard_enabled = config.overlay_duplicate_max_x_span > 0

        duplicate_flag = (
            duplicate_ratio >= config.overlay_duplicate_ratio_threshold
            and (
                not span_guard_enabled
                or span is None
                or span <= config.overlay_duplicate_max_x_span
            )
        )

        if duplicate_flag or (
            config.overlay_oob_ratio_threshold > 0
            and oob_ratio >= config.overlay_oob_ratio_threshold
        ):
            for idx in idxs:
                mask[idx] = True

    return mask


def _duplicate_ratio(chars: List[Dict[str, Any]], idxs: List[int], x_tolerance: float) -> float:
    if not idxs:
        return 0.0
    tol = max(x_tolerance, 0.05)
    seen: Dict[Tuple[str, int], int] = {}
    duplicates = 0
    for idx in idxs:
        char = chars[idx]
        text = char.get("text")
        if not text:
            continue
        x0 = _safe_float(char.get("x0"))
        if x0 is None:
            continue
        bucket = int(round(x0 / tol))
        key = (text, bucket)
        if key in seen:
            duplicates += 1
        else:
            seen[key] = idx
    return duplicates / len(idxs)


def _oob_ratio(
    chars: List[Dict[str, Any]],
    idxs: List[int],
    bbox: Optional[Tuple[float, float, float, float]],
    config: VisibleTextConfig,
) -> float:
    if not idxs or not config.drop_out_of_bounds_chars or bbox is None:
        return 0.0
    oob = 0
    for idx in idxs:
        if _char_out_of_bounds(chars[idx], bbox, margin=config.page_margin_tolerance):
            oob += 1
    return oob / len(idxs)


def _baseline_span(
    chars: List[Dict[str, Any]],
    idxs: List[int],
    *,
    min_font_size: float = 0.0,
) -> Optional[float]:
    xs: List[float] = []
    for idx in idxs:
        size = _safe_float(chars[idx].get("size"))
        if size is not None and size < min_font_size:
            continue
        x0 = _safe_float(chars[idx].get("x0"))
        x1 = _safe_float(chars[idx].get("x1"))
        if x0 is None or x1 is None:
            continue
        xs.append(x0)
        xs.append(x1)
    if len(xs) < 2:
        return None
    return max(xs) - min(xs)


def _is_measurement_group(chars: List[Dict[str, Any]], idxs: List[int], config: VisibleTextConfig) -> bool:
    if not config.drop_measurement_overlays:
        return False
    allowed = set(config.measurement_allowed_chars or "")
    if not allowed:
        return False

    span = _baseline_span(chars, idxs, min_font_size=0.0)
    if span is None or span > config.measurement_max_span:
        return False

    usable = 0
    for idx in idxs:
        char = chars[idx]
        text = char.get("text") or ""
        stripped = text.strip()
        if not stripped:
            continue
        usable += 1
        if any(ch not in allowed for ch in text):
            return False
        size = _safe_float(char.get("size"))
        if size is None or size > config.measurement_max_font_size:
            return False
    if usable < config.measurement_min_chars:
        return False
    return True


def _visible_chars_and_filtered_page(
    page: Any,
    config: Optional[VisibleTextConfig],
    *,
    build_filtered_page: bool,
) -> Tuple[List[Dict[str, Any]], Any]:
    config = config or get_visible_text_config()
    chars: List[Dict[str, Any]] = list(getattr(page, "chars", []) or [])
    bbox = getattr(page, "bbox", None)
    overlay_drop_mask = _compute_small_font_overlay_drop_mask(chars, config, bbox)
    visible_chars: List[Dict[str, Any]] = []
    keep_ids: set[int] = set()
    for idx, char in enumerate(chars):
        if overlay_drop_mask[idx]:
            continue
        if is_visible_char(char, config, page_bbox=bbox):
            visible_chars.append(char)
            keep_ids.add(id(char))

    filtered_page = page
    if build_filtered_page and hasattr(page, "filter"):
        def predicate(obj: Dict[str, Any]) -> bool:
            if obj.get("object_type") != "char":
                return True
            return id(obj) in keep_ids

        filtered_page = page.filter(predicate)

    return visible_chars, filtered_page


__all__ = [
    "VisibleTextConfig",
    "DEFAULT_VISIBLE_TEXT_CONFIG",
    "extract_visible_lines",
    "extract_visible_words",
    "filter_visible_chars",
    "get_visible_text_config",
    "is_visible_char",
    "normalize_color",
    "summarize_color_usage",
]

