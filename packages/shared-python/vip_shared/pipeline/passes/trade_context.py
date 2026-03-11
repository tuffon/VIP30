"""
Trade context extraction for the v2.6 cost-driver-first pipeline.

Builds TradeContext from parser JSON output using exact parsed category titles.
This is the first step of CostDriverPipeline.

Fallback hierarchy:
  1. trade_summary-backed evidence when present, with recap totals remaining authoritative
  2. recap_by_category exact category rows
  3. Synthesize from section totals (last-resort for unknown doc types)

Rollup subtotal labels such as "O&P Items" and "Total" are excluded because they
are recap section buckets, not real estimate categories.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from vip_shared.pipeline.models import CategoryEvidence, TradeContext

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
        TradeContext with normalized category totals for both estimates plus
        source-aware category evidence bundles.

    Note: `source` reflects the primary estimate's dominant source. Phase 34 makes
    trade_summary the preferred source when present because it already combines
    category totals with linked supporting items.
    """
    primary_cats, primary_source, primary_evidence, primary_trade_items = _build_category_view(primary_payload)
    comparison_cats, comparison_source, comparison_evidence, comparison_trade_items = _build_category_view(comparison_payload)

    return TradeContext(
        primary_by_category=primary_cats,
        comparison_by_category=comparison_cats,
        source=primary_source,
        primary_source=primary_source,
        comparison_source=comparison_source,
        primary_category_evidence=primary_evidence,
        comparison_category_evidence=comparison_evidence,
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


def _build_category_view(
    payload: Dict[str, Any],
) -> Tuple[Dict[str, float], str, Dict[str, CategoryEvidence], List[Dict[str, Any]]]:
    """Build exact-label category totals and evidence bundles for one estimate payload."""
    recap = _get_recap(payload)
    trade_items = _get_trade_items(payload)

    recap_totals = _extract_category_totals(recap) if recap else {}
    recap_evidence = _extract_recap_evidence(recap) if recap else {}
    trade_totals, trade_evidence = _extract_trade_summary_evidence(trade_items)

    if trade_evidence:
        totals = dict(recap_totals)
        evidence = dict(recap_evidence)
        for category, trade_bundle in trade_evidence.items():
            if category in recap_totals:
                trade_bundle.total = recap_totals[category]
                totals[category] = recap_totals[category]
            else:
                totals[category] = trade_totals.get(category, trade_bundle.total)
            evidence[category] = trade_bundle
        return totals, "trade_summary", evidence, trade_items

    if recap:
        return recap_totals, "recap_by_category", recap_evidence, trade_items

    synth_totals = _synthesize_from_sections(payload)
    synth_evidence = {
        category: CategoryEvidence(
            category=category,
            total=amount,
            source="synthesized",
            supporting_items=[],
            supporting_groups=[],
        )
        for category, amount in synth_totals.items()
        if amount
    }
    return synth_totals, "synthesized", synth_evidence, trade_items


def _extract_category_totals(recap: Dict[str, Any]) -> Dict[str, float]:
    """Aggregate recap_by_category using exact parsed labels as keys."""
    totals: Dict[str, float] = {}
    group_labels = {
        _normalize_label(str(group_label))
        for group_label, items in recap.items()
        if group_label != "subtotals" and isinstance(items, list)
    }

    for group_label, items in recap.items():
        if group_label == "subtotals" or not isinstance(items, list):
            continue
        for entry in items:
            if not isinstance(entry, dict):
                continue
            amount = _normalize_money(entry.get("total") or entry.get("amount"))
            if amount is None:
                continue
            label = _exact_category_label(
                entry.get("item") or entry.get("name") or entry.get("label") or group_label
            )
            if not label:
                continue
            totals[label] = round(totals.get(label, 0.0) + amount, 2)

    # Preserve subtotal labels exactly rather than remapping them to synthetic buckets.
    subtotals = recap.get("subtotals") if isinstance(recap, dict) else None
    if isinstance(subtotals, list):
        for entry in subtotals:
            if not isinstance(entry, dict):
                continue
            label = _exact_category_label(entry.get("label") or "")
            amount = _normalize_money(entry.get("total"))
            if amount is None:
                continue
            if not label or _is_rollup_subtotal_label(label, group_labels):
                continue
            totals[label] = round(totals.get(label, 0.0) + amount, 2)

    return totals


def _extract_recap_evidence(recap: Dict[str, Any]) -> Dict[str, CategoryEvidence]:
    """Build source-aware category evidence bundles from recap_by_category."""
    evidence: Dict[str, CategoryEvidence] = {}
    group_labels = {
        _normalize_label(str(group_label))
        for group_label, items in recap.items()
        if group_label != "subtotals" and isinstance(items, list)
    }

    for group_label, items in recap.items():
        if group_label == "subtotals" or not isinstance(items, list):
            continue
        for entry in items:
            if not isinstance(entry, dict):
                continue
            amount = _normalize_money(entry.get("total") or entry.get("amount"))
            if amount is None:
                continue
            label = _exact_category_label(
                entry.get("item") or entry.get("name") or entry.get("label") or group_label
            )
            if not label:
                continue
            current = evidence.get(label)
            if current is None:
                evidence[label] = CategoryEvidence(
                    category=label,
                    total=round(amount, 2),
                    source="recap_by_category",
                    supporting_items=[],
                    supporting_groups=[entry],
                )
            else:
                current.total = round(current.total + amount, 2)
                current.supporting_groups.append(entry)

    subtotals = recap.get("subtotals") if isinstance(recap, dict) else None
    if isinstance(subtotals, list):
        for entry in subtotals:
            if not isinstance(entry, dict):
                continue
            label = _exact_category_label(entry.get("label") or "")
            amount = _normalize_money(entry.get("total"))
            if amount is None:
                continue
            if not label or _is_rollup_subtotal_label(label, group_labels):
                continue
            current = evidence.get(label)
            if current is None:
                evidence[label] = CategoryEvidence(
                    category=label,
                    total=round(amount, 2),
                    source="recap_by_category",
                    supporting_items=[],
                    supporting_groups=[entry],
                )
            else:
                current.total = round(current.total + amount, 2)
                current.supporting_groups.append(entry)

    return evidence


def _extract_trade_summary_evidence(
    trade_items: List[Dict[str, Any]],
) -> Tuple[Dict[str, float], Dict[str, CategoryEvidence]]:
    """
    Build category totals/evidence from trade_summary rows.

    trade_summary is preferred because it already links category rollups to the
    items that support those rollups, avoiding separate lookup work later.
    """
    totals: Dict[str, float] = {}
    evidence: Dict[str, CategoryEvidence] = {}

    for trade_row in trade_items:
        if not isinstance(trade_row, dict):
            continue
        mapped = _exact_category_label(trade_row.get("trade") or trade_row.get("trade_code") or "")
        if not mapped:
            continue
        amount = _normalize_trade_total(trade_row)
        items = _normalize_trade_items(trade_row)

        current = evidence.get(mapped)
        if current is None:
            current = CategoryEvidence(
                category=mapped,
                total=0.0,
                source="trade_summary",
                supporting_items=[],
                supporting_groups=[],
            )
            evidence[mapped] = current

        current.total = round(current.total + amount, 2)
        current.supporting_items.extend(items)
        current.supporting_groups.append(trade_row)
        totals[mapped] = round(totals.get(mapped, 0.0) + amount, 2)

    return totals, evidence


def _synthesize_from_sections(payload: Dict[str, Any]) -> Dict[str, float]:
    """
    TRADE-03: Synthesize category totals from section-level data.

    Last-resort fallback when recap_by_category is absent.
    Less accurate than recap_by_category (section names are room names, not trade names).
    """
    totals: Dict[str, float] = {}
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
        label = _exact_category_label(sec.get("section_name") or "")
        if not label:
            continue
        totals[label] = round(totals.get(label, 0.0) + amount, 2)

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


def _normalize_trade_total(trade_row: Dict[str, Any]) -> float:
    """Best-effort replacement-cost total extraction for a trade_summary row."""
    total = trade_row.get("total")
    if isinstance(total, dict):
        amount = _normalize_money(total.get("repl_cost_total"))
        if amount is not None:
            return amount
    if isinstance(total, (int, float, str)):
        amount = _normalize_money(total)
        if amount is not None:
            return amount

    row_sum = 0.0
    for item in trade_row.get("items") or []:
        if not isinstance(item, dict):
            continue
        amount = _normalize_money(item.get("repl_cost_total") or item.get("total"))
        if amount is not None:
            row_sum += amount
    return round(row_sum, 2)


def _normalize_trade_items(trade_row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize trade_summary nested items into line-item-like dicts."""
    normalized: List[Dict[str, Any]] = []
    trade_code = (trade_row.get("trade_code") or "").strip().upper()
    trade = trade_row.get("trade") or ""
    for item in trade_row.get("items") or []:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "type": "line_item",
                "cat": trade_code,
                "trade": trade,
                "description": item.get("description") or "",
                "qty": item.get("line_item_qty") or "",
                "unit": "",
                "total": item.get("repl_cost_total") or item.get("total") or "0.00",
                "source": "trade_summary",
            }
        )
    return normalized


def _exact_category_label(value: object) -> str:
    """Preserve the parsed category title 1:1 except for whitespace normalization."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return _SPACE_RE.sub(" ", text)


def _is_rollup_subtotal_label(label: str, group_labels: set[str]) -> bool:
    """Return True for recap subtotal labels that are rollups, not real categories."""
    normalized = _normalize_label(label)
    if not normalized:
        return True
    if normalized in group_labels:
        return True
    return normalized in {
        "TOTAL",
        "ITEMS SUBTOTAL",
    }
