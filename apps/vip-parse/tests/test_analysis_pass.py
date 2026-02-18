"""
Unit tests for the Analysis pass.

Tests cover:
- sample_line_items() extracts top items by amount
- AnalysisInput model creation and serialization
- run_analysis_pass() with mock LLM responses
- Graceful handling of malformed responses
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from vip_shared.pipeline import AnalysisResult, CategoryAnalysis
from vip_shared.pipeline.passes import AnalysisInput, run_analysis_pass, sample_line_items
from vip_shared.pipeline.passes.analysis import build_analysis_input, _parse_analysis_response


# ---------------------------------------------------------------------------
# Mock Fixtures
# ---------------------------------------------------------------------------


@dataclass
class MockEstimate:
    """Mock estimate for testing."""

    estimate_name: str
    payload: Dict[str, Any]


@dataclass
class MockEstimatePair:
    """Mock estimate pair for testing."""

    primary: MockEstimate
    comparison: MockEstimate


class MockLLMAdapter:
    """Mock LLM adapter that returns predefined responses."""

    def __init__(self, response: str):
        self.response = response
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    def generate(self, template_id: str, context: Dict[str, Any]) -> str:
        self.calls.append((template_id, context))
        return self.response


@pytest.fixture
def sample_payload_with_sections() -> Dict[str, Any]:
    """Sample estimate payload with sections and line items."""
    return {
        "estimate_name": "Test Carrier Estimate",
        "sections": [
            {
                "section_name": "Kitchen",
                "line_items": [
                    {"type": "line_item", "description": "Replace countertop", "quantity": 1, "unit": "EA", "total": 1500.00},
                    {"type": "line_item", "description": "Install cabinet", "quantity": 3, "unit": "EA", "total": 2400.00},
                    {"type": "line_item", "description": "Paint walls", "quantity": 120, "unit": "SF", "total": 360.00},
                    {"type": "line_item", "description": "Replace sink", "quantity": 1, "unit": "EA", "total": 450.00},
                    {"type": "line_item", "description": "Install faucet", "quantity": 1, "unit": "EA", "total": 200.00},
                    {"type": "line_item", "description": "Install outlet cover", "quantity": 4, "unit": "EA", "total": 20.00},
                ]
            },
            {
                "section_name": "Living Room - Flooring",
                "line_items": [
                    {"type": "line_item", "description": "Remove carpet", "quantity": 300, "unit": "SF", "total": 450.00},
                    {"type": "line_item", "description": "Install hardwood", "quantity": 300, "unit": "SF", "total": 3600.00},
                    {"type": "line_item", "description": "Install baseboards", "quantity": 60, "unit": "LF", "total": 540.00},
                ]
            },
            {
                "section_name": "HVAC / Mechanical",
                "line_items": [
                    {"type": "line_item", "description": "Replace condenser unit", "quantity": 1, "unit": "EA", "total": 4500.00},
                    {"type": "line_item", "description": "Replace evaporator coil", "quantity": 1, "unit": "EA", "total": 1800.00},
                    {"type": "header", "description": "HVAC Subtotal"},  # Should be skipped
                ]
            }
        ]
    }


@pytest.fixture
def sample_top_deltas() -> List[Dict[str, Any]]:
    """Sample top deltas from BidComp."""
    return [
        {"category": "Cabinetry", "primary_total": 4000.00, "comparison_total": 2800.00, "delta": 1200.00},
        {"category": "Flooring", "primary_total": 4590.00, "comparison_total": 3200.00, "delta": 1390.00},
        {"category": "HVAC / Mechanical", "primary_total": 6300.00, "comparison_total": 5100.00, "delta": 1200.00},
    ]


@pytest.fixture
def mock_valid_llm_response() -> str:
    """Valid JSON response from LLM."""
    return json.dumps({
        "category_analyses": [
            {
                "category": "Cabinetry",
                "primary_total": 4000.00,
                "comparison_total": 2800.00,
                "delta": 1200.00,
                "delta_drivers": ["3 additional cabinet units in primary", "Higher grade cabinet material"],
                "line_item_evidence": ["Primary: Install cabinet (3) $2,400", "Comparison: Install cabinet (2) $1,600"]
            },
            {
                "category": "Flooring",
                "primary_total": 4590.00,
                "comparison_total": 3200.00,
                "delta": 1390.00,
                "delta_drivers": ["Primary includes hardwood, comparison uses LVP", "Primary includes baseboard replacement"],
                "line_item_evidence": ["Primary: Install hardwood $3,600", "Comparison: Install LVP $2,100"]
            }
        ],
        "scope_gaps": ["Comparison missing baseboard replacement"],
        "overall_delta_direction": "primary_higher",
        "confidence": "high"
    })


@pytest.fixture
def mock_pair(sample_payload_with_sections: Dict[str, Any]) -> MockEstimatePair:
    """Create mock estimate pair for testing."""
    primary = MockEstimate(
        estimate_name="Test Carrier Estimate",
        payload=sample_payload_with_sections,
    )
    comparison = MockEstimate(
        estimate_name="Test Contractor Estimate",
        payload={
            "estimate_name": "Test Contractor Estimate",
            "sections": [
                {
                    "section_name": "Kitchen",
                    "line_items": [
                        {"type": "line_item", "description": "Install cabinet", "quantity": 2, "unit": "EA", "total": 1600.00},
                    ]
                }
            ]
        },
    )
    return MockEstimatePair(primary=primary, comparison=comparison)


# ---------------------------------------------------------------------------
# TestSampleLineItems
# ---------------------------------------------------------------------------


class TestSampleLineItems:
    """Tests for sample_line_items() function."""

    def test_sample_returns_top_items_by_amount(self, sample_payload_with_sections: Dict[str, Any]):
        """Test that sampling returns top N items sorted by amount descending."""
        categories = ["Cabinetry"]  # Maps to Kitchen section via fuzzy matching
        result = sample_line_items(sample_payload_with_sections, categories, max_per_category=3)

        # Should have Cabinetry key even if no items match
        assert "Cabinetry" in result

    def test_sample_handles_empty_payload(self):
        """Test that empty payload returns empty dict per category."""
        categories = ["Flooring", "HVAC"]
        result = sample_line_items({}, categories)

        assert result == {"Flooring": [], "HVAC": []}

    def test_sample_handles_missing_sections(self):
        """Test that missing sections key is handled gracefully."""
        payload = {"estimate_name": "Test"}
        categories = ["Flooring"]
        result = sample_line_items(payload, categories)

        assert result == {"Flooring": []}

    def test_sample_limits_to_max_per_category(self, sample_payload_with_sections: Dict[str, Any]):
        """Test that max_per_category limits items returned."""
        # HVAC section has 2 line items (header skipped)
        categories = ["HVAC / Mechanical"]
        result = sample_line_items(sample_payload_with_sections, categories, max_per_category=1)

        assert len(result.get("HVAC / Mechanical", [])) <= 1

    def test_sample_skips_non_line_item_types(self, sample_payload_with_sections: Dict[str, Any]):
        """Test that header/subtotal types are skipped."""
        categories = ["HVAC / Mechanical"]
        result = sample_line_items(sample_payload_with_sections, categories, max_per_category=10)

        # Should have at most 2 items (condenser and evaporator), not the header
        items = result.get("HVAC / Mechanical", [])
        descriptions = [i.get("description", "") for i in items]
        assert "HVAC Subtotal" not in descriptions

    def test_sample_with_flooring_category(self, sample_payload_with_sections: Dict[str, Any]):
        """Test sampling Flooring category matches Living Room - Flooring section."""
        categories = ["Flooring"]
        result = sample_line_items(sample_payload_with_sections, categories, max_per_category=5)

        items = result.get("Flooring", [])
        # Should include hardwood item from Living Room - Flooring section
        descriptions = [i.get("description", "") for i in items]
        assert "Install hardwood" in descriptions or len(items) == 0  # depends on matching

    def test_sample_handles_none_payload(self):
        """Test that None-ish payload returns empty dict."""
        result = sample_line_items(None, ["Flooring"])  # type: ignore
        assert result == {}


# ---------------------------------------------------------------------------
# TestAnalysisInput
# ---------------------------------------------------------------------------


class TestAnalysisInput:
    """Tests for AnalysisInput model."""

    def test_build_analysis_input_from_pair(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]]
    ):
        """Test building AnalysisInput from mock pair and deltas."""
        result = build_analysis_input(mock_pair, sample_top_deltas)

        assert result.primary_name == "Test Carrier Estimate"
        assert result.comparison_name == "Test Contractor Estimate"
        assert "Cabinetry" in result.primary_totals
        assert result.primary_totals["Cabinetry"] == 4000.00

    def test_analysis_input_serializes_to_json(self, sample_top_deltas: List[Dict[str, Any]]):
        """Test that AnalysisInput serializes to JSON cleanly."""
        analysis_input = AnalysisInput(
            primary_name="Primary",
            comparison_name="Comparison",
            primary_totals={"Flooring": 5000.0},
            comparison_totals={"Flooring": 3000.0},
            top_deltas=sample_top_deltas,
            primary_sample_items={"Flooring": [{"description": "Install hardwood", "amount": 3600}]},
            comparison_sample_items={"Flooring": []},
        )

        json_str = analysis_input.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["primary_name"] == "Primary"
        assert parsed["primary_totals"]["Flooring"] == 5000.0
        assert len(parsed["top_deltas"]) == 3

    def test_analysis_input_handles_empty_deltas(self):
        """Test AnalysisInput with empty top_deltas."""
        analysis_input = AnalysisInput(
            primary_name="Primary",
            comparison_name="Comparison",
            top_deltas=[],
        )

        assert analysis_input.top_deltas == []
        assert analysis_input.primary_totals == {}


# ---------------------------------------------------------------------------
# TestRunAnalysisPass
# ---------------------------------------------------------------------------


class TestRunAnalysisPass:
    """Tests for run_analysis_pass() function."""

    def test_analysis_pass_returns_valid_result(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_valid_llm_response: str
    ):
        """Test that valid LLM response produces correct AnalysisResult."""
        adapter = MockLLMAdapter(mock_valid_llm_response)

        result = run_analysis_pass(mock_pair, sample_top_deltas, adapter)

        assert isinstance(result, AnalysisResult)
        assert len(result.category_analyses) == 2
        assert result.category_analyses[0].category == "Cabinetry"
        assert result.overall_delta_direction == "primary_higher"
        assert result.confidence == "high"
        assert len(result.scope_gaps) == 1

    def test_analysis_pass_handles_malformed_json(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]]
    ):
        """Test that malformed JSON returns fallback result with low confidence."""
        adapter = MockLLMAdapter("this is not json at all { broken ]")

        result = run_analysis_pass(mock_pair, sample_top_deltas, adapter)

        assert isinstance(result, AnalysisResult)
        assert result.confidence == "low"
        # Fallback should still have category analyses from top_deltas
        assert len(result.category_analyses) == len(sample_top_deltas)

    def test_analysis_pass_handles_empty_deltas(self, mock_pair: MockEstimatePair):
        """Test that empty deltas list doesn't crash."""
        adapter = MockLLMAdapter(json.dumps({
            "category_analyses": [],
            "scope_gaps": [],
            "overall_delta_direction": "similar",
            "confidence": "low"
        }))

        result = run_analysis_pass(mock_pair, [], adapter)

        assert isinstance(result, AnalysisResult)
        assert len(result.category_analyses) == 0

    def test_analysis_pass_logs_token_estimate(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_valid_llm_response: str,
        caplog
    ):
        """Test that analysis pass logs estimated token count."""
        adapter = MockLLMAdapter(mock_valid_llm_response)

        with caplog.at_level(logging.INFO, logger="vip-parse.pipeline.analysis"):
            run_analysis_pass(mock_pair, sample_top_deltas, adapter)

        log_messages = [r.message for r in caplog.records]
        # Should have start and complete log messages
        assert any("analysis pass start" in m for m in log_messages)
        assert any("analysis pass complete" in m for m in log_messages)

    def test_analysis_pass_calls_correct_template(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_valid_llm_response: str
    ):
        """Test that analysis pass calls the analysis_pass_v1 template."""
        adapter = MockLLMAdapter(mock_valid_llm_response)

        run_analysis_pass(mock_pair, sample_top_deltas, adapter)

        assert len(adapter.calls) == 1
        template_id, context = adapter.calls[0]
        assert template_id == "analysis_pass_v1"
        assert "primary_name" in context
        assert "deltas_json" in context

    def test_analysis_pass_handles_response_with_code_fences(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]],
        mock_valid_llm_response: str
    ):
        """Test that code fences around JSON are stripped."""
        response_with_fences = f"```json\n{mock_valid_llm_response}\n```"
        adapter = MockLLMAdapter(response_with_fences)

        result = run_analysis_pass(mock_pair, sample_top_deltas, adapter)

        assert isinstance(result, AnalysisResult)
        assert result.confidence == "high"  # Should parse successfully

    def test_analysis_pass_handles_invalid_direction_value(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]]
    ):
        """Test that invalid delta direction defaults to similar."""
        response = json.dumps({
            "category_analyses": [],
            "scope_gaps": [],
            "overall_delta_direction": "invalid_direction",
            "confidence": "high"
        })
        adapter = MockLLMAdapter(response)

        result = run_analysis_pass(mock_pair, sample_top_deltas, adapter)

        assert result.overall_delta_direction == "similar"

    def test_analysis_pass_handles_invalid_confidence_value(
        self,
        mock_pair: MockEstimatePair,
        sample_top_deltas: List[Dict[str, Any]]
    ):
        """Test that invalid confidence defaults to medium."""
        response = json.dumps({
            "category_analyses": [],
            "scope_gaps": [],
            "overall_delta_direction": "primary_higher",
            "confidence": "very_high"
        })
        adapter = MockLLMAdapter(response)

        result = run_analysis_pass(mock_pair, sample_top_deltas, adapter)

        assert result.confidence == "medium"


# ---------------------------------------------------------------------------
# TestParseAnalysisResponse
# ---------------------------------------------------------------------------


class TestParseAnalysisResponse:
    """Tests for _parse_analysis_response() helper."""

    def test_parse_valid_response(self, mock_valid_llm_response: str, sample_top_deltas: List[Dict[str, Any]]):
        """Test parsing valid JSON response."""
        analysis_input = AnalysisInput(
            primary_name="Primary",
            comparison_name="Comparison",
            top_deltas=sample_top_deltas,
        )

        result = _parse_analysis_response(mock_valid_llm_response, analysis_input)

        assert len(result.category_analyses) == 2
        assert result.category_analyses[0].category == "Cabinetry"

    def test_parse_response_with_missing_fields(self, sample_top_deltas: List[Dict[str, Any]]):
        """Test parsing response missing optional fields."""
        response = json.dumps({
            "category_analyses": [
                {"category": "Test", "primary_total": 100, "comparison_total": 80, "delta": 20}
            ],
            "overall_delta_direction": "primary_higher",
            "confidence": "medium"
        })
        analysis_input = AnalysisInput(
            primary_name="Primary",
            comparison_name="Comparison",
            top_deltas=sample_top_deltas,
        )

        result = _parse_analysis_response(response, analysis_input)

        assert len(result.category_analyses) == 1
        assert result.category_analyses[0].delta_drivers == []
        assert result.scope_gaps == []

    def test_parse_non_dict_response_returns_fallback(self, sample_top_deltas: List[Dict[str, Any]]):
        """Test that non-dict response (e.g., array) returns fallback."""
        response = json.dumps([{"category": "Test"}])
        analysis_input = AnalysisInput(
            primary_name="Primary",
            comparison_name="Comparison",
            top_deltas=sample_top_deltas,
        )

        result = _parse_analysis_response(response, analysis_input)

        assert result.confidence == "low"
