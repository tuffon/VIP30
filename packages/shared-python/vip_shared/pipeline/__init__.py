"""
Pipeline module for multi-pass LLM narrative generation.

This module provides:
- Data contracts (Pydantic models) for pipeline pass inputs/outputs
- PipelineState container for intermediate results
- Quality gate checkers for deterministic narrative validation
- Pass implementations (analysis, writer, compliance)
- NarrativePipeline orchestrator for coordinating all passes
- CostDriverPipeline orchestrator for the v2.6 pipeline rewrite
- PipelineCache for Redis-based caching of pass results

Usage:
    from vip_shared.pipeline import NarrativePipeline, PipelineState
    from vip_shared.pipeline import AnalysisResult, DraftNarrative, FinalNarrative
    from vip_shared.pipeline import QualityEvaluator
    from vip_shared.pipeline import run_analysis_pass, run_writer_pass, run_compliance_pass
    from vip_shared.pipeline import PipelineCache, cache_key
"""

from .cache import PipelineCache, cache_key
from .cost_driver_pipeline import CostDriverPipeline
from .models import (
    AnalysisResult,
    CategoryAnalysis,
    DraftNarrative,
    DriverAnalysisResult,
    DriverNarrative,
    FinalNarrative,
    SummaryResult,
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
    EvidenceGroundingChecker,
    HedgingChecker,
    JudgmentLanguageChecker,
    MethodologyNeutralityChecker,
    QuantificationChecker,
    QualityEvaluator,
)
from .state import PipelineState

__all__ = [
    # Orchestrator
    "NarrativePipeline",
    "CostDriverPipeline",
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
    "DriverAnalysisResult",
    "DriverNarrative",
    # Writer pass functions
    "run_writer_pass",
    "WriterInput",
    # Compliance pass models and functions
    "FinalNarrative",
    "SummaryResult",
    "run_compliance_pass",
    "ComplianceInput",
    # Quality gate models
    "QualityCheckResult",
    "QualityReport",
    # Quality gate checkers
    "HedgingChecker",
    "JudgmentLanguageChecker",
    "QuantificationChecker",
    "EvidenceGroundingChecker",
    "MethodologyNeutralityChecker",
    "QualityEvaluator",
    # State container
    "PipelineState",
]
