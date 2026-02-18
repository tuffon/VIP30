from __future__ import annotations

import logging
import math
from typing import Dict, List

from vip_shared.methodology.models import DeltaBreakdown, MethodologyResult

from .models import (
    AlertTag,
    AlertType,
    DiagnosticFollowUp,
    EmphasisFlag,
    RankedImpactRow,
    RankedImpactTable,
    Severity,
    SignalBundle,
)
from .patterns import detect_patterns


logger = logging.getLogger("vip-parse.rules")


class RulesEngine:
    TOP_VARIANCE_PERCENT = 0.20
    MAX_FLAGS = 5
    SCOPE_IMBALANCE_NOTABLE = 5000.0
    SCOPE_IMBALANCE_CRITICAL = 15000.0
    LARGE_UNSPECIFIED_PCT = 15.0

    def evaluate(self, methodology: MethodologyResult) -> SignalBundle:
        ranked = self._build_ranked_impact(methodology.delta_breakdown)
        flags = self._flag_emphasis(ranked)
        alerts = self._detect_alerts(methodology)
        patterns = self._detect_patterns(methodology)
        followups = self._generate_followups(flags, alerts, patterns, methodology)
        self._attach_flag_labels(ranked, flags)
        return SignalBundle(
            ranked_impact=ranked,
            emphasis_flags=flags,
            alert_tags=alerts,
            structural_patterns=patterns,
            diagnostic_followups=followups,
            flags_capped=len(flags) >= self.MAX_FLAGS,
        )

    def _build_ranked_impact(self, delta_breakdown: DeltaBreakdown) -> RankedImpactTable:
        rows: List[RankedImpactRow] = []
        sorted_categories = sorted(
            delta_breakdown.categories,
            key=lambda c: (-float(c.abs_delta), c.category.lower()),
        )
        for idx, cat in enumerate(sorted_categories, start=1):
            rows.append(
                RankedImpactRow(
                    rank=idx,
                    category=cat.category,
                    primary_amount=round(float(cat.primary_amount), 2),
                    comparison_amount=round(float(cat.comparison_amount), 2),
                    delta=round(float(cat.delta), 2),
                    abs_delta=round(float(cat.abs_delta), 2),
                    pct_of_total_variance=round(float(cat.pct_of_total_variance), 2),
                    flags=[],
                )
            )
        return RankedImpactTable(
            rows=rows,
            total_primary=round(float(delta_breakdown.total_primary), 2),
            total_comparison=round(float(delta_breakdown.total_comparison), 2),
            total_delta=round(float(delta_breakdown.total_delta), 2),
            total_abs_variance=round(sum(r.abs_delta for r in rows), 2),
        )

    def _flag_emphasis(self, ranked_impact: RankedImpactTable) -> List[EmphasisFlag]:
        rows = ranked_impact.rows
        if not rows:
            return []
        top_n = max(1, int(math.ceil(len(rows) * self.TOP_VARIANCE_PERCENT)))
        candidate_rows = rows[:top_n]
        flags: List[EmphasisFlag] = []
        for row in candidate_rows:
            if row.pct_of_total_variance >= 25.0 or row.rank == 1:
                severity = Severity.CRITICAL
            elif row.pct_of_total_variance >= 10.0:
                severity = Severity.NOTABLE
            else:
                severity = Severity.INFORMATIONAL
            flags.append(
                EmphasisFlag(
                    category=row.category,
                    severity=severity,
                    delta=row.delta,
                    abs_delta=row.abs_delta,
                    pct_of_total_variance=row.pct_of_total_variance,
                    reason=(
                        f"Top variance driver: {row.pct_of_total_variance:.1f}% of total variance "
                        f"(${row.abs_delta:,.2f})"
                    ),
                )
            )
        flags.sort(key=lambda f: (-f.pct_of_total_variance, f.category.lower()))
        return flags[: self.MAX_FLAGS]

    def _detect_alerts(self, methodology: MethodologyResult) -> List[AlertTag]:
        alerts: List[AlertTag] = []
        p_has_op = methodology.primary_op.structure_type.value != "none"
        c_has_op = methodology.comparison_op.structure_type.value != "none"
        if p_has_op != c_has_op:
            missing_side = "primary" if not p_has_op else "comparison"
            alerts.append(
                AlertTag(
                    alert_type=AlertType.MISSING_OP,
                    severity=Severity.CRITICAL,
                    title=f"Missing O&P in {missing_side} estimate",
                    detail="One estimate includes O&P while the other does not.",
                    affected_amount=round(
                        abs((methodology.primary_op.overhead_total or 0.0) - (methodology.comparison_op.overhead_total or 0.0))
                        + abs((methodology.primary_op.profit_total or 0.0) - (methodology.comparison_op.profit_total or 0.0)),
                        2,
                    ),
                )
            )
        elif methodology.op_treatment_differs:
            alerts.append(
                AlertTag(
                    alert_type=AlertType.OP_STRUCTURE_MISMATCH,
                    severity=Severity.NOTABLE,
                    title="O&P structure mismatch",
                    detail="Both estimates include O&P but treatment differs.",
                    affected_amount=None,
                )
            )

        if methodology.depreciation_approach_differs:
            acv_mismatch = methodology.primary_depreciation.is_acv != methodology.comparison_depreciation.is_acv
            alerts.append(
                AlertTag(
                    alert_type=AlertType.DEPRECIATION_MISMATCH,
                    severity=Severity.CRITICAL if acv_mismatch else Severity.NOTABLE,
                    title="Depreciation approach mismatch",
                    detail="Depreciation settings differ between estimates.",
                    affected_amount=round(abs(methodology.delta_breakdown.total_delta), 2),
                )
            )

        unmatched_max = round(
            max(float(methodology.scope_alignment.primary_only_total), float(methodology.scope_alignment.comparison_only_total)),
            2,
        )
        if unmatched_max > self.SCOPE_IMBALANCE_NOTABLE:
            sev = Severity.CRITICAL if unmatched_max > self.SCOPE_IMBALANCE_CRITICAL else Severity.NOTABLE
            alerts.append(
                AlertTag(
                    alert_type=AlertType.SCOPE_IMBALANCE,
                    severity=sev,
                    title="Scope imbalance detected",
                    detail="Unmatched scope appears materially in one estimate.",
                    affected_amount=unmatched_max,
                )
            )

        for category in methodology.delta_breakdown.categories:
            if category.category == "Other / Unclassified" and float(category.pct_of_total_variance) > self.LARGE_UNSPECIFIED_PCT:
                alerts.append(
                    AlertTag(
                        alert_type=AlertType.LARGE_UNSPECIFIED,
                        severity=Severity.NOTABLE,
                        title="Large unclassified variance",
                        detail="Unclassified category contributes significant share of variance.",
                        affected_amount=round(float(category.abs_delta), 2),
                    )
                )
                break

        if methodology.price_list_differs:
            alerts.append(
                AlertTag(
                    alert_type=AlertType.PRICE_LIST_MISMATCH,
                    severity=Severity.INFORMATIONAL,
                    title="Price list mismatch",
                    detail="Estimates use different price lists or effective periods.",
                    affected_amount=None,
                )
            )

        alerts.sort(key=lambda a: (self._priority_rank(a.severity), a.alert_type.value))
        return alerts

    def _detect_patterns(self, methodology: MethodologyResult):
        return detect_patterns(methodology)

    def _generate_followups(
        self,
        emphasis_flags: List[EmphasisFlag],
        alert_tags: List[AlertTag],
        structural_patterns,
        methodology: MethodologyResult,
    ) -> List[DiagnosticFollowUp]:
        followups: List[DiagnosticFollowUp] = []
        seen: set[str] = set()

        def add(trigger: str, action: str, priority: Severity, category: str | None = None) -> None:
            key = f"{trigger}|{action}|{priority.value}|{category or ''}"
            if key in seen:
                return
            seen.add(key)
            followups.append(DiagnosticFollowUp(trigger=trigger, action=action, priority=priority, category=category))

        for flag in emphasis_flags:
            if flag.severity in (Severity.CRITICAL, Severity.NOTABLE):
                add(
                    trigger=f"Emphasis flag: {flag.category}",
                    action=f"Verify {flag.category} line items — ${flag.abs_delta:,.2f} variance ({flag.pct_of_total_variance:.1f}% of total).",
                    priority=flag.severity,
                    category=flag.category,
                )

        for alert in alert_tags:
            if alert.alert_type == AlertType.MISSING_OP:
                add(alert.title, "Request missing estimate O&P breakdown to confirm overhead and profit treatment.", alert.severity)
            elif alert.alert_type == AlertType.DEPRECIATION_MISMATCH:
                add(alert.title, "Confirm depreciation methodology with both estimators — ACV vs RCV impacts recoverable amount.", alert.severity)
            elif alert.alert_type == AlertType.SCOPE_IMBALANCE:
                count = len(methodology.scope_alignment.primary_only) + len(methodology.scope_alignment.comparison_only)
                amt = max(methodology.scope_alignment.primary_only_total, methodology.scope_alignment.comparison_only_total)
                add(alert.title, f"Cross-reference scope with loss assessment — {count} unmatched items totaling ${amt:,.2f}.", alert.severity)
            elif alert.alert_type == AlertType.LARGE_UNSPECIFIED:
                add(alert.title, "Request category breakdown for unclassified items to attribute variance to trades.", alert.severity)
            elif alert.alert_type == AlertType.PRICE_LIST_MISMATCH:
                add(alert.title, "Confirm both estimates use the same price list and effective date.", alert.severity)
            elif alert.alert_type == AlertType.OP_STRUCTURE_MISMATCH:
                add(alert.title, "Confirm whether O&P is applied globally or embedded in line-item pricing.", alert.severity)

        for pattern in structural_patterns:
            if pattern.pattern_type.value == "partial_vs_full_restoration":
                add("Pattern: partial vs full restoration", "Reconcile restoration depth assumptions and room-level scope boundaries.", Severity.NOTABLE)
            elif pattern.pattern_type.value == "systematic_pricing_difference":
                add("Pattern: systematic pricing", "Compare matched line-item unit rates to isolate systematic pricing bias.", Severity.NOTABLE)
            elif pattern.pattern_type.value == "scope_asymmetry":
                add("Pattern: scope asymmetry", "Validate unmatched items against field documentation and causation notes.", Severity.NOTABLE)

        followups.sort(key=lambda f: (self._priority_rank(f.priority), (f.category or ""), f.action))
        return followups

    def _attach_flag_labels(self, ranked: RankedImpactTable, flags: List[EmphasisFlag]) -> None:
        by_cat: Dict[str, List[str]] = {}
        for flag in flags:
            by_cat.setdefault(flag.category, []).append(flag.severity.value)
        for row in ranked.rows:
            row.flags = sorted(by_cat.get(row.category, []))

    def _priority_rank(self, sev: Severity) -> int:
        if sev == Severity.CRITICAL:
            return 0
        if sev == Severity.NOTABLE:
            return 1
        return 2
