"""Deterministic litigation-ready quality gate checkers."""

from __future__ import annotations

import re
from typing import List, Optional

from vip_shared.methodology.models import GranularityLevel

from .models import DraftNarrative, QualityCheckResult, QualityReport
from .quality_words import (
    HEDGE_WORDS,
    JUDGMENT_ADJECTIVES,
    JUDGMENT_PHRASES,
    METHODOLOGY_PROHIBITED,
    SLOP_PHRASES,
)


def _find_terms(text: str, single_terms: List[str], phrases: List[str]) -> List[str]:
    text_lower = text.lower()
    found: List[str] = []
    for term in single_terms:
        if " " in term:
            continue
        if re.search(rf"\b{re.escape(term.lower())}\b", text_lower):
            found.append(term)
    for phrase in phrases:
        if phrase.lower() in text_lower:
            found.append(phrase)
    return found


class HedgingChecker:
    @property
    def check_name(self) -> str:
        return "GATE-01"

    def check(self, text: str, max_violations: int = 0) -> QualityCheckResult:
        single = [w for w in HEDGE_WORDS + SLOP_PHRASES if " " not in w]
        phrases = [w for w in HEDGE_WORDS + SLOP_PHRASES if " " in w]
        found = _find_terms(text, single, phrases)
        passed = len(found) <= max_violations
        details = f"Found {len(found)} hedge/slop terms: {found}" if found else "No hedge/slop terms found"
        return QualityCheckResult(check_name=self.check_name, passed=passed, details=details)


class JudgmentLanguageChecker:
    @property
    def check_name(self) -> str:
        return "GATE-02"

    def check(self, text: str, max_violations: int = 0) -> QualityCheckResult:
        single = [w for w in JUDGMENT_ADJECTIVES if " " not in w]
        phrases = [w for w in JUDGMENT_ADJECTIVES if " " in w] + JUDGMENT_PHRASES
        found = _find_terms(text, single, phrases)
        passed = len(found) <= max_violations
        details = f"Found {len(found)} judgment terms: {found}" if found else "No judgment language found"
        return QualityCheckResult(check_name=self.check_name, passed=passed, details=details)


class QuantificationChecker:
    DELTA_INDICATORS = [
        r"\bdelta\b", r"\bdifference\b", r"\bvariance\b", r"\bhigher\b", r"\blower\b",
        r"\bmore\b", r"\bless\b", r"\bexceeds?\b", r"\bshortfall\b", r"\bgap\b",
        r"\bvs\.?\b", r"\bversus\b", r"\bcompared\b", r"\bgreater\b", r"\bsmaller\b",
    ]
    DOLLAR_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{2})?")
    PERCENT_PATTERN = re.compile(r"\d+(?:\.\d+)?%")

    @property
    def check_name(self) -> str:
        return "GATE-03"

    def check(self, text: str) -> QualityCheckResult:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", (text or "").strip()) if s.strip()]
        violations: List[str] = []
        for sentence in sentences:
            if not self._references_delta(sentence):
                continue
            has_dollar = bool(self.DOLLAR_PATTERN.search(sentence))
            has_percent = bool(self.PERCENT_PATTERN.search(sentence))
            if not has_dollar or not has_percent:
                missing = []
                if not has_dollar:
                    missing.append("dollar amount")
                if not has_percent:
                    missing.append("percentage")
                violations.append(f"Missing {', '.join(missing)}: {sentence[:120]}")
        passed = len(violations) == 0
        details = "All delta references quantified" if passed else f"{len(violations)} quantification violations: {violations}"
        return QualityCheckResult(check_name=self.check_name, passed=passed, details=details)

    def _references_delta(self, sentence: str) -> bool:
        s = sentence.lower()
        return any(re.search(pattern, s) for pattern in self.DELTA_INDICATORS)


class EvidenceGroundingChecker:
    LINE_ITEM_INDICATORS = [
        r"\b\d+\s+(?:units?|pieces?|sheets?|rolls?|boxes?|bags?|gallons?|feet|sf|lf|sy|ea|hr|windows?|doors?|squares?)\b",
        r"\$[\d,]+(?:\.\d{2})?\s*(?:per|/)\s*(?:unit|sf|lf|sy|ea|hr|sq\s*ft|lin\s*ft|each)",
        r"(?:at|@)\s*\$[\d,]+(?:\.\d{2})?\s*(?:each|per|apiece)",
        r"\b\d+\s+\w+\s+(?:windows?|doors?|cabinets?|fixtures?|units?)\s+(?:at|@)\s*\$",
    ]

    @property
    def check_name(self) -> str:
        return "GATE-04"

    def check(self, text: str, data_granularity: GranularityLevel) -> QualityCheckResult:
        if data_granularity == GranularityLevel.LINE_ITEM:
            return QualityCheckResult(check_name=self.check_name, passed=True, details="LINE_ITEM granularity permits line-item references")

        violations: List[str] = []
        lower = text.lower()
        for pattern in self.LINE_ITEM_INDICATORS:
            if re.search(pattern, lower):
                violations.append(pattern)

        passed = len(violations) == 0
        details = (
            f"Found line-item references not allowed at granularity={data_granularity.value}"
            if violations
            else f"No forbidden line-item references for granularity={data_granularity.value}"
        )
        return QualityCheckResult(check_name=self.check_name, passed=passed, details=details)


class MethodologyNeutralityChecker:
    @property
    def check_name(self) -> str:
        return "GATE-05"

    def check(self, text: str, max_violations: int = 0) -> QualityCheckResult:
        single = [w for w in METHODOLOGY_PROHIBITED if " " not in w]
        phrases = [w for w in METHODOLOGY_PROHIBITED if " " in w]
        found = _find_terms(text, single, phrases)
        passed = len(found) <= max_violations
        details = f"Found {len(found)} methodology-prohibited terms: {found}" if found else "No methodology comparison language found"
        return QualityCheckResult(check_name=self.check_name, passed=passed, details=details)


class QualityEvaluator:
    def __init__(self):
        self.hedging = HedgingChecker()
        self.judgment = JudgmentLanguageChecker()
        self.quantification = QuantificationChecker()
        self.evidence = EvidenceGroundingChecker()
        self.methodology_neutrality = MethodologyNeutralityChecker()

    def evaluate(
        self,
        draft: DraftNarrative,
        data_granularity: Optional[GranularityLevel] = None,
        methodology_text: Optional[str] = None,
    ) -> QualityReport:
        checks: List[QualityCheckResult] = []
        all_narrative_text = self._collect_narrative_text(draft)
        checks.append(self.hedging.check(all_narrative_text))
        checks.append(self.judgment.check(all_narrative_text))
        quant_text = (draft.overview or "") + " " + " ".join(d.narrative for d in draft.key_drivers)
        checks.append(self.quantification.check(quant_text))

        if data_granularity is not None:
            checks.append(self.evidence.check(all_narrative_text, data_granularity))

        if methodology_text is not None:
            checks.append(self.methodology_neutrality.check(methodology_text))

        passed = all(c.passed for c in checks)
        return QualityReport(passed=passed, checks=checks)

    def _collect_narrative_text(self, draft: DraftNarrative) -> str:
        parts = [draft.overview]
        parts.extend(d.narrative for d in draft.key_drivers)
        parts.extend(draft.scope_observations)
        return " ".join(p for p in parts if p)
