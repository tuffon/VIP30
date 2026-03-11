"""
Tests for DriverAnalysisResult model and run_driver_pass function.

Requirements: PASS-01, PASS-02, PASS-03
"""
import json
from unittest.mock import MagicMock

import pytest

from vip_shared.pipeline.models import CostDriver, DriverAnalysisResult, DriverWithItems
from vip_shared.pipeline.passes.driver_pass import run_driver_pass


# --- Helpers ---

def _make_result(category: str = "Painting") -> DriverAnalysisResult:
    return DriverAnalysisResult(
        category=category,
        primary_total=205000.0,
        comparison_total=88000.0,
        delta=117000.0,
        narrative="Delta driven by contractor scope difference.",
        scope_observations=["Primary includes bid item; comparison uses unit rates."],
        suggested_followups=["Verify painting scope with contractor."],
    )


def _make_dwi(category: str = "Painting") -> DriverWithItems:
    driver = CostDriver(
        category=category,
        primary_total=205000.0,
        comparison_total=88000.0,
        delta=117000.0,
    )
    return DriverWithItems(
        driver=driver,
        primary_items=[
            {"type": "line_item", "cat": "PNT", "description": "Painting bid item",
             "total": "205000.00", "qty": 1.0, "unit": "EA"},
        ],
        comparison_items=[
            {"type": "line_item", "cat": "PNT", "description": "Paint walls - 2 coats",
             "total": "88000.00", "qty": 3200.0, "unit": "SF"},
        ],
        verification_ok=True,
        verification_note="",
    )


def _make_adapter(result: DriverAnalysisResult) -> MagicMock:
    adapter = MagicMock()
    adapter.generate_structured.return_value = result
    return adapter


def _make_cache(hit=None) -> MagicMock:
    cache = MagicMock()
    cache.get.return_value = hit
    cache.set.return_value = True
    return cache


# --- PASS-01: context isolation ---

def test_run_driver_pass_calls_generate_structured_once():
    """PASS-01: exactly one LLM call per driver; uses 'driver_analysis_v1' template."""
    result = _make_result()
    adapter = _make_adapter(result)
    dwi = _make_dwi()

    run_driver_pass(dwi, adapter)

    assert adapter.generate_structured.call_count == 1
    call_args = adapter.generate_structured.call_args
    template_id = call_args[0][0]
    assert template_id == "driver_analysis_v1", (
        f"Expected template 'driver_analysis_v1', got '{template_id}'"
    )


def test_run_driver_pass_context_contains_only_this_driver():
    """PASS-01: context passed to LLM contains only this driver's data — no cross-category data."""
    result = _make_result()
    adapter = _make_adapter(result)
    dwi = _make_dwi("Painting")

    run_driver_pass(dwi, adapter)

    call_args = adapter.generate_structured.call_args
    context = call_args[0][1]

    # Required driver-specific keys
    assert "category" in context, "context missing 'category'"
    assert context["category"] == "Painting"
    assert "primary_items_json" in context, "context missing 'primary_items_json'"
    assert "comparison_items_json" in context, "context missing 'comparison_items_json'"
    assert "delta_percent" in context, "context missing 'delta_percent'"
    assert "primary_evidence_json" in context, "context missing 'primary_evidence_json'"
    assert "comparison_evidence_json" in context, "context missing 'comparison_evidence_json'"

    # Must NOT contain cross-category data
    assert "category_analyses" not in context, "context must not have category_analyses (cross-category)"
    assert "top_deltas" not in context, "context must not have top_deltas (cross-category)"
    assert "all_drivers" not in context, "context must not have all_drivers list"


def test_run_driver_pass_items_json_in_context():
    """PASS-01: primary_items_json and comparison_items_json are valid JSON in context."""
    result = _make_result()
    adapter = _make_adapter(result)
    dwi = _make_dwi()

    run_driver_pass(dwi, adapter)

    call_args = adapter.generate_structured.call_args
    context = call_args[0][1]

    # Must be valid JSON
    primary_items = json.loads(context["primary_items_json"])
    comparison_items = json.loads(context["comparison_items_json"])
    assert isinstance(primary_items, list), "primary_items_json must decode to a list"
    assert isinstance(comparison_items, list), "comparison_items_json must decode to a list"

    # Items from our DriverWithItems should be present
    assert len(primary_items) == 1
    assert primary_items[0]["description"] == "Painting bid item"


def test_run_driver_pass_evidence_context_contains_source_and_counts():
    """Phase 34: driver-pass context carries structured evidence metadata."""
    result = _make_result()
    adapter = _make_adapter(result)
    dwi = _make_dwi()

    run_driver_pass(dwi, adapter, primary_name="Estimate A", comparison_name="Estimate B")

    context = adapter.generate_structured.call_args[0][1]
    primary_evidence = json.loads(context["primary_evidence_json"])
    comparison_evidence = json.loads(context["comparison_evidence_json"])

    assert context["primary_name"] == "Estimate A"
    assert context["comparison_name"] == "Estimate B"
    assert context["delta_percent_raw"] > 0
    assert primary_evidence["source"] == "section_items"
    assert primary_evidence["item_count"] == 1
    assert comparison_evidence["item_count"] == 1


# --- PASS-02: structured output, no fallback ---

def test_run_driver_pass_returns_driver_analysis_result():
    """PASS-02: run_driver_pass returns a DriverAnalysisResult instance."""
    expected = _make_result()
    adapter = _make_adapter(expected)
    dwi = _make_dwi()

    actual = run_driver_pass(dwi, adapter)

    assert isinstance(actual, DriverAnalysisResult), (
        f"Expected DriverAnalysisResult, got {type(actual)}"
    )
    assert actual.category == "Painting"
    assert actual.narrative != ""


def test_run_driver_pass_no_fallback_on_error():
    """PASS-02: when generate_structured raises, exception propagates — no silent fallback."""
    adapter = MagicMock()
    adapter.generate_structured.side_effect = RuntimeError("LLM failure")
    dwi = _make_dwi()

    with pytest.raises(RuntimeError, match="LLM failure"):
        run_driver_pass(dwi, adapter)


# --- PASS-03: per-driver cache ---

def test_run_driver_pass_cache_hit_skips_llm():
    """PASS-03: cache hit → generate_structured NOT called; cached result returned."""
    cached_result = _make_result()
    adapter = _make_adapter(_make_result())  # would return different object if called
    cache = _make_cache(hit=cached_result)
    dwi = _make_dwi()

    result = run_driver_pass(dwi, adapter, cache=cache)

    assert adapter.generate_structured.call_count == 0, (
        "generate_structured must NOT be called on cache hit"
    )
    assert result is cached_result, "cache hit must return cached object, not a new one"
    cache.get.assert_called_once()


def test_run_driver_pass_cache_miss_calls_llm_and_sets_cache():
    """PASS-03: cache miss → LLM called → cache.set() called with result."""
    fresh_result = _make_result()
    adapter = _make_adapter(fresh_result)
    cache = _make_cache(hit=None)  # miss
    dwi = _make_dwi()

    result = run_driver_pass(dwi, adapter, cache=cache)

    assert adapter.generate_structured.call_count == 1, "LLM must be called on cache miss"
    cache.set.assert_called_once()

    # set() was called with the result from the LLM
    set_call_args = cache.set.call_args[0]
    stored_result = set_call_args[1]
    assert stored_result is fresh_result, "cache.set must be called with the LLM result"


def test_driver_analysis_result_required_fields():
    """PASS-02: DriverAnalysisResult has all required fields."""
    r = DriverAnalysisResult(
        category="Roofing",
        primary_total=50000.0,
        comparison_total=32000.0,
        delta=18000.0,
        narrative="Test narrative.",
        scope_observations=["One observation."],
        suggested_followups=["One followup."],
    )
    assert r.category == "Roofing"
    assert r.primary_total == 50000.0
    assert r.comparison_total == 32000.0
    assert r.delta == 18000.0
    assert r.narrative == "Test narrative."
    assert r.scope_observations == ["One observation."]
    assert r.suggested_followups == ["One followup."]
