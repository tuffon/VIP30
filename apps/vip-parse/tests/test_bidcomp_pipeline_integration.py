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
    """Sample bid context for testing."""
    return {
        "estimates": [
            {
                "payload": {
                    "estimate_name": "Carrier Estimate",
                    "recaps_and_summaries": {
                        "recap_by_category": {
                            "HVAC": [
                                {"item": "Condenser", "total": 4500.00},
                                {"item": "Ductwork", "total": 1800.00},
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
                                {"item": "Repair condenser", "total": 3000.00},
                                {"item": "Ductwork", "total": 2100.00},
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

        # Second call should have fewer LLM calls due to cache
        # (analysis and writer cached, so no new LLM calls)
        assert second_call_count == first_call_count  # No new calls

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
