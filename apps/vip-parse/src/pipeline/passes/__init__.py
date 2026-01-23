"""
Pipeline passes for the multi-pass LLM narrative generation.

This module contains the individual pass implementations:
- Analysis Pass: Extract structured comparison data from estimate pairs
- Writer Pass: Generate adjuster-tone narratives from analysis results
- Compliance Pass: Rewrite narratives that fail quality gates
"""

from .analysis import AnalysisInput, run_analysis_pass, sample_line_items
from .writer import WriterInput, run_writer_pass
from .compliance import ComplianceInput, run_compliance_pass

__all__ = [
    "run_analysis_pass",
    "sample_line_items",
    "AnalysisInput",
    "run_writer_pass",
    "WriterInput",
    "run_compliance_pass",
    "ComplianceInput",
]
