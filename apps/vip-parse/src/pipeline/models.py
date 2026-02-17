"""
Pydantic models defining data contracts between pipeline passes.

These models are the typed contracts for the multi-pass LLM pipeline:
- Analysis Pass: EstimatePair + TopDeltas -> AnalysisResult
- Writer Pass: AnalysisResult -> DraftNarrative
- Compliance Pass: DraftNarrative -> FinalNarrative (conditional)

All models support JSON serialization for caching and logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal

from pydantic import BaseModel, Field, computed_field


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class CategoryAnalysis(BaseModel):
    """
    Analysis of a single category delta between two estimates.

    Contains the numerical comparison and evidence supporting the delta.
    Used by the Writer pass to generate narrative explanations.
    """

    category: str = Field(description="Category name (e.g., 'Flooring', 'HVAC / Mechanical')")
    primary_total: float = Field(description="Total amount in primary estimate for this category")
    comparison_total: float = Field(description="Total amount in comparison estimate for this category")
    delta: float = Field(description="Difference: primary_total - comparison_total")
    delta_drivers: List[str] = Field(
        default_factory=list,
        description="Explanations of what drives the delta (e.g., '3 window units at $450/each missing')"
    )
    line_item_evidence: List[str] = Field(
        default_factory=list,
        description="Specific line items cited as evidence"
    )


class AnalysisResult(BaseModel):
    """
    Output of the Analysis pass (Pass 1).

    Contains structured comparison data extracted from the estimates.
    This is the input to the Writer pass - no raw estimate data needed downstream.
    """

    category_analyses: List[CategoryAnalysis] = Field(
        default_factory=list,
        description="Analysis for each top delta category"
    )
    scope_gaps: List[str] = Field(
        default_factory=list,
        description="Missing trades, allowances, or scope items"
    )
    overall_delta_direction: Literal["primary_higher", "comparison_higher", "similar"] = Field(
        description="Overall direction of the cost difference"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence in the analysis based on data quality"
    )


class LLMCategoryAnalysis(BaseModel):
    """Structured-output response model for a single category analysis."""

    category: str
    primary_amount: float
    comparison_amount: float
    delta: float
    delta_drivers: List[str]
    line_item_evidence: List[str]


class LLMAnalysisResult(BaseModel):
    """Structured-output response model for analysis pass."""

    category_analyses: List[LLMCategoryAnalysis]
    scope_gaps: List[str]
    overall_delta_direction: Literal["primary_higher", "comparison_higher", "similar"]
    confidence: Literal["high", "medium", "low"]


class DriverNarrative(BaseModel):
    """
    Narrative explanation for a single cost driver.

    Used in DraftNarrative to explain each significant delta.
    """

    category: str = Field(description="Category this driver relates to")
    amounts: str = Field(description="Amount comparison (e.g., '$12,500 vs $8,200')")
    narrative: str = Field(description="Explanation of the delta (e.g., 'Delta driven by...')")


class DraftNarrative(BaseModel):
    """
    Output of the Writer pass (Pass 2).

    Contains the adjuster-tone narrative ready for quality checking.
    If quality passes, this becomes the final output. If quality fails,
    this is sent to the Compliance pass for rewriting.
    """

    overview: str = Field(description="2-3 sentence summary of the comparison")
    key_drivers: List[DriverNarrative] = Field(
        default_factory=list,
        description="Narrative for each significant cost driver"
    )
    scope_observations: List[str] = Field(
        default_factory=list,
        description="Observations about scope differences"
    )
    suggested_followups: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions or investigations"
    )


class QualityCheckResult(BaseModel):
    """
    Result of a single quality check.

    Quality checks are either deterministic (word counts, phrase detection)
    or LLM-based (tone judgment). Each check produces one of these results.
    """

    check_name: str = Field(description="Name of the quality check")
    passed: bool = Field(description="Whether this check passed")
    details: str = Field(
        default="",
        description="Details about the result (e.g., 'Found 5 hedge words (max: 3)')"
    )


class QualityReport(BaseModel):
    """
    Aggregated quality gate results from all checks.

    Determines whether the draft narrative needs compliance rewriting.
    """

    passed: bool = Field(description="Whether all quality checks passed")
    checks: List[QualityCheckResult] = Field(
        default_factory=list,
        description="Results from each quality check"
    )
    checked_at: datetime = Field(
        default_factory=_utc_now,
        description="When the quality check was performed"
    )

    @computed_field
    @property
    def failed_checks(self) -> List[str]:
        """Convenience property: names of checks that failed."""
        return [check.check_name for check in self.checks if not check.passed]


class FinalNarrative(DraftNarrative):
    """
    Output of the Compliance pass (Pass 3) - extends DraftNarrative.

    Contains the final narrative after quality gate processing.
    If quality passed on the draft, this just wraps DraftNarrative.
    If compliance rewriting occurred, rewrites_performed > 0.
    """

    quality_report: QualityReport = Field(
        description="Quality gate results for this narrative"
    )
    rewrites_performed: int = Field(
        default=0,
        description="Number of compliance rewrites performed (0 if quality passed initially)"
    )
