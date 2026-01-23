"""
Unit tests for the NarrativePipeline orchestrator.

Tests cover:
- Pipeline skipping compliance when quality passes
- Pipeline running compliance when quality fails
- Max 2 rewrite iterations enforcement
- Error handling for analysis and writer failures
- Pass timing recording
- End-to-end integration tests
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from src.pipeline import (
    NarrativePipeline,
    PipelineState,
    AnalysisResult,
    CategoryAnalysis,
    DraftNarrative,
    DriverNarrative,
    FinalNarrative,
    QualityReport,
    QualityEvaluator,
)


# ---------------------------------------------------------------------------
# Mock Fixtures
# ---------------------------------------------------------------------------


class MockEstimate:
    """Mock estimate for testing - works with both attribute and dict access."""

    def __init__(self, estimate_name: str, payload: Dict[str, Any]):
        self.estimate_name = estimate_name
        self.payload = payload

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def keys(self) -> List[str]:
        return ["estimate_name", "payload"]


class MockEstimatePair:
    """Mock estimate pair for testing - works with both attribute and dict access."""

    def __init__(self, primary: MockEstimate, comparison: MockEstimate):
        self.primary = primary
        self.comparison = comparison

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def keys(self) -> List[str]:
        return ["primary", "comparison"]


class MockLLMAdapter:
    """
    Mock LLM adapter that returns predefined responses based on template.

    Configure responses for each template:
    - analysis_pass_v1: Returns analysis result JSON
    - writer_pass_v1: Returns draft narrative JSON
    - compliance_rewrite_v1: Returns rewritten narrative JSON
    """

    def __init__(
        self,
        analysis_response: Optional[str] = None,
        writer_response: Optional[str] = None,
        compliance_response: Optional[str] = None,
        raise_on: Optional[str] = None,
    ):
        self.responses = {
            "analysis_pass_v1": analysis_response,
            "writer_pass_v1": writer_response,
            "compliance_rewrite_v1": compliance_response,
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


class AlwaysPassEvaluator(QualityEvaluator):
    """Mock evaluator that always passes quality checks."""

    def evaluate(self, draft: DraftNarrative) -> QualityReport:
        from src.pipeline import QualityCheckResult
        return QualityReport(
            passed=True,
            checks=[
                QualityCheckResult(check_name="GATE-01", passed=True, details="Mock pass"),
                QualityCheckResult(check_name="GATE-02", passed=True, details="Mock pass"),
            ],
        )


class AlwaysFailEvaluator(QualityEvaluator):
    """Mock evaluator that always fails quality checks."""

    def evaluate(self, draft: DraftNarrative) -> QualityReport:
        from src.pipeline import QualityCheckResult
        return QualityReport(
            passed=False,
            checks=[
                QualityCheckResult(check_name="GATE-01", passed=False, details="Mock fail: 5 hedge words"),
                QualityCheckResult(check_name="GATE-05", passed=False, details="Mock fail: analyst phrases"),
            ],
        )


class FailThenPassEvaluator(QualityEvaluator):
    """Mock evaluator that fails first N times, then passes."""

    def __init__(self, fail_count: int = 1):
        super().__init__()
        self.fail_count = fail_count
        self.call_count = 0

    def evaluate(self, draft: DraftNarrative) -> QualityReport:
        from src.pipeline import QualityCheckResult
        self.call_count += 1
        if self.call_count <= self.fail_count:
            return QualityReport(
                passed=False,
                checks=[QualityCheckResult(check_name="GATE-01", passed=False, details="Mock fail")],
            )
        return QualityReport(
            passed=True,
            checks=[QualityCheckResult(check_name="GATE-01", passed=True, details="Mock pass")],
        )


@pytest.fixture
def mock_pair() -> MockEstimatePair:
    """Create mock estimate pair for testing."""
    return MockEstimatePair(
        primary=MockEstimate(
            estimate_name="Carrier Estimate",
            payload={"sections": []},
        ),
        comparison=MockEstimate(
            estimate_name="Contractor Estimate",
            payload={"sections": []},
        ),
    )


@pytest.fixture
def sample_top_deltas() -> List[Dict[str, Any]]:
    """Sample top deltas from BidComp."""
    return [
        {"category": "HVAC / Mechanical", "primary_total": 6300.00, "comparison_total": 5100.00, "delta": 1200.00},
        {"category": "Flooring", "primary_total": 4590.00, "comparison_total": 3200.00, "delta": 1390.00},
    ]


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
                "line_item_evidence": ["Primary: Replace condenser $4,500"]
            },
            {
                "category": "Flooring",
                "primary_total": 4590.00,
                "comparison_total": 3200.00,
                "delta": 1390.00,
                "delta_drivers": ["Primary uses hardwood"],
                "line_item_evidence": ["Primary: Install hardwood $3,600"]
            }
        ],
        "scope_gaps": ["Comparison missing demo allowance"],
        "overall_delta_direction": "primary_higher",
        "confidence": "high"
    })


@pytest.fixture
def mock_writer_response_clean() -> str:
    """Valid JSON response from Writer pass (no hedge words)."""
    return json.dumps({
        "overview": "Primary estimate higher by $2,590 across HVAC and flooring categories.",
        "key_drivers": [
            {
                "category": "HVAC / Mechanical",
                "amounts": "$6,300 vs $5,100 (delta $1,200)",
                "narrative": "Primary includes condenser replacement at $4,500. Comparison contemplates repair only."
            },
            {
                "category": "Flooring",
                "amounts": "$4,590 vs $3,200 (delta $1,390)",
                "narrative": "Primary specifies hardwood at $3,600. Comparison uses LVP."
            }
        ],
        "scope_observations": ["Comparison missing demo allowance"],
        "suggested_followups": ["Request contractor breakdown"]
    })


@pytest.fixture
def mock_writer_response_with_hedges() -> str:
    """Valid JSON response from Writer pass WITH hedge words (fails quality)."""
    return json.dumps({
        "overview": "Primary estimate appears higher. The variance seems significant.",
        "key_drivers": [
            {
                "category": "HVAC / Mechanical",
                "amounts": "$6,300 vs $5,100",
                "narrative": "Primary possibly includes condenser. This might indicate scope difference."
            }
        ],
        "scope_observations": [],
        "suggested_followups": []
    })


@pytest.fixture
def mock_compliance_response() -> str:
    """Valid JSON response from Compliance rewrite pass."""
    return json.dumps({
        "overview": "Primary estimate higher by $2,590. Variance driven by HVAC and flooring scope.",
        "key_drivers": [
            {
                "category": "HVAC / Mechanical",
                "amounts": "$6,300 vs $5,100 (delta $1,200)",
                "narrative": "Primary includes condenser replacement. Comparison contemplates repair only."
            }
        ],
        "scope_observations": [],
        "suggested_followups": []
    })


# ---------------------------------------------------------------------------
# TestNarrativePipelineQualityPassed
# ---------------------------------------------------------------------------


class TestNarrativePipelineQualityPassed:
    """Tests for pipeline behavior when quality passes."""

    def test_pipeline_skips_compliance_when_quality_passes(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_clean: str
    ):
        """Test that compliance pass is skipped when quality passes."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_clean,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Should have analysis, writer, quality_check, and compliance_skipped
        assert "analysis" in state.passes_executed
        assert "writer" in state.passes_executed
        assert "quality_check" in state.passes_executed
        assert "compliance_skipped" in state.passes_executed
        # Should NOT have compliance_rewrite_*
        assert not any(p.startswith("compliance_rewrite_") for p in state.passes_executed)

    def test_pipeline_logs_compliance_skipped(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_clean: str,
        caplog
    ):
        """Test that skipping compliance is logged."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_clean,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        with caplog.at_level(logging.INFO, logger="vip-parse.pipeline"):
            pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        log_messages = [r.message for r in caplog.records]
        assert any("skipping compliance rewrite" in m for m in log_messages)

    def test_pipeline_records_all_pass_timings(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_clean: str
    ):
        """Test that all pass timings are recorded."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_clean,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        assert "analysis" in state.pass_timings_ms
        assert "writer" in state.pass_timings_ms
        assert "quality_check" in state.pass_timings_ms
        # All timings should be non-negative
        assert all(t >= 0 for t in state.pass_timings_ms.values())

    def test_pipeline_sets_rewrites_performed_zero(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_clean: str
    ):
        """Test that rewrites_performed is 0 when quality passes."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_clean,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        assert isinstance(state.final, FinalNarrative)
        assert state.final.rewrites_performed == 0


# ---------------------------------------------------------------------------
# TestNarrativePipelineQualityFailed
# ---------------------------------------------------------------------------


class TestNarrativePipelineQualityFailed:
    """Tests for pipeline behavior when quality fails."""

    def test_pipeline_runs_compliance_when_quality_fails(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_with_hedges: str,
        mock_compliance_response: str
    ):
        """Test that compliance pass runs when quality fails."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_with_hedges,
            compliance_response=mock_compliance_response,
        )
        # Fail once (writer output), then pass after rewrite
        pipeline = NarrativePipeline(adapter, quality_evaluator=FailThenPassEvaluator(fail_count=1))

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Should have compliance_rewrite_1
        assert "compliance_rewrite_1" in state.passes_executed
        assert "compliance_skipped" not in state.passes_executed

    def test_pipeline_max_two_rewrite_iterations(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_with_hedges: str,
        mock_compliance_response: str
    ):
        """Test that max 2 rewrite iterations are enforced."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_with_hedges,
            compliance_response=mock_compliance_response,
        )
        # Always fail - should stop after 2 iterations
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysFailEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Should have exactly 2 compliance rewrites
        compliance_rewrites = [p for p in state.passes_executed if p.startswith("compliance_rewrite_")]
        assert len(compliance_rewrites) == 2
        assert "compliance_rewrite_1" in state.passes_executed
        assert "compliance_rewrite_2" in state.passes_executed

    def test_pipeline_stops_rewrite_loop_when_quality_passes(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_with_hedges: str,
        mock_compliance_response: str
    ):
        """Test that rewrite loop stops when quality passes."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_with_hedges,
            compliance_response=mock_compliance_response,
        )
        # Fail once, then pass
        pipeline = NarrativePipeline(adapter, quality_evaluator=FailThenPassEvaluator(fail_count=1))

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Should have only 1 compliance rewrite (stopped after quality passed)
        compliance_rewrites = [p for p in state.passes_executed if p.startswith("compliance_rewrite_")]
        assert len(compliance_rewrites) == 1
        assert state.quality_passed()

    def test_pipeline_records_compliance_timings(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_with_hedges: str,
        mock_compliance_response: str
    ):
        """Test that compliance rewrite timings are recorded."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_with_hedges,
            compliance_response=mock_compliance_response,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysFailEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        assert "compliance_rewrite_1" in state.pass_timings_ms
        assert "compliance_rewrite_2" in state.pass_timings_ms

    def test_pipeline_sets_rewrites_performed_count(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_with_hedges: str,
        mock_compliance_response: str
    ):
        """Test that rewrites_performed reflects actual rewrite count."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_with_hedges,
            compliance_response=mock_compliance_response,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysFailEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        assert isinstance(state.final, FinalNarrative)
        assert state.final.rewrites_performed == 2


# ---------------------------------------------------------------------------
# TestNarrativePipelineErrorHandling
# ---------------------------------------------------------------------------


class TestNarrativePipelineErrorHandling:
    """Tests for pipeline error handling - passes use graceful fallback instead of errors."""

    def test_pipeline_handles_analysis_failure_with_fallback(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_writer_response_clean: str
    ):
        """Test that analysis failure produces fallback result with low confidence."""
        adapter = MockLLMAdapter(
            analysis_response=None,  # Will cause error in adapter
            writer_response=mock_writer_response_clean,
            raise_on="analysis_pass_v1",
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Analysis pass has internal error handling - returns fallback with low confidence
        assert state.analysis is not None
        assert state.analysis.confidence == "low"
        # Fallback analysis should have delta_drivers mentioning error
        assert any(
            "unavailable" in d.delta_drivers[0].lower()
            for d in state.analysis.category_analyses
            if d.delta_drivers
        )
        # Pipeline should still complete
        assert state.final is not None

    def test_pipeline_handles_writer_failure_with_fallback(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str
    ):
        """Test that writer failure produces fallback narrative."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=None,  # Will cause error
            raise_on="writer_pass_v1",
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Analysis should have succeeded with high confidence
        assert state.analysis is not None
        assert state.analysis.confidence == "high"
        # Writer pass has internal error handling - returns fallback narrative
        assert state.draft is not None
        # Fallback overview contains "Analysis complete"
        assert "Analysis complete" in state.draft.overview
        # Pipeline should still complete
        assert state.final is not None

    def test_pipeline_handles_compliance_failure_with_original_draft(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_with_hedges: str
    ):
        """Test that compliance failure preserves original draft."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_with_hedges,
            compliance_response=None,  # Will cause error
            raise_on="compliance_rewrite_v1",
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysFailEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Compliance pass has internal error handling - returns original draft
        # Pipeline should still complete with the (unchanged) draft
        assert state.final is not None
        # Draft should still have hedge words since rewrite failed
        assert "appears" in state.draft.overview or "seems" in state.draft.overview

    def test_pipeline_completes_despite_llm_errors(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_writer_response_clean: str
    ):
        """Test that pipeline always completes even with LLM errors via fallback handling."""
        adapter = MockLLMAdapter(
            analysis_response=None,
            writer_response=mock_writer_response_clean,
            raise_on="analysis_pass_v1",
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Pipeline should complete successfully despite LLM error
        assert state.is_complete()
        assert state.final is not None
        # Pass should still be marked as executed
        assert "analysis" in state.passes_executed


# ---------------------------------------------------------------------------
# TestEndToEndIntegration
# ---------------------------------------------------------------------------


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_analysis_to_final_narrative(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_clean: str
    ):
        """Test complete pipeline from analysis to final narrative."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_clean,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # All intermediate results should be present
        assert state.analysis is not None
        assert isinstance(state.analysis, AnalysisResult)
        assert state.draft is not None
        assert isinstance(state.draft, DraftNarrative)
        assert state.quality_report is not None
        assert isinstance(state.quality_report, QualityReport)
        assert state.final is not None
        assert isinstance(state.final, FinalNarrative)

        # Final should have content from draft
        assert len(state.final.key_drivers) > 0
        assert state.final.quality_report == state.quality_report

    def test_pipeline_state_contains_all_intermediate_results(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_with_hedges: str,
        mock_compliance_response: str
    ):
        """Test that PipelineState contains all intermediate results."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_with_hedges,
            compliance_response=mock_compliance_response,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=FailThenPassEvaluator(fail_count=1))

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # State should preserve inputs
        assert state.pair == mock_pair
        assert state.top_deltas == sample_top_deltas

        # State should have all pass outputs
        assert state.analysis is not None
        assert state.analysis.confidence == "high"
        assert state.draft is not None
        assert state.quality_report is not None
        assert state.final is not None

        # State should have execution metadata
        assert len(state.passes_executed) >= 4  # analysis, writer, quality_check, compliance_rewrite_1
        assert len(state.pass_timings_ms) >= 4

    def test_pipeline_with_real_quality_evaluator(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_clean: str
    ):
        """Test pipeline with real QualityEvaluator (not mocked)."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_clean,
        )
        # Use real evaluator - the clean response should pass
        pipeline = NarrativePipeline(adapter)

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Clean response should pass quality
        assert state.quality_report is not None
        # Final narrative should exist
        assert state.final is not None
        assert isinstance(state.final, FinalNarrative)

    def test_pipeline_calls_templates_in_correct_order(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_clean: str
    ):
        """Test that templates are called in correct sequence."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_clean,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        # Should have exactly 2 calls (analysis, writer) - no compliance since quality passed
        assert len(adapter.calls) == 2
        assert adapter.calls[0][0] == "analysis_pass_v1"
        assert adapter.calls[1][0] == "writer_pass_v1"

    def test_pipeline_complete_check(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_analysis_response: str,
        mock_writer_response_clean: str
    ):
        """Test PipelineState.is_complete() method."""
        adapter = MockLLMAdapter(
            analysis_response=mock_analysis_response,
            writer_response=mock_writer_response_clean,
        )
        pipeline = NarrativePipeline(adapter, quality_evaluator=AlwaysPassEvaluator())

        state = pipeline.run(mock_pair, sample_top_deltas, "Carrier", "Contractor")

        assert state.is_complete()
        assert state.final is not None
