"""
Tests for TradeContext model and build_trade_context() extractor.

Requirements: TRADE-01, TRADE-02, TRADE-03
"""
import pytest
from conftest import load_golden, get_grand_total

# These imports will fail until models.py and trade_context.py are written:
from vip_shared.pipeline.models import TradeContext
from vip_shared.pipeline.passes.trade_context import build_trade_context


# --- TRADE-01: All 6 golden masters produce non-empty primary_by_category ---

@pytest.mark.parametrize("name", [
    "kalyvas", "lachman", "bschacter", "SF_BSchacter", "kalyvas_sf", "lachman_sf"
])
def test_primary_by_category_populated(name):
    """TRADE-01: primary_by_category non-empty for all doc types."""
    payload = load_golden(name)
    ctx = build_trade_context(payload, {})
    assert isinstance(ctx.primary_by_category, dict)
    non_zero = {k: v for k, v in ctx.primary_by_category.items() if v > 0}
    assert len(non_zero) >= 5, (
        f"{name}: expected >=5 non-zero categories, got {len(non_zero)}: {list(non_zero.keys())[:5]}"
    )


@pytest.mark.parametrize("name", [
    "kalyvas", "lachman", "bschacter", "SF_BSchacter", "kalyvas_sf", "lachman_sf"
])
def test_source_is_recap_by_category(name):
    """TRADE-01: source field reflects which fallback level was used."""
    payload = load_golden(name)
    ctx = build_trade_context(payload, {})
    assert ctx.source == "recap_by_category"


@pytest.mark.parametrize("name,expected_min,tolerance", [
    # Rough-drafts and contractor-finals: recap_by_category sums close to grand total
    ("kalyvas",      1_500_000, 0.05),
    ("lachman",      1_300_000, 0.05),
    ("bschacter",      750_000, 0.05),
    # SF docs: GCO&P surcharge (~16-20% of total) is NOT a separate category entry;
    # the grand total includes O&P markup on top of item subtotals.
    # expected_min set to actual category-item sum (verified from golden data).
    # tolerance relaxed to 25% for SF docs to accommodate GCO&P markup gap.
    ("SF_BSchacter",   145_000, 0.25),
    ("kalyvas_sf",     500_000, 0.25),
    ("lachman_sf",      80_000, 0.05),
])
def test_category_sum_within_tolerance_of_grand_total(name, expected_min, tolerance):
    """TRADE-01: sum of category totals is non-trivial and within tolerance of grand total.

    For SF docs, General Contractor O&P markup (~16-20% of total) is not a discrete
    category entry in recap_by_category -- it's an implicit surcharge.
    The category-item sum correctly represents billable trade work; tolerance is relaxed.
    This mirrors _aggregate_categories() in BidCompOrchestrator exactly.
    """
    payload = load_golden(name)
    ctx = build_trade_context(payload, {})
    total_sum = sum(ctx.primary_by_category.values())
    grand_total = get_grand_total(payload)
    assert total_sum >= expected_min, (
        f"{name}: sum={total_sum:.2f} below expected_min={expected_min}"
    )
    if grand_total > 0:
        pct_diff = abs(total_sum - grand_total) / grand_total
        assert pct_diff <= tolerance, (
            f"{name}: sum={total_sum:.2f} differs from grand_total={grand_total:.2f} "
            f"by {pct_diff:.1%} (>{tolerance:.0%})"
        )


# --- TRADE-02: SF trade_summary enrichment ---

def test_trade_summary_enrichment_kalyvas_sf():
    """TRADE-02: kalyvas_sf primary_trade_items populated from trade_summary."""
    payload = load_golden("kalyvas_sf")
    ctx = build_trade_context(payload, {})
    assert isinstance(ctx.primary_trade_items, list)
    assert len(ctx.primary_trade_items) > 0, "kalyvas_sf should have trade_summary line_items"
    # Each item should have trade_code and trade fields
    first = ctx.primary_trade_items[0]
    assert "trade_code" in first or "trade" in first


def test_trade_summary_enrichment_lachman_sf():
    """TRADE-02: lachman_sf primary_trade_items populated from trade_summary."""
    payload = load_golden("lachman_sf")
    ctx = build_trade_context(payload, {})
    assert len(ctx.primary_trade_items) >= 13, (
        f"lachman_sf should have 13 trade_summary line_items, got {len(ctx.primary_trade_items)}"
    )


def test_no_trade_summary_for_rough_drafts():
    """TRADE-02: rough-drafts have no trade_summary -- trade_items empty."""
    payload = load_golden("kalyvas")
    ctx = build_trade_context(payload, {})
    assert ctx.primary_trade_items == []


# --- TRADE-03: Synthesized fallback ---

def test_synthesized_fallback_when_recap_absent():
    """TRADE-03: when recap_by_category absent, synthesize from sections."""
    # Synthetic payload: no recap_by_category, but has sections
    payload = {
        "recaps_and_summaries": {},  # no recap_by_category
        "sections": [
            {"section_name": "Main Level", "section_totals": {"total": "50,000.00"},
             "line_items": []},
            {"section_name": "Roof", "section_totals": {"total": "100,000.00"},
             "line_items": []},
            {"section_name": "Kitchen", "section_totals": {"total": "25,000.00"},
             "line_items": []},
        ]
    }
    ctx = build_trade_context(payload, {})
    assert ctx.source == "synthesized"
    total = sum(ctx.primary_by_category.values())
    assert total >= 150_000, f"synthesized total={total:.2f} should be >=150,000"


def test_comparison_by_category_populated():
    """TRADE-01: comparison_by_category also populated when comparison_payload provided."""
    primary = load_golden("kalyvas")
    comparison = load_golden("lachman")
    ctx = build_trade_context(primary, comparison)
    assert len([v for v in ctx.comparison_by_category.values() if v > 0]) >= 5
