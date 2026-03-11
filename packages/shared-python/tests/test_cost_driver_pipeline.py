"""
Tests for CostDriverPipeline orchestrator.

Requirements: REWRITE-01, REWRITE-02, REWRITE-03, INTEG-01, INTEG-02
"""
from unittest.mock import MagicMock, patch

from conftest import load_golden

from vip_shared.bid_comp.core import BidComp
from vip_shared.pipeline import CostDriverPipeline
from vip_shared.pipeline.models import (
    CostDriver,
    DriverAnalysisResult,
    DriverWithItems,
    FinalNarrative,
    SummaryResult,
)
from vip_shared.pipeline.state import PipelineState


def _make_driver(category: str = "Painting", delta: float = 117000.0) -> CostDriver:
    return CostDriver(
        category=category,
        primary_total=200000.0,
        comparison_total=200000.0 - delta,
        delta=delta,
    )


def _make_dwi(category: str = "Painting", delta: float = 117000.0) -> DriverWithItems:
    return DriverWithItems(
        driver=_make_driver(category, delta),
        primary_items=[{"description": "Painting item", "total": 200000.0, "type": "line_item"}],
        comparison_items=[{"description": "Painting item", "total": 200000.0 - delta, "type": "line_item"}],
        verification_ok=True,
        verification_note="",
    )


def _make_driver_analysis(category: str = "Painting") -> DriverAnalysisResult:
    return DriverAnalysisResult(
        category=category,
        primary_total=200000.0,
        comparison_total=83000.0,
        delta=117000.0,
        narrative=f"{category} delta driven by scope difference.",
        scope_observations=[f"{category}: primary bid item vs unit rates."],
        suggested_followups=[f"Verify {category} scope."],
    )


def _make_summary(overview: str | None = None) -> SummaryResult:
    return SummaryResult(
        overview=overview or (
            "The primary estimate is higher across key categories. "
            "Painting represents $117k driven by a bid item approach."
        ),
        scope_observations=["Primary uses bid item painting; comparison uses unit rates."],
        suggested_followups=["Verify painting scope with contractor."],
    )


def _make_pair(primary_payload=None, comparison_payload=None):
    pair = MagicMock()
    pair.primary.payload = primary_payload or {
        "recaps_and_summaries": {"recap_by_category": {"groups": [], "subtotals": []}},
        "sections": [],
    }
    pair.comparison.payload = comparison_payload or {
        "recaps_and_summaries": {"recap_by_category": {"groups": [], "subtotals": []}},
        "sections": [],
    }
    pair.primary.estimate_name = "Primary"
    pair.comparison.estimate_name = "Comparison"
    return pair


@patch("vip_shared.pipeline.cost_driver_pipeline.build_trade_context")
@patch("vip_shared.pipeline.cost_driver_pipeline.identify_cost_drivers")
@patch("vip_shared.pipeline.cost_driver_pipeline.map_driver_items")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_driver_pass")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_summary_pass")
def test_pipeline_run_returns_pipeline_state_with_final(
    mock_summary, mock_driver, mock_map, mock_identify, mock_trade
):
    """INTEG-01/02: run() returns PipelineState with FinalNarrative set."""
    mock_trade.return_value = MagicMock()
    mock_identify.return_value = [_make_driver()]
    mock_map.return_value = [_make_dwi()]
    mock_driver.return_value = _make_driver_analysis()
    mock_summary.return_value = _make_summary()

    pipeline = CostDriverPipeline(llm_adapter=MagicMock())
    state = pipeline.run(
        pair=_make_pair(),
        top_deltas=[{"category": "Painting"}],
        primary_name="Primary",
        comparison_name="Comparison",
    )

    assert isinstance(state, PipelineState)
    assert isinstance(state.final, FinalNarrative)
    assert state.final.overview == mock_summary.return_value.overview
    assert state.quality_report is not None
    assert state.final.quality_report is state.quality_report
    mock_map.assert_called_once()
    assert mock_map.call_args.kwargs["trade_ctx"] is mock_trade.return_value
    assert mock_driver.call_args.kwargs["primary_name"] == "Primary"
    assert mock_driver.call_args.kwargs["comparison_name"] == "Comparison"


@patch("vip_shared.pipeline.cost_driver_pipeline.build_trade_context")
@patch("vip_shared.pipeline.cost_driver_pipeline.identify_cost_drivers")
@patch("vip_shared.pipeline.cost_driver_pipeline.map_driver_items")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_driver_pass")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_summary_pass")
def test_pipeline_driver_failure_creates_analysis_unavailable_entry(
    mock_summary, mock_driver, mock_map, mock_identify, mock_trade
):
    """REWRITE-03: failed driver pass produces explicit fallback narrative."""
    mock_trade.return_value = MagicMock()
    mock_identify.return_value = [_make_driver()]
    mock_map.return_value = [_make_dwi()]
    mock_driver.side_effect = RuntimeError("driver failed")
    mock_summary.return_value = _make_summary()

    state = CostDriverPipeline(llm_adapter=MagicMock()).run(
        pair=_make_pair(),
        top_deltas=[{"category": "Painting"}],
        primary_name="Primary",
        comparison_name="Comparison",
    )

    assert state.final is not None
    assert state.final.key_drivers[0].category == "Painting"
    assert "Analysis unavailable." in state.final.key_drivers[0].narrative
    assert state.errors[0]["pass"] == "driver_pass:Painting"


@patch("vip_shared.pipeline.cost_driver_pipeline.build_trade_context")
@patch("vip_shared.pipeline.cost_driver_pipeline.identify_cost_drivers")
@patch("vip_shared.pipeline.cost_driver_pipeline.map_driver_items")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_driver_pass")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_summary_pass")
def test_pipeline_rewrites_once_for_gate_01_or_02_failure(
    mock_summary, mock_driver, mock_map, mock_identify, mock_trade
):
    """REWRITE-01: only one rewrite attempt occurs when GATE-01/02 fails."""
    mock_trade.return_value = MagicMock()
    mock_identify.return_value = [_make_driver()]
    mock_map.return_value = [_make_dwi()]
    mock_driver.return_value = _make_driver_analysis()
    mock_summary.side_effect = [
        _make_summary("The primary estimate is possibly higher than the comparison."),
        _make_summary("The primary estimate is higher than the comparison."),
    ]

    state = CostDriverPipeline(llm_adapter=MagicMock()).run(
        pair=_make_pair(),
        top_deltas=[{"category": "Painting"}],
        primary_name="Primary",
        comparison_name="Comparison",
    )

    assert mock_summary.call_count == 2
    assert state.final is not None
    assert state.final.rewrites_performed == 1
    assert "summary_rewrite_1" in state.passes_executed


@patch("vip_shared.pipeline.cost_driver_pipeline.build_trade_context")
@patch("vip_shared.pipeline.cost_driver_pipeline.identify_cost_drivers")
@patch("vip_shared.pipeline.cost_driver_pipeline.map_driver_items")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_driver_pass")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_summary_pass")
def test_pipeline_skips_rewrite_when_quality_passes(
    mock_summary, mock_driver, mock_map, mock_identify, mock_trade
):
    """REWRITE-01: no rewrite occurs when overview passes GATE-01 and GATE-02."""
    mock_trade.return_value = MagicMock()
    mock_identify.return_value = [_make_driver()]
    mock_map.return_value = [_make_dwi()]
    mock_driver.return_value = _make_driver_analysis()
    mock_summary.return_value = _make_summary("The primary estimate is higher than the comparison.")

    state = CostDriverPipeline(llm_adapter=MagicMock()).run(
        pair=_make_pair(),
        top_deltas=[{"category": "Painting"}],
        primary_name="Primary",
        comparison_name="Comparison",
    )

    assert mock_summary.call_count == 1
    assert state.final is not None
    assert state.final.rewrites_performed == 0


def test_bidcomp_uses_cost_driver_pipeline():
    """INTEG-01: BidComp initializes CostDriverPipeline when LLM is configured."""
    bid_comp = BidComp(llm_adapter=MagicMock())
    assert isinstance(bid_comp._pipeline, CostDriverPipeline)


@patch("vip_shared.bid_comp.core.importlib.import_module")
def test_build_category_table_uses_trade_context_totals(mock_import_module):
    """Phase 34: category table uses the same trade-context totals as the pipeline path."""
    build_trade_context = MagicMock()
    build_trade_context.return_value = MagicMock(
        primary_by_category={"Painting": 120.0},
        comparison_by_category={"Painting": 20.0},
    )
    mock_import_module.return_value = MagicMock(build_trade_context=build_trade_context)

    bid_comp = BidComp(llm_adapter=MagicMock())
    pair = _make_pair(
        primary_payload={"recaps_and_summaries": {"recap_by_category": {"subtotals": []}}, "sections": []},
        comparison_payload={"recaps_and_summaries": {"recap_by_category": {"subtotals": []}}, "sections": []},
    )
    pair.primary.recap = {}
    pair.comparison.recap = {}

    rows = bid_comp._build_category_table(pair)

    build_trade_context.assert_called_once_with(pair.primary.payload, pair.comparison.payload)
    painting = next(row for row in rows if row["category"] == "Painting")
    assert painting["primary_total"] == 120.0
    assert painting["comparison_total"] == 20.0


@patch("vip_shared.pipeline.cost_driver_pipeline.run_summary_pass")
@patch("vip_shared.pipeline.cost_driver_pipeline.run_driver_pass")
def test_bidcomp_run_produces_xlsx_bytes_with_mocked_pipeline_passes(mock_driver, mock_summary):
    """INTEG-02: BidComp.run still exports XLSX from FinalNarrative output."""
    mock_driver.return_value = _make_driver_analysis()
    mock_summary.return_value = _make_summary("The primary estimate is higher than the comparison.")

    bid_context = {
        "estimates": [
            {"payload": load_golden("kalyvas"), "source_filename": "kalyvas.json"},
            {"payload": load_golden("lachman"), "source_filename": "lachman.json"},
        ]
    }

    xlsx_bytes = BidComp(llm_adapter=MagicMock()).run(bid_context, job_id="test-job")

    assert isinstance(xlsx_bytes, bytes)
    assert xlsx_bytes[:2] == b"PK"
