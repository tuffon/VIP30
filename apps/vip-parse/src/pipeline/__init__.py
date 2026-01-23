"""
Pipeline module for multi-pass LLM narrative generation.

This module provides:
- Data contracts (Pydantic models) for pipeline pass inputs/outputs
- PipelineState container for intermediate results
- Quality gate checkers for deterministic narrative validation
- Pass implementations (analysis, writer, compliance)
- NarrativePipeline orchestrator for coordinating all passes
- PipelineCache for Redis-based caching of pass results

Usage:
    from src.pipeline import NarrativePipeline, PipelineState
    from src.pipeline import AnalysisResult, DraftNarrative, FinalNarrative
    from src.pipeline import QualityEvaluator
    from src.pipeline import run_analysis_pass, run_writer_pass, run_compliance_pass
    from src.pipeline import PipelineCache, cache_key
"""

from .cache import PipelineCache, cache_key
from .models import (
    AnalysisResult,
    CategoryAnalysis,
    DraftNarrative,
    DriverNarrative,
    FinalNarrative,
    QualityCheckResult,
    QualityReport,
)
from .orchestrator import NarrativePipeline
from .passes import (
    AnalysisInput,
    ComplianceInput,
    WriterInput,
    run_analysis_pass,
    run_compliance_pass,
    run_writer_pass,
    sample_line_items,
)
from .quality import (
    AnalystToneChecker,
    HedgingChecker,
    QualityEvaluator,
    SlopChecker,
    SummaryLengthChecker,
    ValuationLinkChecker,
    VerbosityChecker,
)
from .state import PipelineState

__all__ = [
    # Orchestrator
    "NarrativePipeline",
    # Cache
    "PipelineCache",
    "cache_key",
    # Analysis pass models
    "AnalysisResult",
    "CategoryAnalysis",
    # Analysis pass functions
    "run_analysis_pass",
    "sample_line_items",
    "AnalysisInput",
    # Writer pass models
    "DraftNarrative",
    "DriverNarrative",
    # Writer pass functions
    "run_writer_pass",
    "WriterInput",
    # Compliance pass models and functions
    "FinalNarrative",
    "run_compliance_pass",
    "ComplianceInput",
    # Quality gate models
    "QualityCheckResult",
    "QualityReport",
    # Quality gate checkers
    "HedgingChecker",
    "VerbosityChecker",
    "ValuationLinkChecker",
    "SummaryLengthChecker",
    "AnalystToneChecker",
    "SlopChecker",
    "QualityEvaluator",
    # State container
    "PipelineState",
]
