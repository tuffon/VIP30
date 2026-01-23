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
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from ..models import AnalysisResult, DraftNarrative, DriverNarrative
from ...llm.adapter import LLMAdapterBase


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
    llm_adapter: LLMAdapterBase
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

    try:
        # Call LLM with writer template
        raw_response = llm_adapter.generate("writer_pass_v1", context)

        # Parse response into DraftNarrative
        result = _parse_writer_response(raw_response)

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
        return _build_fallback_narrative(analysis, str(exc))


def _parse_writer_response(raw_response: str) -> DraftNarrative:
    """
    Parse LLM JSON response into DraftNarrative.

    Strips code fences and parses the JSON into a validated DraftNarrative.

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

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("writer pass JSON parse failed: %s", exc)
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


def _build_fallback_narrative(analysis: AnalysisResult, reason: str) -> DraftNarrative:
    """
    Build a minimal DraftNarrative when parsing fails.

    Creates a fallback narrative using data from the AnalysisResult.

    Args:
        analysis: AnalysisResult to extract basic info from
        reason: Reason for fallback (for logging)

    Returns:
        Minimal DraftNarrative with basic content
    """
    logger.info("building fallback draft narrative: reason=%s", reason)

    # Build basic key drivers from analysis
    key_drivers: List[DriverNarrative] = []
    for cat_analysis in analysis.category_analyses:
        key_drivers.append(DriverNarrative(
            category=cat_analysis.category,
            amounts=f"${cat_analysis.primary_total:,.2f} vs ${cat_analysis.comparison_total:,.2f}",
            narrative=cat_analysis.delta_drivers[0] if cat_analysis.delta_drivers else "See line item details.",
        ))

    return DraftNarrative(
        overview="Analysis complete. See details below.",
        key_drivers=key_drivers,
        scope_observations=analysis.scope_gaps,
        suggested_followups=["Review individual category analyses for details."],
    )
