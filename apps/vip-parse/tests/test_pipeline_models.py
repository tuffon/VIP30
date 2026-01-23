"""
Unit tests for pipeline data contract models.

Tests cover:
- Valid model creation
- Validation errors for invalid data
- JSON serialization round-trips
- PipelineState helper methods
"""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.pipeline import (
    AnalysisResult,
    CategoryAnalysis,
    DraftNarrative,
    DriverNarrative,
    FinalNarrative,
    PipelineState,
    QualityCheckResult,
    QualityReport,
)


class TestCategoryAnalysis:
    """Tests for CategoryAnalysis model."""

    def test_valid_creation(self):
        """Test creating a valid CategoryAnalysis."""
        analysis = CategoryAnalysis(
            category="Flooring",
            primary_total=15000.0,
            comparison_total=12000.0,
            delta=3000.0,
            delta_drivers=["3 additional rooms at $1000/room"],
            line_item_evidence=["Master bedroom hardwood", "Living room LVP"],
        )

        assert analysis.category == "Flooring"
        assert analysis.primary_total == 15000.0
        assert analysis.delta == 3000.0
        assert len(analysis.delta_drivers) == 1
        assert len(analysis.line_item_evidence) == 2

    def test_defaults_for_optional_lists(self):
        """Test that list fields default to empty lists."""
        analysis = CategoryAnalysis(
            category="HVAC",
            primary_total=5000.0,
            comparison_total=4500.0,
            delta=500.0,
        )

        assert analysis.delta_drivers == []
        assert analysis.line_item_evidence == []


class TestAnalysisResult:
    """Tests for AnalysisResult model."""

    def test_valid_creation_with_nested_category_analysis(self):
        """Test creating AnalysisResult with nested CategoryAnalysis list."""
        cat_analysis = CategoryAnalysis(
            category="Electrical",
            primary_total=8000.0,
            comparison_total=6000.0,
            delta=2000.0,
            delta_drivers=["Additional outlets"],
        )

        result = AnalysisResult(
            category_analyses=[cat_analysis],
            scope_gaps=["Missing HVAC allowance"],
            overall_delta_direction="primary_higher",
            confidence="high",
        )

        assert len(result.category_analyses) == 1
        assert result.category_analyses[0].category == "Electrical"
        assert result.overall_delta_direction == "primary_higher"
        assert result.confidence == "high"

    def test_invalid_confidence_rejected(self):
        """Test that invalid confidence value raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisResult(
                category_analyses=[],
                scope_gaps=[],
                overall_delta_direction="primary_higher",
                confidence="invalid_value",  # Must be high/medium/low
            )

        assert "confidence" in str(exc_info.value)

    def test_invalid_delta_direction_rejected(self):
        """Test that invalid overall_delta_direction raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisResult(
                category_analyses=[],
                scope_gaps=[],
                overall_delta_direction="invalid_direction",  # Must be one of literals
                confidence="high",
            )

        assert "overall_delta_direction" in str(exc_info.value)

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            AnalysisResult()  # Missing overall_delta_direction and confidence


class TestDriverNarrative:
    """Tests for DriverNarrative model."""

    def test_valid_creation(self):
        """Test creating a valid DriverNarrative."""
        driver = DriverNarrative(
            category="Roofing",
            amounts="$12,500 vs $8,200",
            narrative="Delta driven by upgraded shingle materials and additional flashing.",
        )

        assert driver.category == "Roofing"
        assert "$12,500" in driver.amounts
        assert "Delta driven by" in driver.narrative


class TestDraftNarrative:
    """Tests for DraftNarrative model."""

    def test_valid_creation_with_nested_driver_narrative(self):
        """Test creating DraftNarrative with nested DriverNarrative list."""
        driver = DriverNarrative(
            category="Plumbing",
            amounts="$5,000 vs $3,500",
            narrative="Additional fixture replacements included.",
        )

        draft = DraftNarrative(
            overview="The primary estimate is $15,000 higher overall.",
            key_drivers=[driver],
            scope_observations=["Primary includes water heater replacement"],
            suggested_followups=["Confirm fixture specifications"],
        )

        assert "primary estimate" in draft.overview.lower()
        assert len(draft.key_drivers) == 1
        assert draft.key_drivers[0].category == "Plumbing"

    def test_defaults_for_optional_lists(self):
        """Test that list fields default to empty lists."""
        draft = DraftNarrative(overview="Summary text.")

        assert draft.key_drivers == []
        assert draft.scope_observations == []
        assert draft.suggested_followups == []


class TestQualityReport:
    """Tests for QualityReport model."""

    def test_passed_scenario(self):
        """Test QualityReport with all checks passed."""
        checks = [
            QualityCheckResult(check_name="hedging", passed=True, details="0 hedge words"),
            QualityCheckResult(check_name="verbosity", passed=True, details="Under limit"),
        ]

        report = QualityReport(passed=True, checks=checks)

        assert report.passed is True
        assert len(report.checks) == 2
        assert report.failed_checks == []

    def test_failed_scenario(self):
        """Test QualityReport with some checks failed."""
        checks = [
            QualityCheckResult(check_name="hedging", passed=False, details="5 hedge words (max: 3)"),
            QualityCheckResult(check_name="verbosity", passed=True, details="Under limit"),
            QualityCheckResult(check_name="analyst_tone", passed=False, details="Found 'it appears'"),
        ]

        report = QualityReport(passed=False, checks=checks)

        assert report.passed is False
        assert len(report.failed_checks) == 2
        assert "hedging" in report.failed_checks
        assert "analyst_tone" in report.failed_checks

    def test_checked_at_default(self):
        """Test that checked_at defaults to current time."""
        before = datetime.now(timezone.utc)
        report = QualityReport(passed=True, checks=[])
        after = datetime.now(timezone.utc)

        assert before <= report.checked_at <= after


class TestFinalNarrative:
    """Tests for FinalNarrative model (inherits from DraftNarrative)."""

    def test_inherits_draft_fields(self):
        """Test that FinalNarrative inherits all DraftNarrative fields."""
        driver = DriverNarrative(
            category="Painting",
            amounts="$3,000 vs $2,500",
            narrative="Higher quality paint specified.",
        )

        quality_report = QualityReport(passed=True, checks=[])

        final = FinalNarrative(
            overview="Both estimates are comparable.",
            key_drivers=[driver],
            scope_observations=["Similar scope"],
            suggested_followups=[],
            quality_report=quality_report,
            rewrites_performed=0,
        )

        # DraftNarrative fields
        assert final.overview == "Both estimates are comparable."
        assert len(final.key_drivers) == 1

        # FinalNarrative-specific fields
        assert final.quality_report.passed is True
        assert final.rewrites_performed == 0

    def test_rewrites_performed_default(self):
        """Test rewrites_performed defaults to 0."""
        quality_report = QualityReport(passed=True, checks=[])

        final = FinalNarrative(
            overview="Summary.",
            quality_report=quality_report,
        )

        assert final.rewrites_performed == 0


class TestSerialization:
    """Tests for JSON serialization."""

    def test_model_dump_produces_dict(self):
        """Test that model_dump() produces a valid dict."""
        analysis = CategoryAnalysis(
            category="Drywall",
            primary_total=4000.0,
            comparison_total=3500.0,
            delta=500.0,
        )

        dumped = analysis.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["category"] == "Drywall"
        assert dumped["delta"] == 500.0

    def test_model_dump_json_produces_string(self):
        """Test that model_dump_json() produces valid JSON string."""
        driver = DriverNarrative(
            category="Windows",
            amounts="$8,000 vs $6,500",
            narrative="Premium window upgrade.",
        )

        json_str = driver.model_dump_json()

        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["category"] == "Windows"

    def test_round_trip_preserves_data(self):
        """Test that model -> JSON -> model preserves all data."""
        original = AnalysisResult(
            category_analyses=[
                CategoryAnalysis(
                    category="Flooring",
                    primary_total=10000.0,
                    comparison_total=8000.0,
                    delta=2000.0,
                    delta_drivers=["LVP vs carpet"],
                    line_item_evidence=["Living room", "Bedroom 1"],
                )
            ],
            scope_gaps=["Missing tile"],
            overall_delta_direction="primary_higher",
            confidence="medium",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        restored = AnalysisResult.model_validate_json(json_str)

        assert restored.category_analyses[0].category == original.category_analyses[0].category
        assert restored.category_analyses[0].delta == original.category_analyses[0].delta
        assert restored.scope_gaps == original.scope_gaps
        assert restored.overall_delta_direction == original.overall_delta_direction
        assert restored.confidence == original.confidence

    def test_quality_report_round_trip_with_datetime(self):
        """Test QualityReport serialization handles datetime correctly."""
        original = QualityReport(
            passed=False,
            checks=[
                QualityCheckResult(check_name="hedging", passed=False, details="Too many")
            ],
        )

        json_str = original.model_dump_json()
        restored = QualityReport.model_validate_json(json_str)

        assert restored.passed == original.passed
        assert len(restored.checks) == 1
        assert restored.failed_checks == ["hedging"]


class TestPipelineState:
    """Tests for PipelineState container."""

    def test_is_complete_false_when_final_none(self):
        """Test is_complete() returns False when final is None."""
        state = PipelineState()

        assert state.is_complete() is False

    def test_is_complete_true_when_final_set(self):
        """Test is_complete() returns True when final is set."""
        draft = DraftNarrative(overview="Complete narrative.")
        state = PipelineState(final=draft)

        assert state.is_complete() is True

    def test_quality_passed_false_when_no_report(self):
        """Test quality_passed() returns False when quality_report is None."""
        state = PipelineState()

        assert state.quality_passed() is False

    def test_quality_passed_reflects_report(self):
        """Test quality_passed() returns quality_report.passed value."""
        passing_report = QualityReport(passed=True, checks=[])
        failing_report = QualityReport(passed=False, checks=[])

        state_pass = PipelineState(quality_report=passing_report)
        state_fail = PipelineState(quality_report=failing_report)

        assert state_pass.quality_passed() is True
        assert state_fail.quality_passed() is False

    def test_add_timing_records_correctly(self):
        """Test add_timing() records pass timing."""
        state = PipelineState()

        state.add_timing("analysis", 150)
        state.add_timing("writer", 100)

        assert state.pass_timings_ms["analysis"] == 150
        assert state.pass_timings_ms["writer"] == 100

    def test_mark_pass_executed_appends(self):
        """Test mark_pass_executed() appends to list."""
        state = PipelineState()

        state.mark_pass_executed("analysis")
        state.mark_pass_executed("writer")
        state.mark_pass_executed("compliance_skipped")

        assert state.passes_executed == ["analysis", "writer", "compliance_skipped"]

    def test_state_with_all_pass_outputs(self):
        """Test PipelineState holding all pipeline outputs."""
        analysis = AnalysisResult(
            category_analyses=[],
            scope_gaps=[],
            overall_delta_direction="similar",
            confidence="high",
        )
        draft = DraftNarrative(overview="Draft summary.")
        quality_report = QualityReport(passed=True, checks=[])
        final = FinalNarrative(
            overview="Final summary.",
            quality_report=quality_report,
        )

        state = PipelineState(
            pair={"name": "test_pair"},
            top_deltas=[{"category": "Flooring", "delta": 1000}],
            analysis=analysis,
            draft=draft,
            final=final,
            quality_report=quality_report,
        )

        state.mark_pass_executed("analysis")
        state.mark_pass_executed("writer")
        state.mark_pass_executed("compliance_skipped")
        state.add_timing("analysis", 200)
        state.add_timing("writer", 150)

        assert state.is_complete() is True
        assert state.quality_passed() is True
        assert len(state.passes_executed) == 3
        assert state.pass_timings_ms["analysis"] == 200
