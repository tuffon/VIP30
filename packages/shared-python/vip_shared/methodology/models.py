from __future__ import annotations

import hashlib
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class GranularityLevel(str, Enum):
    LINE_ITEM = "line_item"
    CATEGORY = "category"
    COVERAGE = "coverage"
    ESTIMATE_TOTAL = "estimate_total"


class MatchMethod(str, Enum):
    ACTIVITY_CODE = "activity_code"
    CAT_SEL = "cat_sel"
    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    UNMATCHED = "unmatched"


class OPStructureType(str, Enum):
    GENERAL = "general"
    PER_LINE = "per_line"
    MIXED = "mixed"
    NONE = "none"


class DataProvenance(BaseModel):
    claim_id: str
    source_estimate: Literal["primary", "comparison"]
    granularity: GranularityLevel
    source_field: str
    raw_value: str

    @classmethod
    def create(
        cls,
        source_estimate: Literal["primary", "comparison"],
        granularity: GranularityLevel | str,
        source_field: str,
        raw_value: object,
    ) -> "DataProvenance":
        granularity_value = (
            granularity.value if isinstance(granularity, GranularityLevel) else str(granularity)
        )
        parts = [
            source_estimate,
            granularity_value,
            source_field,
            str(raw_value),
        ]
        claim_id = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return cls(
            claim_id=claim_id,
            source_estimate=source_estimate,
            granularity=GranularityLevel(granularity_value),
            source_field=source_field,
            raw_value=str(raw_value),
        )


class OPStructure(BaseModel):
    has_general_op: bool
    general_op_pct: Optional[float] = None
    has_per_line_op: bool
    op_items_total: Optional[float] = None
    non_op_items_total: Optional[float] = None
    overhead_total: Optional[float] = None
    profit_total: Optional[float] = None
    depreciate_op: Optional[bool] = None
    structure_type: OPStructureType
    provenance: List[DataProvenance] = Field(default_factory=list)


class DepreciationMethodology(BaseModel):
    is_acv: bool
    depreciate_material: Optional[bool] = None
    depreciate_non_material: Optional[bool] = None
    depreciate_taxes: Optional[bool] = None
    depreciate_removal: Optional[bool] = None
    depreciate_op: Optional[bool] = None
    price_list: Optional[str] = None
    provenance: List[DataProvenance] = Field(default_factory=list)


class LineItemMatch(BaseModel):
    primary_idx: int
    comparison_idx: Optional[int]
    match_method: MatchMethod
    match_score: Optional[float] = None
    primary_description: str
    comparison_description: Optional[str] = None
    primary_amount: Optional[float] = None
    comparison_amount: Optional[float] = None
    delta: Optional[float] = None
    section_name: str
    provenance: DataProvenance


class ScopeAlignmentEntry(BaseModel):
    description: str
    amount: float
    section_name: str
    estimate: Literal["primary", "comparison"]
    provenance: DataProvenance


class ScopeAlignmentMatrix(BaseModel):
    primary_only: List[ScopeAlignmentEntry] = Field(default_factory=list)
    comparison_only: List[ScopeAlignmentEntry] = Field(default_factory=list)
    primary_only_total: float = 0.0
    comparison_only_total: float = 0.0


class CategoryDelta(BaseModel):
    category: str
    primary_amount: float
    comparison_amount: float
    delta: float
    abs_delta: float
    pct_of_total_variance: float
    provenance: List[DataProvenance] = Field(default_factory=list)


class DeltaBreakdown(BaseModel):
    total_primary: float
    total_comparison: float
    total_delta: float
    categories: List[CategoryDelta] = Field(default_factory=list)


class MethodologyResult(BaseModel):
    primary_op: OPStructure
    comparison_op: OPStructure
    primary_depreciation: DepreciationMethodology
    comparison_depreciation: DepreciationMethodology
    op_treatment_differs: bool
    depreciation_approach_differs: bool
    price_list_differs: bool
    locality_factors: Optional[str] = None
    line_matches: List[LineItemMatch] = Field(default_factory=list)
    scope_alignment: ScopeAlignmentMatrix
    delta_breakdown: DeltaBreakdown
    data_granularity: GranularityLevel
