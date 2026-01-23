"""
PipelineState container for holding intermediate pipeline results.

This is the shared state container passed between pipeline passes.
Each pass reads what it needs and writes its output to the appropriate field.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from .models import (
    AnalysisResult,
    DraftNarrative,
    FinalNarrative,
    QualityReport,
)


class PipelineState(BaseModel):
    """
    Container holding all intermediate pipeline results.

    Passed through the pipeline, accumulating results from each pass:
    - Pass 1 (Analysis): Reads pair + top_deltas, writes analysis
    - Pass 2 (Writer): Reads analysis, writes draft
    - Pass 3 (Compliance): Reads draft + quality_report, writes final

    Also tracks execution metadata: which passes ran, timing, errors.
    """

    # Inputs (from BidComp existing flow)
    pair: Any = Field(
        default=None,
        description="EstimatePair equivalent - kept flexible for now"
    )
    top_deltas: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Category deltas from bid_comp analysis"
    )

    # Pass 1 output
    analysis: Optional[AnalysisResult] = Field(
        default=None,
        description="Output of Analysis pass"
    )

    # Pass 2 output
    draft: Optional[DraftNarrative] = Field(
        default=None,
        description="Output of Writer pass"
    )

    # Pass 3 output (or pass-through of draft if quality passed)
    final: Optional[Union[DraftNarrative, FinalNarrative]] = Field(
        default=None,
        description="Final narrative output"
    )

    # Quality gate results
    quality_report: Optional[QualityReport] = Field(
        default=None,
        description="Quality check results"
    )

    # Pipeline metadata
    passes_executed: List[str] = Field(
        default_factory=list,
        description="List of passes that have executed (e.g., ['analysis', 'writer', 'compliance_skipped'])"
    )
    pass_timings_ms: Dict[str, int] = Field(
        default_factory=dict,
        description="Execution time per pass in milliseconds"
    )
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="PassError records for any failures"
    )

    def is_complete(self) -> bool:
        """
        Check if the pipeline has completed (final narrative exists).

        Returns:
            True if final narrative is set, False otherwise.
        """
        return self.final is not None

    def quality_passed(self) -> bool:
        """
        Check if the quality gate passed.

        Returns:
            True if quality_report exists and passed, False otherwise.
        """
        if self.quality_report is None:
            return False
        return self.quality_report.passed

    def add_timing(self, pass_name: str, ms: int) -> None:
        """
        Record execution time for a pass.

        Args:
            pass_name: Name of the pass (e.g., 'analysis', 'writer')
            ms: Execution time in milliseconds
        """
        self.pass_timings_ms[pass_name] = ms

    def mark_pass_executed(self, pass_name: str) -> None:
        """
        Mark a pass as executed.

        Args:
            pass_name: Name of the pass (e.g., 'analysis', 'writer', 'compliance_skipped')
        """
        self.passes_executed.append(pass_name)
