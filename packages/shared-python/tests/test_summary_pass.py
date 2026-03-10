"""
Tests for SummaryResult model and run_summary_pass function.

Requirements: SUMM-01, SUMM-02
"""
import json
from unittest.mock import MagicMock

import pytest

from vip_shared.pipeline.models import DriverAnalysisResult, SummaryResult
from vip_shared.pipeline.passes.summary_pass import run_summary_pass


def _make_driver(category: str = "Painting", delta: float = 117000.0) -> DriverAnalysisResult:
    return DriverAnalysisResult(
        category=category,
        primary_total=200000.0,
        comparison_total=200000.0 - delta,
        delta=delta,
        narrative=f"{category} delta driven by scope difference.",
        scope_observations=[f"{category}: primary uses bid item."],
        suggested_followups=[f"Verify {category} scope."],
    )


def _make_summary() -> SummaryResult:
    return SummaryResult(
        overview=(
            "The primary estimate is higher across three key categories. "
            "Painting represents the largest delta at $117k, driven by a bid item approach."
        ),
        scope_observations=["Primary includes bid item painting; comparison uses unit rates."],
        suggested_followups=["Verify painting scope with contractor."],
    )


def _make_adapter(result: SummaryResult) -> MagicMock:
    adapter = MagicMock()
    adapter.generate_structured.return_value = result
    return adapter


def _make_cache(hit=None) -> MagicMock:
    cache = MagicMock()
    cache.get.return_value = hit
    cache.set.return_value = True
    return cache


def test_run_summary_pass_calls_generate_structured_once():
    """SUMM-01: exactly one LLM call; uses final_summary_v1 template."""
    adapter = _make_adapter(_make_summary())
    drivers = [_make_driver("Painting"), _make_driver("Roofing", delta=45000.0)]

    run_summary_pass(drivers, adapter)

    assert adapter.generate_structured.call_count == 1
    assert adapter.generate_structured.call_args[0][0] == "final_summary_v1"


def test_run_summary_pass_context_has_driver_summaries_not_raw_items():
    """SUMM-01: context contains aggregated driver summaries, not raw line items."""
    adapter = _make_adapter(_make_summary())
    drivers = [_make_driver("Painting")]

    run_summary_pass(drivers, adapter, primary_name="Carrier", comparison_name="Contractor")

    context = adapter.generate_structured.call_args[0][1]
    assert context["primary_name"] == "Carrier"
    assert context["comparison_name"] == "Contractor"
    assert context["driver_count"] == 1
    assert "driver_summaries_json" in context

    summaries = json.loads(context["driver_summaries_json"])
    assert isinstance(summaries, list)
    assert summaries[0]["category"] == "Painting"
    assert "narrative" in summaries[0]

    assert "primary_items" not in context
    assert "comparison_items" not in context
    assert "primary_items_json" not in context


def test_run_summary_pass_quality_notes_included_when_nonempty():
    """SUMM-01: rewrite guidance is included in context when provided."""
    adapter = _make_adapter(_make_summary())

    run_summary_pass(
        [_make_driver()],
        adapter,
        quality_notes="Found hedge words: maybe, possibly",
    )

    context = adapter.generate_structured.call_args[0][1]
    assert "quality_notes" in context
    assert context["quality_notes"] != ""
    assert "hedge words" in context["quality_notes"].lower()


def test_run_summary_pass_returns_summary_result():
    """SUMM-02: run_summary_pass returns structured SummaryResult."""
    expected = _make_summary()
    adapter = _make_adapter(expected)

    actual = run_summary_pass([_make_driver()], adapter)

    assert isinstance(actual, SummaryResult)
    assert actual is expected


def test_run_summary_pass_propagates_generate_structured_errors():
    """SUMM-01: no silent fallback when summary generation fails."""
    adapter = MagicMock()
    adapter.generate_structured.side_effect = RuntimeError("LLM summary failure")

    with pytest.raises(RuntimeError, match="LLM summary failure"):
        run_summary_pass([_make_driver()], adapter)


def test_run_summary_pass_cache_hit_skips_llm():
    """SUMM-01: cache hit returns SummaryResult without LLM call."""
    cached = _make_summary()
    adapter = _make_adapter(_make_summary())
    cache = _make_cache(hit=cached)

    result = run_summary_pass([_make_driver()], adapter, cache=cache)

    assert result is cached
    assert adapter.generate_structured.call_count == 0
    cache.get.assert_called_once()


def test_run_summary_pass_cache_miss_calls_llm_and_sets_cache():
    """SUMM-01: cache miss calls LLM once and stores the result."""
    fresh = _make_summary()
    adapter = _make_adapter(fresh)
    cache = _make_cache(hit=None)

    result = run_summary_pass([_make_driver()], adapter, cache=cache)

    assert result is fresh
    assert adapter.generate_structured.call_count == 1
    cache.set.assert_called_once()
    assert cache.set.call_args[0][1] is fresh


def test_summary_result_required_fields():
    """SUMM-02: SummaryResult carries overview, scope observations, and followups."""
    result = SummaryResult(
        overview="Executive overview.",
        scope_observations=["Scope item."],
        suggested_followups=["Follow-up item."],
    )

    assert result.overview == "Executive overview."
    assert result.scope_observations == ["Scope item."]
    assert result.suggested_followups == ["Follow-up item."]
