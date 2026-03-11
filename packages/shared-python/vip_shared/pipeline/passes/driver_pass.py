"""
Per-driver LLM pass for the v2.6 cost-driver-first pipeline.

Each top cost driver gets its own LLM request with context scoped to that
driver only — no other category data in the context window.

Key design constraints (Phase 31 requirements):
- PASS-01: Context isolation — only driver.category, totals, and items in context
- PASS-02: generate_structured() only — no JSON repair fallback, no generate() call
- PASS-03: Per-driver content-hash cache — same inputs skip LLM on re-run

No circular import issue here: driver_pass.py only imports from pipeline.models
and pipeline.cache — no bid_comp dependency at any level.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from vip_shared.pipeline.cache import PipelineCache, cache_key
from vip_shared.pipeline.models import DriverAnalysisResult, DriverWithItems
from vip_shared.llm.adapter import LLMAdapterBase

from pydantic import BaseModel, Field


logger = logging.getLogger("vip-parse.pipeline.driver_pass")


class DriverPassInput(BaseModel):
    """
    Pydantic model used to compute the content-hash cache key for a driver pass.

    Contains only the data that determines LLM output. Serialized via
    model_dump_json(exclude_none=True) by cache_key() for SHA256 hashing.
    """

    category: str = Field(description="Driver category name")
    primary_total: float = Field(description="Category total in primary estimate")
    comparison_total: float = Field(description="Category total in comparison estimate")
    delta: float = Field(description="Signed delta")
    primary_items: list = Field(default_factory=list, description="Line items from primary")
    comparison_items: list = Field(default_factory=list, description="Line items from comparison")
    primary_name: str = Field(default="", description="Display name for primary estimate")
    comparison_name: str = Field(default="", description="Display name for comparison estimate")
    verification_note: str = Field(default="", description="Verification discrepancy note")


def run_driver_pass(
    driver_with_items: DriverWithItems,
    llm_adapter: LLMAdapterBase,
    primary_name: str = "",
    comparison_name: str = "",
    cache: Optional[PipelineCache] = None,
) -> DriverAnalysisResult:
    """
    Run the per-driver LLM pass for a single cost driver.

    PASS-01: Context is scoped to this driver only — category, totals, and line items.
             No other category data is included in the context window.
    PASS-02: generate_structured() is the only LLM call path — no JSON repair fallback.
             If generate_structured raises, the exception propagates to the caller.
    PASS-03: When cache is provided, try cache first. On miss, call LLM and store result.

    Args:
        driver_with_items: DriverWithItems from map_driver_items() — one cost driver
            with all matching line items from both estimates.
        llm_adapter: LLM adapter implementing generate_structured().
        cache: Optional PipelineCache. If None, caching is skipped.

    Returns:
        DriverAnalysisResult with narrative, scope_observations, and suggested_followups.

    Raises:
        Any exception from generate_structured() — no fallback (PASS-02).
    """
    driver = driver_with_items.driver

    # --- PASS-03: try cache first ---
    key: Optional[str] = None
    if cache is not None:
        pass_input = DriverPassInput(
            category=driver.category,
            primary_total=driver.primary_total,
            comparison_total=driver.comparison_total,
            delta=driver.delta,
            primary_items=driver_with_items.primary_items,
            comparison_items=driver_with_items.comparison_items,
            primary_name=primary_name,
            comparison_name=comparison_name,
            verification_note=driver_with_items.verification_note,
        )
        key = cache_key("driver_pass", pass_input)
        cached = cache.get(key, DriverAnalysisResult)
        if cached is not None:
            logger.info(
                "driver_pass cache hit: category=%s key=%s",
                driver.category,
                key[:40],
            )
            return cached

    # --- PASS-01: build isolated context (this driver only) ---
    verification_note = driver_with_items.verification_note or ""
    delta_percent_raw = _delta_percent(driver.primary_total, driver.comparison_total)
    delta_percent = f"{delta_percent_raw:+.1f}%"
    primary_evidence = _build_evidence_context(driver_with_items.primary_items)
    comparison_evidence = _build_evidence_context(driver_with_items.comparison_items)
    context: Dict[str, Any] = {
        "category": driver.category,
        "primary_name": primary_name or "Primary estimate",
        "comparison_name": comparison_name or "Comparison estimate",
        "primary_total": f"${driver.primary_total:,.2f}",
        "comparison_total": f"${driver.comparison_total:,.2f}",
        "delta": f"${driver.delta:+,.2f}",
        "delta_percent": delta_percent,
        "primary_total_raw": driver.primary_total,
        "comparison_total_raw": driver.comparison_total,
        "delta_raw": driver.delta,
        "delta_percent_raw": delta_percent_raw,
        "primary_item_count": len(driver_with_items.primary_items),
        "comparison_item_count": len(driver_with_items.comparison_items),
        "primary_evidence_json": json.dumps(primary_evidence, indent=2),
        "comparison_evidence_json": json.dumps(comparison_evidence, indent=2),
        "primary_items_json": json.dumps(driver_with_items.primary_items, indent=2),
        "comparison_items_json": json.dumps(driver_with_items.comparison_items, indent=2),
        "verification_context": (
            f"\n\nNote: Item sum verification flagged: {verification_note}"
            if verification_note else ""
        ),
    }

    logger.info(
        "driver_pass start: category=%s primary=$%.2f comparison=$%.2f delta=$%.2f items=%d/%d",
        driver.category,
        driver.primary_total,
        driver.comparison_total,
        driver.delta,
        len(driver_with_items.primary_items),
        len(driver_with_items.comparison_items),
    )

    # --- PASS-02: generate_structured only — no fallback ---
    result: DriverAnalysisResult = llm_adapter.generate_structured(
        "driver_analysis_v1",
        context,
        response_model=DriverAnalysisResult,
    )

    logger.info(
        "driver_pass complete: category=%s narrative_chars=%d observations=%d followups=%d",
        driver.category,
        len(result.narrative),
        len(result.scope_observations),
        len(result.suggested_followups),
    )

    # --- PASS-03: store in cache on miss ---
    if cache is not None and key is not None:
        cache.set(key, result)

    return result


def _delta_percent(primary_total: float, comparison_total: float) -> float:
    """Compute signed delta percentage relative to comparison total when possible."""
    if comparison_total:
        return round(((primary_total - comparison_total) / abs(comparison_total)) * 100.0, 1)
    if primary_total:
        return 100.0
    return 0.0


def _build_evidence_context(items: list[dict[str, Any]]) -> Dict[str, Any]:
    """Summarize item evidence source and preserve the underlying items."""
    source = "section_items"
    if items and any(item.get("source") == "trade_summary" for item in items if isinstance(item, dict)):
        source = "trade_summary"
    return {
        "source": source,
        "item_count": len(items),
        "items": items,
    }
