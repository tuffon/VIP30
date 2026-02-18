"""
Unit tests for the Compliance pass.

Tests cover:
- ComplianceInput model creation and serialization
- build_compliance_input() from DraftNarrative and QualityReport
- run_compliance_pass() with mock LLM responses
- Graceful handling of malformed responses
- Original draft preservation on error
"""

import json
import logging
from typing import Any, Dict, List

import pytest

from vip_shared.pipeline import (
    DraftNarrative,
    DriverNarrative,
    QualityCheckResult,
    QualityReport,
    run_compliance_pass,
    ComplianceInput,
)
from vip_shared.pipeline.passes.compliance import build_compliance_input, _parse_compliance_response


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
def sample_draft_with_hedges() -> DraftNarrative:
    """Sample DraftNarrative with hedge words that would fail GATE-01."""
    return DraftNarrative(
        overview="Primary estimate appears to be higher. The variance seems to suggest scope differences. Flooring may indicate different material choices.",
        key_drivers=[
            DriverNarrative(
                category="HVAC / Mechanical",
                amounts="$6,300 vs $5,100 (delta $1,200)",
                narrative="Primary possibly includes condenser replacement. The variance might be driven by labor rate differences."
            ),
            DriverNarrative(
                category="Flooring",
                amounts="$4,590 vs $3,200 (delta $1,390)",
                narrative="Primary likely uses hardwood while comparison uses LVP. This indicates material cost variance."
            ),
        ],
        scope_observations=["Comparison appears missing demolition allowance"],
        suggested_followups=["Review contractor scope details"],
    )


@pytest.fixture
def sample_draft_clean() -> DraftNarrative:
    """Sample DraftNarrative without quality issues."""
    return DraftNarrative(
        overview="Primary estimate higher by $6,190. HVAC, flooring, and electrical scope differences drive variance.",
        key_drivers=[
            DriverNarrative(
                category="HVAC / Mechanical",
                amounts="$6,300 vs $5,100 (delta $1,200)",
                narrative="Primary includes condenser replacement. Comparison contemplates repair only."
            ),
            DriverNarrative(
                category="Flooring",
                amounts="$4,590 vs $3,200 (delta $1,390)",
                narrative="Primary specifies hardwood. Comparison uses LVP. Delta driven by material selection."
            ),
        ],
        scope_observations=["Comparison missing demolition allowance"],
        suggested_followups=["Request itemized mitigation breakdown"],
    )


@pytest.fixture
def failed_quality_report() -> QualityReport:
    """QualityReport with failed checks."""
    return QualityReport(
        passed=False,
        checks=[
            QualityCheckResult(
                check_name="GATE-01",
                passed=False,
                details="Found 5 hedge words: ['appears', 'seems', 'may', 'possibly', 'might'] (max: 3)"
            ),
            QualityCheckResult(
                check_name="GATE-02",
                passed=True,
                details="Sentences: 2, Avg words: 15.5 (max: 2 sentences, 40 avg words)"
            ),
            QualityCheckResult(
                check_name="GATE-05",
                passed=False,
                details="Found 2 analyst tone phrases: ['seems to suggest', 'may indicate']"
            ),
            QualityCheckResult(
                check_name="GATE-06",
                passed=True,
                details="No GPT-isms found"
            ),
        ],
    )


@pytest.fixture
def passed_quality_report() -> QualityReport:
    """QualityReport with all checks passing."""
    return QualityReport(
        passed=True,
        checks=[
            QualityCheckResult(check_name="GATE-01", passed=True, details="Found 0 hedge words (max: 3)"),
            QualityCheckResult(check_name="GATE-02", passed=True, details="Sentences: 2, Avg words: 15.0"),
            QualityCheckResult(check_name="GATE-03", passed=True, details="Found valuation reference: $6,300"),
            QualityCheckResult(check_name="GATE-04", passed=True, details="2 bullets (max 6), longest: 8 words"),
            QualityCheckResult(check_name="GATE-05", passed=True, details="No analyst tone phrases found"),
            QualityCheckResult(check_name="GATE-06", passed=True, details="No GPT-isms found"),
        ],
    )


@pytest.fixture
def mock_rewritten_response() -> str:
    """Mock LLM response with cleaned narrative."""
    return json.dumps({
        "overview": "Primary estimate higher by $6,190. HVAC, flooring, and electrical scope differences drive variance.",
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
        ],
        "scope_observations": ["Comparison missing demolition allowance"],
        "suggested_followups": ["Request itemized mitigation breakdown"],
    })


# ---------------------------------------------------------------------------
# TestComplianceInput
# ---------------------------------------------------------------------------


class TestComplianceInput:
    """Tests for ComplianceInput model and build_compliance_input()."""

    def test_build_compliance_input_extracts_failed_checks(
        self,
        sample_draft_with_hedges: DraftNarrative,
        failed_quality_report: QualityReport
    ):
        """Test building ComplianceInput extracts failed check details."""
        result = build_compliance_input(
            sample_draft_with_hedges,
            failed_quality_report,
            primary_name="Carrier Estimate",
            comparison_name="Contractor Estimate"
        )

        assert result.primary_name == "Carrier Estimate"
        assert result.comparison_name == "Contractor Estimate"
        assert len(result.failed_checks) == 2  # GATE-01 and GATE-05 failed
        assert "GATE-01" in result.failed_checks[0]
        assert "GATE-05" in result.failed_checks[1]
        assert "hedge words" in result.failed_checks[0]

    def test_compliance_input_serializes_to_json(
        self,
        sample_draft_with_hedges: DraftNarrative
    ):
        """Test that ComplianceInput serializes to JSON cleanly."""
        compliance_input = ComplianceInput(
            draft=sample_draft_with_hedges,
            failed_checks=["GATE-01: Found 5 hedge words", "GATE-05: Found analyst phrases"],
            primary_name="Primary",
            comparison_name="Comparison",
        )

        json_str = compliance_input.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["primary_name"] == "Primary"
        assert len(parsed["failed_checks"]) == 2
        assert "draft" in parsed
        assert "overview" in parsed["draft"]

    def test_compliance_input_handles_empty_failures(
        self,
        sample_draft_clean: DraftNarrative,
        passed_quality_report: QualityReport
    ):
        """Test ComplianceInput with all checks passing (empty failures)."""
        result = build_compliance_input(
            sample_draft_clean,
            passed_quality_report,
            primary_name="Primary",
            comparison_name="Comparison"
        )

        assert result.failed_checks == []
        assert result.draft == sample_draft_clean


# ---------------------------------------------------------------------------
# TestRunCompliancePass
# ---------------------------------------------------------------------------


class TestRunCompliancePass:
    """Tests for run_compliance_pass() function."""

    def test_compliance_pass_returns_rewritten_draft(
        self,
        sample_draft_with_hedges: DraftNarrative,
        failed_quality_report: QualityReport,
        mock_rewritten_response: str
    ):
        """Test that valid LLM response produces rewritten DraftNarrative."""
        adapter = MockLLMAdapter(mock_rewritten_response)

        result = run_compliance_pass(
            sample_draft_with_hedges,
            failed_quality_report,
            primary_name="Carrier Estimate",
            comparison_name="Contractor Estimate",
            llm_adapter=adapter
        )

        assert isinstance(result, DraftNarrative)
        # Rewritten narrative should not have hedge words
        assert "appears" not in result.overview
        assert "seems" not in result.overview
        assert "possibly" not in result.key_drivers[0].narrative

    def test_compliance_pass_handles_malformed_json(
        self,
        sample_draft_with_hedges: DraftNarrative,
        failed_quality_report: QualityReport
    ):
        """Test that malformed JSON returns original draft unchanged."""
        adapter = MockLLMAdapter("this is not json at all { broken ]")

        result = run_compliance_pass(
            sample_draft_with_hedges,
            failed_quality_report,
            primary_name="Carrier",
            comparison_name="Contractor",
            llm_adapter=adapter
        )

        # Should return original draft unchanged
        assert result == sample_draft_with_hedges
        assert "appears" in result.overview

    def test_compliance_pass_preserves_original_on_error(
        self,
        sample_draft_with_hedges: DraftNarrative,
        failed_quality_report: QualityReport
    ):
        """Test that parsing errors preserve original draft."""
        # Response that parses as JSON but is not a dict
        adapter = MockLLMAdapter(json.dumps(["array", "not", "dict"]))

        result = run_compliance_pass(
            sample_draft_with_hedges,
            failed_quality_report,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        assert result == sample_draft_with_hedges

    def test_compliance_pass_logs_failed_checks(
        self,
        sample_draft_with_hedges: DraftNarrative,
        failed_quality_report: QualityReport,
        mock_rewritten_response: str,
        caplog
    ):
        """Test that compliance pass logs failed checks."""
        adapter = MockLLMAdapter(mock_rewritten_response)

        with caplog.at_level(logging.INFO, logger="vip-parse.pipeline.compliance"):
            run_compliance_pass(
                sample_draft_with_hedges,
                failed_quality_report,
                primary_name="Carrier",
                comparison_name="Contractor",
                llm_adapter=adapter
            )

        log_messages = [r.message for r in caplog.records]
        assert any("compliance pass start" in m for m in log_messages)
        assert any("compliance pass complete" in m for m in log_messages)

    def test_compliance_pass_calls_correct_template(
        self,
        sample_draft_with_hedges: DraftNarrative,
        failed_quality_report: QualityReport,
        mock_rewritten_response: str
    ):
        """Test that compliance pass calls the compliance_rewrite_v1 template."""
        adapter = MockLLMAdapter(mock_rewritten_response)

        run_compliance_pass(
            sample_draft_with_hedges,
            failed_quality_report,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        assert len(adapter.calls) == 1
        template_id, context = adapter.calls[0]
        assert template_id == "compliance_rewrite_v1"
        assert "primary_name" in context
        assert "failed_checks" in context
        assert "draft_json" in context

    def test_compliance_pass_handles_response_with_code_fences(
        self,
        sample_draft_with_hedges: DraftNarrative,
        failed_quality_report: QualityReport,
        mock_rewritten_response: str
    ):
        """Test that code fences around JSON are stripped."""
        response_with_fences = f"```json\n{mock_rewritten_response}\n```"
        adapter = MockLLMAdapter(response_with_fences)

        result = run_compliance_pass(
            sample_draft_with_hedges,
            failed_quality_report,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        assert isinstance(result, DraftNarrative)
        assert "appears" not in result.overview  # Should parse successfully

    def test_compliance_pass_includes_failed_checks_in_context(
        self,
        sample_draft_with_hedges: DraftNarrative,
        failed_quality_report: QualityReport,
        mock_rewritten_response: str
    ):
        """Test that LLM context includes formatted failed checks."""
        adapter = MockLLMAdapter(mock_rewritten_response)

        run_compliance_pass(
            sample_draft_with_hedges,
            failed_quality_report,
            primary_name="Primary",
            comparison_name="Comparison",
            llm_adapter=adapter
        )

        _, context = adapter.calls[0]
        failed_checks_str = context["failed_checks"]

        # Should have bullet-formatted failed checks
        assert "GATE-01" in failed_checks_str
        assert "GATE-05" in failed_checks_str
        assert "hedge words" in failed_checks_str


# ---------------------------------------------------------------------------
# TestParseComplianceResponse
# ---------------------------------------------------------------------------


class TestParseComplianceResponse:
    """Tests for _parse_compliance_response() helper."""

    def test_parse_valid_response(self, mock_rewritten_response: str):
        """Test parsing valid JSON response."""
        result = _parse_compliance_response(mock_rewritten_response)

        assert isinstance(result, DraftNarrative)
        assert len(result.key_drivers) == 2
        assert result.key_drivers[0].category == "HVAC / Mechanical"

    def test_parse_response_with_missing_optional_fields(self):
        """Test parsing response missing optional fields."""
        response = json.dumps({
            "overview": "Test overview",
            "key_drivers": []
        })

        result = _parse_compliance_response(response)

        assert result.overview == "Test overview"
        assert result.key_drivers == []
        assert result.scope_observations == []
        assert result.suggested_followups == []

    def test_parse_response_strips_code_fences(self, mock_rewritten_response: str):
        """Test that code fences are stripped before parsing."""
        response_with_fences = f"```json\n{mock_rewritten_response}\n```"

        result = _parse_compliance_response(response_with_fences)

        assert isinstance(result, DraftNarrative)
        assert len(result.key_drivers) == 2

    def test_parse_response_raises_on_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="JSON parse error"):
            _parse_compliance_response("not valid json")

    def test_parse_response_raises_on_non_dict(self):
        """Test that non-dict response raises ValueError."""
        with pytest.raises(ValueError, match="Response not a dict"):
            _parse_compliance_response(json.dumps(["array", "not", "dict"]))

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

        result = _parse_compliance_response(response)

        # Non-dict entry is skipped, but dict with missing fields gets defaults
        assert len(result.key_drivers) == 2
        assert result.key_drivers[0].category == "Valid"
        assert result.key_drivers[1].category == "Unknown"  # defaulted
