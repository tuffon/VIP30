"""
Cost driver identification for the v2.6 cost-driver-first pipeline.

Identifies top cost drivers by absolute dollar delta from TradeContext,
maps all matching line items per driver, and verifies item sums against
category totals.

Requirements: DRIVER-01, DRIVER-02, DRIVER-03

Note on imports: same circular import constraint as trade_context.py applies here.
All bid_comp imports are deferred to function call time.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from vip_shared.pipeline.models import CostDriver, DriverWithItems, TradeContext

# --- Inline normalize helper (avoid bid_comp import cycle at module load time) ---

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


def _get_core_constants() -> Tuple[Dict[str, str], str]:
    """
    Lazy-load XACTIMATE_CATEGORY_CODE_MAP and CATEGORY_FALLBACK from bid_comp.core.

    Deferred to invocation time to break bid_comp/__init__ -> core.py -> ..pipeline cycle.
    O(1) on repeat calls (Python module cache).
    Returns: (XACTIMATE_CATEGORY_CODE_MAP, CATEGORY_FALLBACK)
    """
    import importlib
    core = importlib.import_module("vip_shared.bid_comp.core")
    return core.XACTIMATE_CATEGORY_CODE_MAP, core.CATEGORY_FALLBACK


# ---------- Public API ----------

def identify_cost_drivers(
    trade_ctx: TradeContext,
    top_n: int = 5,
) -> List[CostDriver]:
    """
    DRIVER-01: Identify top cost drivers by absolute dollar delta.

    Args:
        trade_ctx: TradeContext from build_trade_context() with category totals.
        top_n: Number of top drivers to return (default 5).

    Returns:
        List of CostDriver sorted by abs(delta) descending, length == top_n.
        Categories where both primary and comparison total == 0 are excluded.
    """
    drivers: List[CostDriver] = []

    for category in trade_ctx.primary_by_category:
        primary_total = trade_ctx.primary_by_category.get(category, 0.0)
        comparison_total = trade_ctx.comparison_by_category.get(category, 0.0)

        # Exclude categories where both estimates have zero (no activity in either)
        if primary_total == 0.0 and comparison_total == 0.0:
            continue

        delta = round(primary_total - comparison_total, 2)
        drivers.append(CostDriver(
            category=category,
            primary_total=primary_total,
            comparison_total=comparison_total,
            delta=delta,
        ))

    # Sort by abs_delta descending (deterministic -- DRIVER-01)
    drivers.sort(key=lambda d: d.abs_delta, reverse=True)
    return drivers[:top_n]


def map_driver_items(
    cost_drivers: List[CostDriver],
    primary_payload: Dict[str, Any],
    comparison_payload: Dict[str, Any],
    trade_ctx: Optional[TradeContext] = None,
) -> List[DriverWithItems]:
    """
    DRIVER-02: Map all line items for each cost driver category.

    Iterates all sections in both payloads, collecting type=='line_item' entries
    whose cat code resolves to driver.category via XACTIMATE_CATEGORY_CODE_MAP.

    DRIVER-03: Verifies that item sums approximate category totals.
    Tolerance: abs(item_sum - category_total) <= max(category_total * 0.10, 100.0)

    Args:
        cost_drivers: Output of identify_cost_drivers().
        primary_payload: Raw parser JSON dict for primary estimate.
        comparison_payload: Raw parser JSON dict for comparison estimate.

    Returns:
        List[DriverWithItems] in same order as cost_drivers input.
    """
    xactimate_map, fallback = _get_core_constants()
    selected_categories = [driver.category for driver in cost_drivers]

    primary_items_by_cat = _collect_items_for_categories(
        primary_payload,
        selected_categories,
        xactimate_map,
        fallback,
    )
    comparison_items_by_cat = _collect_items_for_categories(
        comparison_payload,
        selected_categories,
        xactimate_map,
        fallback,
    )

    results: List[DriverWithItems] = []
    for driver in cost_drivers:
        p_items = _resolve_driver_items(
            driver.category,
            payload_items=primary_items_by_cat.get(driver.category, []),
            evidence_map=(trade_ctx.primary_category_evidence if trade_ctx else None),
        )
        c_items = _resolve_driver_items(
            driver.category,
            payload_items=comparison_items_by_cat.get(driver.category, []),
            evidence_map=(trade_ctx.comparison_category_evidence if trade_ctx else None),
        )

        verification_ok, verification_note = _verify_item_sums(
            p_items, driver.primary_total,
            c_items, driver.comparison_total,
        )

        results.append(DriverWithItems(
            driver=driver,
            primary_items=p_items,
            comparison_items=c_items,
            verification_ok=verification_ok,
            verification_note=verification_note,
        ))

    return results


# ---------- Private helpers ----------

def _collect_items_for_categories(
    payload: Dict[str, Any],
    selected_categories: List[str],
    xactimate_map: Dict[str, str],
    fallback: str,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    One-pass extraction: iterate all sections -> all line_items -> group by mapped category.

    Only type=='line_item' entries collected. 'header' type entries are skipped.
    cat code mapped via XACTIMATE_CATEGORY_CODE_MAP; unmapped codes -> fallback.
    """
    allowed = set(selected_categories)
    result: Dict[str, List[Dict[str, Any]]] = {category: [] for category in allowed}

    if not isinstance(payload, dict):
        return result

    sections = payload.get("sections") or []
    if not isinstance(sections, list):
        return result

    for section in sections:
        if not isinstance(section, dict):
            continue
        line_items = section.get("line_items") or []
        if not isinstance(line_items, list):
            continue
        for item in line_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "line_item":
                continue  # skip 'header' type entries
            cat_code = item.get("cat") or ""
            category = xactimate_map.get(cat_code.upper(), fallback)
            if category not in allowed:
                continue
            result[category].append(item)

    return result


def _resolve_driver_items(
    category: str,
    payload_items: List[Dict[str, Any]],
    evidence_map: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Prefer trade-summary-derived evidence when available for the selected category.

    Otherwise fall back to section item mapping for the selected category only.
    """
    if evidence_map:
        evidence = evidence_map.get(category)
        supporting_items = getattr(evidence, "supporting_items", None)
        if supporting_items:
            return list(supporting_items)
    return payload_items


def _verify_item_sums(
    primary_items: List[Dict[str, Any]],
    primary_category_total: float,
    comparison_items: List[Dict[str, Any]],
    comparison_category_total: float,
) -> Tuple[bool, str]:
    """
    DRIVER-03: Verify that item sums approximately match category totals.

    Tolerance: abs(item_sum - category_total) <= max(category_total * 0.10, 100.0)

    Returns (verification_ok, verification_note).
    verification_note is empty when ok=True.
    """
    p_sum = _sum_item_totals(primary_items)
    c_sum = _sum_item_totals(comparison_items)

    p_ok = _within_tolerance(p_sum, primary_category_total)
    c_ok = _within_tolerance(c_sum, comparison_category_total)

    if p_ok and c_ok:
        return True, ""

    parts = []
    if not p_ok:
        parts.append(
            f"primary item sum ${p_sum:,.2f} vs category total ${primary_category_total:,.2f} "
            f"(delta ${p_sum - primary_category_total:,.2f})"
        )
    if not c_ok:
        parts.append(
            f"comparison item sum ${c_sum:,.2f} vs category total ${comparison_category_total:,.2f} "
            f"(delta ${c_sum - comparison_category_total:,.2f})"
        )
    return False, "; ".join(parts)


def _sum_item_totals(items: List[Dict[str, Any]]) -> float:
    """Sum the 'total' field of all items, treating None/unparseable as 0.0."""
    total = 0.0
    for item in items:
        amount = _normalize_money(item.get("total"))
        if amount is not None:
            total += amount
    return round(total, 2)


def _within_tolerance(item_sum: float, category_total: float) -> bool:
    """True when abs difference <= max(10% of category_total, $100.00)."""
    if category_total == 0.0 and item_sum == 0.0:
        return True
    tolerance = max(abs(category_total) * 0.10, 100.0)
    return abs(item_sum - category_total) <= tolerance
