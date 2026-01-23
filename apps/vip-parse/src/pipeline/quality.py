"""
Deterministic quality gate checkers for narrative validation.

These checkers run without LLM calls and provide pass/fail signals for
the conditional compliance rewrite decision. Quality gates include:
- GATE-01: Hedging limit check
- GATE-02: Verbosity check (sentence count, word average)
- GATE-03: Valuation link check (dollar amounts, delta references)
- GATE-04: Summary length check (bullet count, bullet word limits)

Usage:
    from src.pipeline.quality import QualityEvaluator

    evaluator = QualityEvaluator()
    report = evaluator.evaluate(draft_narrative)
    if not report.passed:
        # Send to compliance rewrite pass
"""

from __future__ import annotations

import re
from typing import List

import textstat

from .models import DraftNarrative, QualityCheckResult, QualityReport


class HedgingChecker:
    """
    GATE-01: Checks for excessive hedge words in text.

    Hedge words weaken authoritative adjuster tone. Narratives with more than
    the allowed number of hedge words fail this check and require rewriting.

    Threshold: max 3 hedge words per section (configurable).
    """

    HEDGE_WORDS = [
        "appears", "seems", "might", "may", "could", "possibly", "potentially",
        "suggests", "indicates", "perhaps", "likely", "probably", "apparently"
    ]

    @property
    def check_name(self) -> str:
        """Return the gate identifier."""
        return "GATE-01"

    def check(self, text: str, max_hedges: int = 3) -> QualityCheckResult:
        """
        Check text for excessive hedge words.

        Args:
            text: The text to check for hedge words.
            max_hedges: Maximum allowed hedge words (default: 3).

        Returns:
            QualityCheckResult with pass/fail status and details.
        """
        found_hedges: List[str] = []
        text_lower = text.lower()

        for hedge in self.HEDGE_WORDS:
            # Whole word match to avoid false positives (e.g., "display" matching "may")
            pattern = rf'\b{re.escape(hedge)}\b'
            matches = re.findall(pattern, text_lower)
            found_hedges.extend(matches)

        count = len(found_hedges)
        passed = count <= max_hedges

        if found_hedges:
            details = f"Found {count} hedge words: {found_hedges} (max: {max_hedges})"
        else:
            details = f"Found 0 hedge words (max: {max_hedges})"

        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details
        )


class VerbosityChecker:
    """
    GATE-02: Checks for excessive verbosity in trade narratives.

    Trade sections should be concise. Too many sentences or overly long
    sentences indicate verbose writing that needs tightening.

    Thresholds:
    - Max 2 sentences per trade section
    - Max 40 average words per sentence
    """

    @property
    def check_name(self) -> str:
        """Return the gate identifier."""
        return "GATE-02"

    def check(
        self,
        text: str,
        max_sentences: int = 2,
        max_avg_words: int = 40
    ) -> QualityCheckResult:
        """
        Check text for excessive verbosity.

        Args:
            text: The text to check for verbosity.
            max_sentences: Maximum allowed sentences (default: 2).
            max_avg_words: Maximum average words per sentence (default: 40).

        Returns:
            QualityCheckResult with pass/fail status and details.
        """
        sentence_count = textstat.sentence_count(text)
        word_count = textstat.lexicon_count(text, removepunct=True)

        # Calculate average words per sentence (avoid division by zero)
        avg_words = word_count / sentence_count if sentence_count > 0 else 0

        passed = sentence_count <= max_sentences and avg_words <= max_avg_words

        details = (
            f"Sentences: {sentence_count}, Avg words: {avg_words:.1f} "
            f"(max: {max_sentences} sentences, {max_avg_words} avg words)"
        )

        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details
        )


class ValuationLinkChecker:
    """
    GATE-03: Checks that trade sections reference dollar amounts or deltas.

    Every trade narrative should tie back to concrete valuation figures.
    Missing valuation links indicate vague writing that needs strengthening.

    Passes if any of these patterns are found:
    - Dollar amounts ($12,500, $1,234.56)
    - Word amounts (12500 dollars, 500 USD)
    - Delta references (delta: $500, variance: 1200)
    """

    # Regex patterns for valuation references
    VALUATION_PATTERNS = [
        r'\$[\d,]+(?:\.\d{2})?',  # $12,500 or $1,234.56
        r'\b\d+(?:,\d{3})*\s*(?:dollars?|USD)\b',  # 12500 dollars, 500 USD
        r'(?:delta|variance|difference)[:\s]+\$?[\d,]+',  # delta: $500, variance: 1200
    ]

    @property
    def check_name(self) -> str:
        """Return the gate identifier."""
        return "GATE-03"

    def check(self, text: str) -> QualityCheckResult:
        """
        Check text for valuation references (dollar amounts or delta mentions).

        Args:
            text: The text to check for valuation links.

        Returns:
            QualityCheckResult with pass/fail status and details.
        """
        for pattern in self.VALUATION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return QualityCheckResult(
                    check_name=self.check_name,
                    passed=True,
                    details=f"Found valuation reference: {match.group()}"
                )

        return QualityCheckResult(
            check_name=self.check_name,
            passed=False,
            details="No dollar amounts or delta references found"
        )


class SummaryLengthChecker:
    """
    GATE-04: Checks that summary bullets are concise and not too numerous.

    Summary observations should be brief and scannable. Too many bullets
    or overly wordy bullets dilute the key points.

    Thresholds:
    - Max 6 bullets total
    - Max 30 words per bullet
    """

    @property
    def check_name(self) -> str:
        """Return the gate identifier."""
        return "GATE-04"

    def check(
        self,
        bullets: List[str],
        max_bullet_words: int = 30,
        max_bullets: int = 6
    ) -> QualityCheckResult:
        """
        Check that summary bullets meet length constraints.

        Args:
            bullets: List of bullet point strings.
            max_bullet_words: Maximum words per bullet (default: 30).
            max_bullets: Maximum number of bullets (default: 6).

        Returns:
            QualityCheckResult with pass/fail status and details.
        """
        bullet_count = len(bullets)
        exceeded_bullets: List[int] = []  # Track which bullets exceeded limit

        max_word_count = 0
        for i, bullet in enumerate(bullets):
            word_count = len(bullet.split())
            if word_count > max_word_count:
                max_word_count = word_count
            if word_count > max_bullet_words:
                exceeded_bullets.append(i + 1)  # 1-indexed for readability

        passed = bullet_count <= max_bullets and len(exceeded_bullets) == 0

        details = (
            f"{bullet_count} bullets (max {max_bullets}), "
            f"longest: {max_word_count} words (max {max_bullet_words})"
        )

        if exceeded_bullets:
            details += f" - bullets exceeding limit: {exceeded_bullets}"

        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details
        )


class AnalystToneChecker:
    """
    GATE-05: Checks for analyst hedging phrases in text.

    Analyst-specific hedging phrases weaken professional authority and make
    the narrative sound uncertain. These multi-word phrases are more specific
    than individual hedge words (covered by GATE-01) and indicate analyst
    writing patterns that should be avoided.

    Zero tolerance by default - any analyst phrase fails the check.
    """

    ANALYST_PHRASES = [
        "may indicate",
        "likely due to",
        "appears to be",
        "seems to suggest",
        "could potentially",
        "might be attributed to",
        "possibly due to",
        "suggests that",
        "this indicates that",
        "this suggests",
    ]

    @property
    def check_name(self) -> str:
        """Return the gate identifier."""
        return "GATE-05"

    def check(self, text: str, max_violations: int = 0) -> QualityCheckResult:
        """
        Check text for analyst hedging phrases.

        Args:
            text: The text to check for analyst phrases.
            max_violations: Maximum allowed phrases (default: 0, zero tolerance).

        Returns:
            QualityCheckResult with pass/fail status and details.
        """
        found_phrases: List[str] = []
        text_lower = text.lower()

        for phrase in self.ANALYST_PHRASES:
            # Case-insensitive phrase matching
            if phrase.lower() in text_lower:
                found_phrases.append(phrase)

        count = len(found_phrases)
        passed = count <= max_violations

        if found_phrases:
            details = f"Found {count} analyst tone phrases: {found_phrases}"
        else:
            details = "No analyst tone phrases found"

        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details
        )


class SlopChecker:
    """
    GATE-06: Checks for GPT-isms and overused AI-sounding phrases.

    These words and phrases are telltale signs of AI-generated text.
    Professional adjuster narratives should sound human and authoritative,
    not like generic AI output.

    Zero tolerance by default - any slop phrase fails the check.
    """

    SLOP_PHRASES = [
        # Single words
        "delve", "tapestry", "landscape", "comprehensive", "holistic",
        "leverage", "synergy", "significantly", "ultimately", "essentially",
        "arguably", "undoubtedly", "furthermore", "moreover", "nevertheless",
        # Multi-word phrases
        "it's worth noting", "it is worth noting",
        "it is important to", "it's important to",
        "in conclusion", "at the end of the day",
        "moving forward", "in order to",
        "a testament to", "serves as a reminder",
        "a myriad of", "a plethora of",
        "dive into", "dive deep",
        "as we navigate", "navigating the",
    ]

    @property
    def check_name(self) -> str:
        """Return the gate identifier."""
        return "GATE-06"

    def check(self, text: str, max_violations: int = 0) -> QualityCheckResult:
        """
        Check text for GPT-isms and overused AI phrases.

        Args:
            text: The text to check for slop phrases.
            max_violations: Maximum allowed phrases (default: 0, zero tolerance).

        Returns:
            QualityCheckResult with pass/fail status and details.
        """
        found_phrases: List[str] = []
        text_lower = text.lower()

        for phrase in self.SLOP_PHRASES:
            phrase_lower = phrase.lower()
            # For single words, use whole word matching to avoid false positives
            if ' ' not in phrase:
                pattern = rf'\b{re.escape(phrase_lower)}\b'
                if re.search(pattern, text_lower):
                    found_phrases.append(phrase)
            else:
                # For multi-word phrases, check for substring
                if phrase_lower in text_lower:
                    found_phrases.append(phrase)

        count = len(found_phrases)
        passed = count <= max_violations

        if found_phrases:
            details = f"Found {count} GPT-isms: {found_phrases}"
        else:
            details = "No GPT-isms found"

        return QualityCheckResult(
            check_name=self.check_name,
            passed=passed,
            details=details
        )


class QualityEvaluator:
    """
    Aggregates all deterministic quality checks into a single evaluation.

    Runs all six quality gates on a DraftNarrative and returns a QualityReport
    indicating whether the narrative passes quality or needs compliance rewriting.

    Gates:
    - GATE-01: Hedging check on overview
    - GATE-02: Verbosity check on each driver narrative
    - GATE-03: Valuation link check on each driver narrative
    - GATE-04: Summary length check on scope observations
    - GATE-05: Analyst tone check on overview and each driver narrative
    - GATE-06: GPT-ism (slop) check on overview and each driver narrative
    """

    def __init__(
        self,
        max_hedges: int = 3,
        max_sentences_per_trade: int = 2,
        max_avg_words: int = 40,
        max_bullet_words: int = 30,
        max_bullets: int = 6,
        max_analyst_phrases: int = 0,
        max_slop_phrases: int = 0
    ):
        """
        Initialize QualityEvaluator with configurable thresholds.

        Args:
            max_hedges: Maximum hedge words allowed in overview (default: 3).
            max_sentences_per_trade: Max sentences per trade narrative (default: 2).
            max_avg_words: Max average words per sentence in trades (default: 40).
            max_bullet_words: Max words per summary bullet (default: 30).
            max_bullets: Max number of summary bullets (default: 6).
            max_analyst_phrases: Max analyst tone phrases (default: 0, zero tolerance).
            max_slop_phrases: Max GPT-isms allowed (default: 0, zero tolerance).
        """
        self.hedging = HedgingChecker()
        self.verbosity = VerbosityChecker()
        self.valuation = ValuationLinkChecker()
        self.summary_length = SummaryLengthChecker()
        self.tone = AnalystToneChecker()
        self.slop = SlopChecker()

        # Store thresholds
        self.max_hedges = max_hedges
        self.max_sentences_per_trade = max_sentences_per_trade
        self.max_avg_words = max_avg_words
        self.max_bullet_words = max_bullet_words
        self.max_bullets = max_bullets
        self.max_analyst_phrases = max_analyst_phrases
        self.max_slop_phrases = max_slop_phrases

    def evaluate(self, draft: DraftNarrative) -> QualityReport:
        """
        Run all deterministic quality checks on a draft narrative.

        Args:
            draft: The DraftNarrative to evaluate.

        Returns:
            QualityReport with aggregated results from all checks.
        """
        checks: List[QualityCheckResult] = []

        # GATE-01: Hedging check on overview
        checks.append(self.hedging.check(draft.overview, self.max_hedges))

        # GATE-05: Analyst tone check on overview
        checks.append(self.tone.check(draft.overview, self.max_analyst_phrases))

        # GATE-06: Slop check on overview
        checks.append(self.slop.check(draft.overview, self.max_slop_phrases))

        # GATE-02, GATE-03, GATE-05, GATE-06 on each driver narrative
        for driver in draft.key_drivers:
            checks.append(
                self.verbosity.check(
                    driver.narrative,
                    self.max_sentences_per_trade,
                    self.max_avg_words
                )
            )
            checks.append(self.valuation.check(driver.narrative))
            checks.append(self.tone.check(driver.narrative, self.max_analyst_phrases))
            checks.append(self.slop.check(driver.narrative, self.max_slop_phrases))

        # GATE-04: Summary length on scope observations
        checks.append(
            self.summary_length.check(
                draft.scope_observations,
                self.max_bullet_words,
                self.max_bullets
            )
        )

        passed = all(c.passed for c in checks)
        return QualityReport(passed=passed, checks=checks)
