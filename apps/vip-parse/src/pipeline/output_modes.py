from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.methodology.models import MethodologyResult
from src.pipeline.models import FinalNarrative


class OutputMode(str, Enum):
    EXECUTIVE = "executive"
    CARRIER = "carrier"
    LITIGATION = "litigation"
    INTERNAL = "internal"


@dataclass
class ModeFilteredOutput:
    mode: OutputMode
    total_delta: float
    top_drivers: List[dict] = field(default_factory=list)
    structural_flags: List[str] = field(default_factory=list)
    methodology_summary: Optional[str] = None
    scope_observations: List[str] = field(default_factory=list)
    followups: List[str] = field(default_factory=list)
    sections: Dict[str, Any] = field(default_factory=dict)
    include_methodology_sheet: bool = True
    include_scope_sheet: bool = True
    include_category_detail: bool = True


class OutputModeFilter:
    @staticmethod
    def apply(
        mode: OutputMode,
        narrative: FinalNarrative,
        methodology: Optional[MethodologyResult],
        signal_bundle: Optional[Any],
    ) -> ModeFilteredOutput:
        key_drivers = list(getattr(narrative, "key_drivers", []) or [])
        top_drivers = [
            {
                "category": d.category if hasattr(d, "category") else d.get("category"),
                "amounts": d.amounts if hasattr(d, "amounts") else d.get("amounts"),
                "narrative": d.narrative if hasattr(d, "narrative") else d.get("narrative"),
            }
            for d in key_drivers
        ]

        structural_flags: List[str] = []
        if signal_bundle is not None:
            for alert in getattr(signal_bundle, "alert_tags", []) or []:
                sev = getattr(getattr(alert, "severity", None), "value", getattr(alert, "severity", ""))
                structural_flags.append(f"[{sev}] {getattr(alert, 'title', '')}: {getattr(alert, 'detail', '')}".strip())

        total_delta = OutputModeFilter._parse_total_delta_from_overview(getattr(narrative, "overview", ""))
        if total_delta is None:
            total_delta = 0.0

        methodology_summary = None
        if methodology is not None:
            methodology_summary = (
                f"O&P: {methodology.primary_op.structure_type.value} vs {methodology.comparison_op.structure_type.value}; "
                f"Depreciation differs: {methodology.depreciation_approach_differs}; "
                f"Price list differs: {methodology.price_list_differs}; "
                f"Granularity: {methodology.data_granularity.value}"
            )

        base = ModeFilteredOutput(
            mode=mode,
            total_delta=round(float(total_delta), 2),
            top_drivers=top_drivers,
            structural_flags=structural_flags,
            methodology_summary=methodology_summary,
            scope_observations=list(getattr(narrative, "scope_observations", []) or []),
            followups=list(getattr(narrative, "suggested_followups", []) or []),
            sections={
                "overview": getattr(narrative, "overview", ""),
                "key_drivers": top_drivers,
                "scope_observations": list(getattr(narrative, "scope_observations", []) or []),
                "suggested_followups": list(getattr(narrative, "suggested_followups", []) or []),
            },
            include_methodology_sheet=True,
            include_scope_sheet=True,
            include_category_detail=True,
        )

        if mode == OutputMode.INTERNAL:
            return base

        if mode == OutputMode.EXECUTIVE:
            base.top_drivers = base.top_drivers[:3]
            base.sections["key_drivers"] = base.top_drivers
            base.followups = []
            base.sections["suggested_followups"] = []
            base.scope_observations = []
            base.sections["scope_observations"] = []
            base.include_methodology_sheet = False
            base.include_scope_sheet = False
            base.include_category_detail = False
            return base

        if mode == OutputMode.CARRIER:
            return base

        if mode == OutputMode.LITIGATION:
            base.followups = []
            base.sections["suggested_followups"] = []
            return base

        return base

    @staticmethod
    def _parse_total_delta_from_overview(text: str) -> Optional[float]:
        import re

        if not text:
            return None
        # Read first dollar value as heuristic for summary total delta.
        match = re.search(r"\$([\d,]+(?:\.\d{2})?)", text)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
