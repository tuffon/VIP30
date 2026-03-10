"""
Final summary LLM pass for the v2.6 cost-driver-first pipeline.

Aggregates per-driver DriverAnalysisResult objects into one executive overview.
Uses structured output only and optional content-hash caching.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from vip_shared.llm.adapter import LLMAdapterBase
from vip_shared.pipeline.cache import PipelineCache, cache_key
from vip_shared.pipeline.models import DriverAnalysisResult, SummaryResult


logger = logging.getLogger("vip-parse.pipeline.summary_pass")


class SummaryPassInput(BaseModel):
    """Input model used to derive a deterministic cache key for summary_pass."""

    primary_name: str = Field(description="Primary estimate display name")
    comparison_name: str = Field(description="Comparison estimate display name")
    quality_notes: str = Field(default="", description="Rewrite guidance for failed quality gates")
    driver_summaries: list = Field(
        default_factory=list,
        description="Serialized driver analysis summaries passed to the final summary prompt"
    )


def run_summary_pass(
    driver_analyses: List[DriverAnalysisResult],
    llm_adapter: LLMAdapterBase,
    primary_name: str = "Primary",
    comparison_name: str = "Comparison",
    quality_notes: str = "",
    cache: Optional[PipelineCache] = None,
) -> SummaryResult:
    """
    Run the final summary pass across all driver analyses.

    Raises:
        Any exception from generate_structured() — no fallback is applied here.
    """
    driver_summaries = [
        {
            "category": driver.category,
            "primary_total": driver.primary_total,
            "comparison_total": driver.comparison_total,
            "delta": driver.delta,
            "narrative": driver.narrative,
            "scope_observations": driver.scope_observations,
            "suggested_followups": driver.suggested_followups,
        }
        for driver in driver_analyses
    ]

    key: Optional[str] = None
    if cache is not None:
        pass_input = SummaryPassInput(
            primary_name=primary_name,
            comparison_name=comparison_name,
            quality_notes=quality_notes,
            driver_summaries=driver_summaries,
        )
        key = cache_key("summary_pass", pass_input)
        cached = cache.get(key, SummaryResult)
        if cached is not None:
            logger.info("summary_pass cache hit: key=%s", key[:40])
            return cached

    context = {
        "primary_name": primary_name,
        "comparison_name": comparison_name,
        "driver_count": len(driver_analyses),
        "driver_summaries_json": json.dumps(driver_summaries, indent=2),
        "quality_notes": quality_notes,
    }

    logger.info(
        "summary_pass start: primary=%s comparison=%s drivers=%d rewrite=%s",
        primary_name,
        comparison_name,
        len(driver_analyses),
        bool(quality_notes),
    )

    result: SummaryResult = llm_adapter.generate_structured(
        "final_summary_v1",
        context,
        response_model=SummaryResult,
    )

    logger.info(
        "summary_pass complete: overview_chars=%d observations=%d followups=%d",
        len(result.overview),
        len(result.scope_observations),
        len(result.suggested_followups),
    )

    if cache is not None and key is not None:
        cache.set(key, result)

    return result
