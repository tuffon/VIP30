from __future__ import annotations

from typing import List

from vip_shared.methodology.models import MethodologyResult

from .models import PatternType, StructuralPattern


def detect_partial_vs_full_restoration(methodology: MethodologyResult) -> List[StructuralPattern]:
    out: List[StructuralPattern] = []
    p_count = len(methodology.scope_alignment.primary_only)
    c_count = len(methodology.scope_alignment.comparison_only)
    p_total = round(float(methodology.scope_alignment.primary_only_total or 0.0), 2)
    c_total = round(float(methodology.scope_alignment.comparison_only_total or 0.0), 2)
    count_trigger = (p_count >= max(3, int(c_count * 1.3))) or (c_count >= max(3, int(p_count * 1.3)))
    amt_trigger = (p_total > c_total * 1.2 and p_total > 0) or (c_total > p_total * 1.2 and c_total > 0)
    if count_trigger or amt_trigger:
        dominant = "primary" if (p_total > c_total or p_count > c_count) else "comparison"
        counterpart = "comparison" if dominant == "primary" else "primary"
        sample = methodology.scope_alignment.primary_only if dominant == "primary" else methodology.scope_alignment.comparison_only
        evidence = [
            f"{dominant} unique count={p_count if dominant=='primary' else c_count}",
            f"{counterpart} unique count={c_count if dominant=='primary' else p_count}",
            f"{dominant} unique amount=${p_total if dominant=='primary' else c_total:,.2f}",
            f"{counterpart} unique amount=${c_total if dominant=='primary' else p_total:,.2f}",
        ]
        evidence.extend([f"scope-only item: {x.description} (${x.amount:,.2f})" for x in sample[:3]])
        out.append(
            StructuralPattern(
                pattern_type=PatternType.PARTIAL_VS_FULL_RESTORATION,
                description=f"{dominant} appears to include broader restoration scope while {counterpart} appears partial on matched scope.",
                evidence=evidence,
                estimated_impact=round(abs(p_total - c_total), 2),
            )
        )
    return out


def detect_systematic_pricing(methodology: MethodologyResult) -> List[StructuralPattern]:
    out: List[StructuralPattern] = []
    ratios: List[float] = []
    positive = 0
    negative = 0
    samples: List[str] = []
    for match in methodology.line_matches:
        if match.comparison_amount is None or match.primary_amount is None or match.comparison_amount == 0:
            continue
        ratio = float(match.primary_amount) / float(match.comparison_amount)
        ratios.append(ratio)
        if ratio > 1.0:
            positive += 1
        elif ratio < 1.0:
            negative += 1
        if len(samples) < 3:
            samples.append(
                f"{match.primary_description[:60]} :: ${match.primary_amount:,.2f} vs ${match.comparison_amount:,.2f} (x{ratio:.2f})"
            )
    total = len(ratios)
    if total >= 5:
        bias = max(positive, negative) / total
        if bias >= 0.60:
            direction = "higher" if positive >= negative else "lower"
            evidence = [
                f"matched items analyzed={total}",
                f"directional bias={bias:.1%}",
                f"average ratio={sum(ratios)/total:.2f}",
            ] + samples
            if methodology.price_list_differs:
                evidence.append("price lists differ across estimates")
            out.append(
                StructuralPattern(
                    pattern_type=PatternType.SYSTEMATIC_PRICING_DIFFERENCE,
                    description=f"Primary pricing is systematically {direction} across matched items.",
                    evidence=evidence,
                    estimated_impact=round(abs(methodology.delta_breakdown.total_delta), 2),
                )
            )
    return out


def detect_scope_asymmetry(methodology: MethodologyResult) -> List[StructuralPattern]:
    out: List[StructuralPattern] = []
    p_total = round(float(methodology.scope_alignment.primary_only_total or 0.0), 2)
    c_total = round(float(methodology.scope_alignment.comparison_only_total or 0.0), 2)
    base_p = max(float(methodology.delta_breakdown.total_primary or 0.0), 1.0)
    base_c = max(float(methodology.delta_breakdown.total_comparison or 0.0), 1.0)
    p_ratio = p_total / base_p
    c_ratio = c_total / base_c
    if p_ratio > 0.15 or c_ratio > 0.15:
        evidence = [
            f"primary-only=${p_total:,.2f} ({p_ratio:.1%} of primary total)",
            f"comparison-only=${c_total:,.2f} ({c_ratio:.1%} of comparison total)",
            f"primary-only count={len(methodology.scope_alignment.primary_only)}",
            f"comparison-only count={len(methodology.scope_alignment.comparison_only)}",
        ]
        out.append(
            StructuralPattern(
                pattern_type=PatternType.SCOPE_ASYMMETRY,
                description="Scope asymmetry detected: unmatched scope exceeds 15% threshold on at least one side.",
                evidence=evidence,
                estimated_impact=round(max(p_total, c_total), 2),
            )
        )
    return out


def detect_patterns(methodology: MethodologyResult) -> List[StructuralPattern]:
    patterns: List[StructuralPattern] = []
    patterns.extend(detect_partial_vs_full_restoration(methodology))
    patterns.extend(detect_systematic_pricing(methodology))
    patterns.extend(detect_scope_asymmetry(methodology))
    patterns.sort(key=lambda p: (p.pattern_type.value, p.description))
    return patterns
