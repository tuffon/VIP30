from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    NOTABLE = "notable"
    INFORMATIONAL = "informational"


class AlertType(str, Enum):
    MISSING_OP = "missing_op"
    SCOPE_IMBALANCE = "scope_imbalance"
    DEPRECIATION_MISMATCH = "depreciation_mismatch"
    LARGE_UNSPECIFIED = "large_unspecified"
    OP_STRUCTURE_MISMATCH = "op_structure_mismatch"
    PRICE_LIST_MISMATCH = "price_list_mismatch"


class PatternType(str, Enum):
    PARTIAL_VS_FULL_RESTORATION = "partial_vs_full_restoration"
    SYSTEMATIC_PRICING_DIFFERENCE = "systematic_pricing_difference"
    SCOPE_ASYMMETRY = "scope_asymmetry"


class EmphasisFlag(BaseModel):
    category: str
    severity: Severity
    delta: float
    abs_delta: float
    pct_of_total_variance: float
    reason: str


class AlertTag(BaseModel):
    alert_type: AlertType
    severity: Severity
    title: str
    detail: str
    affected_amount: Optional[float] = None


class StructuralPattern(BaseModel):
    pattern_type: PatternType
    description: str
    evidence: List[str] = Field(default_factory=list)
    estimated_impact: Optional[float] = None


class DiagnosticFollowUp(BaseModel):
    trigger: str
    action: str
    priority: Severity
    category: Optional[str] = None


class RankedImpactRow(BaseModel):
    rank: int
    category: str
    primary_amount: float
    comparison_amount: float
    delta: float
    abs_delta: float
    pct_of_total_variance: float
    flags: List[str] = Field(default_factory=list)


class RankedImpactTable(BaseModel):
    rows: List[RankedImpactRow] = Field(default_factory=list)
    total_primary: float
    total_comparison: float
    total_delta: float
    total_abs_variance: float


class SignalBundle(BaseModel):
    ranked_impact: RankedImpactTable
    emphasis_flags: List[EmphasisFlag] = Field(default_factory=list)
    alert_tags: List[AlertTag] = Field(default_factory=list)
    structural_patterns: List[StructuralPattern] = Field(default_factory=list)
    diagnostic_followups: List[DiagnosticFollowUp] = Field(default_factory=list)
    flags_capped: bool = False
