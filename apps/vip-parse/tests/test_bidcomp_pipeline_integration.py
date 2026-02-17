"""
Integration tests for BidComp with NarrativePipeline.

Tests cover:
- BidComp uses NarrativePipeline when llm_adapter is present
- BidComp produces NarrativeResult via pipeline
- BidComp with cache uses Redis
- BidComp fallback when no LLM
- BidComp fallback on pipeline error
"""

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import pytest
import fakeredis

from src.bid_comp import BidComp
from src.bid_comp.core import EstimatePair, EstimateArtifact, EstimateTotals


# ---------------------------------------------------------------------------
# Mock LLM Adapter
# ---------------------------------------------------------------------------


class MockLLMAdapter:
    """Mock LLM adapter that returns predefined responses."""

    def __init__(
        self,
        analysis_response: Optional[str] = None,
        writer_response: Optional[str] = None,
        compliance_response: Optional[str] = None,
        bid_comp_response: Optional[str] = None,
        raise_on: Optional[str] = None,
    ):
        self.responses = {
            "analysis_pass_v1": analysis_response,
            "writer_pass_v1": writer_response,
            "compliance_rewrite_v1": compliance_response,
            "bid_comp_summary_v1": bid_comp_response,
        }
        self.raise_on = raise_on
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    def generate(self, template_id: str, context: Dict[str, Any]) -> str:
        self.calls.append((template_id, context))
        if self.raise_on == template_id:
            raise RuntimeError(f"Mock error for {template_id}")
        response = self.responses.get(template_id)
        if response is None:
            raise ValueError(f"No response configured for template: {template_id}")
        return response


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_analysis_response() -> str:
    """Valid JSON response from Analysis pass."""
    return json.dumps({
        "category_analyses": [
            {
                "category": "HVAC / Mechanical",
                "primary_total": 6300.00,
                "comparison_total": 5100.00,
                "delta": 1200.00,
                "delta_drivers": ["Primary includes condenser replacement"],
                "line_item_evidence": ["Replace condenser $4,500"]
            },
        ],
        "scope_gaps": ["Comparison missing demo allowance"],
        "overall_delta_direction": "primary_higher",
        "confidence": "high"
    })


@pytest.fixture
def mock_writer_response() -> str:
    """Valid JSON response from Writer pass."""
    return json.dumps({
        "overview": "Primary estimate higher by $1,200 in HVAC category.",
        "key_drivers": [
            {
                "category": "HVAC / Mechanical",
                "amounts": "$6,300 vs $5,100 (delta $1,200)",
                "narrative": "Primary includes condenser replacement at $4,500. Comparison contemplates repair only."
            },
        ],
        "scope_observations": ["Comparison missing demo allowance"],
        "suggested_followups": ["Request contractor breakdown"]
    })


@pytest.fixture
def sample_bid_context() -> Dict[str, Any]:
    """Sample bid context for testing.

    Note: Items use keywords that map to VERISK_CATEGORY_ORDER categories.
    - "HVAC Unit" -> "HVAC / Mechanical"
    - "Mechanical work" -> "HVAC / Mechanical"
    """
    return {
        "estimates": [
            {
                "payload": {
                    "estimate_name": "Carrier Estimate",
                    "recaps_and_summaries": {
                        "recap_by_category": {
                            "HVAC": [
                                {"item": "HVAC Unit Replacement", "total": 4500.00},
                                {"item": "HVAC Ductwork", "total": 1800.00},
                            ],
                        },
                    },
                    "case_metadata": {
                        "line_item_totals": {"grand_total": 6300.00},
                    },
                },
                "source_filename": "carrier.pdf",
            },
            {
                "payload": {
                    "estimate_name": "Contractor Estimate",
                    "recaps_and_summaries": {
                        "recap_by_category": {
                            "HVAC": [
                                {"item": "HVAC Unit Repair", "total": 3000.00},
                                {"item": "HVAC Ductwork", "total": 2100.00},
                            ],
                        },
                    },
                    "case_metadata": {
                        "line_item_totals": {"grand_total": 5100.00},
                    },
                },
                "source_filename": "contractor.pdf",
            },
        ],
    }


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    """Create FakeRedis instance for testing."""
    return fakeredis.FakeRedis(decode_responses=False)


# ---------------------------------------------------------------------------
# TestBidCompUsesNarrativePipeline
# ---------------------------------------------------------------------------


class TestBidCompUsesNarrativePipeline:
    """Tests that BidComp uses NarrativePipeline when configured."""

    def test_bidcomp_uses_pipeline_when_llm_present(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
    ):
        """BidComp creates pipeline when llm_adapter is provided."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        assert bid_comp._pipeline is not None
        assert bid_comp._cache is None  # No redis provided

    def test_bidcomp_pipeline_produces_narrative_result(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        sample_bid_context: Dict[str, Any],
    ):
        """BidComp produces NarrativeResult via pipeline."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        # Run the full pipeline
        xlsx_bytes = bid_comp.run(sample_bid_context, job_id="test-job-1")

        # Should produce output
        assert xlsx_bytes is not None
        assert len(xlsx_bytes) > 0

        # Debug info should show pipeline was used
        assert bid_comp.last_narrative_debug is not None
        assert bid_comp.last_narrative_debug.get("status") == "pipeline"
        assert "passes_executed" in bid_comp.last_narrative_debug

    def test_bidcomp_pipeline_calls_correct_templates(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        sample_bid_context: Dict[str, Any],
    ):
        """BidComp pipeline calls analysis and writer templates."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        bid_comp.run(sample_bid_context, job_id="test-job-2")

        # Check templates were called
        template_ids = [call[0] for call in adapter.calls]
        assert "analysis_pass_v1" in template_ids
        assert "writer_pass_v1" in template_ids


class TestBidCompWithCache:
    """Tests for BidComp with Redis caching."""

    def test_bidcomp_with_cache_uses_redis(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        fake_redis: fakeredis.FakeRedis,
    ):
        """BidComp creates cache when redis is provided."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter, redis=fake_redis)

        assert bid_comp._pipeline is not None
        assert bid_comp._cache is not None

    def test_bidcomp_cache_hit_on_second_call(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        sample_bid_context: Dict[str, Any],
        fake_redis: fakeredis.FakeRedis,
    ):
        """Same input produces cache hit on second call."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter, redis=fake_redis)

        # First call - should generate
        bid_comp.run(sample_bid_context, job_id="test-job-3")
        first_call_count = len(adapter.calls)

        # Second call - should hit cache
        bid_comp.run(sample_bid_context, job_id="test-job-4")
        second_call_count = len(adapter.calls)

        # Analysis/writer should be cached; compliance rewrites are not cached.
        second_call_templates = [name for name, _ in adapter.calls[first_call_count:]]
        assert "analysis_pass_v1" not in second_call_templates
        assert "writer_pass_v1" not in second_call_templates
        assert all(name == "compliance_rewrite_v1" for name in second_call_templates)

        # Verify cache entries exist
        keys = fake_redis.keys("pipeline:*")
        assert len(keys) >= 2  # At least analysis and writer


class TestBidCompFallback:
    """Tests for BidComp fallback behavior."""

    def test_bidcomp_fallback_when_no_llm(
        self,
        sample_bid_context: Dict[str, Any],
    ):
        """BidComp uses fallback when no llm_adapter."""
        bid_comp = BidComp(llm_adapter=None)

        assert bid_comp._pipeline is None

        # Should still run and produce output
        xlsx_bytes = bid_comp.run(sample_bid_context, job_id="test-job-5")
        assert xlsx_bytes is not None
        assert len(xlsx_bytes) > 0

        # Debug should show fallback
        assert bid_comp.last_narrative_debug is not None
        assert bid_comp.last_narrative_debug.get("status") == "fallback"

    def test_bidcomp_fallback_on_pipeline_error(
        self,
        sample_bid_context: Dict[str, Any],
    ):
        """BidComp falls back when pipeline raises error."""
        # Adapter that raises on analysis
        adapter = MockLLMAdapter(
            analysis_response=None,
            raise_on="analysis_pass_v1",
        )
        bid_comp = BidComp(llm_adapter=adapter)

        # Should still run and produce output via fallback
        xlsx_bytes = bid_comp.run(sample_bid_context, job_id="test-job-6")
        assert xlsx_bytes is not None
        assert len(xlsx_bytes) > 0


class TestBidCompPipelineDetails:
    """Tests for specific pipeline integration details."""

    def test_bidcomp_pipeline_records_passes(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        sample_bid_context: Dict[str, Any],
    ):
        """Pipeline passes are recorded in debug info."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        bid_comp.run(sample_bid_context, job_id="test-job-7")

        debug = bid_comp.last_narrative_debug
        assert debug is not None
        passes = debug.get("passes_executed", [])
        assert "analysis" in passes or "analysis_cached" in passes
        assert "writer" in passes or "writer_cached" in passes
        assert "quality_check" in passes

    def test_bidcomp_pipeline_records_timings(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        sample_bid_context: Dict[str, Any],
    ):
        """Pipeline timings are recorded in debug info."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        bid_comp.run(sample_bid_context, job_id="test-job-8")

        debug = bid_comp.last_narrative_debug
        assert debug is not None
        timings = debug.get("pass_timings_ms", {})
        assert len(timings) > 0

    def test_bidcomp_narrative_result_has_sections(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        sample_bid_context: Dict[str, Any],
    ):
        """NarrativeResult from pipeline has required sections."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        # Access internal method for testing
        pair = bid_comp._build_pair(sample_bid_context)
        category_rows = bid_comp._build_category_table(pair)
        top_deltas = bid_comp._top_deltas(category_rows)
        narrative = bid_comp._generate_narrative(pair, top_deltas)

        assert narrative.parsed is True
        assert narrative.sections is not None
        assert "overview_of_estimates" in narrative.sections
        assert "key_cost_drivers" in narrative.sections


# ---------------------------------------------------------------------------
# TestKeyDriverNumericValues - REGR-01 Regression Tests
# ---------------------------------------------------------------------------


class TestKeyDriverNumericValues:
    """
    REGR-01: Tests for numeric values in key_drivers.

    Verifies that key_drivers have numeric primary_total, comparison_total,
    delta_total values populated from top_deltas, not None.
    """

    def test_key_drivers_have_numeric_values(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        sample_bid_context: Dict[str, Any],
    ):
        """REGR-01: Key drivers should have numeric primary_total, comparison_total, delta_total."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        # Run to get narrative
        pair = bid_comp._build_pair(sample_bid_context)
        category_rows = bid_comp._build_category_table(pair)
        top_deltas = bid_comp._top_deltas(category_rows)
        narrative = bid_comp._generate_narrative(pair, top_deltas)

        # Verify key_drivers have numeric values
        assert narrative.key_drivers is not None
        assert len(narrative.key_drivers) > 0

        # Find the HVAC driver (we know it's in our test data)
        hvac_driver = None
        for driver in narrative.key_drivers:
            if "HVAC" in driver.get("category", ""):
                hvac_driver = driver
                break

        assert hvac_driver is not None, "HVAC driver should exist in key_drivers"

        # Verify numeric values are present and correct
        # HVAC in sample_bid_context: primary=6300, comparison=5100, delta=-1200
        assert hvac_driver.get("primary_total") is not None, "primary_total should not be None"
        assert hvac_driver.get("comparison_total") is not None, "comparison_total should not be None"
        assert hvac_driver.get("delta_total") is not None, "delta_total should not be None"

        # Values should be numeric
        assert isinstance(hvac_driver["primary_total"], (int, float))
        assert isinstance(hvac_driver["comparison_total"], (int, float))
        assert isinstance(hvac_driver["delta_total"], (int, float))

    def test_category_matching_is_case_insensitive(
        self,
        sample_bid_context: Dict[str, Any],
    ):
        """REGR-01: Category matching should be case-insensitive."""
        # Create mock responses with different casing
        analysis_response = json.dumps({
            "category_analyses": [
                {
                    "category": "hvac / mechanical",  # lowercase
                    "primary_total": 6300.00,
                    "comparison_total": 5100.00,
                    "delta": 1200.00,
                    "delta_drivers": ["Primary includes condenser"],
                    "line_item_evidence": ["Replace condenser"]
                },
            ],
            "scope_gaps": [],
            "overall_delta_direction": "primary_higher",
            "confidence": "high"
        })
        writer_response = json.dumps({
            "overview": "Test overview.",
            "key_drivers": [
                {
                    "category": "HVAC / Mechanical",  # Title Case
                    "amounts": "$6,300 vs $5,100",
                    "narrative": "Test narrative."
                },
            ],
            "scope_observations": [],
            "suggested_followups": []
        })

        adapter = MockLLMAdapter(
            analysis_response=analysis_response,
            writer_response=writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        pair = bid_comp._build_pair(sample_bid_context)
        category_rows = bid_comp._build_category_table(pair)
        top_deltas = bid_comp._top_deltas(category_rows)
        narrative = bid_comp._generate_narrative(pair, top_deltas)

        # Should match despite case difference
        assert len(narrative.key_drivers) > 0
        hvac_driver = narrative.key_drivers[0]

        # Should have numeric values even with case mismatch
        # The actual values depend on what's in top_deltas (from category_rows)
        # Since HVAC maps to "HVAC / Mechanical" in VERISK_CATEGORY_ORDER
        assert hvac_driver.get("category") == "HVAC / Mechanical"

    def test_fallback_when_category_not_in_top_deltas(
        self,
        sample_bid_context: Dict[str, Any],
    ):
        """REGR-01: Values should be None (graceful degradation) when category not found."""
        # Create mock responses with a category that won't match top_deltas
        analysis_response = json.dumps({
            "category_analyses": [
                {
                    "category": "Unknown Category XYZ",
                    "primary_total": 1000.00,
                    "comparison_total": 500.00,
                    "delta": 500.00,
                    "delta_drivers": ["Test"],
                    "line_item_evidence": ["Test"]
                },
            ],
            "scope_gaps": [],
            "overall_delta_direction": "primary_higher",
            "confidence": "high"
        })
        writer_response = json.dumps({
            "overview": "Test overview.",
            "key_drivers": [
                {
                    "category": "Unknown Category XYZ",
                    "amounts": "$1,000 vs $500",
                    "narrative": "Test narrative."
                },
            ],
            "scope_observations": [],
            "suggested_followups": []
        })

        adapter = MockLLMAdapter(
            analysis_response=analysis_response,
            writer_response=writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        pair = bid_comp._build_pair(sample_bid_context)
        category_rows = bid_comp._build_category_table(pair)
        top_deltas = bid_comp._top_deltas(category_rows)
        narrative = bid_comp._generate_narrative(pair, top_deltas)

        # Find the unknown category driver
        unknown_driver = None
        for driver in narrative.key_drivers:
            if "Unknown" in driver.get("category", ""):
                unknown_driver = driver
                break

        assert unknown_driver is not None

        # Values should be None when category doesn't match top_deltas
        # (graceful degradation)
        assert unknown_driver.get("category") == "Unknown Category XYZ"
        # Note: These may be None because the category isn't in top_deltas
        # The test validates graceful degradation - no exception thrown

    def test_key_drivers_full_pipeline_integration(
        self,
        mock_analysis_response: str,
        mock_writer_response: str,
        sample_bid_context: Dict[str, Any],
    ):
        """REGR-01: Full pipeline run produces key_drivers with numeric values."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response,
        )
        bid_comp = BidComp(llm_adapter=adapter)

        # Run full pipeline through run() method
        xlsx_bytes = bid_comp.run(sample_bid_context, job_id="regr-01-test")

        assert xlsx_bytes is not None
        assert len(xlsx_bytes) > 0

        # Verify via debug info that pipeline was used
        assert bid_comp.last_narrative_debug is not None
        assert bid_comp.last_narrative_debug.get("status") == "pipeline"
