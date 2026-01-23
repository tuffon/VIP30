"""
Compliance Pass - Third LLM pass for quality-triggered rewrites.

This pass rewrites draft narratives that fail quality gates, removing
hedge words, analyst phrases, GPT-isms, and fixing other quality issues.

The output replaces the DraftNarrative if quality passes after rewriting.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from ..models import DraftNarrative, DriverNarrative, QualityReport
from ...llm.adapter import LLMAdapterBase


logger = logging.getLogger("vip-parse.pipeline.compliance")


class ComplianceInput(BaseModel):
    """
    Input model for the Compliance pass.

    Contains the draft narrative and quality gate failures that need fixing.
    """

    draft: DraftNarrative = Field(description="Draft narrative to rewrite")
    failed_checks: List[str] = Field(
        default_factory=list,
        description="Human-readable descriptions of failed quality checks"
    )
    primary_name: str = Field(description="Name of the primary estimate")
    comparison_name: str = Field(description="Name of the comparison estimate")


def build_compliance_input(
    draft: DraftNarrative,
    quality_report: QualityReport,
    primary_name: str,
    comparison_name: str
) -> ComplianceInput:
    """
    Build ComplianceInput from draft narrative and quality report.

    Extracts failed check details from quality_report and formats them
    as human-readable strings for the LLM prompt.

    Args:
        draft: DraftNarrative that failed quality gates
        quality_report: QualityReport with check results
        primary_name: Name of the primary estimate
        comparison_name: Name of the comparison estimate

    Returns:
        ComplianceInput ready for the compliance pass
    """
    failed_checks: List[str] = []
    for check in quality_report.checks:
        if not check.passed:
            failed_checks.append(f"{check.check_name}: {check.details}")

    return ComplianceInput(
        draft=draft,
        failed_checks=failed_checks,
        primary_name=primary_name,
        comparison_name=comparison_name,
    )


def run_compliance_pass(
    draft: DraftNarrative,
    quality_report: QualityReport,
    primary_name: str,
    comparison_name: str,
    llm_adapter: LLMAdapterBase
) -> DraftNarrative:
    """
    Run the Compliance pass to rewrite draft narratives that fail quality gates.

    This is Pass 3 of the pipeline. It takes a draft narrative and quality report,
    generates a revised version that addresses the failed quality checks.

    Args:
        draft: DraftNarrative that failed quality gates
        quality_report: QualityReport with check results
        primary_name: Name of the primary estimate
        comparison_name: Name of the comparison estimate
        llm_adapter: LLM adapter for generating rewritten narrative

    Returns:
        DraftNarrative with quality issues fixed, or original if rewrite fails
    """
    # Build compliance input
    compliance_input = build_compliance_input(
        draft, quality_report, primary_name, comparison_name
    )

    # Log input details
    logger.info(
        "compliance pass start: primary=%s comparison=%s failed_checks=%d",
        compliance_input.primary_name,
        compliance_input.comparison_name,
        len(compliance_input.failed_checks),
    )
    logger.debug("failed checks: %s", compliance_input.failed_checks)

    # Build context for template
    draft_dict = {
        "overview": draft.overview,
        "key_drivers": [
            {
                "category": d.category,
                "amounts": d.amounts,
                "narrative": d.narrative,
            }
            for d in draft.key_drivers
        ],
        "scope_observations": draft.scope_observations,
        "suggested_followups": draft.suggested_followups,
    }

    context = {
        "primary_name": compliance_input.primary_name,
        "comparison_name": compliance_input.comparison_name,
        "failed_checks": "\n".join(f"- {check}" for check in compliance_input.failed_checks),
        "draft_json": json.dumps(draft_dict, indent=2),
    }

    try:
        # Call LLM with compliance rewrite template
        raw_response = llm_adapter.generate("compliance_rewrite_v1", context)

        # Parse response into DraftNarrative
        result = _parse_compliance_response(raw_response)

        logger.info(
            "compliance pass complete: overview_len=%d key_drivers=%d",
            len(result.overview),
            len(result.key_drivers),
        )
        return result

    except Exception as exc:
        logger.warning(
            "compliance pass failed: error=%s - returning original draft unchanged",
            exc,
        )
        return draft


def _parse_compliance_response(raw_response: str) -> DraftNarrative:
    """
    Parse LLM JSON response into DraftNarrative.

    Strips code fences and parses the JSON into a validated DraftNarrative.

    Args:
        raw_response: Raw string response from LLM

    Returns:
        Validated DraftNarrative

    Raises:
        ValueError: If response cannot be parsed
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
        logger.warning("compliance pass JSON parse failed: %s", exc)
        raise ValueError(f"JSON parse error: {exc}") from exc

    if not isinstance(data, dict):
        logger.warning("compliance pass response is not a dict")
        raise ValueError("Response not a dict")

    # Parse overview
    overview = data.get("overview", "")
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
