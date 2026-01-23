"""
NarrativePipeline orchestrator for multi-pass narrative generation.

This module provides the main pipeline class that coordinates:
1. Analysis Pass: Extract structured deltas from estimates
2. Writer Pass: Generate adjuster-tone draft narrative
3. Quality Check: Run deterministic quality gates
4. Compliance Pass: Rewrite if quality fails (max 2 iterations)

Caching:
- Analysis pass: Cached with 1hr TTL (same estimates = same analysis)
- Writer pass: Cached with 30min TTL (same analysis = same draft)
- Compliance pass: NOT cached (quality gates may change)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .cache import PipelineCache, cache_key
from .models import AnalysisResult, DraftNarrative, FinalNarrative, QualityReport
from .passes import run_analysis_pass, run_writer_pass, run_compliance_pass, WriterInput
from .quality import QualityEvaluator
from .state import PipelineState
from ..llm.adapter import LLMAdapterBase


logger = logging.getLogger("vip-parse.pipeline")


class AnalysisCacheInput(BaseModel):
    """Input model for generating analysis cache key."""

    primary_payload: Any
    comparison_payload: Any
    top_deltas: List[Dict[str, Any]]


class NarrativePipeline:
    """
    Orchestrates the three-pass narrative generation pipeline.

    Pass sequence:
    1. Analysis pass: Extract structured deltas from estimates
    2. Writer pass: Generate adjuster-tone draft narrative
    3. Quality check: Run deterministic quality gates
    4. Compliance pass: Rewrite if quality fails (max 2 iterations)

    Caching (when enabled):
    - Analysis pass: Cached with configurable TTL (default 1hr)
    - Writer pass: Cached with configurable TTL (default 30min)
    - Compliance pass: NOT cached (quality gates may change)

    Usage:
        pipeline = NarrativePipeline(llm_adapter)
        state = pipeline.run(pair, top_deltas, primary_name, comparison_name)
        final_narrative = state.final

    With caching:
        cache = PipelineCache(redis_client)
        pipeline = NarrativePipeline(llm_adapter, cache=cache)
    """

    MAX_REWRITE_ITERATIONS = 2

    def __init__(
        self,
        llm_adapter: LLMAdapterBase,
        quality_evaluator: Optional[QualityEvaluator] = None,
        cache: Optional[PipelineCache] = None,
        analysis_ttl: int = 3600,    # 1 hour
        writer_ttl: int = 1800,      # 30 min
    ):
        """
        Initialize the NarrativePipeline.

        Args:
            llm_adapter: LLM adapter for generating content
            quality_evaluator: Optional custom QualityEvaluator (defaults to standard)
            cache: Optional PipelineCache for Redis caching
            analysis_ttl: TTL for analysis pass cache in seconds (default: 3600)
            writer_ttl: TTL for writer pass cache in seconds (default: 1800)
        """
        self.llm_adapter = llm_adapter
        self.evaluator = quality_evaluator or QualityEvaluator()
        self.cache = cache
        self.analysis_ttl = analysis_ttl
        self.writer_ttl = writer_ttl
        self.logger = logging.getLogger("vip-parse.pipeline")

    def run(
        self,
        pair: Any,  # EstimatePair - use Any to avoid circular import
        top_deltas: List[Dict[str, Any]],
        primary_name: str,
        comparison_name: str
    ) -> PipelineState:
        """
        Execute the full pipeline and return PipelineState with results.

        Args:
            pair: EstimatePair with primary and comparison estimates
            top_deltas: List of top delta category dicts from BidComp
            primary_name: Name of the primary estimate
            comparison_name: Name of the comparison estimate

        Returns:
            PipelineState containing all intermediate and final results
        """
        state = PipelineState(pair=pair, top_deltas=top_deltas)

        self.logger.info(
            "pipeline start: primary=%s comparison=%s deltas=%d",
            primary_name,
            comparison_name,
            len(top_deltas),
        )

        # Pass 1: Analysis
        state = self._run_analysis(state, primary_name, comparison_name)
        if state.analysis is None:
            return self._finalize_with_error(state, "analysis_failed")

        # Pass 2: Writer
        state = self._run_writer(state, primary_name, comparison_name)
        if state.draft is None:
            return self._finalize_with_error(state, "writer_failed")

        # Quality check
        state = self._check_quality(state)

        # Pass 3: Conditional Compliance (max 2 iterations)
        if not state.quality_passed():
            state = self._run_compliance_loop(state, primary_name, comparison_name)
        else:
            state.mark_pass_executed("compliance_skipped")
            self.logger.info("quality passed, skipping compliance rewrite")

        # Finalize
        state = self._finalize(state)

        self.logger.info(
            "pipeline complete: rewrites=%d quality_passed=%s total_passes=%d",
            state.final.rewrites_performed if state.final else 0,
            state.quality_passed(),
            len(state.passes_executed),
        )

        return state

    def _get_analysis_cache_key(self, pair: Any, top_deltas: List[Dict[str, Any]]) -> str:
        """
        Generate cache key for analysis pass based on input content.

        Args:
            pair: EstimatePair with primary and comparison estimates
            top_deltas: List of top delta dicts

        Returns:
            Cache key string
        """
        # Extract payloads from pair for hashing
        primary_payload = pair.primary.payload if hasattr(pair, 'primary') else str(pair)
        comparison_payload = pair.comparison.payload if hasattr(pair, 'comparison') else ""

        cache_input = AnalysisCacheInput(
            primary_payload=primary_payload,
            comparison_payload=comparison_payload,
            top_deltas=top_deltas,
        )
        return cache_key("analysis", cache_input)

    def _run_analysis(
        self,
        state: PipelineState,
        primary_name: str,
        comparison_name: str
    ) -> PipelineState:
        """
        Run the Analysis pass and update state.

        Args:
            state: Current pipeline state
            primary_name: Name of the primary estimate
            comparison_name: Name of the comparison estimate

        Returns:
            Updated PipelineState with analysis results
        """
        start_ms = _now_ms()

        # Check cache first
        if self.cache:
            analysis_cache_key = self._get_analysis_cache_key(state.pair, state.top_deltas)
            cached = self.cache.get(analysis_cache_key, AnalysisResult)
            if cached:
                state.analysis = cached
                state.add_timing("analysis_cached", _now_ms() - start_ms)
                state.mark_pass_executed("analysis_cached")
                self.logger.info(
                    "analysis pass cache hit: categories=%d confidence=%s timing_ms=%d",
                    len(cached.category_analyses),
                    cached.confidence,
                    _now_ms() - start_ms,
                )
                return state

        try:
            result = run_analysis_pass(state.pair, state.top_deltas, self.llm_adapter)
            state.analysis = result
            state.add_timing("analysis", _now_ms() - start_ms)
            state.mark_pass_executed("analysis")
            self.logger.info(
                "analysis pass success: categories=%d confidence=%s timing_ms=%d",
                len(result.category_analyses),
                result.confidence,
                _now_ms() - start_ms,
            )

            # Store in cache after successful LLM call
            if self.cache:
                analysis_cache_key = self._get_analysis_cache_key(state.pair, state.top_deltas)
                self.cache.set(analysis_cache_key, result, self.analysis_ttl)

        except Exception as exc:
            state.add_timing("analysis", _now_ms() - start_ms)
            state.errors.append({
                "pass": "analysis",
                "error": str(exc),
                "error_type": type(exc).__name__,
            })
            self.logger.error("analysis pass failed: %s", exc)
        return state

    def _get_writer_cache_key(
        self,
        analysis: AnalysisResult,
        primary_name: str,
        comparison_name: str
    ) -> str:
        """
        Generate cache key for writer pass based on analysis result.

        Args:
            analysis: AnalysisResult from analysis pass
            primary_name: Name of the primary estimate
            comparison_name: Name of the comparison estimate

        Returns:
            Cache key string
        """
        # Serialize category analyses to dict format for hashing
        category_analyses_dicts: List[Dict[str, Any]] = []
        for cat_analysis in analysis.category_analyses:
            category_analyses_dicts.append({
                "category": cat_analysis.category,
                "primary_total": cat_analysis.primary_total,
                "comparison_total": cat_analysis.comparison_total,
                "delta": cat_analysis.delta,
                "delta_drivers": cat_analysis.delta_drivers,
                "line_item_evidence": cat_analysis.line_item_evidence,
            })

        writer_input = WriterInput(
            primary_name=primary_name,
            comparison_name=comparison_name,
            category_analyses=category_analyses_dicts,
            scope_gaps=analysis.scope_gaps,
            overall_delta_direction=analysis.overall_delta_direction,
            confidence=analysis.confidence,
        )
        return cache_key("writer", writer_input)

    def _run_writer(
        self,
        state: PipelineState,
        primary_name: str,
        comparison_name: str
    ) -> PipelineState:
        """
        Run the Writer pass and update state.

        Args:
            state: Current pipeline state
            primary_name: Name of the primary estimate
            comparison_name: Name of the comparison estimate

        Returns:
            Updated PipelineState with draft narrative
        """
        start_ms = _now_ms()

        # Check cache first
        if self.cache and state.analysis:
            writer_cache_key = self._get_writer_cache_key(
                state.analysis, primary_name, comparison_name
            )
            cached = self.cache.get(writer_cache_key, DraftNarrative)
            if cached:
                state.draft = cached
                state.add_timing("writer_cached", _now_ms() - start_ms)
                state.mark_pass_executed("writer_cached")
                self.logger.info(
                    "writer pass cache hit: overview_len=%d drivers=%d timing_ms=%d",
                    len(cached.overview),
                    len(cached.key_drivers),
                    _now_ms() - start_ms,
                )
                return state

        try:
            result = run_writer_pass(
                state.analysis,
                primary_name,
                comparison_name,
                self.llm_adapter
            )
            state.draft = result
            state.add_timing("writer", _now_ms() - start_ms)
            state.mark_pass_executed("writer")
            self.logger.info(
                "writer pass success: overview_len=%d drivers=%d timing_ms=%d",
                len(result.overview),
                len(result.key_drivers),
                _now_ms() - start_ms,
            )

            # Store in cache after successful LLM call
            if self.cache and state.analysis:
                writer_cache_key = self._get_writer_cache_key(
                    state.analysis, primary_name, comparison_name
                )
                self.cache.set(writer_cache_key, result, self.writer_ttl)

        except Exception as exc:
            state.add_timing("writer", _now_ms() - start_ms)
            state.errors.append({
                "pass": "writer",
                "error": str(exc),
                "error_type": type(exc).__name__,
            })
            self.logger.error("writer pass failed: %s", exc)
        return state

    def _check_quality(self, state: PipelineState) -> PipelineState:
        """
        Run quality checks on the draft narrative.

        Args:
            state: Current pipeline state with draft narrative

        Returns:
            Updated PipelineState with quality report
        """
        start_ms = _now_ms()
        try:
            report = self.evaluator.evaluate(state.draft)
            state.quality_report = report
            state.add_timing("quality_check", _now_ms() - start_ms)
            state.mark_pass_executed("quality_check")
            self.logger.info(
                "quality check complete: passed=%s failed_checks=%d timing_ms=%d",
                report.passed,
                len(report.failed_checks),
                _now_ms() - start_ms,
            )
            if not report.passed:
                self.logger.info(
                    "quality check failed gates: %s",
                    report.failed_checks,
                )
        except Exception as exc:
            state.add_timing("quality_check", _now_ms() - start_ms)
            state.errors.append({
                "pass": "quality_check",
                "error": str(exc),
                "error_type": type(exc).__name__,
            })
            self.logger.error("quality check failed: %s", exc)
        return state

    def _run_compliance_loop(
        self,
        state: PipelineState,
        primary_name: str,
        comparison_name: str
    ) -> PipelineState:
        """
        Run compliance rewrite loop until quality passes or max iterations reached.

        NOTE: Compliance pass is NOT cached. Quality gates may change between runs,
        and we want fresh rewrites each time quality fails.

        Args:
            state: Current pipeline state with failed quality
            primary_name: Name of the primary estimate
            comparison_name: Name of the comparison estimate

        Returns:
            Updated PipelineState with rewritten draft
        """
        # Compliance pass NOT cached - quality gates may change
        for iteration in range(1, self.MAX_REWRITE_ITERATIONS + 1):
            self.logger.info(
                "compliance rewrite iteration %d/%d",
                iteration,
                self.MAX_REWRITE_ITERATIONS,
            )

            start_ms = _now_ms()
            try:
                rewritten = run_compliance_pass(
                    state.draft,
                    state.quality_report,
                    primary_name,
                    comparison_name,
                    self.llm_adapter
                )
                state.draft = rewritten
                state.add_timing(f"compliance_rewrite_{iteration}", _now_ms() - start_ms)
                state.mark_pass_executed(f"compliance_rewrite_{iteration}")
                self.logger.info(
                    "compliance rewrite %d complete: overview_len=%d timing_ms=%d",
                    iteration,
                    len(rewritten.overview),
                    _now_ms() - start_ms,
                )
            except Exception as exc:
                state.add_timing(f"compliance_rewrite_{iteration}", _now_ms() - start_ms)
                state.errors.append({
                    "pass": f"compliance_rewrite_{iteration}",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                })
                self.logger.error("compliance rewrite %d failed: %s", iteration, exc)
                break

            # Re-check quality
            state = self._check_quality_after_rewrite(state, iteration)
            if state.quality_passed():
                self.logger.info(
                    "quality passed after rewrite iteration %d",
                    iteration,
                )
                break

        if not state.quality_passed():
            self.logger.warning(
                "quality still failing after %d rewrite iterations",
                self.MAX_REWRITE_ITERATIONS,
            )

        return state

    def _check_quality_after_rewrite(
        self,
        state: PipelineState,
        iteration: int
    ) -> PipelineState:
        """
        Re-check quality after a compliance rewrite.

        Args:
            state: Current pipeline state with rewritten draft
            iteration: Current rewrite iteration number

        Returns:
            Updated PipelineState with new quality report
        """
        start_ms = _now_ms()
        try:
            report = self.evaluator.evaluate(state.draft)
            state.quality_report = report
            state.add_timing(f"quality_check_after_rewrite_{iteration}", _now_ms() - start_ms)
            self.logger.info(
                "quality check after rewrite %d: passed=%s failed_checks=%d",
                iteration,
                report.passed,
                len(report.failed_checks),
            )
        except Exception as exc:
            state.add_timing(f"quality_check_after_rewrite_{iteration}", _now_ms() - start_ms)
            state.errors.append({
                "pass": f"quality_check_after_rewrite_{iteration}",
                "error": str(exc),
                "error_type": type(exc).__name__,
            })
            self.logger.error("quality check after rewrite %d failed: %s", iteration, exc)
        return state

    def _finalize(self, state: PipelineState) -> PipelineState:
        """
        Finalize the pipeline by wrapping draft as FinalNarrative.

        Args:
            state: Current pipeline state

        Returns:
            Updated PipelineState with final narrative
        """
        # Count rewrites from passes_executed
        rewrites = sum(
            1 for p in state.passes_executed
            if p.startswith("compliance_rewrite_")
        )

        state.final = FinalNarrative(
            overview=state.draft.overview,
            key_drivers=state.draft.key_drivers,
            scope_observations=state.draft.scope_observations,
            suggested_followups=state.draft.suggested_followups,
            quality_report=state.quality_report,
            rewrites_performed=rewrites,
        )

        self.logger.info(
            "pipeline finalized: rewrites=%d quality_passed=%s",
            rewrites,
            state.quality_passed(),
        )

        return state

    def _finalize_with_error(
        self,
        state: PipelineState,
        error_type: str
    ) -> PipelineState:
        """
        Finalize pipeline with error - create minimal FinalNarrative.

        Args:
            state: Current pipeline state
            error_type: Type of error (analysis_failed, writer_failed)

        Returns:
            Updated PipelineState with error-state final narrative
        """
        self.logger.error("pipeline terminated early: %s", error_type)

        # Create minimal quality report
        error_report = QualityReport(
            passed=False,
            checks=[],
        )

        # Create minimal final narrative
        state.final = FinalNarrative(
            overview=f"Pipeline error: {error_type}. See logs for details.",
            key_drivers=[],
            scope_observations=[],
            suggested_followups=[],
            quality_report=error_report,
            rewrites_performed=0,
        )

        return state


def _now_ms() -> int:
    """Get current time in milliseconds."""
    return int(time.perf_counter() * 1000)
