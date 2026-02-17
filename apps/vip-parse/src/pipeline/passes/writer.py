"""
Writer Pass - Second LLM pass for adjuster-tone narrative generation.

This pass transforms structured analysis (AnalysisResult) into professional
adjuster narratives (DraftNarrative) using few-shot examples and terminology
glossary.

The output (DraftNarrative) feeds into quality gates and optional compliance pass.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..models import AnalysisResult, DraftNarrative, DriverNarrative
from ...llm.adapter import LLMAdapterBase
from ...rules.models import SignalBundle


logger = logging.getLogger("vip-parse.pipeline.writer")


class WriterInput(BaseModel):
    """
    Input model for the Writer pass.

    Contains structured analysis data ready for narrative generation.
    Designed to provide context for adjuster-tone writing.
    """

    primary_name: str = Field(description="Name of the primary estimate")
    comparison_name: str = Field(description="Name of the comparison estimate")
    category_analyses: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Serialized CategoryAnalysis list for prompt injection"
    )
    scope_gaps: List[str] = Field(
        default_factory=list,
        description="Missing trades, allowances, or scope items"
    )
    overall_delta_direction: str = Field(
        description="Overall direction of the cost difference"
    )
    confidence: str = Field(
        description="Confidence level from analysis pass"
    )


def build_writer_input(
    analysis: AnalysisResult,
    primary_name: str,
    comparison_name: str
) -> WriterInput:
    """
    Build WriterInput from an AnalysisResult.

    Converts the Pydantic AnalysisResult into a WriterInput model
    with serialized category_analyses for prompt injection.

    Args:
        analysis: AnalysisResult from the analysis pass
        primary_name: Name of the primary estimate
        comparison_name: Name of the comparison estimate

    Returns:
        WriterInput ready for the writer pass
    """
    # Serialize category analyses to dict format
    category_analyses_dicts: List[Dict[str, Any]] = []
    for cat_analysis in analysis.category_analyses:
        category_analyses_dicts.append({
            "category": cat_analysis.category,
            "primary_total": cat_analysis.primary_total,
            "comparison_total": cat_analysis.comparison_total,
            "delta": cat_analysis.delta,
            "delta_drivers": cat_analysis.delta_drivers,
            "line_item_evidence": cat_analysis.line_item_evidence,
        })

    return WriterInput(
        primary_name=primary_name,
        comparison_name=comparison_name,
        category_analyses=category_analyses_dicts,
        scope_gaps=analysis.scope_gaps,
        overall_delta_direction=analysis.overall_delta_direction,
        confidence=analysis.confidence,
    )


def run_writer_pass(
    analysis: AnalysisResult,
    primary_name: str,
    comparison_name: str,
    llm_adapter: LLMAdapterBase,
    signals: SignalBundle | None = None,
    data_granularity: Optional[str] = None,
) -> DraftNarrative:
    """
    Run the Writer pass to generate adjuster-tone narratives.

    This is Pass 2 of the pipeline. It takes structured analysis data
    and generates professional adjuster narratives with comparative framing.

    Args:
        analysis: AnalysisResult from the analysis pass
        primary_name: Name of the primary estimate
        comparison_name: Name of the comparison estimate
        llm_adapter: LLM adapter for generating narratives

    Returns:
        DraftNarrative with overview, key_drivers, scope_observations, and suggested_followups
    """
    # Build writer input
    writer_input = build_writer_input(analysis, primary_name, comparison_name)

    # Log input details
    logger.info(
        "writer pass start: primary=%s comparison=%s categories=%d scope_gaps=%d confidence=%s",
        writer_input.primary_name,
        writer_input.comparison_name,
        len(writer_input.category_analyses),
        len(writer_input.scope_gaps),
        writer_input.confidence,
    )

    # Build context for template
    context = {
        "primary_name": writer_input.primary_name,
        "comparison_name": writer_input.comparison_name,
        "category_analyses_json": json.dumps(writer_input.category_analyses, indent=2),
        "scope_gaps_json": json.dumps(writer_input.scope_gaps, indent=2),
        "overall_delta_direction": writer_input.overall_delta_direction,
        "confidence": writer_input.confidence,
    }
    template_id = "writer_pass_v1"
    if data_granularity:
        template_id = "writer_pass_v2"
        context["data_granularity"] = data_granularity
        evidence_descriptions = {
            "line_item": "Specific line items, unit prices, quantities, and materials available",
            "category": "Category names and totals only — no line-item details",
            "coverage": "Coverage types and totals only",
            "estimate_total": "Grand totals only",
        }
        context["available_evidence"] = evidence_descriptions.get(data_granularity, "Unknown")
    if signals is not None:
        context["category_analyses_json"] = (
            f"{context['category_analyses_json']}\n\nAlert Tags (must be mentioned in narrative):\n"
            f"{_build_alert_context(signals)}\n\n"
            f"Structural Patterns (weave into analysis narrative):\n{_build_pattern_context(signals)}\n\n"
            f"Diagnostic Follow-Ups (include as next steps section):\n{_build_followup_context(signals)}"
        )
        context["_system_append"] = (
            "Alert Tags must appear in the narrative — each alert represents a verified analytical finding. "
            "Structural Patterns should be referenced when explaining why deltas exist. "
            "Diagnostic Follow-Ups go in the suggested_followups field and should use the provided actions."
        )

    try:
        # Call LLM with writer template
        raw_response = llm_adapter.generate(template_id, context)

        # Parse response into DraftNarrative
        result = _parse_writer_response(raw_response)
        if signals is not None:
            result.suggested_followups = _merge_followups(result.suggested_followups, signals)

        logger.info(
            "writer pass complete: overview_len=%d key_drivers=%d scope_observations=%d followups=%d",
            len(result.overview),
            len(result.key_drivers),
            len(result.scope_observations),
            len(result.suggested_followups),
        )
        return result

    except Exception as exc:
        logger.warning(
            "writer pass failed: error=%s - returning minimal DraftNarrative",
            exc,
        )
        # Try to salvage overview from raw response before falling back
        extracted_overview = _extract_overview_from_raw(raw_response) if 'raw_response' in dir() else None
        return _build_fallback_narrative(analysis, str(exc), primary_name, comparison_name, extracted_overview)


def _build_alert_context(signals: SignalBundle) -> str:
    lines = []
    for alert in signals.alert_tags:
        amt = f" (${alert.affected_amount:,.2f})" if alert.affected_amount is not None else ""
        lines.append(f"- [{alert.severity.value}] {alert.title}: {alert.detail}{amt}")
    return "\n".join(lines) if lines else "- none"


def _build_pattern_context(signals: SignalBundle) -> str:
    lines = []
    for pattern in signals.structural_patterns:
        evidence = "; ".join(pattern.evidence[:3]) if pattern.evidence else "n/a"
        lines.append(f"- {pattern.pattern_type.value}: {pattern.description}\n  Evidence: {evidence}")
    return "\n".join(lines) if lines else "- none"


def _build_followup_context(signals: SignalBundle) -> str:
    lines = [
        f"- [{f.priority.value}] {f.action} (triggered by: {f.trigger})"
        for f in signals.diagnostic_followups
    ]
    return "\n".join(lines) if lines else "- none"


def _merge_followups(existing: List[str], signals: SignalBundle) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for followup in signals.diagnostic_followups:
        key = " ".join(followup.action.lower().split())
        if key not in seen:
            seen.add(key)
            out.append(followup.action)
    for item in existing:
        key = " ".join(str(item).lower().split())
        if key not in seen:
            seen.add(key)
            out.append(str(item))
    return out


def _repair_json(text: str) -> str:
    """
    Attempt to repair common JSON issues from LLM output.

    Common issues:
    - Missing comma between object properties
    - Trailing commas
    - Unescaped newlines in strings
    """
    import re

    # Fix missing comma between "..." and "key": (common LLM error)
    # Pattern: "...(end of string value)" followed by whitespace then "key":
    text = re.sub(r'"\s*\n\s*"([a-z_]+)":', r'",\n  "\1":', text)

    # Fix trailing commas before } or ]
    text = re.sub(r',(\s*[}\]])', r'\1', text)

    return text


def _extract_overview_from_raw(raw_response: str) -> str | None:
    """
    Try to extract the overview field from raw response even if JSON is malformed.

    Returns the overview string if found, None otherwise.
    """
    import re

    # Look for "overview": "..." pattern
    match = re.search(r'"overview"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', raw_response, re.DOTALL)
    if match:
        overview = match.group(1)
        # Unescape common escapes
        overview = overview.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
        # Clean up whitespace
        overview = ' '.join(overview.split())
        if len(overview) > 50:  # Only use if substantive
            return overview
    return None


def _parse_writer_response(raw_response: str) -> DraftNarrative:
    """
    Parse LLM JSON response into DraftNarrative.

    Strips code fences and parses the JSON into a validated DraftNarrative.
    Attempts JSON repair for common LLM output issues.

    Args:
        raw_response: Raw string response from LLM

    Returns:
        Validated DraftNarrative
    """
    # Strip code fences if present
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Try parsing, with repair attempt on failure
    data = None
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as first_exc:
        logger.warning("writer pass JSON parse failed (attempt 1): %s", first_exc)
        # Try repairing common issues
        repaired = _repair_json(cleaned)
        try:
            data = json.loads(repaired)
            logger.info("writer pass JSON repair succeeded")
        except json.JSONDecodeError as exc:
            logger.warning("writer pass JSON repair also failed: %s", exc)
            raise ValueError(f"JSON parse error: {exc}") from exc

    if not isinstance(data, dict):
        logger.warning("writer pass response is not a dict")
        raise ValueError("Response not a dict")

    # Parse overview
    overview = data.get("overview", "Analysis complete. See details below.")
    if not isinstance(overview, str):
        overview = str(overview)

    # Parse key drivers
    key_drivers: List[DriverNarrative] = []
    raw_drivers = data.get("key_drivers", [])
    if isinstance(raw_drivers, list):
        for item in raw_drivers:
            if not isinstance(item, dict):
                continue
            try:
                key_drivers.append(DriverNarrative(
                    category=item.get("category", "Unknown"),
                    amounts=item.get("amounts", ""),
                    narrative=item.get("narrative", ""),
                ))
            except Exception as exc:
                logger.warning("failed to parse key driver: %s", exc)
                continue

    # Parse scope observations
    scope_observations = data.get("scope_observations", [])
    if not isinstance(scope_observations, list):
        scope_observations = []
    scope_observations = [str(s) for s in scope_observations if s]

    # Parse suggested followups
    suggested_followups = data.get("suggested_followups", [])
    if not isinstance(suggested_followups, list):
        suggested_followups = []
    suggested_followups = [str(f) for f in suggested_followups if f]

    return DraftNarrative(
        overview=overview,
        key_drivers=key_drivers,
        scope_observations=scope_observations,
        suggested_followups=suggested_followups,
    )


def _build_fallback_narrative(
    analysis: AnalysisResult,
    reason: str,
    primary_name: str = "Primary",
    comparison_name: str = "Comparison",
    extracted_overview: str | None = None,
) -> DraftNarrative:
    """
    Build a minimal DraftNarrative when parsing fails.

    Creates a fallback narrative using data from the AnalysisResult.

    Args:
        analysis: AnalysisResult to extract basic info from
        reason: Reason for fallback (for logging)
        primary_name: Name of the primary estimate
        comparison_name: Name of the comparison estimate
        extracted_overview: Overview extracted from raw response (if available)

    Returns:
        Minimal DraftNarrative with basic content
    """
    logger.info("building fallback draft narrative: reason=%s extracted_overview=%s", reason, bool(extracted_overview))

    # Build basic key drivers from analysis
    key_drivers: List[DriverNarrative] = []
    for cat_analysis in analysis.category_analyses:
        key_drivers.append(DriverNarrative(
            category=cat_analysis.category,
            amounts=f"${cat_analysis.primary_total:,.2f} vs ${cat_analysis.comparison_total:,.2f}",
            narrative=cat_analysis.delta_drivers[0] if cat_analysis.delta_drivers else "See line item details.",
        ))

    # Use extracted overview if available, otherwise build from analysis data
    if extracted_overview:
        overview = extracted_overview
    else:
        # Build a data-driven overview from the analysis
        top_category = analysis.category_analyses[0] if analysis.category_analyses else None
        if top_category:
            delta_direction = "higher" if top_category.delta > 0 else "lower"
            overview = (
                f"Comparing {primary_name} and {comparison_name}, the largest variance is in "
                f"{top_category.category} (${abs(top_category.delta):,.2f} {delta_direction} in comparison). "
                f"Overall direction: {analysis.overall_delta_direction}. See key drivers below for details."
            )
        else:
            overview = f"Comparison of {primary_name} and {comparison_name}. See key drivers below for details."

    return DraftNarrative(
        overview=overview,
        key_drivers=key_drivers,
        scope_observations=analysis.scope_gaps,
        suggested_followups=[f"Review {primary_name} and {comparison_name} line items for specifics."],
    )
