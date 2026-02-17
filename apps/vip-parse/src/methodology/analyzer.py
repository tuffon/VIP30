from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.bid_comp.core import CATEGORY_FALLBACK, CATEGORY_KEYWORDS
from src.bid_comp.matchers import HeuristicMatcher
from src.bid_comp.normalize import normalize_label, normalize_money
from src.bid_comp.taxonomy import canonicalize_group

from .models import (
    CategoryDelta,
    DataProvenance,
    DeltaBreakdown,
    DepreciationMethodology,
    GranularityLevel,
    LineItemMatch,
    MatchMethod,
    MethodologyResult,
    OPStructure,
    OPStructureType,
    ScopeAlignmentEntry,
    ScopeAlignmentMatrix,
)

logger = logging.getLogger("vip-parse.methodology")

_ACTIVITY_RE = re.compile(r"^\s*([A-Z]{2,4})\s+([A-Z0-9\-]{1,20})(?:\s+([A-Z0-9+\-]{1,10}))?")


def _round_money(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def _categorize_label(label: str) -> str:
    normalized = normalize_label(label)
    for keyword, category in CATEGORY_KEYWORDS:
        if keyword in normalized:
            return category
    return CATEGORY_FALLBACK


class MethodologyAnalyzer:
    def __init__(self, matcher: Optional[HeuristicMatcher] = None) -> None:
        self.matcher = matcher or HeuristicMatcher()
        self._primary_items: List[Dict[str, Any]] = []
        self._comparison_items: List[Dict[str, Any]] = []
        self._matched_comparison_indices: set[int] = set()

    def analyze(self, primary_payload: dict, comparison_payload: dict) -> MethodologyResult:
        self._primary_items = self._extract_line_items(primary_payload, "primary")
        self._comparison_items = self._extract_line_items(comparison_payload, "comparison")
        self._matched_comparison_indices = set()

        primary_op = self._detect_op_structure(primary_payload, "primary")
        comparison_op = self._detect_op_structure(comparison_payload, "comparison")
        primary_depr = self._detect_depreciation(primary_payload, "primary")
        comparison_depr = self._detect_depreciation(comparison_payload, "comparison")
        line_matches = self._match_line_items(primary_payload, comparison_payload)
        scope_alignment = self._build_scope_alignment(line_matches)
        delta_breakdown = self._build_delta_breakdown(primary_payload, comparison_payload)

        data_granularity = self._determine_granularity(primary_payload, comparison_payload)
        primary_price_list = normalize_label(primary_depr.price_list or "")
        comparison_price_list = normalize_label(comparison_depr.price_list or "")
        locality_factors = self._derive_locality_factors(primary_payload, comparison_payload)

        return MethodologyResult(
            primary_op=primary_op,
            comparison_op=comparison_op,
            primary_depreciation=primary_depr,
            comparison_depreciation=comparison_depr,
            op_treatment_differs=self._op_differs(primary_op, comparison_op),
            depreciation_approach_differs=self._depreciation_differs(primary_depr, comparison_depr),
            price_list_differs=bool(primary_price_list and comparison_price_list and primary_price_list != comparison_price_list),
            locality_factors=locality_factors,
            line_matches=line_matches,
            scope_alignment=scope_alignment,
            delta_breakdown=delta_breakdown,
            data_granularity=data_granularity,
        )

    def _extract_line_items(self, payload: dict, estimate: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        sections = payload.get("sections")
        if not isinstance(sections, list):
            return results

        for s_idx, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            section_name = str(section.get("section_name") or section.get("name") or "")
            line_items = section.get("line_items")
            if not isinstance(line_items, list):
                continue
            for l_idx, item in enumerate(line_items):
                if not isinstance(item, dict):
                    continue
                if item.get("type") not in (None, "line_item"):
                    continue
                description = str(item.get("description") or item.get("item") or "").strip()
                amount = _round_money(normalize_money(item.get("total") or item.get("amount")))
                cat = str(item.get("cat") or item.get("category_code") or "").strip().upper() or None
                sel = str(item.get("sel") or item.get("selector") or "").strip().upper() or None
                act = str(item.get("act") or item.get("activity") or "").strip().upper() or None
                if not (cat and sel):
                    parsed = self._parse_activity_code(description)
                    if parsed:
                        cat, sel, act = parsed
                results.append(
                    {
                        "estimate": estimate,
                        "section_name": section_name,
                        "description": description,
                        "amount": amount,
                        "cat": cat,
                        "sel": sel,
                        "act": act,
                        "source_field": f"sections[{s_idx}].line_items[{l_idx}]",
                    }
                )
        return results

    def _parse_activity_code(self, description: str) -> Optional[Tuple[str, str, Optional[str]]]:
        match = _ACTIVITY_RE.match(description or "")
        if not match:
            return None
        cat = (match.group(1) or "").upper()
        sel = (match.group(2) or "").upper()
        act = (match.group(3) or "").upper() if match.group(3) else None
        if not cat or not sel:
            return None
        return cat, sel, act

    def _detect_op_structure(self, payload: dict, estimate_label: str) -> OPStructure:
        provenance: List[DataProvenance] = []
        recap = self._extract_recap(payload)
        subtotals = recap.get("subtotals") if isinstance(recap.get("subtotals"), list) else []
        op_items_total: Optional[float] = None
        non_op_items_total: Optional[float] = None
        overhead_total: Optional[float] = None
        profit_total: Optional[float] = None

        for idx, subtotal in enumerate(subtotals):
            if not isinstance(subtotal, dict):
                continue
            label = str(subtotal.get("label") or "")
            total = _round_money(normalize_money(subtotal.get("total")))
            if total is None:
                continue
            group = canonicalize_group(label)
            field_path = f"recaps_and_summaries.recap_by_category.subtotals[{idx}].total"
            if group == "O&P ITEMS":
                op_items_total = total
                provenance.append(DataProvenance.create(estimate_label, GranularityLevel.CATEGORY, field_path, subtotal.get("total")))
            elif group == "NON-O&P ITEMS":
                non_op_items_total = total
                provenance.append(DataProvenance.create(estimate_label, GranularityLevel.CATEGORY, field_path, subtotal.get("total")))
            elif group == "OVERHEAD":
                overhead_total = total
                provenance.append(DataProvenance.create(estimate_label, GranularityLevel.CATEGORY, field_path, subtotal.get("total")))
            elif group == "PROFIT":
                profit_total = total
                provenance.append(DataProvenance.create(estimate_label, GranularityLevel.CATEGORY, field_path, subtotal.get("total")))

        case_metadata = payload.get("case_metadata") if isinstance(payload.get("case_metadata"), dict) else {}
        line_totals = case_metadata.get("line_item_totals") if isinstance(case_metadata.get("line_item_totals"), dict) else {}
        op_total = _round_money(normalize_money(line_totals.get("overhead_profit")))
        general_op_pct = _round_money(normalize_money(case_metadata.get("overhead_profit_pct")))
        depreciate_op = case_metadata.get("depreciate_op")

        if op_total is not None:
            provenance.append(
                DataProvenance.create(
                    estimate_label,
                    GranularityLevel.ESTIMATE_TOTAL,
                    "case_metadata.line_item_totals.overhead_profit",
                    line_totals.get("overhead_profit"),
                )
            )
            if overhead_total is None and profit_total is None:
                overhead_total = _round_money(op_total / 2.0)
                profit_total = _round_money(op_total / 2.0)

        has_per_line_op = any(
            item.get("cat") and item.get("sel") and item.get("act") and "O&P" in normalize_label(item.get("description") or "")
            for item in (self._primary_items if estimate_label == "primary" else self._comparison_items)
        )
        has_general_op = any(v is not None and v > 0 for v in (op_total, op_items_total, overhead_total, profit_total))
        if has_general_op and has_per_line_op:
            structure_type = OPStructureType.MIXED
        elif has_general_op:
            structure_type = OPStructureType.GENERAL
        elif has_per_line_op:
            structure_type = OPStructureType.PER_LINE
        else:
            structure_type = OPStructureType.NONE

        return OPStructure(
            has_general_op=has_general_op,
            general_op_pct=general_op_pct,
            has_per_line_op=has_per_line_op,
            op_items_total=op_items_total,
            non_op_items_total=non_op_items_total,
            overhead_total=overhead_total,
            profit_total=profit_total,
            depreciate_op=bool(depreciate_op) if isinstance(depreciate_op, bool) else None,
            structure_type=structure_type,
            provenance=sorted(provenance, key=lambda p: p.claim_id),
        )

    def _detect_depreciation(self, payload: dict, estimate_label: str) -> DepreciationMethodology:
        case_metadata = payload.get("case_metadata") if isinstance(payload.get("case_metadata"), dict) else {}
        provenance: List[DataProvenance] = []
        fields = [
            "depreciate_material",
            "depreciate_non_material",
            "depreciate_taxes",
            "depreciate_removal",
            "depreciate_op",
            "price_list",
        ]
        for field in fields:
            if field in case_metadata and case_metadata.get(field) is not None:
                provenance.append(
                    DataProvenance.create(
                        estimate_label,
                        GranularityLevel.ESTIMATE_TOTAL,
                        f"case_metadata.{field}",
                        case_metadata.get(field),
                    )
                )

        coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
        is_acv = False
        for cov_key, cov_data in coverage.items():
            if not isinstance(cov_data, dict):
                continue
            dep_pct = _round_money(normalize_money(cov_data.get("depreciation_pct")))
            dep_amt = _round_money(normalize_money(cov_data.get("depreciation")))
            if (dep_pct and dep_pct > 0) or (dep_amt and dep_amt > 0):
                is_acv = True
                provenance.append(
                    DataProvenance.create(
                        estimate_label,
                        GranularityLevel.COVERAGE,
                        f"coverage.{cov_key}.depreciation",
                        dep_amt if dep_amt is not None else dep_pct,
                    )
                )

        return DepreciationMethodology(
            is_acv=is_acv,
            depreciate_material=self._as_optional_bool(case_metadata.get("depreciate_material")),
            depreciate_non_material=self._as_optional_bool(case_metadata.get("depreciate_non_material")),
            depreciate_taxes=self._as_optional_bool(case_metadata.get("depreciate_taxes")),
            depreciate_removal=self._as_optional_bool(case_metadata.get("depreciate_removal")),
            depreciate_op=self._as_optional_bool(case_metadata.get("depreciate_op")),
            price_list=(str(case_metadata.get("price_list")).strip() if case_metadata.get("price_list") else None),
            provenance=sorted(provenance, key=lambda p: p.claim_id),
        )

    def _match_line_items(self, primary_payload: dict, comparison_payload: dict) -> List[LineItemMatch]:
        del primary_payload, comparison_payload
        if not self._primary_items:
            return []

        left_labels: List[str] = []
        right_labels: List[str] = []
        left_lookup: Dict[str, Dict[str, Any]] = {}
        right_lookup: Dict[str, Dict[str, Any]] = {}

        for idx, item in enumerate(self._primary_items):
            label = self._unique_label(item.get("description") or f"line-{idx}", idx)
            left_labels.append(label)
            left_lookup[normalize_label(label)] = {**item, "primary_idx": idx}
        for idx, item in enumerate(self._comparison_items):
            label = self._unique_label(item.get("description") or f"line-{idx}", idx)
            right_labels.append(label)
            right_lookup[normalize_label(label)] = {**item, "comparison_idx": idx}

        matched = self.matcher.match_sets(
            left_labels,
            right_labels,
            left_items=self._primary_items,
            right_items=self._comparison_items,
        )

        output: List[LineItemMatch] = []
        for left_norm, result in matched.items():
            left_item = left_lookup.get(left_norm)
            if not left_item:
                continue
            right_item = right_lookup.get(normalize_label(result.right or "")) if result.right else None
            if right_item and isinstance(right_item.get("comparison_idx"), int):
                self._matched_comparison_indices.add(int(right_item["comparison_idx"]))
            primary_amount = _round_money(left_item.get("amount"))
            comparison_amount = _round_money(right_item.get("amount")) if right_item else None
            delta = _round_money((primary_amount or 0.0) - (comparison_amount or 0.0)) if right_item else None
            output.append(
                LineItemMatch(
                    primary_idx=int(left_item.get("primary_idx", 0)),
                    comparison_idx=int(right_item["comparison_idx"]) if right_item else None,
                    match_method=self._map_match_method(result.method),
                    match_score=_round_money(result.score) if result.score is not None else None,
                    primary_description=str(left_item.get("description") or ""),
                    comparison_description=str(right_item.get("description")) if right_item else None,
                    primary_amount=primary_amount,
                    comparison_amount=comparison_amount,
                    delta=delta,
                    section_name=str(left_item.get("section_name") or ""),
                    provenance=DataProvenance.create(
                        "primary",
                        GranularityLevel.LINE_ITEM,
                        f"{left_item.get('source_field')}.total",
                        left_item.get("amount"),
                    ),
                )
            )

        output.sort(key=lambda item: (normalize_label(item.section_name), item.primary_idx))
        return output

    def _build_scope_alignment(self, line_matches: List[LineItemMatch]) -> ScopeAlignmentMatrix:
        primary_only: List[ScopeAlignmentEntry] = []
        comparison_only: List[ScopeAlignmentEntry] = []

        for match in line_matches:
            if match.comparison_idx is None:
                primary_only.append(
                    ScopeAlignmentEntry(
                        description=match.primary_description,
                        amount=_round_money(match.primary_amount or 0.0) or 0.0,
                        section_name=match.section_name,
                        estimate="primary",
                        provenance=match.provenance,
                    )
                )

        for idx, item in enumerate(self._comparison_items):
            if idx in self._matched_comparison_indices:
                continue
            amount = _round_money(item.get("amount"))
            if amount is None:
                continue
            comparison_only.append(
                ScopeAlignmentEntry(
                    description=str(item.get("description") or ""),
                    amount=amount,
                    section_name=str(item.get("section_name") or ""),
                    estimate="comparison",
                    provenance=DataProvenance.create(
                        "comparison",
                        GranularityLevel.LINE_ITEM,
                        f"{item.get('source_field')}.total",
                        item.get("amount"),
                    ),
                )
            )

        primary_only.sort(key=lambda x: (-x.amount, normalize_label(x.description)))
        comparison_only.sort(key=lambda x: (-x.amount, normalize_label(x.description)))
        return ScopeAlignmentMatrix(
            primary_only=primary_only,
            comparison_only=comparison_only,
            primary_only_total=_round_money(sum(x.amount for x in primary_only)) or 0.0,
            comparison_only_total=_round_money(sum(x.amount for x in comparison_only)) or 0.0,
        )

    def _build_delta_breakdown(self, primary_payload: dict, comparison_payload: dict) -> DeltaBreakdown:
        primary_recap = self._extract_recap(primary_payload)
        comparison_recap = self._extract_recap(comparison_payload)
        primary_by_category, primary_prov = self._category_totals(primary_recap, "primary")
        comparison_by_category, comparison_prov = self._category_totals(comparison_recap, "comparison")

        all_categories = sorted(set(primary_by_category) | set(comparison_by_category), key=normalize_label)
        rows: List[CategoryDelta] = []
        for category in all_categories:
            p_amount = _round_money(primary_by_category.get(category, 0.0)) or 0.0
            c_amount = _round_money(comparison_by_category.get(category, 0.0)) or 0.0
            delta = _round_money(p_amount - c_amount) or 0.0
            abs_delta = _round_money(abs(delta)) or 0.0
            provenance = sorted(
                primary_prov.get(category, []) + comparison_prov.get(category, []),
                key=lambda p: p.claim_id,
            )
            rows.append(
                CategoryDelta(
                    category=category,
                    primary_amount=p_amount,
                    comparison_amount=c_amount,
                    delta=delta,
                    abs_delta=abs_delta,
                    pct_of_total_variance=0.0,
                    provenance=provenance,
                )
            )

        total_variance = sum(row.abs_delta for row in rows) or 1.0
        for row in rows:
            row.pct_of_total_variance = _round_money((row.abs_delta / total_variance) * 100.0) or 0.0
        rows.sort(key=lambda r: (-r.abs_delta, normalize_label(r.category)))

        total_primary = self._extract_grand_total(primary_payload, primary_by_category)
        total_comparison = self._extract_grand_total(comparison_payload, comparison_by_category)
        return DeltaBreakdown(
            total_primary=total_primary,
            total_comparison=total_comparison,
            total_delta=_round_money(total_primary - total_comparison) or 0.0,
            categories=rows,
        )

    def _extract_recap(self, payload: dict) -> dict:
        recaps = payload.get("recaps_and_summaries")
        if isinstance(recaps, dict) and isinstance(recaps.get("recap_by_category"), dict):
            return recaps["recap_by_category"]
        recap = payload.get("recap_by_category")
        return recap if isinstance(recap, dict) else {}

    def _category_totals(
        self, recap: dict, estimate: Literal["primary", "comparison"]
    ) -> Tuple[Dict[str, float], Dict[str, List[DataProvenance]]]:
        totals: Dict[str, float] = {}
        provenance: Dict[str, List[DataProvenance]] = {}
        subtotals = recap.get("subtotals") if isinstance(recap.get("subtotals"), list) else []
        for idx, entry in enumerate(subtotals):
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label") or "")
            amount = _round_money(normalize_money(entry.get("total")))
            if amount is None:
                continue
            category = _categorize_label(label)
            totals[category] = _round_money((totals.get(category, 0.0) + amount)) or 0.0
            provenance.setdefault(category, []).append(
                DataProvenance.create(
                    estimate,
                    GranularityLevel.CATEGORY,
                    f"recaps_and_summaries.recap_by_category.subtotals[{idx}].total",
                    entry.get("total"),
                )
            )
        return totals, provenance

    def _extract_grand_total(self, payload: dict, category_totals: Dict[str, float]) -> float:
        case_metadata = payload.get("case_metadata") if isinstance(payload.get("case_metadata"), dict) else {}
        line_totals = case_metadata.get("line_item_totals") if isinstance(case_metadata.get("line_item_totals"), dict) else {}
        grand = _round_money(normalize_money(line_totals.get("grand_total")))
        if grand is not None:
            return grand
        return _round_money(sum(category_totals.values())) or 0.0

    def _determine_granularity(self, primary_payload: dict, comparison_payload: dict) -> GranularityLevel:
        if self._primary_items or self._comparison_items:
            return GranularityLevel.LINE_ITEM
        if self._extract_recap(primary_payload) or self._extract_recap(comparison_payload):
            return GranularityLevel.CATEGORY
        if isinstance(primary_payload.get("coverage"), dict) or isinstance(comparison_payload.get("coverage"), dict):
            return GranularityLevel.COVERAGE
        return GranularityLevel.ESTIMATE_TOTAL

    def _derive_locality_factors(self, primary_payload: dict, comparison_payload: dict) -> Optional[str]:
        primary_price_list = (
            (primary_payload.get("case_metadata") or {}).get("price_list")
            if isinstance(primary_payload.get("case_metadata"), dict)
            else None
        )
        comparison_price_list = (
            (comparison_payload.get("case_metadata") or {}).get("price_list")
            if isinstance(comparison_payload.get("case_metadata"), dict)
            else None
        )
        if primary_price_list and comparison_price_list and str(primary_price_list) != str(comparison_price_list):
            return f"{primary_price_list} vs {comparison_price_list}"
        return str(primary_price_list or comparison_price_list) if (primary_price_list or comparison_price_list) else None

    def _op_differs(self, primary: OPStructure, comparison: OPStructure) -> bool:
        return (
            primary.structure_type != comparison.structure_type
            or (primary.general_op_pct or 0.0) != (comparison.general_op_pct or 0.0)
            or bool(primary.has_general_op) != bool(comparison.has_general_op)
            or bool(primary.has_per_line_op) != bool(comparison.has_per_line_op)
        )

    def _depreciation_differs(self, primary: DepreciationMethodology, comparison: DepreciationMethodology) -> bool:
        return (
            primary.is_acv != comparison.is_acv
            or primary.depreciate_material != comparison.depreciate_material
            or primary.depreciate_non_material != comparison.depreciate_non_material
            or primary.depreciate_taxes != comparison.depreciate_taxes
            or primary.depreciate_removal != comparison.depreciate_removal
            or primary.depreciate_op != comparison.depreciate_op
        )

    def _as_optional_bool(self, value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        return None

    def _map_match_method(self, value: str) -> MatchMethod:
        normalized = normalize_label(value)
        if normalized.startswith("ACTIVITY_CODE"):
            return MatchMethod.ACTIVITY_CODE
        if normalized.startswith("CAT_SEL"):
            return MatchMethod.CAT_SEL
        if normalized.startswith("EXACT"):
            return MatchMethod.EXACT
        if normalized.startswith("ALIAS"):
            return MatchMethod.ALIAS
        if normalized.startswith("FUZZY"):
            return MatchMethod.FUZZY
        return MatchMethod.UNMATCHED

    def _unique_label(self, description: str, index: int) -> str:
        clean = (description or "").strip() or f"line-{index}"
        return f"{clean} __idx_{index}"
