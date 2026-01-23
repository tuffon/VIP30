"""
Unit tests for deterministic quality gate checkers.

Tests cover:
- HedgingChecker (GATE-01): Hedge word detection
- VerbosityChecker (GATE-02): Sentence count and word average
- ValuationLinkChecker (GATE-03): Dollar amounts and delta references
- SummaryLengthChecker (GATE-04): Bullet count and word limits
- AnalystToneChecker (GATE-05): Analyst hedging phrase detection
- SlopChecker (GATE-06): GPT-ism detection
- QualityEvaluator: Integration of all gates
"""

import pytest

from src.pipeline import (
    DraftNarrative,
    DriverNarrative,
    QualityReport,
)
from src.pipeline.quality import (
    AnalystToneChecker,
    HedgingChecker,
    QualityEvaluator,
    SlopChecker,
    SummaryLengthChecker,
    ValuationLinkChecker,
    VerbosityChecker,
)


# ==============================================================================
# HedgingChecker Tests (GATE-01)
# ==============================================================================

class TestHedgingChecker:
    """Tests for HedgingChecker (GATE-01)."""

    def setup_method(self):
        """Set up checker instance for each test."""
        self.checker = HedgingChecker()

    def test_check_name_is_gate_01(self):
        """Verify check_name property returns correct gate ID."""
        assert self.checker.check_name == "GATE-01"

    def test_hedging_passes_with_no_hedges(self):
        """Text with no hedge words should pass."""
        text = "The estimate shows a clear difference of $5,000 in flooring costs."
        result = self.checker.check(text)
        assert result.passed is True
        assert "Found 0 hedge words" in result.details

    def test_hedging_passes_at_threshold(self):
        """Text with exactly 3 hedge words (threshold) should pass."""
        text = "It appears the estimate may show what could be a difference."
        result = self.checker.check(text, max_hedges=3)
        assert result.passed is True
        assert "Found 3 hedge words" in result.details

    def test_hedging_fails_over_threshold(self):
        """Text with more than 3 hedge words should fail."""
        text = (
            "It appears this might potentially suggest what could possibly "
            "be an issue that seems problematic."
        )
        result = self.checker.check(text, max_hedges=3)
        assert result.passed is False
        assert int(result.details.split()[1]) > 3  # Found N > 3

    def test_hedging_case_insensitive(self):
        """Hedge detection should be case-insensitive."""
        text = "APPEARS to be an issue. Seems LIKELY that it Might fail."
        result = self.checker.check(text)
        assert result.passed is False  # 4 hedges: appears, seems, likely, might

    def test_hedging_whole_word_match(self):
        """Should not match hedge words within larger words."""
        text = "Display the mayonnaise container that could be outdated."
        result = self.checker.check(text)
        # "display" should not match "may", "mayonnaise" should not match "may"
        # Only "could" should be found
        assert result.passed is True
        assert "Found 1 hedge words" in result.details

    def test_hedging_custom_threshold(self):
        """Custom max_hedges threshold should work."""
        text = "It appears and seems correct."  # 2 hedges
        assert self.checker.check(text, max_hedges=2).passed is True
        assert self.checker.check(text, max_hedges=1).passed is False


# ==============================================================================
# VerbosityChecker Tests (GATE-02)
# ==============================================================================

class TestVerbosityChecker:
    """Tests for VerbosityChecker (GATE-02)."""

    def setup_method(self):
        """Set up checker instance for each test."""
        self.checker = VerbosityChecker()

    def test_check_name_is_gate_02(self):
        """Verify check_name property returns correct gate ID."""
        assert self.checker.check_name == "GATE-02"

    def test_verbosity_passes_short_text(self):
        """Short, concise text should pass."""
        text = "Delta of $5,000 driven by missing flooring allowance."
        result = self.checker.check(text)
        assert result.passed is True
        assert "Sentences: 1" in result.details

    def test_verbosity_passes_at_threshold(self):
        """Text with exactly 2 sentences should pass."""
        # textstat requires substantive sentences for accurate counting
        text = (
            "The flooring estimate includes premium materials for the entire first floor. "
            "Additional costs come from upgraded installation requirements."
        )
        result = self.checker.check(text, max_sentences=2, max_avg_words=40)
        assert result.passed is True
        assert "Sentences: 2" in result.details

    def test_verbosity_fails_too_many_sentences(self):
        """Text with 3+ sentences should fail with default threshold."""
        # textstat requires substantive sentences (enough words) for accurate counting
        text = (
            "The flooring estimate shows a significant difference between the two bids. "
            "The primary estimate includes premium materials while the contractor uses standard grades. "
            "This explains the cost variance that we are observing in this category."
        )
        result = self.checker.check(text, max_sentences=2)
        assert result.passed is False
        assert "Sentences: 3" in result.details

    def test_verbosity_fails_high_avg_words(self):
        """Text with high average words per sentence should fail."""
        # Create text with ~45 words in one sentence
        long_sentence = (
            "The contractor estimate includes numerous line items covering "
            "flooring materials labor installation preparation demolition "
            "cleanup disposal permits fees overhead profit insurance taxes "
            "equipment rental transportation storage handling supervision "
            "quality control safety measures warranty documentation and "
            "administrative costs that significantly exceed the adjuster "
            "scope assessment."
        )
        result = self.checker.check(long_sentence, max_avg_words=40)
        assert result.passed is False
        assert "Avg words:" in result.details

    def test_verbosity_custom_thresholds(self):
        """Custom thresholds should work."""
        # textstat requires substantive sentences, so use realistic text
        text = (
            "The flooring estimate is higher than expected. "
            "Material costs drive most of the variance. "
            "Labor rates also contribute to the difference."
        )
        # 3 sentences detected by textstat
        assert self.checker.check(text, max_sentences=3, max_avg_words=20).passed is True
        assert self.checker.check(text, max_sentences=2, max_avg_words=20).passed is False


# ==============================================================================
# ValuationLinkChecker Tests (GATE-03)
# ==============================================================================

class TestValuationLinkChecker:
    """Tests for ValuationLinkChecker (GATE-03)."""

    def setup_method(self):
        """Set up checker instance for each test."""
        self.checker = ValuationLinkChecker()

    def test_check_name_is_gate_03(self):
        """Verify check_name property returns correct gate ID."""
        assert self.checker.check_name == "GATE-03"

    def test_valuation_passes_with_dollar_amount(self):
        """Text with dollar amount should pass."""
        text = "The flooring category shows a delta of $5,000."
        result = self.checker.check(text)
        assert result.passed is True
        assert "$5,000" in result.details

    def test_valuation_passes_with_dollar_cents(self):
        """Text with dollar amount and cents should pass."""
        text = "Line item total is $1,234.56 for materials."
        result = self.checker.check(text)
        assert result.passed is True
        assert "$1,234.56" in result.details

    def test_valuation_passes_with_word_amount(self):
        """Text with word-based amount should pass."""
        text = "The difference amounts to 5000 dollars in labor costs."
        result = self.checker.check(text)
        assert result.passed is True
        assert "5000 dollars" in result.details

    def test_valuation_passes_with_usd(self):
        """Text with USD reference should pass."""
        text = "Expected variance of 2500 USD."
        result = self.checker.check(text)
        assert result.passed is True
        assert "2500 USD" in result.details

    def test_valuation_passes_with_delta_reference(self):
        """Text with explicit delta reference should pass."""
        text = "The delta: $500 is primarily from material costs."
        result = self.checker.check(text)
        assert result.passed is True
        # Should find either "delta: $500" or "$500"

    def test_valuation_passes_with_variance_reference(self):
        """Text with variance reference should pass."""
        text = "Observed variance: 1200 in the HVAC category."
        result = self.checker.check(text)
        assert result.passed is True
        assert "variance: 1200" in result.details

    def test_valuation_fails_no_amounts(self):
        """Text without any valuation references should fail."""
        text = "The flooring category shows a significant difference."
        result = self.checker.check(text)
        assert result.passed is False
        assert "No dollar amounts or delta references found" in result.details

    def test_valuation_case_insensitive(self):
        """Dollar/delta detection should be case-insensitive."""
        text = "DELTA: 500 in the roofing scope."
        result = self.checker.check(text)
        assert result.passed is True


# ==============================================================================
# SummaryLengthChecker Tests (GATE-04)
# ==============================================================================

class TestSummaryLengthChecker:
    """Tests for SummaryLengthChecker (GATE-04)."""

    def setup_method(self):
        """Set up checker instance for each test."""
        self.checker = SummaryLengthChecker()

    def test_check_name_is_gate_04(self):
        """Verify check_name property returns correct gate ID."""
        assert self.checker.check_name == "GATE-04"

    def test_summary_passes_within_limits(self):
        """Bullets within all limits should pass."""
        bullets = [
            "Missing flooring allowance of $2,000",
            "HVAC unit cost difference of $3,500",
            "Labor rate variance in electrical",
        ]
        result = self.checker.check(bullets)
        assert result.passed is True
        assert "3 bullets (max 6)" in result.details

    def test_summary_passes_at_bullet_limit(self):
        """Exactly 6 bullets should pass."""
        bullets = [f"Bullet point {i}" for i in range(6)]
        result = self.checker.check(bullets, max_bullets=6)
        assert result.passed is True
        assert "6 bullets (max 6)" in result.details

    def test_summary_fails_too_many_bullets(self):
        """More than 6 bullets should fail."""
        bullets = [f"Bullet point {i}" for i in range(7)]
        result = self.checker.check(bullets, max_bullets=6)
        assert result.passed is False
        assert "7 bullets (max 6)" in result.details

    def test_summary_fails_bullet_too_long(self):
        """Bullet with more than 30 words should fail."""
        long_bullet = " ".join(["word"] * 35)  # 35 words
        bullets = [
            "Short bullet one",
            long_bullet,
            "Short bullet three",
        ]
        result = self.checker.check(bullets, max_bullet_words=30)
        assert result.passed is False
        assert "longest: 35 words" in result.details
        assert "bullets exceeding limit: [2]" in result.details

    def test_summary_tracks_multiple_long_bullets(self):
        """Multiple long bullets should all be tracked."""
        long_bullet1 = " ".join(["word"] * 32)
        long_bullet2 = " ".join(["word"] * 33)
        bullets = [
            "Short bullet",
            long_bullet1,
            "Another short",
            long_bullet2,
        ]
        result = self.checker.check(bullets, max_bullet_words=30)
        assert result.passed is False
        assert "[2, 4]" in result.details  # Bullets 2 and 4 exceeded

    def test_summary_empty_bullets_passes(self):
        """Empty bullet list should pass."""
        result = self.checker.check([])
        assert result.passed is True
        assert "0 bullets" in result.details

    def test_summary_custom_thresholds(self):
        """Custom thresholds should work."""
        bullets = ["One two three four five", "Six seven eight nine ten"]  # 5 words each
        assert self.checker.check(bullets, max_bullet_words=5, max_bullets=2).passed is True
        assert self.checker.check(bullets, max_bullet_words=4, max_bullets=2).passed is False


# ==============================================================================
# AnalystToneChecker Tests (GATE-05)
# ==============================================================================

class TestAnalystToneChecker:
    """Tests for AnalystToneChecker (GATE-05)."""

    def setup_method(self):
        """Set up checker instance for each test."""
        self.checker = AnalystToneChecker()

    def test_check_name_is_gate_05(self):
        """Verify check_name property returns correct gate ID."""
        assert self.checker.check_name == "GATE-05"

    def test_tone_passes_no_analyst_phrases(self):
        """Text with no analyst phrases should pass."""
        text = "The flooring estimate shows a difference of $5,000 in material costs."
        result = self.checker.check(text)
        assert result.passed is True
        assert "No analyst tone phrases found" in result.details

    def test_tone_fails_with_may_indicate(self):
        """Text with 'may indicate' should fail."""
        text = "The higher costs may indicate a scope difference in the flooring category."
        result = self.checker.check(text)
        assert result.passed is False
        assert "may indicate" in result.details

    def test_tone_fails_with_likely_due_to(self):
        """Text with 'likely due to' should fail."""
        text = "The variance is likely due to material upgrades."
        result = self.checker.check(text)
        assert result.passed is False
        assert "likely due to" in result.details

    def test_tone_detects_multiple_phrases(self):
        """Multiple analyst phrases should all be detected."""
        text = (
            "The difference may indicate issues that are likely due to "
            "scope changes that appears to be significant."
        )
        result = self.checker.check(text)
        assert result.passed is False
        assert "Found 3 analyst tone phrases" in result.details
        assert "may indicate" in result.details
        assert "likely due to" in result.details
        assert "appears to be" in result.details

    def test_tone_case_insensitive(self):
        """Analyst phrase detection should be case-insensitive."""
        text = "MAY INDICATE that Likely Due To changes that APPEARS TO BE relevant."
        result = self.checker.check(text)
        assert result.passed is False
        # Should find all three phrases regardless of case

    def test_tone_custom_threshold(self):
        """Custom max_violations threshold should work."""
        text = "This may indicate something that appears to be different."  # 2 phrases
        assert self.checker.check(text, max_violations=2).passed is True
        assert self.checker.check(text, max_violations=1).passed is False


# ==============================================================================
# SlopChecker Tests (GATE-06)
# ==============================================================================

class TestSlopChecker:
    """Tests for SlopChecker (GATE-06)."""

    def setup_method(self):
        """Set up checker instance for each test."""
        self.checker = SlopChecker()

    def test_check_name_is_gate_06(self):
        """Verify check_name property returns correct gate ID."""
        assert self.checker.check_name == "GATE-06"

    def test_slop_passes_clean_text(self):
        """Text with no GPT-isms should pass."""
        text = "The flooring estimate shows a difference of $5,000 in material costs."
        result = self.checker.check(text)
        assert result.passed is True
        assert "No GPT-isms found" in result.details

    def test_slop_fails_with_delve(self):
        """Text with 'delve' should fail."""
        text = "Let's delve into the flooring costs to understand the variance."
        result = self.checker.check(text)
        assert result.passed is False
        assert "delve" in result.details

    def test_slop_fails_with_tapestry(self):
        """Text with 'tapestry' should fail."""
        text = "The tapestry of cost factors in this estimate is complex."
        result = self.checker.check(text)
        assert result.passed is False
        assert "tapestry" in result.details

    def test_slop_fails_with_worth_noting(self):
        """Text with 'it's worth noting' should fail."""
        text = "It's worth noting that the contractor's bid lacks detail."
        result = self.checker.check(text)
        assert result.passed is False
        assert "it's worth noting" in result.details

    def test_slop_detects_multiple_gptisms(self):
        """Multiple GPT-isms should all be detected."""
        text = (
            "Let's delve into the comprehensive landscape of cost factors. "
            "It's worth noting that this analysis shows holistic coverage."
        )
        result = self.checker.check(text)
        assert result.passed is False
        # Should find: delve, comprehensive, landscape, it's worth noting, holistic
        assert "Found 5 GPT-isms" in result.details

    def test_slop_case_insensitive(self):
        """GPT-ism detection should be case-insensitive."""
        text = "DELVE into the TAPESTRY of COMPREHENSIVE analysis."
        result = self.checker.check(text)
        assert result.passed is False
        # Should find all three phrases regardless of case

    def test_slop_whole_word_match(self):
        """Single words should match whole words only."""
        text = "The delivered materials essentially arrived on time."
        result = self.checker.check(text)
        # "delivered" should not match "delve", but "essentially" should match
        assert result.passed is False
        assert "essentially" in result.details
        # Verify "delve" is not in the list
        assert "delve" not in result.details

    def test_slop_custom_threshold(self):
        """Custom max_violations threshold should work."""
        text = "This comprehensive holistic approach works well."  # 2 slop words
        assert self.checker.check(text, max_violations=2).passed is True
        assert self.checker.check(text, max_violations=1).passed is False


# ==============================================================================
# QualityEvaluator Integration Tests
# ==============================================================================

class TestQualityEvaluator:
    """Integration tests for QualityEvaluator."""

    def setup_method(self):
        """Set up evaluator instance for each test."""
        self.evaluator = QualityEvaluator()

    def _make_good_narrative(self) -> DraftNarrative:
        """Create a DraftNarrative that passes all quality gates."""
        return DraftNarrative(
            overview="Clear comparison shows primary estimate is $15,000 higher than contractor bid.",
            key_drivers=[
                DriverNarrative(
                    category="Flooring",
                    amounts="$8,500 vs $5,500",
                    narrative="Delta of $3,000 driven by upgraded materials.",
                ),
                DriverNarrative(
                    category="HVAC",
                    amounts="$12,000 vs $10,000",
                    narrative="Variance of $2,000 from unit pricing.",
                ),
            ],
            scope_observations=[
                "Missing flooring prep allowance",
                "HVAC permits not included in contractor bid",
                "Debris removal scope differs",
            ],
            suggested_followups=[
                "Verify flooring material specifications",
                "Confirm permit responsibility",
            ],
        )

    def _make_hedgy_narrative(self) -> DraftNarrative:
        """Create a DraftNarrative that fails the hedging check."""
        return DraftNarrative(
            overview=(
                "It appears the primary estimate may possibly suggest what could "
                "potentially be a difference that seems likely to indicate higher costs."
            ),
            key_drivers=[
                DriverNarrative(
                    category="Flooring",
                    amounts="$8,500 vs $5,500",
                    narrative="Delta of $3,000 driven by materials.",
                ),
            ],
            scope_observations=["Missing items noted"],
            suggested_followups=[],
        )

    def _make_verbose_narrative(self) -> DraftNarrative:
        """Create a DraftNarrative that fails the verbosity check."""
        long_narrative = (
            "The flooring category shows significant differences. "
            "Multiple line items contribute to this variance. "
            "Further investigation reveals complex pricing structures. "
            "Material costs alone account for most of the delta: $5,000."
        )
        return DraftNarrative(
            overview="Clear comparison at $10,000 higher.",
            key_drivers=[
                DriverNarrative(
                    category="Flooring",
                    amounts="$8,500 vs $5,500",
                    narrative=long_narrative,  # 4 sentences
                ),
            ],
            scope_observations=["Note one"],
            suggested_followups=[],
        )

    def _make_no_valuation_narrative(self) -> DraftNarrative:
        """Create a DraftNarrative that fails the valuation link check."""
        return DraftNarrative(
            overview="The primary estimate is higher than the contractor bid.",
            key_drivers=[
                DriverNarrative(
                    category="Flooring",
                    amounts="Primary higher",  # No $ amount
                    narrative="Significant differences in flooring scope noted.",  # No $ or delta
                ),
            ],
            scope_observations=["Missing items"],
            suggested_followups=[],
        )

    def test_evaluator_passes_good_narrative(self):
        """Good narrative should pass all checks."""
        draft = self._make_good_narrative()
        report = self.evaluator.evaluate(draft)

        assert isinstance(report, QualityReport)
        assert report.passed is True
        assert len(report.failed_checks) == 0

    def test_evaluator_fails_hedgy_narrative(self):
        """Hedgy narrative should fail GATE-01."""
        draft = self._make_hedgy_narrative()
        report = self.evaluator.evaluate(draft)

        assert report.passed is False
        assert "GATE-01" in report.failed_checks

    def test_evaluator_fails_verbose_narrative(self):
        """Verbose narrative should fail GATE-02."""
        draft = self._make_verbose_narrative()
        report = self.evaluator.evaluate(draft)

        assert report.passed is False
        assert "GATE-02" in report.failed_checks

    def test_evaluator_fails_no_valuation_narrative(self):
        """Narrative without valuation links should fail GATE-03."""
        draft = self._make_no_valuation_narrative()
        report = self.evaluator.evaluate(draft)

        assert report.passed is False
        assert "GATE-03" in report.failed_checks

    def test_evaluator_returns_all_check_results(self):
        """Evaluator should return results for all checks run."""
        draft = self._make_good_narrative()
        report = self.evaluator.evaluate(draft)

        # With 2 key_drivers:
        # Overview: GATE-01 (hedging) + GATE-05 (tone) + GATE-06 (slop) = 3
        # Each driver: GATE-02 (verbosity) + GATE-03 (valuation) + GATE-05 (tone) + GATE-06 (slop) = 4 per driver = 8
        # Summary: GATE-04 = 1
        # Total: 3 + 8 + 1 = 12
        assert len(report.checks) == 12

        check_names = [c.check_name for c in report.checks]
        assert "GATE-01" in check_names
        assert check_names.count("GATE-02") == 2  # One per driver
        assert check_names.count("GATE-03") == 2  # One per driver
        assert "GATE-04" in check_names
        assert check_names.count("GATE-05") == 3  # Overview + 2 drivers
        assert check_names.count("GATE-06") == 3  # Overview + 2 drivers

    def test_evaluator_custom_thresholds(self):
        """Custom thresholds should be respected."""
        # Create evaluator with stricter hedging threshold
        strict_evaluator = QualityEvaluator(max_hedges=0)

        draft = DraftNarrative(
            overview="This may show a difference of $5,000.",  # 1 hedge word
            key_drivers=[
                DriverNarrative(
                    category="Test",
                    amounts="$1,000 vs $500",
                    narrative="Delta of $500 noted.",
                ),
            ],
            scope_observations=["One observation"],
            suggested_followups=[],
        )

        # Default evaluator (max_hedges=3) should pass
        assert self.evaluator.evaluate(draft).passed is True

        # Strict evaluator (max_hedges=0) should fail
        assert strict_evaluator.evaluate(draft).passed is False

    def test_evaluator_report_has_timestamp(self):
        """QualityReport should have checked_at timestamp."""
        draft = self._make_good_narrative()
        report = self.evaluator.evaluate(draft)

        assert report.checked_at is not None

    def test_evaluator_runs_analyst_tone_checks(self):
        """Evaluator should run GATE-05 (analyst tone) on overview and drivers."""
        draft = DraftNarrative(
            overview="The variance may indicate a scope difference worth $5,000.",
            key_drivers=[
                DriverNarrative(
                    category="Flooring",
                    amounts="$8,500 vs $5,500",
                    narrative="Delta of $3,000 driven by materials.",
                ),
            ],
            scope_observations=["Missing items noted"],
            suggested_followups=[],
        )
        report = self.evaluator.evaluate(draft)

        # Should fail GATE-05 due to "may indicate" in overview
        assert report.passed is False
        assert "GATE-05" in report.failed_checks

    def test_evaluator_runs_slop_checks(self):
        """Evaluator should run GATE-06 (slop) on overview and drivers."""
        draft = DraftNarrative(
            overview="Let's delve into the comprehensive comparison showing $15,000 higher.",
            key_drivers=[
                DriverNarrative(
                    category="Flooring",
                    amounts="$8,500 vs $5,500",
                    narrative="Delta of $3,000 driven by materials.",
                ),
            ],
            scope_observations=["Missing items noted"],
            suggested_followups=[],
        )
        report = self.evaluator.evaluate(draft)

        # Should fail GATE-06 due to "delve" and "comprehensive" in overview
        assert report.passed is False
        assert "GATE-06" in report.failed_checks

    def test_evaluator_fails_narrative_with_gptisms(self):
        """Narrative with GPT-isms in driver should fail GATE-06."""
        draft = DraftNarrative(
            overview="Clear comparison shows primary is $15,000 higher.",
            key_drivers=[
                DriverNarrative(
                    category="Flooring",
                    amounts="$8,500 vs $5,500",
                    narrative="It's worth noting the delta of $3,000 is significant.",
                ),
            ],
            scope_observations=["Missing items noted"],
            suggested_followups=[],
        )
        report = self.evaluator.evaluate(draft)

        # Should fail GATE-06 due to "it's worth noting" and "significant" in driver narrative
        assert report.passed is False
        assert "GATE-06" in report.failed_checks


# ==============================================================================
# Import verification test
# ==============================================================================

class TestImports:
    """Verify all quality gate classes are importable from pipeline module."""

    def test_import_from_pipeline(self):
        """All checkers should be importable from src.pipeline."""
        from src.pipeline import (
            AnalystToneChecker,
            HedgingChecker,
            QualityEvaluator,
            SlopChecker,
            SummaryLengthChecker,
            ValuationLinkChecker,
            VerbosityChecker,
        )

        # Verify they are classes with expected methods
        assert hasattr(HedgingChecker, 'check')
        assert hasattr(VerbosityChecker, 'check')
        assert hasattr(ValuationLinkChecker, 'check')
        assert hasattr(SummaryLengthChecker, 'check')
        assert hasattr(AnalystToneChecker, 'check')
        assert hasattr(SlopChecker, 'check')
        assert hasattr(QualityEvaluator, 'evaluate')
