"""Unit tests for the current Phase 11 quality gate implementation."""

from vip_shared.methodology.models import GranularityLevel
from vip_shared.pipeline.models import DraftNarrative, DriverNarrative, QualityReport
from vip_shared.pipeline.quality import (
    EvidenceGroundingChecker,
    HedgingChecker,
    JudgmentLanguageChecker,
    MethodologyNeutralityChecker,
    QuantificationChecker,
    QualityEvaluator,
)


class TestHedgingChecker:
    def setup_method(self):
        self.checker = HedgingChecker()

    def test_check_name(self):
        assert self.checker.check_name == "GATE-01"

    def test_passes_without_hedge_or_slop_terms(self):
        result = self.checker.check("Delta is $4,000 (10%) in roofing scope.")
        assert result.passed is True
        assert "No hedge/slop terms found" in result.details

    def test_fails_when_terms_present(self):
        result = self.checker.check("It appears this may change and is comprehensive.")
        assert result.passed is False
        assert "appears" in result.details
        assert "may" in result.details
        assert "comprehensive" in result.details

    def test_honors_max_violations(self):
        text = "It appears this may change."
        assert self.checker.check(text, max_violations=2).passed is True
        assert self.checker.check(text, max_violations=1).passed is False


class TestJudgmentLanguageChecker:
    def setup_method(self):
        self.checker = JudgmentLanguageChecker()

    def test_check_name(self):
        assert self.checker.check_name == "GATE-02"

    def test_passes_without_judgment_language(self):
        result = self.checker.check("Primary total is $12,000 and comparison total is $9,000.")
        assert result.passed is True
        assert "No judgment language found" in result.details

    def test_fails_with_judgment_terms_and_phrases(self):
        result = self.checker.check("This is excessive and clearly overstates the true cost.")
        assert result.passed is False
        assert "excessive" in result.details
        assert "clearly overstates" in result.details


class TestQuantificationChecker:
    def setup_method(self):
        self.checker = QuantificationChecker()

    def test_check_name(self):
        assert self.checker.check_name == "GATE-03"

    def test_passes_when_delta_sentence_has_dollar_and_percent(self):
        result = self.checker.check("The delta is $2,500 (8%).")
        assert result.passed is True
        assert "All delta references quantified" in result.details

    def test_fails_when_delta_missing_percent(self):
        result = self.checker.check("The variance is $2,500.")
        assert result.passed is False
        assert "Missing percentage" in result.details

    def test_fails_when_delta_missing_dollar_amount(self):
        result = self.checker.check("The difference is 8%.")
        assert result.passed is False
        assert "Missing dollar amount" in result.details

    def test_ignores_sentences_without_delta_reference(self):
        result = self.checker.check("Material count changed across both estimates.")
        assert result.passed is True


class TestEvidenceGroundingChecker:
    def setup_method(self):
        self.checker = EvidenceGroundingChecker()

    def test_check_name(self):
        assert self.checker.check_name == "GATE-04"

    def test_line_item_granularity_allows_line_item_references(self):
        text = "3 units windows at $450 each are included."
        result = self.checker.check(text, GranularityLevel.LINE_ITEM)
        assert result.passed is True
        assert "LINE_ITEM granularity permits line-item references" in result.details

    def test_category_granularity_blocks_line_item_references(self):
        text = "3 units windows at $450 each are included."
        result = self.checker.check(text, GranularityLevel.CATEGORY)
        assert result.passed is False
        assert "Found line-item references not allowed" in result.details

    def test_category_granularity_passes_without_line_item_references(self):
        text = "Flooring category delta is $4,200 (11%)."
        result = self.checker.check(text, GranularityLevel.CATEGORY)
        assert result.passed is True


class TestMethodologyNeutralityChecker:
    def setup_method(self):
        self.checker = MethodologyNeutralityChecker()

    def test_check_name(self):
        assert self.checker.check_name == "GATE-05"

    def test_passes_without_comparative_methodology_language(self):
        result = self.checker.check("Both estimates were reviewed for variance categories.")
        assert result.passed is True
        assert "No methodology comparison language found" in result.details

    def test_fails_with_prohibited_methodology_language(self):
        result = self.checker.check("This is a better and recommended approach.")
        assert result.passed is False
        assert "better" in result.details
        assert "recommended" in result.details


class TestQualityEvaluator:
    def setup_method(self):
        self.evaluator = QualityEvaluator()

    def _baseline_draft(self) -> DraftNarrative:
        return DraftNarrative(
            overview="Total delta is $10,000 (12%).",
            key_drivers=[
                DriverNarrative(
                    category="Flooring",
                    amounts="$18,000 vs $12,000",
                    narrative="Flooring delta is $6,000 (15%) from material pricing.",
                )
            ],
            scope_observations=["Scope notes are provided by category only."],
            suggested_followups=[],
        )

    def test_evaluator_runs_core_checks_by_default(self):
        report = self.evaluator.evaluate(self._baseline_draft())
        assert isinstance(report, QualityReport)
        assert report.passed is True
        assert len(report.checks) == 3
        assert {c.check_name for c in report.checks} == {"GATE-01", "GATE-02", "GATE-03"}

    def test_evaluator_adds_evidence_and_methodology_checks_when_inputs_provided(self):
        report = self.evaluator.evaluate(
            self._baseline_draft(),
            data_granularity=GranularityLevel.CATEGORY,
            methodology_text="Methodology summary without comparative standards.",
        )
        assert len(report.checks) == 5
        assert {c.check_name for c in report.checks} == {
            "GATE-01",
            "GATE-02",
            "GATE-03",
            "GATE-04",
            "GATE-05",
        }

    def test_evaluator_fails_for_hedging_language(self):
        draft = self._baseline_draft()
        draft.overview = "It appears the delta is $10,000 (12%)."
        report = self.evaluator.evaluate(draft)
        assert report.passed is False
        assert "GATE-01" in report.failed_checks

    def test_evaluator_fails_for_missing_delta_percentage(self):
        draft = self._baseline_draft()
        draft.overview = "Total delta is $10,000."
        draft.key_drivers[0].narrative = "Flooring delta is $6,000 from material pricing."
        report = self.evaluator.evaluate(draft)
        assert report.passed is False
        assert "GATE-03" in report.failed_checks

    def test_evaluator_fails_for_non_neutral_methodology_when_checked(self):
        report = self.evaluator.evaluate(
            self._baseline_draft(),
            methodology_text="This is the best and industry standard methodology.",
        )
        assert report.passed is False
        assert "GATE-05" in report.failed_checks


class TestImports:
    def test_import_from_pipeline(self):
        from vip_shared.pipeline import (
            EvidenceGroundingChecker,
            HedgingChecker,
            JudgmentLanguageChecker,
            MethodologyNeutralityChecker,
            QuantificationChecker,
            QualityEvaluator,
        )

        assert hasattr(HedgingChecker, "check")
        assert hasattr(JudgmentLanguageChecker, "check")
        assert hasattr(QuantificationChecker, "check")
        assert hasattr(EvidenceGroundingChecker, "check")
        assert hasattr(MethodologyNeutralityChecker, "check")
        assert hasattr(QualityEvaluator, "evaluate")
