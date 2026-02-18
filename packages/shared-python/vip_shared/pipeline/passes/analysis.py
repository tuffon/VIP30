"""
Analysis Pass - First LLM pass for structured delta extraction.

This pass extracts structured comparison data from estimate pairs,
reducing token count from 100k+ to ~5-10k through line item sampling.

The output (AnalysisResult) feeds into the Writer pass.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..models import AnalysisResult, CategoryAnalysis, LLMAnalysisResult
from ...llm.adapter import LLMAdapterBase
from ...methodology.models import MethodologyResult
from ...rules.models import SignalBundle


logger = logging.getLogger("vip-parse.pipeline.analysis")


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    name = exc.__class__.__name__.lower()
    return (
        "too many requests" in text
        or "rate limit" in text
        or "status code 429" in text
        or "http 429" in text
        or "ratelimit" in name
    )


class AnalysisInput(BaseModel):
    """
    Input model for the Analysis pass.

    Contains summarized data from estimate pairs needed for LLM analysis.
    Designed to minimize token count while preserving analysis context.
    """

    primary_name: str = Field(description="Name of the primary estimate")
    comparison_name: str = Field(description="Name of the comparison estimate")
    primary_totals: Dict[str, float] = Field(
        default_factory=dict,
        description="Category totals from primary estimate"
    )
    comparison_totals: Dict[str, float] = Field(
        default_factory=dict,
        description="Category totals from comparison estimate"
    )
    top_deltas: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top delta categories from BidComp._top_deltas"
    )
    primary_sample_items: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Sampled line items by category from primary estimate"
    )
    comparison_sample_items: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Sampled line items by category from comparison estimate"
    )


def sample_line_items(
    payload: Dict[str, Any],
    categories: List[str],
    max_per_category: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract top line items by amount from an estimate payload.

    Reduces token count by sampling only the most significant items
    per category rather than including all line items.

    Args:
        payload: Estimate payload dict with sections/line_items
        categories: List of category names to extract items for
        max_per_category: Maximum items to return per category (default 5)

    Returns:
        Dict mapping category name to list of sampled items.
        Each item has: description, quantity, unit, amount
    """
    if not isinstance(payload, dict):
        return {}

    result: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in categories}

    # Collect all line items from sections
    all_items: List[Dict[str, Any]] = []
    sections = payload.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_name = section.get("section_name", "")
            line_items = section.get("line_items")
            if not isinstance(line_items, list):
                continue
            for item in line_items:
                if not isinstance(item, dict):
                    continue
                # Skip non-line-item entries (headers, subtotals, etc.)
                if item.get("type", "line_item") != "line_item":
                    continue
                all_items.append({
                    "section_name": section_name,
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity"),
                    "unit": item.get("unit", ""),
                    "amount": _normalize_amount(item.get("total") or item.get("amount")),
                    "raw_item": item,
                })

    # Also check for top-level line_items (alternative payload structure)
    top_items = payload.get("line_items")
    if isinstance(top_items, list):
        for item in top_items:
            if not isinstance(item, dict):
                continue
            if item.get("type", "line_item") != "line_item":
                continue
            all_items.append({
                "section_name": item.get("category", ""),
                "description": item.get("description", ""),
                "quantity": item.get("quantity"),
                "unit": item.get("unit", ""),
                "amount": _normalize_amount(item.get("total") or item.get("amount")),
                "raw_item": item,
            })

    # For each category, find matching items and take top N by amount
    for category in categories:
        category_upper = category.upper()
        matching_items: List[Dict[str, Any]] = []

        for item in all_items:
            # Match by section name containing category (case-insensitive)
            section_upper = (item.get("section_name") or "").upper()
            if category_upper in section_upper or _fuzzy_category_match(category, section_upper):
                matching_items.append(item)

        # Sort by amount descending and take top N
        matching_items.sort(key=lambda x: x.get("amount") or 0, reverse=True)
        top_items_list = matching_items[:max_per_category]

        # Build clean output items
        result[category] = [
            {
                "description": item.get("description", ""),
                "quantity": item.get("quantity"),
                "unit": item.get("unit", ""),
                "amount": item.get("amount"),
            }
            for item in top_items_list
        ]

    return result


def _normalize_amount(value: Any) -> Optional[float]:
    """Normalize a monetary value to float, handling various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove currency symbols and commas
        cleaned = value.replace("$", "").replace(",", "").replace(" ", "").strip()
        # Handle parentheses for negatives
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _fuzzy_category_match(category: str, section_name: str) -> bool:
    """Check for fuzzy match between category and section name."""
    # Common category -> section name mappings
    mappings = {
        "FLOORING": ["FLOOR", "CARPET", "TILE", "HARDWOOD", "LVP", "VINYL"],
        "ELECTRICAL": ["ELECTRIC", "WIRING", "LIGHTING"],
        "PLUMBING": ["PLUMB", "PIPE", "WATER", "DRAIN"],
        "HVAC / MECHANICAL": ["HVAC", "HEATING", "COOLING", "AC", "AIR COND", "MECHANICAL"],
        "ROOFING": ["ROOF", "SHINGLE", "GUTTER"],
        "INTERIOR WALL": ["DRYWALL", "WALL", "PAINT", "INTERIOR"],
        "EXTERIOR WALL": ["SIDING", "EXTERIOR", "STUCCO"],
        "CABINETRY": ["CABINET", "COUNTER", "KITCHEN"],
        "APPLIANCES": ["APPLIANCE", "REFRIGERATOR", "DISHWASHER", "RANGE"],
        "DOORS & WINDOWS": ["DOOR", "WINDOW", "ENTRY"],
    }

    category_upper = category.upper()
    for cat, keywords in mappings.items():
        if category_upper in cat or cat in category_upper:
            for kw in keywords:
                if kw in section_name:
                    return True
    return False


def build_analysis_input(
    pair: Any,  # EstimatePair - using Any to avoid circular import
    top_deltas: List[Dict[str, Any]]
) -> AnalysisInput:
    """
    Build AnalysisInput from an EstimatePair and top deltas.

    Extracts names, totals, and samples line items for both estimates.

    Args:
        pair: EstimatePair with primary and comparison estimates
        top_deltas: List of top delta category dicts from BidComp

    Returns:
        AnalysisInput ready for the analysis pass
    """
    # Extract category names from top_deltas
    categories = [d.get("category", "") for d in top_deltas if d.get("category")]

    # Build category totals from top_deltas
    primary_totals: Dict[str, float] = {}
    comparison_totals: Dict[str, float] = {}
    for delta in top_deltas:
        cat = delta.get("category", "")
        if cat:
            primary_totals[cat] = delta.get("primary_total", 0.0) or 0.0
            comparison_totals[cat] = delta.get("comparison_total", 0.0) or 0.0

    # Sample line items from both estimates
    primary_sample = sample_line_items(
        pair.primary.payload if hasattr(pair.primary, "payload") else {},
        categories
    )
    comparison_sample = sample_line_items(
        pair.comparison.payload if hasattr(pair.comparison, "payload") else {},
        categories
    )

    return AnalysisInput(
        primary_name=getattr(pair.primary, "estimate_name", "Primary"),
        comparison_name=getattr(pair.comparison, "estimate_name", "Comparison"),
        primary_totals=primary_totals,
        comparison_totals=comparison_totals,
        top_deltas=top_deltas,
        primary_sample_items=primary_sample,
        comparison_sample_items=comparison_sample,
    )


def run_analysis_pass(
    pair: Any,  # EstimatePair - using Any to avoid circular import
    top_deltas: List[Dict[str, Any]],
    llm_adapter: LLMAdapterBase,
    methodology: Optional[MethodologyResult] = None,
    signals: Optional[SignalBundle] = None,
) -> AnalysisResult:
    """
    Run the Analysis pass to extract structured comparison data.

    This is Pass 1 of the pipeline. It takes raw estimate data and extracts
    structured analysis that the Writer pass can use to generate narratives.

    Args:
        pair: EstimatePair with primary and comparison estimates
        top_deltas: List of top delta category dicts from BidComp
        llm_adapter: LLM adapter for generating analysis

    Returns:
        AnalysisResult with category analyses, scope gaps, and confidence
    """
    # Build analysis input
    analysis_input = build_analysis_input(pair, top_deltas)

    # Log input token estimate
    input_json = analysis_input.model_dump_json()
    estimated_tokens = len(input_json) // 4  # rough estimate: 4 chars per token
    logger.info(
        "analysis pass start: primary=%s comparison=%s categories=%d estimated_tokens=%d",
        analysis_input.primary_name,
        analysis_input.comparison_name,
        len(top_deltas),
        estimated_tokens,
    )

    # Build context for template
    context = {
        "primary_name": analysis_input.primary_name,
        "comparison_name": analysis_input.comparison_name,
        "deltas_json": json.dumps(analysis_input.top_deltas, indent=2),
        "primary_items_json": json.dumps(analysis_input.primary_sample_items, indent=2),
        "comparison_items_json": json.dumps(analysis_input.comparison_sample_items, indent=2),
    }
    if methodology is not None:
        context["deltas_json"] = f"{context['deltas_json']}\n\nMethodology Context (pre-analyzed, do not contradict):\n{_build_methodology_context(methodology)}"
        context["_system_append"] = (
            "The Methodology Context section contains pre-analyzed facts. "
            "Reference these directly. Do NOT contradict or re-derive methodology findings. "
            "If data_granularity is 'category', do NOT reference specific line items."
        )
    if signals is not None:
        context["deltas_json"] = f"{context['deltas_json']}\n\nRanked Impact Context (pre-analyzed, do not contradict):\n{_build_ranked_impact_context(signals, analysis_input.primary_name, analysis_input.comparison_name)}"
        append = (
            "The Ranked Impact Context contains pre-analyzed variance rankings. "
            "Use these rankings to prioritize your analysis. Focus detailed analysis on CRITICAL and NOTABLE categories. "
            "Do NOT re-rank or contradict the impact ordering."
        )
        context["_system_append"] = f"{context.get('_system_append','')}\n{append}".strip()

    try:
        # Prefer Structured Outputs for deterministic schema compliance.
        try:
            llm_result = llm_adapter.generate_structured(
                "analysis_pass_v1",
                context,
                response_model=LLMAnalysisResult,
            )
            result = AnalysisResult(
                category_analyses=[
                    CategoryAnalysis(
                        category=ca.category,
                        primary_total=float(ca.primary_amount),
                        comparison_total=float(ca.comparison_amount),
                        delta=float(ca.delta),
                        delta_drivers=list(ca.delta_drivers),
                        line_item_evidence=list(ca.line_item_evidence),
                    )
                    for ca in llm_result.category_analyses
                ],
                scope_gaps=list(llm_result.scope_gaps),
                overall_delta_direction=llm_result.overall_delta_direction,
                confidence=llm_result.confidence,
            )
        except Exception as structured_exc:  # noqa: BLE001
            logger.warning("analysis structured output failed, falling back: %s", structured_exc)
            if _is_rate_limit_error(structured_exc):
                return _build_fallback_result(
                    analysis_input,
                    "LLM service temporarily rate-limited during analysis pass",
                )
            raw_response = llm_adapter.generate("analysis_pass_v1", context)
            result = _parse_analysis_response(raw_response, analysis_input)

        logger.info(
            "analysis pass complete: categories=%d scope_gaps=%d confidence=%s",
            len(result.category_analyses),
            len(result.scope_gaps),
            result.confidence,
        )
        return result

    except Exception as exc:
        logger.warning(
            "analysis pass failed: error=%s - returning fallback result",
            exc,
        )
        return _build_fallback_result(analysis_input, str(exc))


def _parse_analysis_response(raw_response: str, analysis_input: AnalysisInput) -> AnalysisResult:
    """Parse LLM JSON response into AnalysisResult."""
    # Strip code fences if present
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("analysis pass JSON parse failed: %s", exc)
        return _build_fallback_result(analysis_input, f"JSON parse error: {exc}")

    if not isinstance(data, dict):
        logger.warning("analysis pass response is not a dict")
        return _build_fallback_result(analysis_input, "Response not a dict")

    # Parse category analyses
    category_analyses: List[CategoryAnalysis] = []
    raw_analyses = data.get("category_analyses", [])
    if isinstance(raw_analyses, list):
        for item in raw_analyses:
            if not isinstance(item, dict):
                continue
            try:
                category_analyses.append(CategoryAnalysis(
                    category=item.get("category", "Unknown"),
                    primary_total=float(item.get("primary_total", 0)),
                    comparison_total=float(item.get("comparison_total", 0)),
                    delta=float(item.get("delta", 0)),
                    delta_drivers=item.get("delta_drivers", []),
                    line_item_evidence=item.get("line_item_evidence", []),
                ))
            except (ValueError, TypeError) as exc:
                logger.warning("failed to parse category analysis: %s", exc)
                continue

    # Parse scope gaps
    scope_gaps = data.get("scope_gaps", [])
    if not isinstance(scope_gaps, list):
        scope_gaps = []
    scope_gaps = [str(g) for g in scope_gaps if g]

    # Parse overall direction
    direction = data.get("overall_delta_direction", "similar")
    if direction not in ("primary_higher", "comparison_higher", "similar"):
        direction = "similar"

    # Parse confidence
    confidence = data.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    return AnalysisResult(
        category_analyses=category_analyses,
        scope_gaps=scope_gaps,
        overall_delta_direction=direction,
        confidence=confidence,
    )


def _build_methodology_context(methodology: MethodologyResult) -> str:
    primary_price_list = methodology.primary_depreciation.price_list or "n/a"
    comparison_price_list = methodology.comparison_depreciation.price_list or "n/a"
    lines = [
        (
            f"- O&P treatment: {methodology.primary_op.structure_type.value} vs "
            f"{methodology.comparison_op.structure_type.value}. Differs: {methodology.op_treatment_differs}"
        ),
        (
            f"- Depreciation: Primary ACV={methodology.primary_depreciation.is_acv}, "
            f"Comparison ACV={methodology.comparison_depreciation.is_acv}. "
            f"Differs: {methodology.depreciation_approach_differs}"
        ),
        (
            f"- Price lists: {primary_price_list} vs {comparison_price_list}. "
            f"Differs: {methodology.price_list_differs}"
        ),
        (
            f"- Scope alignment: {len(methodology.scope_alignment.primary_only)} items unique to primary, "
            f"{len(methodology.scope_alignment.comparison_only)} items unique to comparison"
        ),
        f"- Data granularity: {methodology.data_granularity.value}",
    ]
    return "\n".join(lines)


def _build_ranked_impact_context(signals: SignalBundle, primary_name: str, comparison_name: str) -> str:
    rows = []
    for row in signals.ranked_impact.rows[:5]:
        labels = f" [{', '.join(row.flags)}]" if row.flags else ""
        rows.append(
            f"{row.rank}. {row.category}: ${row.delta:,.2f} ({row.pct_of_total_variance:.1f}% of total variance){labels}"
        )
    flag_lines = [f"- [{f.severity.value}] {f.category}: {f.reason}" for f in signals.emphasis_flags]
    direction = "higher" if signals.ranked_impact.total_delta > 0 else "lower"
    lines = [
        "Top variance categories by impact:",
        *(rows or ["- none"]),
        "",
        "Emphasis flags:",
        *(flag_lines or ["- none"]),
        "",
        f"Total variance: ${signals.ranked_impact.total_abs_variance:,.2f}",
        f"Direction: {primary_name} is ${abs(signals.ranked_impact.total_delta):,.2f} {direction} than {comparison_name}",
    ]
    return "\n".join(lines)


def _build_fallback_result(analysis_input: AnalysisInput, reason: str) -> AnalysisResult:
    """Build a low-confidence fallback result when parsing fails."""
    logger.info("building fallback analysis result: reason=%s", reason)

    # Create minimal category analyses from input data
    category_analyses: List[CategoryAnalysis] = []
    for delta in analysis_input.top_deltas:
        cat = delta.get("category", "")
        if not cat:
            continue
        primary = delta.get("primary_total", 0) or 0
        comparison = delta.get("comparison_total", 0) or 0
        category_analyses.append(CategoryAnalysis(
            category=cat,
            primary_total=float(primary),
            comparison_total=float(comparison),
            delta=float(delta.get("delta", 0) or 0),
            delta_drivers=[f"Analysis unavailable: {reason}"],
            line_item_evidence=[],
        ))

    # Determine direction from totals
    primary_sum = sum(analysis_input.primary_totals.values())
    comparison_sum = sum(analysis_input.comparison_totals.values())
    if abs(primary_sum - comparison_sum) / max(primary_sum, comparison_sum, 1) < 0.05:
        direction = "similar"
    elif primary_sum > comparison_sum:
        direction = "primary_higher"
    else:
        direction = "comparison_higher"

    return AnalysisResult(
        category_analyses=category_analyses,
        scope_gaps=[],
        overall_delta_direction=direction,
        confidence="low",
    )
