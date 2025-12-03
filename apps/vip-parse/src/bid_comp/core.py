from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .export_xlsx import export_xlsx
from .identity import ensure_estimate_identity
from .normalize import normalize_label, normalize_money
from ..llm.adapter import LLMAdapterBase

logger = logging.getLogger("vip-parse.bid-comp")

VERISK_CATEGORY_ORDER: List[str] = [
    "Cleaning / Restoration",
    "Contents / Packout / Storage",
    "Demolition",
    "Framing / Structural",
    "Drywall / Insulation",
    "Painting",
    "Flooring",
    "Doors / Windows / Glass",
    "Cabinetry / Millwork",
    "Electrical",
    "Plumbing",
    "HVAC / Mechanical",
    "Roofing",
    "Siding / Exterior Finishes",
    "Masonry / Concrete / Foundation",
    "Fencing / Gates",
    "Landscaping / Trees / Shrubs",
    "Pools & Spas",
    "Appliances / Equipment",
    "Specialty Systems (low voltage, alarms, AV, solar)",
    "Miscellaneous / General Requirements",
    "Overhead & Profit",
    "Permit Fees",
    "Material Sales Tax",
    "Other / Unclassified",
]

CATEGORY_FALLBACK = "Other / Unclassified"

CATEGORY_KEYWORDS: List[tuple[str, str]] = [
    ("CLEAN", "Cleaning / Restoration"),
    ("RESTORATION", "Cleaning / Restoration"),
    ("SMOKE", "Cleaning / Restoration"),
    ("CONTENT", "Contents / Packout / Storage"),
    ("PACK", "Contents / Packout / Storage"),
    ("STORAGE", "Contents / Packout / Storage"),
    ("DEMOL", "Demolition"),
    ("FRAM", "Framing / Structural"),
    ("STRUCT", "Framing / Structural"),
    ("DRYWALL", "Drywall / Insulation"),
    ("INSUL", "Drywall / Insulation"),
    ("PAINT", "Painting"),
    ("FLOOR", "Flooring"),
    ("CARPET", "Flooring"),
    ("DOOR", "Doors / Windows / Glass"),
    ("WINDOW", "Doors / Windows / Glass"),
    ("GLAZ", "Doors / Windows / Glass"),
    ("GLASS", "Doors / Windows / Glass"),
    ("CABINET", "Cabinetry / Millwork"),
    ("MILLWORK", "Cabinetry / Millwork"),
    ("TRIM", "Cabinetry / Millwork"),
    ("ELECT", "Electrical"),
    ("PLUMB", "Plumbing"),
    ("MECHANICAL", "HVAC / Mechanical"),
    ("HVAC", "HVAC / Mechanical"),
    ("VENT", "HVAC / Mechanical"),
    ("ROOF", "Roofing"),
    ("SIDING", "Siding / Exterior Finishes"),
    ("STUCCO", "Siding / Exterior Finishes"),
    ("EXTERIOR", "Siding / Exterior Finishes"),
    ("MASON", "Masonry / Concrete / Foundation"),
    ("CONCRETE", "Masonry / Concrete / Foundation"),
    ("FOUNDATION", "Masonry / Concrete / Foundation"),
    ("STONE", "Masonry / Concrete / Foundation"),
    ("FENCE", "Fencing / Gates"),
    ("GATE", "Fencing / Gates"),
    ("LANDSCAP", "Landscaping / Trees / Shrubs"),
    ("TREE", "Landscaping / Trees / Shrubs"),
    ("SHRUB", "Landscaping / Trees / Shrubs"),
    ("POOL", "Pools & Spas"),
    ("SPA", "Pools & Spas"),
    ("APPLIANCE", "Appliances / Equipment"),
    ("EQUIP", "Appliances / Equipment"),
    ("LOW VOLT", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("ALARM", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("SECURITY", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("A/V", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("TELECOM", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("SOLAR", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("MISC", "Miscellaneous / General Requirements"),
    ("GENERAL REQUIREMENT", "Miscellaneous / General Requirements"),
    ("TEMP", "Miscellaneous / General Requirements"),
]

NARRATIVE_OUTPUT_TEMPLATE = json.dumps(
    {
        "executive_summary": "Two to three concise sentences summarizing the bid comparison.",
        "largest_deltas": [
            {
                "title": "Category driver",
                "category": "Category from provided list",
                "bid_a_total": 0,
                "bid_b_total": 0,
                "delta": 0,
                "insight": "Why the delta exists (scope, quantity, fees, etc.).",
            }
        ],
        "contextual_drivers": [
            "Short bullet on broader drivers or missing information."
        ],
        "follow_up_actions": [
            "Specific follow-up question or action item."
        ],
    },
    indent=2,
)


@dataclass
class EstimateTotals:
    grand_total: Optional[float]
    material_tax: Optional[float]
    overhead_and_profit: Optional[float]
    permit_fees: Optional[float]


@dataclass
class BidEstimate:
    role: str
    estimate_name: str
    payload: Dict[str, Any]
    recap: Dict[str, Any]
    totals: EstimateTotals
    summary_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BidPair:
    bid_a: BidEstimate
    bid_b: BidEstimate


@dataclass
class NarrativeResult:
    executive_summary: str
    largest_deltas: List[Dict[str, Any]]
    contextual_drivers: List[str]
    follow_up_actions: List[str]
    raw_response: str = ""
    parsed: bool = False


class BidComp:
    def __init__(self, llm_adapter: Optional[LLMAdapterBase] = None, top_delta_count: int = 6) -> None:
        self.llm_adapter = llm_adapter
        self.top_delta_count = max(1, int(top_delta_count))
        self.last_narrative_debug: Optional[Dict[str, Any]] = None
        self.last_narrative_artifact: Optional[Dict[str, Any]] = None

    def run(self, bid_context: dict, job_id: str) -> bytes:
        self.last_narrative_debug = None
        self.last_narrative_artifact = None
        pair = self._build_pair(bid_context)
        category_rows = self._build_category_table(pair)
        top_deltas = self._top_deltas(category_rows)
        narrative = self._generate_narrative(pair, top_deltas)
        recap_rows = self._flatten_original_recaps(pair)
        return export_xlsx(pair=pair, narrative=narrative, category_rows=category_rows, recap_rows=recap_rows)

    # ---------- Pair + estimate helpers ----------
    def _build_pair(self, bid_context: dict) -> BidPair:
        if not isinstance(bid_context, dict):
            raise ValueError("bid_context must be a dict")

        estimates_raw = bid_context.get("estimates")
        if isinstance(estimates_raw, list) and len(estimates_raw) >= 2:
            left_raw = estimates_raw[0]
            right_raw = estimates_raw[1]
            left_payload = self._resolve_payload(left_raw)
            right_payload = self._resolve_payload(right_raw)
        else:
            left_payload = self._resolve_payload(bid_context.get("carrier"))
            right_payload = self._resolve_payload(bid_context.get("contractor"))

        if not left_payload or not right_payload:
            raise ValueError("bid_context must include two estimate payloads")

        bid_a = self._build_estimate(left_payload, fallback_role="Bid A")
        bid_b = self._build_estimate(right_payload, fallback_role="Bid B")
        return BidPair(bid_a=bid_a, bid_b=bid_b)

    def _resolve_payload(self, value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(value, dict) and "payload" in value and isinstance(value["payload"], dict):
            return value["payload"]
        if isinstance(value, dict):
            return value
        return None

    def _build_estimate(self, payload: Dict[str, Any], fallback_role: str) -> BidEstimate:
        estimate_name = ensure_estimate_identity(payload, fallback_role)
        recap = self._extract_recap_from_context(payload)
        totals = self._extract_totals(payload, recap)
        summary_snapshot = self._build_summary_snapshot(payload, recap)
        return BidEstimate(
            role=fallback_role,
            estimate_name=estimate_name,
            payload=payload,
            recap=recap,
            totals=totals,
            summary_snapshot=summary_snapshot,
        )

    def _extract_recap_from_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        recaps = payload.get("recaps_and_summaries")
        if isinstance(recaps, dict):
            rb = recaps.get("recap_by_category")
            if isinstance(rb, dict):
                return rb
        rb = payload.get("recap_by_category")
        if isinstance(rb, dict):
            return rb
        return {}

    def _extract_totals(self, payload: Dict[str, Any], recap: Dict[str, Any]) -> EstimateTotals:
        case_md = payload.get("case_metadata") if isinstance(payload, dict) else {}
        li_totals = case_md.get("line_item_totals") if isinstance(case_md, dict) else {}
        grand_total = normalize_money((li_totals or {}).get("grand_total"))
        material_tax = normalize_money((li_totals or {}).get("material_sales_tax"))
        overhead_profit = normalize_money((li_totals or {}).get("overhead_profit"))
        permit_fees = self._extract_subtotal_amount(recap, "PERMIT")
        return EstimateTotals(
            grand_total=grand_total,
            material_tax=material_tax,
            overhead_and_profit=overhead_profit,
            permit_fees=permit_fees,
        )

    def _build_summary_snapshot(self, payload: Dict[str, Any], recap: Dict[str, Any]) -> Dict[str, Any]:
        sections = payload.get("sections") or []
        parsed_sections: List[Dict[str, Any]] = []
        if isinstance(sections, list):
            for sec in sections:
                if not isinstance(sec, dict):
                    continue
                raw_total = (sec.get("section_totals") or {}).get("total")
                total = normalize_money(raw_total)
                parsed_sections.append(
                    {
                        "section_name": sec.get("section_name"),
                        "total": total if total is not None else raw_total,
                        "line_item_preview": [
            {
                                "description": li.get("description"),
                                "total": normalize_money(li.get("total")) or li.get("total"),
                            }
                            for li in (sec.get("line_items") or [])[:3]
                            if isinstance(li, dict) and li.get("type", "line_item") == "line_item"
                        ],
            }
                )
        parsed_sections.sort(key=lambda s: s.get("total") or 0, reverse=True)
        parsed_sections = parsed_sections[:10]

        recaps_and_summaries = payload.get("recaps_and_summaries") or {}
        trade_summary = recaps_and_summaries.get("trade_summary") if isinstance(recaps_and_summaries, dict) else None

        case_metadata = payload.get("case_metadata") if isinstance(payload, dict) else {}

        return {
            "estimate_name": payload.get("estimate_name"),
            "case_metadata": case_metadata,
            "line_item_totals": (case_metadata or {}).get("line_item_totals"),
            "recap_by_category": recap,
            "trade_summary": trade_summary,
            "top_sections": parsed_sections,
        }

    # ---------- Category table ----------
    def _build_category_table(self, pair: BidPair) -> List[Dict[str, Any]]:
        bid_a_totals = self._aggregate_categories(pair.bid_a.recap)
        bid_b_totals = self._aggregate_categories(pair.bid_b.recap)
        rows: List[Dict[str, Any]] = []
        for category in VERISK_CATEGORY_ORDER:
            a_val = bid_a_totals.get(category, 0.0)
            b_val = bid_b_totals.get(category, 0.0)
            delta = round((b_val or 0.0) - (a_val or 0.0), 2)
            delta_pct = (delta / a_val) if a_val else None
            rows.append(
                {
                    "category": category,
                    "bid_a_total": a_val,
                    "bid_b_total": b_val,
                    "delta": delta,
                    "delta_pct": delta_pct,
        }
            )
        return rows

    def _aggregate_categories(self, recap: Dict[str, Any]) -> Dict[str, float]:
        totals: Dict[str, float] = {cat: 0.0 for cat in VERISK_CATEGORY_ORDER}
        for group_label, items in recap.items():
            if group_label == "subtotals" or not isinstance(items, list):
                continue
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                amount = normalize_money(entry.get("total") or entry.get("amount"))
                if amount is None:
                    continue
                raw_name = entry.get("item") or entry.get("name") or entry.get("label") or ""
                mapped = self._map_category(raw_name or group_label)
                totals[mapped] = round(totals.get(mapped, 0.0) + amount, 2)

        # Fees and taxes live in subtotals
        subtotals = recap.get("subtotals") if isinstance(recap, dict) else None
        if isinstance(subtotals, list):
            for entry in subtotals:
                if not isinstance(entry, dict):
                    continue
                label = normalize_label(entry.get("label") or "")
                amount = normalize_money(entry.get("total"))
                if amount is None:
                    continue
                if "OVERHEAD" in label or "PROFIT" in label:
                    totals["Overhead & Profit"] = round(totals.get("Overhead & Profit", 0.0) + amount, 2)
                elif "MATERIAL" in label and "TAX" in label:
                    totals["Material Sales Tax"] = round(totals.get("Material Sales Tax", 0.0) + amount, 2)
                elif "PERMIT" in label:
                    totals["Permit Fees"] = round(totals.get("Permit Fees", 0.0) + amount, 2)

        return totals

    def _map_category(self, raw_name: str) -> str:
        normalized = normalize_label(raw_name or "")
        for needle, mapped in CATEGORY_KEYWORDS:
            if needle in normalized:
                return mapped
        return CATEGORY_FALLBACK

    def _extract_subtotal_amount(self, recap: Dict[str, Any], needle: str) -> Optional[float]:
        subtotals = recap.get("subtotals")
        if not isinstance(subtotals, list):
            return None
        target = needle.upper()
        for entry in subtotals:
            if not isinstance(entry, dict):
                continue
            label = normalize_label(entry.get("label") or "")
            if target in label:
                amount = normalize_money(entry.get("total"))
                if amount is not None:
                    return amount
        return None

    def _top_deltas(self, category_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = sorted(category_rows, key=lambda r: abs(r.get("delta") or 0), reverse=True)
        return rows[: self.top_delta_count]

    # ---------- Narrative ----------
    def _generate_narrative(self, pair: BidPair, top_deltas: List[Dict[str, Any]]) -> NarrativeResult:
        if not self.llm_adapter:
            return self._fallback_narrative(top_deltas, reason="LLM disabled")

        context = {
            "bid_a_name": pair.bid_a.estimate_name,
            "bid_b_name": pair.bid_b.estimate_name,
            "bid_a_json": json.dumps(pair.bid_a.payload, ensure_ascii=False),
            "bid_b_json": json.dumps(pair.bid_b.payload, ensure_ascii=False),
            "category_table_json": json.dumps(top_deltas, ensure_ascii=False),
        }

        try:
            raw = self.llm_adapter.generate("bid_comp_summary_v1", context)
        except Exception as exc:  # noqa: BLE001
            logger.warning("narrative prompt failed: %s", exc)
            return self._fallback_narrative(top_deltas, reason=str(exc), raw_response="", context=context)

        try:
            payload = json.loads(raw)
        except Exception:
            logger.warning(
                "narrative parse failed: bid_a=%s bid_b=%s preview=%s",
                pair.bid_a.estimate_name,
                pair.bid_b.estimate_name,
                self._preview(raw),
            )
            return self._fallback_narrative(top_deltas, reason="parse_error", raw_response=raw, context=context)

        if not isinstance(payload, dict):
            logger.warning(
                "narrative payload invalid: bid_a=%s bid_b=%s preview=%s",
                pair.bid_a.estimate_name,
                pair.bid_b.estimate_name,
                self._preview(raw),
            )
            return self._fallback_narrative(top_deltas, reason="invalid_payload", raw_response=raw, context=context)

        exec_summary = str(payload.get("executive_summary") or "").strip()
        contextual = [str(x).strip() for x in (payload.get("contextual_drivers") or []) if str(x).strip()]
        follow_up = [str(x).strip() for x in (payload.get("follow_up_actions") or []) if str(x).strip()]
        largest: List[Dict[str, Any]] = []
        for entry in payload.get("largest_deltas") or []:
            if not isinstance(entry, dict):
                continue
            largest.append(
                {
                    "title": entry.get("title") or entry.get("category") or "",
                    "category": entry.get("category") or entry.get("title") or "",
                    "bid_a_total": normalize_money(entry.get("bid_a_total")),
                    "bid_b_total": normalize_money(entry.get("bid_b_total")),
                    "delta": normalize_money(entry.get("delta")),
                    "insight": entry.get("insight"),
                }
            )

        if not largest:
            largest = [
                    {
                    "title": row["category"],
                    "category": row["category"],
                    "bid_a_total": row["bid_a_total"],
                    "bid_b_total": row["bid_b_total"],
                    "delta": row["delta"],
                    "insight": "See delta table.",
                }
                for row in top_deltas[:3]
            ]

        self.last_narrative_debug = {"status": "ok"}
        self.last_narrative_artifact = None
        return NarrativeResult(
            executive_summary=exec_summary or "Summary unavailable.",
            largest_deltas=largest,
            contextual_drivers=contextual or ["No additional context supplied."],
            follow_up_actions=follow_up or ["No follow-up actions supplied."],
            raw_response=raw,
            parsed=True,
        )

    def _fallback_narrative(
        self,
        top_deltas: List[Dict[str, Any]],
        reason: Optional[str] = None,
        raw_response: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> NarrativeResult:
        if not top_deltas:
            summary = "Unable to generate narrative; no delta data available."
            largest: List[Dict[str, Any]] = []
        else:
            biggest = top_deltas[0]
            summary = (
                f"Largest delta in {biggest['category']} ({biggest['delta']:+,.0f}). "
                "LLM narrative is unavailable; review category table below."
            )
            largest = [
                {
                    "title": row["category"],
                    "category": row["category"],
                    "bid_a_total": row["bid_a_total"],
                    "bid_b_total": row["bid_b_total"],
                    "delta": row["delta"],
                    "insight": "LLM narrative unavailable.",
                }
                for row in top_deltas[:3]
            ]

        preview = (raw_response or "")[:2000]
        context_note = f"Narrative fallback: {reason}" if reason else "Narrative fallback invoked."
        self.last_narrative_debug = {
            "status": "fallback",
            "reason": reason or "unknown",
            "raw_response_preview": preview,
        }
        if context and raw_response:
            self.last_narrative_artifact = {
                "context": context,
                "response": raw_response,
            }
        else:
            self.last_narrative_artifact = None
        return NarrativeResult(
            executive_summary=summary,
            largest_deltas=largest,
            contextual_drivers=[context_note],
            follow_up_actions=["Review supporting estimate sections manually."],
            raw_response=raw_response,
            parsed=False,
        )

    def _preview(self, raw: str, limit: int = 2000) -> str:
        text = raw or ""
        return text[:limit]

    # ---------- Recap flattening ----------
    def _flatten_original_recaps(self, pair: BidPair) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for estimate in (pair.bid_a, pair.bid_b):
            recap = estimate.recap
            for group_label, items in recap.items():
                if group_label == "subtotals":
                    continue
                if not isinstance(items, list):
                    continue
                for entry in items:
                    if not isinstance(entry, dict):
                        continue
                    total = normalize_money(entry.get("total") or entry.get("amount"))
                    rows.append(
                        {
                            "estimate": estimate.estimate_name,
                            "group": group_label,
                            "item": entry.get("item") or entry.get("name"),
                            "total": total,
                        }
                    )
            subtotals = recap.get("subtotals")
            if isinstance(subtotals, list):
                for entry in subtotals:
                    if not isinstance(entry, dict):
                        continue
                    rows.append(
                        {
                            "estimate": estimate.estimate_name,
                            "group": "Subtotal",
                            "item": entry.get("label"),
                            "total": normalize_money(entry.get("total")),
                        }
                    )
        return rows


__all__ = ["BidComp"]

