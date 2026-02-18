"""
Unit tests for the Writer pass.

Tests cover:
- WriterInput model creation and serialization
- build_writer_input() from AnalysisResult
- run_writer_pass() with mock LLM responses
- Graceful handling of malformed responses
- Integration flow from analysis to writer
"""

import json
import logging
from typing import Any, Dict, List

import pytest

from vip_shared.pipeline import (
    AnalysisResult,
    CategoryAnalysis,
    DraftNarrative,
    DriverNarrative,
    run_writer_pass,
    WriterInput,
)
from vip_shared.pipeline.passes.writer import build_writer_input, _parse_writer_response


# ---------------------------------------------------------------------------
# Mock Fixtures
# ---------------------------------------------------------------------------


class MockLLMAdapter:
    """Mock LLM adapter that returns predefined responses."""

    def __init__(self, response: str):
        self.response = response
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    def generate(self, template_id: str, context: Dict[str, Any]) -> str:
        self.calls.append((template_id, context))
        return self.response


@pytest.fixture
def sample_analysis_result() -> AnalysisResult:
    """Sample AnalysisResult with 3 CategoryAnalysis items."""
    return AnalysisResult(
        category_analyses=[
            CategoryAnalysis(
                category="HVAC / Mechanical",
                primary_total=6300.00,
                comparison_total=5100.00,
                delta=1200.00,
                delta_drivers=["Primary includes condenser replacement", "Labor rate difference"],
                line_item_evidence=["Primary: Replace condenser unit $4,500", "Comparison: Repair condenser $3,200"],
            ),
            CategoryAnalysis(
                category="Flooring",
                primary_total=4590.00,
                comparison_total=3200.00,
                delta=1390.00,
                delta_drivers=["Primary uses hardwood", "Comparison uses LVP"],
                line_item_evidence=["Primary: Install hardwood $3,600", "Comparison: Install LVP $2,100"],
            ),
            CategoryAnalysis(
                category="Electrical",
                primary_total=4800.00,
                comparison_total=1200.00,
                delta=3600.00,
                delta_drivers=["Primary includes panel upgrade", "Comparison omits circuit work"],
                line_item_evidence=["Primary: Panel upgrade + 12 circuits $4,800", "Comparison: Service upgrade only $1,200"],
            ),
        ],
        scope_gaps=["Comparison missing demolition allowance", "Primary includes permit fees"],
        overall_delta_direction="primary_higher",
        confidence="high",
    )


@pytest.fixture
def mock_valid_writer_response() -> str:
    """Valid JSON response from Writer pass LLM."""
    return json.dumps({
        "overview": "Primary estimate higher by $6,190 across 3 categories. HVAC, flooring, and electrical scope differences drive variance.",
        "key_drivers": [
            {
                "category": "HVAC / Mechanical",
                "amounts": "$6,300 vs $5,100 (delta $1,200)",
                "narrative": "Primary includes condenser replacement. Comparison contemplates repair only."
            },
            {
                "category": "Flooring",
                "amounts": "$4,590 vs $3,200 (delta $1,390)",
                "narrative": "Primary specifies hardwood. Comparison uses LVP. Delta driven by material selection."
            },
            {
                "category": "Electrical",
                "amounts": "$4,800 vs $1,200 (delta $3,600)",
                "narrative": "Primary includes panel upgrade + 12 circuits. Comparison fails to include circuit work."
            }
        ],
        "scope_observations": [
            "Comparison missing demolition allowance",
            "Primary includes permit fees not in comparison"
        ],
        "suggested_followups": [
            "Request itemized mitigation breakdown from contractor",
            "Clarify ELE scope requirements"
        ]
    })


@pytest.fixture
def empty_analysis_result() -> AnalysisResult:
    """Empty AnalysisResult for edge case testing."""
    return AnalysisResult(
        category_analyses=[],
        scope_gaps=[],
        overall_delta_direction="similar",
        confidence="low",
    )


# ---------------------------------------------------------------------------
# TestWriterInput
# ---------------------------------------------------------------------------


class TestWriterInput:
    """Tests for WriterInput model and build_writer_input()."""

    def test_build_writer_input_from_analysis(self, sample_analysis_result: AnalysisResult):
        """Test building WriterInput from AnalysisResult."""
        result = build_writer_input(
            sample_analysis_result,
            primary_name="Carrier Estimate",
            comparison_name="Contractor Estimate"
        )

        assert result.primary_name == "Carrier Estimate"
        assert result.comparison_name == "Contractor Estimate"
        assert len(result.category_analyses) == 3
        assert result.category_analyses[0]["category"] == "HVAC / Mechanical"
        assert result.overall_delta_direction == "primary_higher"
        assert result.confidence == "high"

    def test_writer_input_serializes_to_json(self, sample_analysis_result: AnalysisResult):
        """Test that WriterInput serializes to JSON cleanly."""
        writer_input = build_writer_input(
            sample_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison"
        )

        json_str = writer_input.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["primary_name"] == "Primary"
        assert len(parsed["category_analyses"]) == 3
        assert parsed["overall_delta_direction"] == "primary_higher"

    def test_writer_input_handles_empty_analysis(self, empty_analysis_result: AnalysisResult):
        """Test WriterInput with empty AnalysisResult."""
        result = build_writer_input(
            empty_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison"
        )

        assert result.category_analyses == []
        assert result.scope_gaps == []
        assert result.overall_delta_direction == "similar"
        assert result.confidence == "low"

    def test_writer_input_preserves_category_details(self, sample_analysis_result: AnalysisResult):
        """Test that category details are fully preserved in serialization."""
        result = build_writer_input(
            sample_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison"
        )

        hvac_analysis = result.category_analyses[0]
        assert hvac_analysis["primary_total"] == 6300.00
        assert hvac_analysis["comparison_total"] == 5100.00
        assert hvac_analysis["delta"] == 1200.00
        assert "condenser replacement" in hvac_analysis["delta_drivers"][0]


# ---------------------------------------------------------------------------
# TestRunWriterPass
# ---------------------------------------------------------------------------


class TestRunWriterPass:
    """Tests for run_writer_pass() function."""

    def test_writer_pass_returns_valid_draft_narrative(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str
    ):
        """Test that valid LLM response produces correct DraftNarrative."""
        adapter = MockLLMAdapter(mock_valid_writer_response)

        result = run_writer_pass(
            sample_analysis_result,
            primary_name="Carrier Estimate",
            comparison_name="Contractor Estimate",
            llm_adapter=adapter
        )

        assert isinstance(result, DraftNarrative)
        assert "Primary estimate higher" in result.overview
        assert len(result.key_drivers) == 3
        assert result.key_drivers[0].category == "HVAC / Mechanical"
        assert len(result.scope_observations) == 2
        assert len(result.suggested_followups) == 2

    def test_writer_pass_handles_malformed_json(self, sample_analysis_result: AnalysisResult):
        """Test that malformed JSON returns fallback DraftNarrative."""
        adapter = MockLLMAdapter("this is not json at all { broken ]")

        result = run_writer_pass(
            sample_analysis_result,
            primary_name="Carrier Estimate",
            comparison_name="Contractor Estimate",
            llm_adapter=adapter
        )

        assert isinstance(result, DraftNarrative)
        assert "Comparing Carrier Estimate and Contractor Estimate" in result.overview
        # Fallback should create key_drivers from analysis categories
        assert len(result.key_drivers) == 3

    def test_writer_pass_handles_empty_analysis(self, empty_analysis_result: AnalysisResult):
        """Test that empty AnalysisResult doesn't crash."""
        response = json.dumps({
            "overview": "Estimates are similar.",
            "key_drivers": [],
            "scope_observations": [],
            "suggested_followups": []
        })
        adapter = MockLLMAdapter(response)

        result = run_writer_pass(
            empty_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        assert isinstance(result, DraftNarrative)
        assert "similar" in result.overview.lower()

    def test_writer_pass_parses_key_drivers(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str
    ):
        """Test that key_drivers are parsed into DriverNarrative objects."""
        adapter = MockLLMAdapter(mock_valid_writer_response)

        result = run_writer_pass(
            sample_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        assert all(isinstance(d, DriverNarrative) for d in result.key_drivers)
        assert result.key_drivers[0].amounts == "$6,300 vs $5,100 (delta $1,200)"
        assert "condenser replacement" in result.key_drivers[0].narrative

    def test_writer_pass_parses_scope_observations(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str
    ):
        """Test that scope_observations are parsed correctly."""
        adapter = MockLLMAdapter(mock_valid_writer_response)

        result = run_writer_pass(
            sample_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        assert len(result.scope_observations) == 2
        assert "demolition allowance" in result.scope_observations[0]
        assert "permit fees" in result.scope_observations[1]

    def test_writer_pass_logs_request_details(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str,
        caplog
    ):
        """Test that writer pass logs request details."""
        adapter = MockLLMAdapter(mock_valid_writer_response)

        with caplog.at_level(logging.INFO, logger="vip-parse.pipeline.writer"):
            run_writer_pass(
                sample_analysis_result,
                primary_name="Carrier Estimate",
                comparison_name="Contractor Estimate",
                llm_adapter=adapter
            )

        log_messages = [r.message for r in caplog.records]
        assert any("writer pass start" in m for m in log_messages)
        assert any("writer pass complete" in m for m in log_messages)

    def test_writer_pass_calls_correct_template(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str
    ):
        """Test that writer pass calls the writer_pass_v1 template."""
        adapter = MockLLMAdapter(mock_valid_writer_response)

        run_writer_pass(
            sample_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        assert len(adapter.calls) == 1
        template_id, context = adapter.calls[0]
        assert template_id == "writer_pass_v1"
        assert "primary_name" in context
        assert "category_analyses_json" in context

    def test_writer_pass_handles_response_with_code_fences(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str
    ):
        """Test that code fences around JSON are stripped."""
        response_with_fences = f"```json\n{mock_valid_writer_response}\n```"
        adapter = MockLLMAdapter(response_with_fences)

        result = run_writer_pass(
            sample_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        assert isinstance(result, DraftNarrative)
        assert len(result.key_drivers) == 3  # Should parse successfully

    def test_writer_pass_includes_context_in_llm_call(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str
    ):
        """Test that LLM context includes all required fields."""
        adapter = MockLLMAdapter(mock_valid_writer_response)

        run_writer_pass(
            sample_analysis_result,
            primary_name="Carrier",
            comparison_name="Contractor",
            llm_adapter=adapter
        )

        _, context = adapter.calls[0]
        assert context["primary_name"] == "Carrier"
        assert context["comparison_name"] == "Contractor"
        assert "category_analyses_json" in context
        assert "scope_gaps_json" in context
        assert context["overall_delta_direction"] == "primary_higher"
        assert context["confidence"] == "high"


# ---------------------------------------------------------------------------
# TestParseWriterResponse
# ---------------------------------------------------------------------------


class TestParseWriterResponse:
    """Tests for _parse_writer_response() helper."""

    def test_parse_valid_response(self, mock_valid_writer_response: str):
        """Test parsing valid JSON response."""
        result = _parse_writer_response(mock_valid_writer_response)

        assert isinstance(result, DraftNarrative)
        assert len(result.key_drivers) == 3
        assert len(result.scope_observations) == 2

    def test_parse_response_with_missing_optional_fields(self):
        """Test parsing response missing optional fields."""
        response = json.dumps({
            "overview": "Test overview",
            "key_drivers": []
        })

        result = _parse_writer_response(response)

        assert result.overview == "Test overview"
        assert result.key_drivers == []
        assert result.scope_observations == []
        assert result.suggested_followups == []

    def test_parse_response_strips_code_fences(self, mock_valid_writer_response: str):
        """Test that code fences are stripped before parsing."""
        response_with_fences = f"```json\n{mock_valid_writer_response}\n```"

        result = _parse_writer_response(response_with_fences)

        assert isinstance(result, DraftNarrative)
        assert len(result.key_drivers) == 3

    def test_parse_response_raises_on_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="JSON parse error"):
            _parse_writer_response("not valid json")

    def test_parse_response_raises_on_non_dict(self):
        """Test that non-dict response raises ValueError."""
        with pytest.raises(ValueError, match="Response not a dict"):
            _parse_writer_response(json.dumps(["array", "not", "dict"]))

    def test_parse_response_handles_malformed_driver(self):
        """Test that malformed driver entries are skipped or defaulted."""
        response = json.dumps({
            "overview": "Test",
            "key_drivers": [
                {"category": "Valid", "amounts": "$100 vs $50", "narrative": "Test"},
                "not a dict",
                {"invalid": "missing required fields"},
            ],
            "scope_observations": [],
            "suggested_followups": []
        })

        result = _parse_writer_response(response)

        # Non-dict entry is skipped, but dict with missing fields gets defaults
        assert len(result.key_drivers) == 2
        assert result.key_drivers[0].category == "Valid"
        assert result.key_drivers[1].category == "Unknown"  # defaulted


# ---------------------------------------------------------------------------
# TestIntegration
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests for analysis to writer flow."""

    def test_analysis_to_writer_flow(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str
    ):
        """Test complete flow from AnalysisResult to DraftNarrative."""
        adapter = MockLLMAdapter(mock_valid_writer_response)

        # Build writer input from analysis
        writer_input = build_writer_input(
            sample_analysis_result,
            primary_name="Carrier Estimate",
            comparison_name="Contractor Estimate"
        )

        # Verify input was built correctly
        assert len(writer_input.category_analyses) == 3
        assert writer_input.overall_delta_direction == "primary_higher"

        # Run writer pass
        result = run_writer_pass(
            sample_analysis_result,
            primary_name="Carrier Estimate",
            comparison_name="Contractor Estimate",
            llm_adapter=adapter
        )

        # Verify output
        assert isinstance(result, DraftNarrative)
        assert len(result.key_drivers) == 3
        assert all(isinstance(d, DriverNarrative) for d in result.key_drivers)

    def test_writer_pass_context_contains_analysis_data(
        self,
        sample_analysis_result: AnalysisResult,
        mock_valid_writer_response: str
    ):
        """Test that LLM context contains serialized analysis data."""
        adapter = MockLLMAdapter(mock_valid_writer_response)

        run_writer_pass(
            sample_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        _, context = adapter.calls[0]

        # Parse the JSON strings in context
        category_analyses = json.loads(context["category_analyses_json"])
        scope_gaps = json.loads(context["scope_gaps_json"])

        assert len(category_analyses) == 3
        assert category_analyses[0]["category"] == "HVAC / Mechanical"
        assert len(scope_gaps) == 2

    def test_fallback_preserves_analysis_content(self, sample_analysis_result: AnalysisResult):
        """Test that fallback narrative preserves content from analysis."""
        adapter = MockLLMAdapter("invalid json")

        result = run_writer_pass(
            sample_analysis_result,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        # Fallback should have created drivers from analysis
        assert len(result.key_drivers) == 3
        assert result.key_drivers[0].category == "HVAC / Mechanical"
        assert "$6,300.00 vs $5,100.00" in result.key_drivers[0].amounts

        # Scope observations should come from analysis
        assert result.scope_observations == sample_analysis_result.scope_gaps
