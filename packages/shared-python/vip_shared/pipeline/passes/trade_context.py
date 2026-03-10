"""
Trade context extraction for the v2.6 cost-driver-first pipeline.

Builds TradeContext from parser JSON output (recap_by_category).
This is the first step of CostDriverPipeline (Phase 32).

Fallback hierarchy (TRADE-01, TRADE-02, TRADE-03):
  1. recap_by_category (all 6 doc types -- primary source)
  2. trade_summary enrichment when present (StateFarm final-drafts only)
  3. Synthesize from section totals (last-resort for unknown doc types)

Note on imports: vip_shared.bid_comp.__init__ imports BidComp from core.py, and
bid_comp/core.py imports from ..pipeline (NarrativePipeline etc.), creating a
circular import when this module is loaded at pipeline init time (via passes/__init__).
All bid_comp imports are deferred to function call time to break the cycle.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from vip_shared.pipeline.models import TradeContext

# --- Inline normalize helpers (avoid bid_comp import cycle at module load time) ---
# These replicate bid_comp.normalize exactly so we don't need a module-level import.

_SPACE_RE = re.compile(r"\s+")
_MONEY_RE = re.compile(r"[^0-9.\-]")


def _normalize_money(value: object) -> Optional[float]:
    """Replicate vip_shared.bid_comp.normalize.normalize_money exactly."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.upper() in {"N/A", "NULL"}:
        return None
    cleaned = _MONEY_RE.sub("", s)
    if cleaned in {"", "-", "."}:
        return None
    try:
        return round(float(cleaned), 2)
    except Exception:
        return None


def _normalize_label(s: str) -> str:
    """Replicate vip_shared.bid_comp.normalize.normalize_label exactly."""
    if not s:
        return ""
    s2 = s.upper().replace("\u2014", "-").replace("\u2013", "-")
    s2 = _SPACE_RE.sub(" ", s2).strip()
    return s2


def _get_core_constants() -> Tuple[List[str], Dict[str, str], List[tuple], str]:
    """
    Lazy-load category constants from bid_comp.core.

    bid_comp/__init__ imports BidComp from core.py, and core.py imports
    from ..pipeline (NarrativePipeline) — circular at module load time.
    By the time any test or caller invokes build_trade_context(), the full
    module graph is initialized and the deferred import succeeds.

    Returns: (VERISK_CATEGORY_ORDER, XACTIMATE_CATEGORY_CODE_MAP, CATEGORY_KEYWORDS, CATEGORY_FALLBACK)
    """
    # Import submodule directly to bypass bid_comp/__init__ side-effects.
    # Python caches the module after first load so this is O(1) on repeat calls.
    import importlib
    core = importlib.import_module("vip_shared.bid_comp.core")
    return (
        core.VERISK_CATEGORY_ORDER,
        core.XACTIMATE_CATEGORY_CODE_MAP,
        core.CATEGORY_KEYWORDS,
        core.CATEGORY_FALLBACK,
    )


def build_trade_context(
    primary_payload: Dict[str, Any],
    comparison_payload: Dict[str, Any],
) -> TradeContext:
    """
    Build TradeContext from two parser JSON payloads.

    Args:
        primary_payload: Parser JSON dict for the primary (adjuster) estimate.
        comparison_payload: Parser JSON dict for the comparison (insurance) estimate.

    Returns:
        TradeContext with normalized category totals for both estimates.
        source == "recap_by_category" when recap data is present.
        source == "synthesized" when recap absent (falls back to section totals).

    Note: source reflects the primary estimate's source. If primary uses recap but
    comparison uses synthesized, source is still "recap_by_category".
    """
    primary_recap = _get_recap(primary_payload)
    comparison_recap = _get_recap(comparison_payload)

    if primary_recap:
        primary_cats = _extract_category_totals(primary_recap)
        source = "recap_by_category"
    else:
        primary_cats = _synthesize_from_sections(primary_payload)
        source = "synthesized"

    if comparison_recap:
        comparison_cats = _extract_category_totals(comparison_recap)
    else:
        comparison_cats = _synthesize_from_sections(comparison_payload)

    primary_trade_items = _get_trade_items(primary_payload)
    comparison_trade_items = _get_trade_items(comparison_payload)

    return TradeContext(
        primary_by_category=primary_cats,
        comparison_by_category=comparison_cats,
        source=source,
        primary_trade_items=primary_trade_items,
        comparison_trade_items=comparison_trade_items,
    )


# ---------- Private helpers ----------

def _get_recap(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract recap_by_category dict from payload, or None if absent."""
    if not isinstance(payload, dict):
        return None
    recaps = payload.get("recaps_and_summaries")
    if isinstance(recaps, dict):
        rb = recaps.get("recap_by_category")
        if isinstance(rb, dict) and rb:
            return rb
    # Fallback: recap_by_category at top level (defensive)
    rb = payload.get("recap_by_category")
    if isinstance(rb, dict) and rb:
        return rb
    return None


def _extract_category_totals(recap: Dict[str, Any]) -> Dict[str, float]:
    """
    Aggregate recap_by_category into display_category -> float totals.

    Mirrors BidCompOrchestrator._aggregate_categories() logic exactly.
    All non-"subtotals" keys are treated as category group lists.

    Group entry schema: {"item": "UPPERCASE_NAME", "total": "amount_str", ...}
    Subtotals schema: {"label": "...", "total": "amount_str"}
    """
    VERISK_CATEGORY_ORDER, XACTIMATE_CATEGORY_CODE_MAP, CATEGORY_KEYWORDS, CATEGORY_FALLBACK = _get_core_constants()
    totals: Dict[str, float] = {cat: 0.0 for cat in VERISK_CATEGORY_ORDER}

    for group_label, items in recap.items():
        if group_label == "subtotals" or not isinstance(items, list):
            continue
        for entry in items:
            if not isinstance(entry, dict):
                continue
            amount = _normalize_money(entry.get("total") or entry.get("amount"))
            if amount is None:
                continue
            raw_name = entry.get("item") or entry.get("name") or entry.get("label") or ""
            mapped = _map_category(
                raw_name or group_label,
                XACTIMATE_CATEGORY_CODE_MAP,
                CATEGORY_KEYWORDS,
                CATEGORY_FALLBACK,
            )
            totals[mapped] = round(totals.get(mapped, 0.0) + amount, 2)

    # Subtotals: map Overhead/Profit -> "Overhead & Profit", Tax -> "Material Sales Tax"
    subtotals = recap.get("subtotals") if isinstance(recap, dict) else None
    if isinstance(subtotals, list):
        for entry in subtotals:
            if not isinstance(entry, dict):
                continue
            label = _normalize_label(entry.get("label") or "")
            amount = _normalize_money(entry.get("total"))
            if amount is None:
                continue
            if "OVERHEAD" in label or "PROFIT" in label:
                totals["Overhead & Profit"] = round(totals.get("Overhead & Profit", 0.0) + amount, 2)
            elif "MATERIAL" in label and "TAX" in label:
                totals["Material Sales Tax"] = round(totals.get("Material Sales Tax", 0.0) + amount, 2)
            elif "PERMIT" in label:
                totals["Permit Fees"] = round(totals.get("Permit Fees", 0.0) + amount, 2)

    return totals


def _map_category(
    raw_name: str,
    xactimate_map: Dict[str, str],
    keywords: List[tuple],
    fallback: str,
) -> str:
    """
    Map a raw XACTIMATE name or code to a VERISK display category name.

    Mirrors BidCompOrchestrator._map_category() exactly.
    """
    normalized = _normalize_label(raw_name or "")
    if not normalized:
        return fallback

    # Prefer explicit Xactimate category codes when present (e.g., "FRM Framing")
    code = normalized.split(" ", 1)[0].strip("-:")
    if code in xactimate_map:
        return xactimate_map[code]

    for needle, mapped in keywords:
        if needle in normalized:
            return mapped
    return fallback


def _synthesize_from_sections(payload: Dict[str, Any]) -> Dict[str, float]:
    """
    TRADE-03: Synthesize category totals from section-level data.

    Last-resort fallback when recap_by_category is absent.
    Less accurate than recap_by_category (section names are room names, not trade names).
    """
    VERISK_CATEGORY_ORDER, XACTIMATE_CATEGORY_CODE_MAP, CATEGORY_KEYWORDS, CATEGORY_FALLBACK = _get_core_constants()
    totals: Dict[str, float] = {cat: 0.0 for cat in VERISK_CATEGORY_ORDER}
    if not isinstance(payload, dict):
        return totals

    sections = payload.get("sections") or []
    if not isinstance(sections, list):
        return totals

    for sec in sections:
        if not isinstance(sec, dict):
            continue
        raw_total = (sec.get("section_totals") or {}).get("total")
        amount = _normalize_money(raw_total)
        if amount is None:
            continue
        section_name = sec.get("section_name") or ""
        mapped = _map_category(
            section_name,
            XACTIMATE_CATEGORY_CODE_MAP,
            CATEGORY_KEYWORDS,
            CATEGORY_FALLBACK,
        )
        totals[mapped] = round(totals.get(mapped, 0.0) + amount, 2)

    return totals


def _get_trade_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    TRADE-02: Extract trade_summary line_items when present.

    Returns the raw line_items list from trade_summary (StateFarm final-drafts only).
    Returns empty list for all other doc types.
    """
    if not isinstance(payload, dict):
        return []
    recaps = payload.get("recaps_and_summaries")
    if not isinstance(recaps, dict):
        return []
    trade = recaps.get("trade_summary")
    if not isinstance(trade, dict):
        return []
    items = trade.get("line_items")
    if not isinstance(items, list):
        return []
    return items
