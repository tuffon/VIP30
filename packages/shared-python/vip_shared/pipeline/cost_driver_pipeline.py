"""
Cost-driver-first narrative pipeline for Phase 32.

Builds trade context, identifies major cost drivers, runs one LLM pass per
driver, then aggregates the successful driver analyses into one final summary.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from vip_shared.llm.adapter import LLMAdapterBase
from vip_shared.methodology.models import MethodologyResult
from vip_shared.rules.models import SignalBundle

from .cache import PipelineCache
from .models import DraftNarrative, DriverNarrative, FinalNarrative, QualityReport
from .passes import (
    build_trade_context,
    identify_cost_drivers,
    map_driver_items,
    run_driver_pass,
    run_summary_pass,
)
from .quality import HedgingChecker, JudgmentLanguageChecker
from .state import PipelineState


logger = logging.getLogger("vip-parse.pipeline.cost-driver")


def _now_ms() -> int:
    return int(time.perf_counter() * 1000)


def _timing_key(prefix: str, category: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in category).strip("_")
    return f"{prefix}:{slug or 'unknown'}"


class CostDriverPipeline:
    """Drop-in pipeline replacement for BidComp using the v2.6 architecture."""

    MAX_REWRITE_ATTEMPTS = 1

    def __init__(
        self,
        llm_adapter: LLMAdapterBase,
        cache: Optional[PipelineCache] = None,
    ) -> None:
        self.llm_adapter = llm_adapter
        self.cache = cache
        self.logger = logger

    def run(
        self,
        pair: Any,
        top_deltas: List[Dict[str, Any]],
        primary_name: str,
        comparison_name: str,
        methodology: Optional[MethodologyResult] = None,
        signals: Optional[SignalBundle] = None,
    ) -> PipelineState:
        state = PipelineState(pair=pair, top_deltas=top_deltas, methodology=methodology, signals=signals)

        self.logger.info(
            "cost-driver pipeline start: primary=%s comparison=%s top_deltas=%d",
            primary_name,
            comparison_name,
            len(top_deltas),
        )

        trade_start = _now_ms()
        trade_context = build_trade_context(pair.primary.payload, pair.comparison.payload)
        state.add_timing("trade_context", _now_ms() - trade_start)
        state.mark_pass_executed("trade_context")

        identify_start = _now_ms()
        top_n = len(top_deltas) if top_deltas else 5
        drivers = identify_cost_drivers(trade_context, top_n=top_n)
        state.add_timing("identify_cost_drivers", _now_ms() - identify_start)
        state.mark_pass_executed("identify_cost_drivers")

        map_start = _now_ms()
        drivers_with_items = map_driver_items(drivers, pair.primary.payload, pair.comparison.payload)
        state.add_timing("map_driver_items", _now_ms() - map_start)
        state.mark_pass_executed("map_driver_items")

        driver_analyses = []
        key_drivers: List[DriverNarrative] = []
        for driver_with_items in drivers_with_items:
            category = driver_with_items.driver.category
            pass_name = _timing_key("driver_pass", category)
            start_ms = _now_ms()
            try:
                analysis = run_driver_pass(driver_with_items, self.llm_adapter, cache=self.cache)
                driver_analyses.append(analysis)
                key_drivers.append(
                    DriverNarrative(
                        category=category,
                        amounts=(
                            f"${driver_with_items.driver.primary_total:,.2f} vs "
                            f"${driver_with_items.driver.comparison_total:,.2f}"
                        ),
                        narrative=analysis.narrative,
                    )
                )
            except Exception as exc:
                self.logger.warning("driver_pass failed for %s: %s", category, exc)
                state.errors.append({"pass": f"driver_pass:{category}", "error": str(exc)})
                key_drivers.append(
                    DriverNarrative(
                        category=category,
                        amounts=(
                            f"${driver_with_items.driver.primary_total:,.2f} vs "
                            f"${driver_with_items.driver.comparison_total:,.2f}"
                        ),
                        narrative=f"Analysis unavailable. Delta: ${driver_with_items.driver.delta:+,.2f}",
                    )
                )
            finally:
                state.add_timing(pass_name, _now_ms() - start_ms)
                state.mark_pass_executed(pass_name)

        summary = self._run_summary(
            driver_analyses,
            key_drivers,
            state,
            primary_name,
            comparison_name,
        )

        state.final = FinalNarrative(
            overview=summary.overview,
            key_drivers=key_drivers,
            scope_observations=summary.scope_observations,
            suggested_followups=summary.suggested_followups,
            quality_report=state.quality_report,
            rewrites_performed=self._rewrite_count(state),
        )

        state.draft = DraftNarrative(
            overview=summary.overview,
            key_drivers=key_drivers,
            scope_observations=summary.scope_observations,
            suggested_followups=summary.suggested_followups,
        )

        self.logger.info(
            "cost-driver pipeline complete: drivers=%d quality_passed=%s rewrites=%d",
            len(key_drivers),
            state.quality_passed(),
            state.final.rewrites_performed,
        )
        return state

    def _run_summary(
        self,
        driver_analyses,
        key_drivers: List[DriverNarrative],
        state: PipelineState,
        primary_name: str,
        comparison_name: str,
    ):
        summary_start = _now_ms()
        summary = run_summary_pass(
            driver_analyses,
            self.llm_adapter,
            primary_name=primary_name,
            comparison_name=comparison_name,
            cache=self.cache,
        )
        state.add_timing("summary_pass", _now_ms() - summary_start)
        state.mark_pass_executed("summary_pass")

        state.quality_report = self._check_quality(summary.overview)
        state.mark_pass_executed("quality_check")

        if self._rewrite_needed(state.quality_report):
            quality_notes = self._quality_notes(state.quality_report)
            rewrite_start = _now_ms()
            summary = run_summary_pass(
                driver_analyses,
                self.llm_adapter,
                primary_name=primary_name,
                comparison_name=comparison_name,
                quality_notes=quality_notes,
                cache=self.cache,
            )
            state.add_timing("summary_rewrite_1", _now_ms() - rewrite_start)
            state.mark_pass_executed("summary_rewrite_1")
            state.quality_report = self._check_quality(summary.overview)
            state.mark_pass_executed("quality_check_after_rewrite_1")

        return summary

    def _check_quality(self, overview: str) -> QualityReport:
        hedging = HedgingChecker().check(overview or "")
        judgment = JudgmentLanguageChecker().check(overview or "")
        checks = [hedging, judgment]
        return QualityReport(passed=all(check.passed for check in checks), checks=checks)

    def _quality_notes(self, report: QualityReport) -> str:
        failed_details = [check.details for check in report.checks if not check.passed and check.details]
        return " | ".join(failed_details)

    def _rewrite_needed(self, report: QualityReport) -> bool:
        return any(not check.passed for check in report.checks if check.check_name in {"GATE-01", "GATE-02"})

    def _rewrite_count(self, state: PipelineState) -> int:
        return min(
            self.MAX_REWRITE_ATTEMPTS,
            sum(1 for name in state.passes_executed if name.startswith("summary_rewrite_")),
        )
