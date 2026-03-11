from __future__ import annotations

import ast
import importlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .export_xlsx import export_xlsx
from .identity import ensure_estimate_identity
from .markdown import MarkdownBlock, parse_markdown
from .normalize import normalize_label, normalize_money
from ..llm.adapter import LLMAdapterBase
from ..methodology.models import MethodologyResult
from ..pipeline import CostDriverPipeline, PipelineCache, FinalNarrative, PipelineState
from ..rules.models import SignalBundle

try:
    from redis import Redis
except ImportError:
    Redis = None  # type: ignore

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
PRIMARY_FALLBACK_NAME = "Estimate 1"
COMPARISON_FALLBACK_NAME = "Estimate 2"

# Source: Verisk/Xactware Help Center, "Commercial and Residential Category Codes"
# https://xactware.helpdocs.io/article/j8s7xhwj7y-commercial-and-residential-category-codes
XACTIMATE_CATEGORY_CODE_MAP: Dict[str, str] = {
    "ADB": "Miscellaneous / General Requirements",
    "APL": "Appliances / Equipment",
    "BAS": "Miscellaneous / General Requirements",
    "CAB": "Cabinetry / Millwork",
    "CAR": "Cabinetry / Millwork",
    "CLN": "Cleaning / Restoration",
    "COM": "Contents / Packout / Storage",
    "CON": "Masonry / Concrete / Foundation",
    "DIA": "Miscellaneous / General Requirements",
    "DMO": "Demolition",
    "DRY": "Drywall / Insulation",
    "ELE": "Electrical",
    "ETC": "Specialty Systems (low voltage, alarms, AV, solar)",
    "FEN": "Fencing / Gates",
    "FIN": "Cabinetry / Millwork",
    "FIR": "Doors / Windows / Glass",
    "FPL": "HVAC / Mechanical",
    "FRM": "Framing / Structural",
    "GAS": "Framing / Structural",
    "GEN": "Miscellaneous / General Requirements",
    "GLS": "Doors / Windows / Glass",
    "HVC": "HVAC / Mechanical",
    "INS": "Drywall / Insulation",
    "LIT": "Electrical",
    "MAR": "Flooring",
    "MEC": "Framing / Structural",
    "MIT": "Miscellaneous / General Requirements",
    "MLD": "Cabinetry / Millwork",
    "MTL": "Miscellaneous / General Requirements",
    "PAI": "Painting",
    "PNT": "Painting",
    "PLU": "Plumbing",
    "POL": "Contents / Packout / Storage",
    "RFG": "Roofing",
    "RST": "Miscellaneous / General Requirements",
    "SCA": "Miscellaneous / General Requirements",
    "SEA": "Siding / Exterior Finishes",
    "SID": "Siding / Exterior Finishes",
    "SOL": "Flooring",
    "SPR": "Specialty Systems (low voltage, alarms, AV, solar)",
    "STL": "Framing / Structural",
    "STU": "Siding / Exterior Finishes",
    "TAR": "Miscellaneous / General Requirements",
    "TIL": "Flooring",
    "TRK": "Miscellaneous / General Requirements",
    "TWN": "Cabinetry / Millwork",
    "UPH": "Contents / Packout / Storage",
    "VNT": "HVAC / Mechanical",
    "WAT": "Cleaning / Restoration",
    "WDR": "Doors / Windows / Glass",
    "WEL": "Framing / Structural",
    "WOO": "Cabinetry / Millwork",
    "WWP": "Painting",
}

CATEGORY_KEYWORDS: List[tuple[str, str]] = [
    ("CLEAN", "Cleaning / Restoration"),
    ("RESTORATION", "Cleaning / Restoration"),
    ("REMEDIATION", "Cleaning / Restoration"),
    ("HAZARDOUS MATERIAL", "Cleaning / Restoration"),
    ("ASBESTOS", "Cleaning / Restoration"),
    ("MOLD", "Cleaning / Restoration"),
    ("SMOKE", "Cleaning / Restoration"),
    ("WATER EXTRACTION", "Cleaning / Restoration"),
    ("CONTENT", "Contents / Packout / Storage"),
    ("PACK", "Contents / Packout / Storage"),
    ("STORAGE", "Contents / Packout / Storage"),
    ("PERSONAL PROPERTY", "Contents / Packout / Storage"),
    ("UPHOLSTERY", "Contents / Packout / Storage"),
    ("DEMOL", "Demolition"),
    ("FRAM", "Framing / Structural"),
    ("STRUCT", "Framing / Structural"),
    ("STEEL", "Framing / Structural"),
    ("WELD", "Framing / Structural"),
    ("DRYWALL", "Drywall / Insulation"),
    ("INSUL", "Drywall / Insulation"),
    ("PAINT", "Painting"),
    ("WALLPAPER", "Painting"),
    ("FLOOR", "Flooring"),
    ("CARPET", "Flooring"),
    ("TILE", "Flooring"),
    ("MARBLE", "Flooring"),
    ("DOOR", "Doors / Windows / Glass"),
    ("WINDOW", "Doors / Windows / Glass"),
    ("GLAZ", "Doors / Windows / Glass"),
    ("GLASS", "Doors / Windows / Glass"),
    ("HARDWARE", "Doors / Windows / Glass"),
    ("WINDOW TREAT", "Doors / Windows / Glass"),
    ("CABINET", "Cabinetry / Millwork"),
    ("MILLWORK", "Cabinetry / Millwork"),
    ("TRIM", "Cabinetry / Millwork"),
    ("CARPENTRY", "Cabinetry / Millwork"),
    ("WOODWORK", "Cabinetry / Millwork"),
    ("MOLDING", "Cabinetry / Millwork"),
    ("ELECT", "Electrical"),
    ("LIGHT FIXTURE", "Electrical"),
    ("LIGHTING", "Electrical"),
    ("PLUMB", "Plumbing"),
    ("MECHANICAL", "HVAC / Mechanical"),
    ("HVAC", "HVAC / Mechanical"),
    ("VENT", "HVAC / Mechanical"),
    ("FIREPLACE", "HVAC / Mechanical"),
    ("ROOF", "Roofing"),
    ("SIDING", "Siding / Exterior Finishes"),
    ("STUCCO", "Siding / Exterior Finishes"),
    ("EXTERIOR", "Siding / Exterior Finishes"),
    ("AWNING", "Siding / Exterior Finishes"),
    ("PATIO COVER", "Siding / Exterior Finishes"),
    ("SEAL", "Siding / Exterior Finishes"),
    ("MASON", "Masonry / Concrete / Foundation"),
    ("CONCRETE", "Masonry / Concrete / Foundation"),
    ("FOUNDATION", "Masonry / Concrete / Foundation"),
    ("STONE", "Masonry / Concrete / Foundation"),
    ("ASPHALT", "Masonry / Concrete / Foundation"),
    ("FENCE", "Fencing / Gates"),
    ("ORNAMENTAL IRON", "Fencing / Gates"),
    ("IRONWORK", "Fencing / Gates"),
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
    ("FIRE PROTECTION", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("SPRINKLER", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("SPECIALTY ITEM", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("ELECTRONIC", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("COMPUTER", "Specialty Systems (low voltage, alarms, AV, solar)"),
    ("MISC", "Miscellaneous / General Requirements"),
    ("GENERAL REQUIREMENT", "Miscellaneous / General Requirements"),
    ("LABOR ONLY", "Miscellaneous / General Requirements"),
    ("TEMP", "Miscellaneous / General Requirements"),
    ("SCAFFOLD", "Miscellaneous / General Requirements"),
    ("TRUCK", "Miscellaneous / General Requirements"),
    ("HAUL", "Miscellaneous / General Requirements"),
    ("RESET", "Miscellaneous / General Requirements"),
    ("BASE SERVICE", "Miscellaneous / General Requirements"),
    ("MATERIAL HANDLING", "Miscellaneous / General Requirements"),
    ("DIAGNOS", "Miscellaneous / General Requirements"),
    ("TEMPORARY REPAIR", "Miscellaneous / General Requirements"),
]

NARRATIVE_OUTPUT_TEMPLATE = json.dumps(
    {
        "markdown": "# Overview of Estimates\n"
        "Provide 2-3 sentences comparing the intent, scope, and magnitude of both estimates.\n\n"
        "## Key Cost Drivers\n"
        "- Bullet per major driver naming the category, the amounts for each estimate, and why they differ.\n\n"
        "## Scope Observations\n"
        "- Call out major gaps, missing allowances, or assumptions.\n\n"
        "## Suggested Follow-ups\n"
        "- Bullet list of follow-up questions or reconciliation steps.\n",
        "metadata": {
            "confidence": "high|medium|low",
            "notes": "Optional clarifications or caveats.",
        },
    },
    indent=2,
)

EXPECTED_NARRATIVE_HEADERS: List[str] = [
    "# Overview of Estimates",
    "## Key Cost Drivers",
    "## Scope Observations",
    "## Suggested Follow-ups",
]


@dataclass
class EstimateTotals:
    grand_total: Optional[float]
    material_tax: Optional[float]
    overhead_and_profit: Optional[float]
    permit_fees: Optional[float]


@dataclass
class EstimateArtifact:
    position: str
    estimate_name: str
    payload: Dict[str, Any]
    recap: Dict[str, Any]
    totals: EstimateTotals
    summary_snapshot: Dict[str, Any] = field(default_factory=dict)
    source_filename: Optional[str] = None


@dataclass
class EstimatePair:
    primary: EstimateArtifact
    comparison: EstimateArtifact


@dataclass
class NarrativeResult:
    markdown: str
    blocks: List[MarkdownBlock]
    delta_rows: List[Dict[str, Any]]
    sections: Dict[str, Any] = field(default_factory=dict)
    key_drivers: List[Dict[str, Any]] = field(default_factory=list)
    raw_response: str = ""
    parsed: bool = False

    @property
    def overview(self) -> str:
        return self.sections.get("overview_of_estimates", "") or ""

    @property
    def scope_observations(self) -> List[str]:
        return list(self.sections.get("scope_observations") or [])

    @property
    def suggested_followups(self) -> List[str]:
        return list(self.sections.get("suggested_followups") or [])


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _extract_json_snippet(candidate: str) -> Optional[str]:
    start = candidate.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(candidate)):
        ch = candidate[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return candidate[start : idx + 1]
    return None


def _looks_like_json_blob(value: str) -> bool:
    stripped = (value or "").strip()
    return bool(stripped.startswith("{") and stripped.endswith("}"))


def _coerce_structured_llm_output(raw: str) -> tuple[Optional[Dict[str, Any]], List[str], Optional[str]]:
    """
    Attempt to coerce an LLM response into a dict even if it uses Python-style quoting,
    code fences, or has additional commentary wrapped around the JSON object.
    """
    issues: List[str] = []
    candidate = _strip_code_fences(raw)

    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as exc:
        issues.append(f"json_error:{exc.__class__.__name__}")
    else:
        if isinstance(obj, dict):
            return obj, issues, "json"
        issues.append("json_error:non_dict")

    try:
        literal_obj = ast.literal_eval(candidate)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"literal_error:{exc.__class__.__name__}")
    else:
        if isinstance(literal_obj, dict):
            return literal_obj, issues, "literal"
        issues.append("literal_error:non_dict")

    snippet = _extract_json_snippet(candidate)
    if snippet:
        try:
            obj = json.loads(snippet)
        except Exception as exc:  # noqa: BLE001
            issues.append(f"snippet_error:{exc.__class__.__name__}")
        else:
            if isinstance(obj, dict):
                return obj, issues, "snippet"
            issues.append("snippet_error:non_dict")

    return None, issues, None


class BidComp:
    def __init__(
        self,
        llm_adapter: Optional[LLMAdapterBase] = None,
        top_delta_count: int = 6,
        redis: Optional[Any] = None,  # Optional Redis for caching
    ) -> None:
        self.llm_adapter = llm_adapter
        self.top_delta_count = max(1, int(top_delta_count))
        self.last_narrative_debug: Optional[Dict[str, Any]] = None
        self.last_narrative_artifact: Optional[Dict[str, Any]] = None
        self._current_job_id: Optional[str] = None

        # Set up pipeline with optional caching
        self._pipeline: Optional[CostDriverPipeline] = None
        self._cache: Optional[PipelineCache] = None
        if llm_adapter:
            if redis is not None:
                self._cache = PipelineCache(redis)
            self._pipeline = CostDriverPipeline(
                llm_adapter=llm_adapter,
                cache=self._cache,
            )

    def run(
        self,
        bid_context: dict,
        job_id: str,
    ) -> bytes:
        self.last_narrative_debug = None
        self.last_narrative_artifact = None
        self._current_job_id = job_id
        self._log(logging.INFO, "run start", top_delta_target=self.top_delta_count)
        try:
            pair = self._build_pair(bid_context)
            self._log(
                logging.INFO,
                "pair resolved",
                primary_name=pair.primary.estimate_name,
                comparison_name=pair.comparison.estimate_name,
                primary_source=pair.primary.source_filename or "n/a",
                comparison_source=pair.comparison.source_filename or "n/a",
            )
            category_rows = self._build_category_table(pair)
            self._log(logging.INFO, "category table ready", rows=len(category_rows))
            top_deltas = self._top_deltas(category_rows)
            methodology = bid_context.get("methodology") if isinstance(bid_context, dict) else None
            if not isinstance(methodology, MethodologyResult):
                methodology = None
            signals = bid_context.get("signals") if isinstance(bid_context, dict) else None
            if not isinstance(signals, SignalBundle):
                signals = None
            top_delta_label = top_deltas[0].get("category") if top_deltas else None
            self._log(
                logging.INFO,
                "top deltas computed",
                count=len(top_deltas),
                top_category=top_delta_label or "none",
            )
            narrative = self._generate_narrative(pair, top_deltas, methodology=methodology, signals=signals)
            markdown_len = len(narrative.markdown or "")
            self._log(
                logging.INFO,
                "narrative ready",
                parsed=narrative.parsed,
                markdown_chars=markdown_len,
                driver_count=len(narrative.key_drivers or []),
            )
            recap_rows = self._flatten_original_recaps(pair)
            self._log(logging.INFO, "recap rows flattened", rows=len(recap_rows))
            xlsx_bytes = export_xlsx(
                pair=pair,
                narrative=narrative,
                category_rows=category_rows,
                recap_rows=recap_rows,
                methodology=methodology,
                signal_bundle=signals,
            )
            self._log(logging.INFO, "export complete", xlsx_bytes=len(xlsx_bytes))
            return xlsx_bytes
        finally:
            self._current_job_id = None

    # ---------- Pair + estimate helpers ----------
    def _build_pair(self, bid_context: dict) -> EstimatePair:
        if not isinstance(bid_context, dict):
            raise ValueError("bid_context must be a dict")

        estimates_raw = bid_context.get("estimates")
        if isinstance(estimates_raw, list) and len(estimates_raw) >= 2:
            left_raw = estimates_raw[0]
            right_raw = estimates_raw[1]
            left_payload, left_source = self._resolve_entry(left_raw)
            right_payload, right_source = self._resolve_entry(right_raw)
        else:
            left_payload, left_source = self._resolve_entry(bid_context.get("carrier"))
            right_payload, right_source = self._resolve_entry(bid_context.get("contractor"))

        if not left_payload or not right_payload:
            raise ValueError("bid_context must include two estimate payloads")

        carrier_source = left_source or bid_context.get("carrier_source_filename")
        contractor_source = right_source or bid_context.get("contractor_source_filename")

        primary = self._build_estimate(left_payload, position="primary", source_filename=carrier_source)
        comparison = self._build_estimate(right_payload, position="comparison", source_filename=contractor_source)
        return EstimatePair(primary=primary, comparison=comparison)

    def _resolve_payload(self, value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(value, dict) and "payload" in value and isinstance(value["payload"], dict):
            return value["payload"]
        if isinstance(value, dict):
            return value
        return None
    
    def _resolve_entry(self, value: Any) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        payload = self._resolve_payload(value)
        source_filename: Optional[str] = None
        if isinstance(value, dict):
            for key in ("source_filename", "original_filename", "filename"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    source_filename = candidate.strip()
                    break
        if not source_filename and isinstance(payload, dict):
            for key in ("original_filename", "source_filename", "file_name"):
                candidate = payload.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    source_filename = candidate.strip()
                    break
        return payload, source_filename

    def _build_estimate(
        self,
        payload: Dict[str, Any],
        *,
        position: str,
        source_filename: Optional[str],
    ) -> EstimateArtifact:
        fallback_label = PRIMARY_FALLBACK_NAME if position == "primary" else COMPARISON_FALLBACK_NAME
        preferred_label = self._preferred_label(payload, source_filename, fallback_label)
        preexisting_name = payload.get("estimate_name") if isinstance(payload, dict) else None
        preexisting_clean = preexisting_name.strip() if isinstance(preexisting_name, str) else ""
        estimate_name = ensure_estimate_identity(payload, preferred_label)
        recap = self._extract_recap_from_context(payload)
        totals = self._extract_totals(payload, recap)
        summary_snapshot = self._build_summary_snapshot(payload, recap)
        self._log(
            logging.INFO,
            "estimate artifact ready",
            position=position,
            estimate_name=estimate_name,
            preferred_label=preferred_label,
            source_filename=source_filename or "n/a",
            fallback_used=bool(estimate_name == fallback_label and estimate_name != preexisting_clean),
            recap_groups=len(recap),
            identity=self._summarize_identity(payload),
        )
        return EstimateArtifact(
            position=position,
            estimate_name=estimate_name,
            payload=payload,
            recap=recap,
            totals=totals,
            summary_snapshot=summary_snapshot,
            source_filename=source_filename,
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
    def _build_category_table(self, pair: EstimatePair) -> List[Dict[str, Any]]:
        build_trade_context = importlib.import_module(
            "vip_shared.pipeline.passes.trade_context"
        ).build_trade_context
        trade_ctx = build_trade_context(pair.primary.payload, pair.comparison.payload)
        primary_totals = trade_ctx.primary_by_category
        comparison_totals = trade_ctx.comparison_by_category
        categories = sorted(
            set(primary_totals) | set(comparison_totals),
            key=lambda category: (
                -abs(round((comparison_totals.get(category, 0.0) or 0.0) - (primary_totals.get(category, 0.0) or 0.0), 2)),
                normalize_label(category),
            ),
        )
        rows: List[Dict[str, Any]] = []
        for category in categories:
            a_val = primary_totals.get(category, 0.0)
            b_val = comparison_totals.get(category, 0.0)
            delta = round((b_val or 0.0) - (a_val or 0.0), 2)
            delta_pct = (delta / a_val) if a_val else None
            rows.append(
                {
                    "category": category,
                    "primary_total": a_val,
                    "comparison_total": b_val,
                    "delta": delta,
                    "delta_pct": delta_pct,
        }
            )
        return rows

    def _aggregate_categories(self, recap: Dict[str, Any]) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        group_labels = {
            normalize_label(str(group_label))
            for group_label, items in recap.items()
            if group_label != "subtotals" and isinstance(items, list)
        }
        for group_label, items in recap.items():
            if group_label == "subtotals" or not isinstance(items, list):
                continue
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                amount = normalize_money(entry.get("total") or entry.get("amount"))
                if amount is None:
                    continue
                label = str(entry.get("item") or entry.get("name") or entry.get("label") or group_label).strip()
                if not label:
                    continue
                totals[label] = round(totals.get(label, 0.0) + amount, 2)

        # Keep only real subtotal categories; skip recap rollup rows like O&P Items and Total.
        subtotals = recap.get("subtotals") if isinstance(recap, dict) else None
        if isinstance(subtotals, list):
            for entry in subtotals:
                if not isinstance(entry, dict):
                    continue
                label = str(entry.get("label") or "").strip()
                normalized = normalize_label(label)
                amount = normalize_money(entry.get("total"))
                if amount is None:
                    continue
                if not label or normalized in group_labels or normalized in {"TOTAL", "ITEMS SUBTOTAL"}:
                    continue
                totals[label] = round(totals.get(label, 0.0) + amount, 2)

        return totals

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

    def _build_delta_rows(self, top_deltas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for row in top_deltas:
            rows.append(
                {
                    "category": row.get("category"),
                    "primary_total": row.get("primary_total"),
                    "comparison_total": row.get("comparison_total"),
                    "delta": row.get("delta"),
                }
            )
        return rows

    # ---------- Narrative ----------
    def _generate_narrative(
        self,
        pair: EstimatePair,
        top_deltas: List[Dict[str, Any]],
        methodology: Optional[MethodologyResult] = None,
        signals: Optional[SignalBundle] = None,
    ) -> NarrativeResult:
        self._log(
            logging.INFO,
            "narrative stage start",
            llm_enabled=bool(self.llm_adapter),
            pipeline_enabled=bool(self._pipeline),
            top_delta_count=len(top_deltas),
        )
        delta_rows = self._build_delta_rows(top_deltas)

        # Use pipeline if available
        if self._pipeline:
            return self._generate_narrative_via_pipeline(
                pair,
                top_deltas,
                delta_rows,
                methodology=methodology,
                signals=signals,
            )

        # Fallback to legacy path if no LLM adapter
        if not self.llm_adapter:
            self._log(logging.INFO, "narrative fallback triggered", reason="llm_disabled")
            return self._fallback_narrative(top_deltas, reason="LLM disabled", pair=pair)

        # Legacy path (should not reach here if pipeline is initialized)
        return self._generate_narrative_legacy(pair, top_deltas, delta_rows)

    def _generate_narrative_via_pipeline(
        self,
        pair: EstimatePair,
        top_deltas: List[Dict[str, Any]],
        delta_rows: List[Dict[str, Any]],
        methodology: Optional[MethodologyResult] = None,
        signals: Optional[SignalBundle] = None,
    ) -> NarrativeResult:
        """Use CostDriverPipeline for narrative generation."""
        try:
            state = self._pipeline.run(
                pair=pair,
                top_deltas=top_deltas,
                primary_name=pair.primary.estimate_name,
                comparison_name=pair.comparison.estimate_name,
                methodology=methodology,
                signals=signals,
            )

            # Convert PipelineState to NarrativeResult
            return self._convert_pipeline_result(state, pair, delta_rows, top_deltas)
        except Exception as exc:
            self._log(logging.WARNING, "pipeline error", error=str(exc))
            return self._fallback_narrative(top_deltas, reason=f"pipeline_error:{exc}", pair=pair)

    def _convert_pipeline_result(
        self,
        state: PipelineState,
        pair: EstimatePair,
        delta_rows: List[Dict[str, Any]],
        top_deltas: List[Dict[str, Any]],
    ) -> NarrativeResult:
        """Convert PipelineState to NarrativeResult for existing export flow."""
        final = state.final
        if not final:
            return self._fallback_narrative(
                delta_rows, reason="pipeline_no_final", pair=pair
            )

        # Align key drivers to top_deltas order so XLSX rows always map to the correct category.
        driver_by_category = {
            str(d.category or "").strip().lower(): d for d in final.key_drivers
        }
        key_drivers = []
        for idx, delta_data in enumerate(top_deltas):
            category = str(delta_data.get("category") or "").strip()
            matched = driver_by_category.get(category.lower())
            if matched is None and idx < len(final.key_drivers):
                # Contract fallback: tolerate label drift when model preserves ordering.
                matched = final.key_drivers[idx]
            key_drivers.append({
                "category": category,
                "primary_total": delta_data.get("primary_total"),
                "comparison_total": delta_data.get("comparison_total"),
                "delta_total": delta_data.get("delta"),
                "narrative": (matched.narrative if matched is not None else ""),
            })

        # Build sections dict for export
        sections = {
            "overview_of_estimates": final.overview,
            "key_cost_drivers": key_drivers,
            "scope_observations": final.scope_observations,
            "suggested_followups": final.suggested_followups,
        }

        # Build markdown from FinalNarrative
        markdown_text = self._render_structured_markdown(pair, sections, key_drivers)

        blocks = parse_markdown(markdown_text)

        # Update debug/artifact tracking
        self.last_narrative_debug = {
            "status": "pipeline",
            "passes_executed": state.passes_executed,
            "pass_timings_ms": state.pass_timings_ms,
            "quality_passed": state.quality_passed(),
            "rewrites": final.rewrites_performed if hasattr(final, 'rewrites_performed') else 0,
        }
        if state.errors:
            self.last_narrative_debug["errors"] = state.errors

        self._log(
            logging.INFO,
            "narrative pipeline complete",
            passes=",".join(state.passes_executed),
            quality_passed=state.quality_passed(),
            rewrites=final.rewrites_performed if hasattr(final, 'rewrites_performed') else 0,
        )

        return NarrativeResult(
            markdown=markdown_text,
            blocks=blocks,
            delta_rows=delta_rows,
            sections=sections,
            key_drivers=key_drivers,
            raw_response="",  # Pipeline doesn't expose raw
            parsed=True,
        )

    def _generate_narrative_legacy(
        self,
        pair: EstimatePair,
        top_deltas: List[Dict[str, Any]],
        delta_rows: List[Dict[str, Any]],
    ) -> NarrativeResult:
        """Legacy narrative generation using direct LLM calls."""
        context = {
            "primary_name": pair.primary.estimate_name,
            "comparison_name": pair.comparison.estimate_name,
            "primary_json": json.dumps(pair.primary.payload, ensure_ascii=False),
            "comparison_json": json.dumps(pair.comparison.payload, ensure_ascii=False),
            "category_table_json": json.dumps(top_deltas, ensure_ascii=False),
        }
        missing_keys = [k for k, v in context.items() if not v]
        if missing_keys:
            self._log(
                logging.WARNING,
                "narrative context incomplete",
                missing_keys=",".join(missing_keys),
                primary=pair.primary.estimate_name,
                comparison=pair.comparison.estimate_name,
            )
            logger.warning(
                "narrative context incomplete (missing=%s) for estimates (%s, %s)",
                missing_keys,
                pair.primary.estimate_name,
                pair.comparison.estimate_name,
            )
            return self._fallback_narrative(
                top_deltas,
                reason=f"missing_context:{','.join(missing_keys)}",
                raw_response="",
                context=context,
                pair=pair,
            )

        try:
            context_bytes = sum(len(context.get(key) or "") for key in ("primary_json", "comparison_json", "category_table_json"))
            self._log(
                logging.INFO,
                "narrative llm request",
                template="bid_comp_summary_v1",
                primary=pair.primary.estimate_name,
                comparison=pair.comparison.estimate_name,
                driver_count=len(top_deltas),
                context_bytes=context_bytes,
            )
            raw = self.llm_adapter.generate("bid_comp_summary_v1", context)
            self._log(
                logging.INFO,
                "narrative llm response",
                chars=len(raw or ""),
                preview=self._preview(raw, 200),
            )
        except Exception as exc:  # noqa: BLE001
            self._log(
                logging.WARNING,
                "narrative llm error",
                error=str(exc),
                primary=pair.primary.estimate_name,
                comparison=pair.comparison.estimate_name,
            )
            logger.warning(
                "narrative prompt failed for (%s, %s): %s",
                pair.primary.estimate_name,
                pair.comparison.estimate_name,
                exc,
            )
            return self._fallback_narrative(
                top_deltas,
                reason=str(exc),
                raw_response="",
                context=context,
                pair=pair,
            )

        markdown_text = ""
        metadata: Dict[str, Any] = {}
        payload, parse_issues, parse_stage = _coerce_structured_llm_output(raw)
        self._log(
            logging.INFO,
            "narrative llm parse",
            stage=parse_stage or "raw",
            issues=",".join(parse_issues) if parse_issues else "none",
        )

        sections_payload = payload.get("sections") if payload else None
        normalized_sections, driver_rows = self._normalize_sections(sections_payload)
        if not driver_rows:
            driver_rows = self._drivers_from_deltas(top_deltas)

        # Extract narratives from markdown if JSON fields are empty
        if payload:
            markdown_for_extraction = payload.get("markdown") or ""
            driver_rows = self._enrich_drivers_from_markdown(driver_rows, markdown_for_extraction)
            # Sync enriched drivers back to sections for xlsx export
            normalized_sections["key_cost_drivers"] = driver_rows
            # Extract overview from markdown if JSON sections.overview_of_estimates is empty
            if not normalized_sections.get("overview_of_estimates"):
                extracted_overview = self._extract_overview_from_markdown(markdown_for_extraction)
                if extracted_overview:
                    normalized_sections["overview_of_estimates"] = extracted_overview
                    self._log(
                        logging.INFO,
                        "narrative overview extracted from markdown",
                        chars=len(extracted_overview),
                    )

        if payload:
            candidate = payload.get("markdown") or payload.get("narrative") or payload.get("content")
            if isinstance(candidate, str):
                markdown_text = candidate.strip()
            else:
                parse_issues.append("missing_markdown_field")
            metadata_value = payload.get("metadata")
            if isinstance(metadata_value, dict):
                metadata = metadata_value
            elif metadata_value is not None:
                parse_issues.append("invalid_metadata_type")
        else:
            markdown_text = raw.strip()

        sections_have_content = self._sections_have_content(normalized_sections, driver_rows)
        if not markdown_text and sections_have_content:
            markdown_text = self._render_structured_markdown(pair, normalized_sections, driver_rows)
        elif _looks_like_json_blob(markdown_text):
            self._log(
                logging.WARNING,
                "narrative markdown looks like json blob",
                primary=pair.primary.estimate_name,
                comparison=pair.comparison.estimate_name,
            )

        if not markdown_text:
            self._log(
                logging.WARNING,
                "narrative markdown missing",
                primary=pair.primary.estimate_name,
                comparison=pair.comparison.estimate_name,
            )
            logger.warning(
                "narrative markdown missing: primary=%s comparison=%s preview=%s",
                pair.primary.estimate_name,
                pair.comparison.estimate_name,
                self._preview(raw),
            )
            reason = "empty_markdown"
            if parse_issues:
                reason = f"{reason} ({';'.join(parse_issues)})"
            return self._fallback_narrative(
                top_deltas,
                reason=reason,
                raw_response=raw,
                context=context,
                pair=pair,
            )

        blocks = parse_markdown(markdown_text)
        missing_sections = self._missing_narrative_sections(markdown_text, EXPECTED_NARRATIVE_HEADERS)
        self.last_narrative_debug = {
            "status": "ok",
            "format": "markdown",
            "block_count": len(blocks),
        }
        if parse_issues:
            self.last_narrative_debug["parse_issues"] = parse_issues
        if missing_sections:
            self.last_narrative_debug["missing_sections"] = missing_sections
        if sections_have_content:
            self.last_narrative_debug["sections"] = {
                "overview": bool(normalized_sections.get("overview_of_estimates")),
                "scope_observations": len(normalized_sections.get("scope_observations") or []),
                "suggested_followups": len(normalized_sections.get("suggested_followups") or []),
                "drivers": len(driver_rows),
            }
        if metadata:
            self.last_narrative_debug["metadata"] = metadata
        self.last_narrative_artifact = {
            "context": context,
            "response": raw,
            "markdown": markdown_text,
            "metadata": metadata,
        }
        self._log(
            logging.INFO,
            "narrative parsed",
            blocks=len(blocks),
            missing_sections=len(missing_sections),
        )
        return NarrativeResult(
            markdown=markdown_text,
            blocks=blocks,
            delta_rows=delta_rows,
            sections=normalized_sections,
            key_drivers=driver_rows,
            raw_response=raw,
            parsed=True,
        )

    def _fallback_narrative(
        self,
        top_deltas: List[Dict[str, Any]],
        reason: Optional[str] = None,
        raw_response: str = "",
        context: Optional[Dict[str, Any]] = None,
        pair: Optional[EstimatePair] = None,
    ) -> NarrativeResult:
        delta_rows = self._build_delta_rows(top_deltas)
        driver_rows = self._drivers_from_deltas(top_deltas)
        self._log(
            logging.WARNING,
            "narrative fallback rendering",
            reason=reason or "unknown",
            driver_count=len(driver_rows),
        )
        overview_text = self._build_fallback_overview(pair, reason)
        scope_observations = [
            "Automated comparison unavailable; review supporting sections manually.",
        ]
        suggested_followups = ["Review supporting estimate sections manually."]
        sections = {
            "overview_of_estimates": overview_text,
            "key_cost_drivers": driver_rows,
            "scope_observations": scope_observations,
            "suggested_followups": suggested_followups,
        }
        markdown_text = self._render_structured_markdown(pair, sections, driver_rows)
        blocks = parse_markdown(markdown_text)
        preview = (raw_response or "")[:2000]
        self.last_narrative_debug = {
            "status": "fallback",
            "reason": reason or "unknown",
            "raw_response_preview": preview,
        }
        if context is not None:
            self.last_narrative_artifact = {
                "context": context,
                "response": raw_response,
                "reason": reason,
            }
        else:
            self.last_narrative_artifact = {"response": raw_response, "reason": reason}
        return NarrativeResult(
            markdown=markdown_text,
            blocks=blocks,
            delta_rows=delta_rows,
            sections=sections,
            key_drivers=driver_rows,
            raw_response=raw_response,
            parsed=False,
        )

    def _missing_narrative_sections(self, markdown_text: str, expected_headers: List[str]) -> List[str]:
        lowered = (markdown_text or "").lower()
        missing: List[str] = []
        for header in expected_headers:
            if header.lower() not in lowered:
                missing.append(header)
        return missing

    def _preferred_label(
        self,
        payload: Optional[Dict[str, Any]],
        source_filename: Optional[str],
        fallback_label: str,
    ) -> str:
        candidates: List[str] = []
        if isinstance(payload, dict):
            raw_name = payload.get("estimate_name")
            if isinstance(raw_name, str):
                candidates.append(raw_name)
            case_md = payload.get("case_metadata")
            if isinstance(case_md, dict):
                for key in (
                    "estimate_name",
                    "file_name",
                    "original_filename",
                    "uploaded_filename",
                ):
                    val = case_md.get(key)
                    if isinstance(val, str):
                        candidates.append(val)
            if isinstance(payload.get("estimate_metadata"), dict):
                display_name = payload["estimate_metadata"].get("display_name")
                if isinstance(display_name, str):
                    candidates.append(display_name)
            metadata = payload.get("metadata")
            if isinstance(metadata, dict):
                file_name = metadata.get("file_name") or metadata.get("original_filename")
                if isinstance(file_name, str):
                    candidates.append(file_name)
            for key in (
                "original_filename",
                "source_filename",
                "uploaded_filename",
            ):
                val = payload.get(key)
                if isinstance(val, str):
                    candidates.append(val)
        if isinstance(source_filename, str):
            candidates.append(source_filename)
        candidates.append(fallback_label)
        for candidate in candidates:
            if isinstance(candidate, str):
                cleaned = candidate.strip()
                if cleaned:
                    return cleaned
        return fallback_label

    def _normalize_sections(self, sections: Any) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        normalized: Dict[str, Any] = {
            "overview_of_estimates": "",
            "scope_observations": [],
            "suggested_followups": [],
        }
        drivers: List[Dict[str, Any]] = []
        if isinstance(sections, dict):
            overview = sections.get("overview_of_estimates")
            if isinstance(overview, str):
                normalized["overview_of_estimates"] = overview.strip()
            normalized["scope_observations"] = self._coerce_str_list(sections.get("scope_observations"))
            normalized["suggested_followups"] = self._coerce_str_list(sections.get("suggested_followups"))
            raw_drivers = sections.get("key_cost_drivers")
            if isinstance(raw_drivers, list):
                for entry in raw_drivers:
                    normalized_driver = self._normalize_driver_entry(entry)
                    if normalized_driver:
                        drivers.append(normalized_driver)
        normalized["key_cost_drivers"] = drivers
        return normalized, drivers

    def _normalize_driver_entry(self, entry: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(entry, dict):
            return None

        raw_category = entry.get("category")
        if isinstance(raw_category, str):
            category = raw_category.strip() or "Unspecified"
        elif raw_category is None:
            category = "Unspecified"
        else:
            category = str(raw_category).strip() or "Unspecified"

        primary_total = self._extract_driver_amount(entry, "primary_total", "total1", "estimate_a_total", "left_total")
        comparison_total = self._extract_driver_amount(
            entry,
            "comparison_total",
            "total2",
            "estimate_b_total",
            "right_total",
        )
        delta_total = self._extract_driver_amount(entry, "delta_total", "delta")
        if delta_total is None and primary_total is not None and comparison_total is not None:
            delta_total = round(comparison_total - primary_total, 2)

        narrative = entry.get("narrative") or entry.get("explanation") or ""
        if isinstance(narrative, str):
            narrative_text = narrative.strip()
        else:
            narrative_text = str(narrative).strip() if narrative is not None else ""

        return {
            "category": category,
            "primary_total": primary_total,
            "comparison_total": comparison_total,
            "delta_total": delta_total,
            "narrative": narrative_text,
        }

    def _extract_driver_amount(self, entry: Dict[str, Any], *keys: str) -> Optional[float]:
        for key in keys:
            if key in entry:
                amount = normalize_money(entry.get(key))
                if amount is not None:
                    return amount
        return None

    def _coerce_str_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        items: List[str] = []
        for entry in value:
            if isinstance(entry, str):
                text = entry.strip()
                if text:
                    items.append(text)
        return items

    def _drivers_from_deltas(self, top_deltas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        drivers: List[Dict[str, Any]] = []
        for row in top_deltas:
            drivers.append(
                {
                    "category": row.get("category") or "Category",
                    "primary_total": row.get("primary_total"),
                    "comparison_total": row.get("comparison_total"),
                    "delta_total": row.get("delta"),
                    "narrative": "",
                }
            )
        return drivers

    def _enrich_drivers_from_markdown(
        self, drivers: List[Dict[str, Any]], markdown: str
    ) -> List[Dict[str, Any]]:
        """Extract narratives from markdown bullets if JSON narrative fields are empty."""
        if not markdown or not drivers:
            return drivers

        import re
        narratives_from_md: Dict[str, str] = {}

        # Pattern 1: Same-line narrative after em-dash, double-dash, or spaced hyphen
        # - **Category**: $X vs $Y (delta $Z) — narrative here
        # - **Category**: $X vs $Y (delta: -$Z) - narrative here
        # Also handles format: 253660.97 vs 1732.73 (delta: -251928.24) - narrative
        pattern1 = r'-\s*\*\*([^*]+)\*\*[^—\n]*?(?:—|--|\)\s+-\s+|\)\s*-\s+)\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern1, markdown, re.IGNORECASE):
            category = match.group(1).strip()
            narrative = match.group(2).strip()
            if narrative:
                narratives_from_md[category.lower()] = narrative

        # Pattern 2: Sub-bullet narrative on next line (LLM commonly uses this)
        # - **Category**: $X vs $Y (delta: $Z)
        #   - Narrative text here
        pattern2 = r'-\s*\*\*([^*]+)\*\*[^\n]*\n\s+-\s+([^*\n-].+?)(?:\n|$)'
        for match in re.finditer(pattern2, markdown):
            category = match.group(1).strip()
            narrative = match.group(2).strip()
            if narrative and category.lower() not in narratives_from_md:
                narratives_from_md[category.lower()] = narrative

        # Pattern 3: Indented text (not a bullet) on next line
        # - **Category**: $X vs $Y (delta: $Z)
        #   Narrative text here
        pattern3 = r'-\s*\*\*([^*]+)\*\*[^\n]*\)\n\s{2,}([A-Z][^*\n-].{15,}?)(?:\n|$)'
        for match in re.finditer(pattern3, markdown):
            category = match.group(1).strip()
            narrative = match.group(2).strip()
            if narrative and category.lower() not in narratives_from_md:
                narratives_from_md[category.lower()] = narrative

        if not narratives_from_md:
            self._log(
                logging.DEBUG,
                "narrative markdown extraction found no matches",
                markdown_preview=markdown[:500] if markdown else "",
            )
            return drivers

        # Enrich drivers that have empty narratives
        enriched_count = 0
        for driver in drivers:
            if driver.get("narrative"):
                continue
            category = (driver.get("category") or "").lower()
            if category in narratives_from_md:
                driver["narrative"] = narratives_from_md[category]
                enriched_count += 1

        if enriched_count:
            self._log(
                logging.INFO,
                "narrative enriched from markdown",
                enriched_count=enriched_count,
                total_drivers=len(drivers),
            )

        return drivers

    def _extract_overview_from_markdown(self, markdown: str) -> str:
        """Extract the Overview of Estimates section from markdown text.

        Returns all content between '# Overview of Estimates' and the next ## heading.
        """
        if not markdown:
            return ""

        import re

        # Find the Overview section - match from "# Overview" to the next ## heading
        # The overview content includes multiple paragraphs with **bold labels**
        pattern = r'#\s*Overview\s+of\s+Estimates\s*\n+(.*?)(?=\n##|\Z)'
        match = re.search(pattern, markdown, re.IGNORECASE | re.DOTALL)

        if not match:
            return ""

        overview_content = match.group(1).strip()

        # If empty, return nothing
        if not overview_content:
            return ""

        # Clean up but preserve line breaks between paragraphs
        # The content should have format:
        # **Total Comparison**: ...
        # **EstimateName1**: ...
        # **EstimateName2**: ...
        # **Key Takeaway**: ...
        lines = []
        for line in overview_content.split('\n'):
            line = line.strip()
            if line:
                lines.append(line)

        # Join with double newlines to preserve paragraph structure
        return '\n\n'.join(lines)

    def _sections_have_content(self, sections: Dict[str, Any], drivers: List[Dict[str, Any]]) -> bool:
        if not sections:
            return bool(drivers)
        if sections.get("overview_of_estimates"):
            return True
        if sections.get("scope_observations"):
            return True
        if sections.get("suggested_followups"):
            return True
        return bool(drivers)

    def _render_structured_markdown(
        self,
        pair: Optional[EstimatePair],
        sections: Dict[str, Any],
        drivers: List[Dict[str, Any]],
    ) -> str:
        lines: List[str] = []
        lines.append("# Overview of Estimates")
        overview_text = (sections.get("overview_of_estimates") or "").strip()
        if overview_text:
            lines.append(overview_text)
        else:
            lines.append("Summary unavailable.")
        lines.append("")
        lines.append("## Key Cost Drivers")
        if drivers:
            for driver in drivers:
                lines.append(f"- {self._format_driver_bullet(pair, driver)}")
        else:
            lines.append("- No driver details were provided.")
        lines.append("")
        lines.append("## Scope Observations")
        scope_items = sections.get("scope_observations") or []
        if scope_items:
            for item in scope_items:
                lines.append(f"- {item}")
        else:
            lines.append("- No scope observations provided.")
        lines.append("")
        lines.append("## Suggested Follow-ups")
        followups = sections.get("suggested_followups") or []
        if followups:
            for item in followups:
                lines.append(f"- {item}")
        else:
            lines.append("- No follow-up questions were supplied.")
        return "\n".join(lines)

    def _format_driver_bullet(self, pair: Optional[EstimatePair], driver: Dict[str, Any]) -> str:
        primary_name = pair.primary.estimate_name if pair else PRIMARY_FALLBACK_NAME
        comparison_name = pair.comparison.estimate_name if pair else COMPARISON_FALLBACK_NAME
        category = driver.get("category") or "Category"
        primary_val = self._format_currency(driver.get("primary_total"))
        comparison_val = self._format_currency(driver.get("comparison_total"))
        delta_val = self._format_currency(driver.get("delta_total"))
        bullet = (
            f"**{category}**: {primary_name} {primary_val} vs "
            f"{comparison_name} {comparison_val} (Δ {delta_val})"
        )
        narrative = (driver.get("narrative") or "").strip()
        if narrative:
            bullet = f"{bullet} — {narrative}"
        return bullet

    def _build_fallback_overview(self, pair: Optional[EstimatePair], reason: Optional[str]) -> str:
        note = f"Narrative fallback: {reason}" if reason else "Narrative fallback invoked."
        if pair:
            primary_total = self._format_currency(pair.primary.totals.grand_total)
            comparison_total = self._format_currency(pair.comparison.totals.grand_total)
            return (
                f"{note} {pair.primary.estimate_name} totals {primary_total} "
                f"versus {pair.comparison.estimate_name} {comparison_total}. "
                "Review key category deltas below."
            )
        return f"{note} Review key category deltas below."

    def _preview(self, raw: str, limit: int = 2000) -> str:
        text = raw or ""
        return text[:limit]

    def _format_currency(self, value: Optional[float]) -> str:
        if value is None:
            return "N/A"
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return str(value)
        if abs(amount) >= 1000:
            return f"${amount:,.0f}"
        return f"${amount:,.2f}"

    # ---------- Recap flattening ----------
    def _flatten_original_recaps(self, pair: EstimatePair) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for estimate in (pair.primary, pair.comparison):
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

    def _summarize_identity(self, payload: Dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            return "{}"
        case_md = payload.get("case_metadata")
        if not isinstance(case_md, dict):
            case_md = {}
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        summary = {
            "payload.estimate_name": payload.get("estimate_name"),
            "payload.original_filename": payload.get("original_filename"),
            "case_metadata.estimate_name": case_md.get("estimate_name"),
            "case_metadata.file_name": case_md.get("file_name"),
            "case_metadata.original_filename": case_md.get("original_filename"),
            "metadata.file_name": metadata.get("file_name"),
            "metadata.original_filename": metadata.get("original_filename"),
        }
        compact = {k: v for k, v in summary.items() if v}
        try:
            return json.dumps(compact, ensure_ascii=False)
        except Exception:
            return str(compact)

    def _log(self, level: int, message: str, **fields: Any) -> None:
        prefix = f"[job={self._current_job_id or 'n/a'}] {message}"
        if fields:
            formatted = []
            for key, value in fields.items():
                if value is None:
                    continue
                text = str(value)
                if len(text) > 400:
                    text = f"{text[:397]}..."
                formatted.append(f"{key}={text}")
            if formatted:
                prefix = f"{prefix} " + " ".join(formatted)
        logger.log(level, prefix)


__all__ = ["BidComp"]
