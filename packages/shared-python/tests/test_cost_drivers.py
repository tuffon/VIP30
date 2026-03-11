"""
Tests for CostDriver / DriverWithItems models and identify/map functions.

Requirements: DRIVER-01, DRIVER-02, DRIVER-03
"""
import pytest

from conftest import load_golden
from vip_shared.pipeline.models import CostDriver, DriverWithItems, TradeContext
from vip_shared.pipeline.passes.trade_context import build_trade_context

# These imports fail until cost_drivers.py is created (TDD RED -- expected):
from vip_shared.pipeline.passes.cost_drivers import identify_cost_drivers, map_driver_items


# --- DRIVER-01: identify_cost_drivers ---

def test_identify_sorted_by_abs_delta():
    """DRIVER-01: result is sorted by abs(delta) descending."""
    ctx = build_trade_context(load_golden("kalyvas"), load_golden("lachman"))
    drivers = identify_cost_drivers(ctx, top_n=10)
    assert len(drivers) > 0
    for i in range(len(drivers) - 1):
        assert drivers[i].abs_delta >= drivers[i + 1].abs_delta, (
            f"driver[{i}].abs_delta={drivers[i].abs_delta:.2f} < "
            f"driver[{i+1}].abs_delta={drivers[i+1].abs_delta:.2f}"
        )


def test_identify_top_n_respected():
    """DRIVER-01: top_n parameter limits output count."""
    ctx = build_trade_context(load_golden("kalyvas"), load_golden("lachman"))
    for n in [1, 3, 5]:
        drivers = identify_cost_drivers(ctx, top_n=n)
        assert len(drivers) == n, f"top_n={n} -> expected {n} drivers, got {len(drivers)}"


def test_identify_delta_is_signed():
    """DRIVER-01: delta = primary_total - comparison_total (signed); abs_delta = abs(delta)."""
    ctx = build_trade_context(load_golden("kalyvas"), load_golden("lachman"))
    drivers = identify_cost_drivers(ctx, top_n=10)
    for d in drivers:
        expected = round(d.primary_total - d.comparison_total, 2)
        assert abs(d.delta - expected) < 0.02, (
            f"{d.category}: delta={d.delta:.2f} != {expected:.2f}"
        )
        assert abs(d.abs_delta - abs(d.delta)) < 0.02


def test_identify_excludes_all_zero_categories():
    """DRIVER-01: categories where both primary and comparison are 0 are excluded."""
    ctx = build_trade_context(load_golden("kalyvas"), load_golden("lachman"))
    drivers = identify_cost_drivers(ctx, top_n=10)
    for d in drivers:
        assert d.primary_total > 0 or d.comparison_total > 0, (
            f"{d.category}: both totals are 0.0 but appeared in drivers"
        )


def test_identify_returns_cost_driver_instances():
    """DRIVER-01: each result is a CostDriver Pydantic model instance."""
    ctx = build_trade_context(load_golden("kalyvas"), load_golden("lachman"))
    drivers = identify_cost_drivers(ctx)
    assert all(isinstance(d, CostDriver) for d in drivers)


# --- DRIVER-02: map_driver_items ---

def test_map_items_length_matches_input():
    """DRIVER-02: output length == len(cost_drivers) input."""
    primary = load_golden("kalyvas")
    comparison = load_golden("lachman")
    ctx = build_trade_context(primary, comparison)
    drivers = identify_cost_drivers(ctx, top_n=5)
    results = map_driver_items(drivers, primary, comparison, trade_ctx=ctx)
    assert len(results) == 5
    assert all(isinstance(r, DriverWithItems) for r in results)


def test_map_items_populated_for_kalyvas():
    """DRIVER-02: kalyvas has 887 items -- top 5 drivers should yield items."""
    primary = load_golden("kalyvas")
    ctx = build_trade_context(primary, {})
    drivers = identify_cost_drivers(ctx, top_n=5)
    results = map_driver_items(drivers, primary, {}, trade_ctx=ctx)
    populated = [r for r in results if len(r.primary_items) > 0]
    assert len(populated) >= 3, (
        f"Expected >=3 drivers with primary_items in kalyvas (887 items), "
        f"got {len(populated)}. Drivers: {[r.driver.category for r in results]}"
    )


def test_map_items_only_line_item_type():
    """DRIVER-02: header-type entries are excluded; only type=='line_item' collected."""
    primary = load_golden("kalyvas")
    ctx = build_trade_context(primary, {})
    drivers = identify_cost_drivers(ctx, top_n=5)
    results = map_driver_items(drivers, primary, {}, trade_ctx=ctx)
    for r in results:
        for item in r.primary_items + r.comparison_items:
            assert item.get("type") == "line_item", (
                f"Non-line_item type in {r.driver.category}: type={item.get('type')}"
            )


def test_map_items_painting_cat_codes():
    """DRIVER-02: Painting driver items resolve to the exact PAINTING category."""
    primary = load_golden("kalyvas")
    ctx = build_trade_context(primary, {})
    drivers = identify_cost_drivers(ctx, top_n=10)
    results = map_driver_items(drivers, primary, {}, trade_ctx=ctx)
    painting = next((r for r in results if r.driver.category == "PAINTING"), None)
    if painting is None or not painting.primary_items:
        pytest.skip("Painting not in top 10 drivers or has no items for this doc")
    for item in painting.primary_items:
        assert item.get("cat") == "PNT", (
            f"PAINTING driver item should preserve exact PNT items, got cat={item.get('cat')}"
        )


# --- DRIVER-03: verification gate ---

def test_verification_ok_for_kalyvas_self():
    """DRIVER-03: kalyvas self-check returns explicit verification results per exact category.

    After Phase 34.1, the fallback mapper preserves exact recap categories rather than
    collapsing them into broader umbrella buckets. That makes the verification result
    more honest for rough-draft payloads with coarse item codes: top exact categories
    can legitimately fail verification, but they must still emit populated notes.
    """
    kalyvas = load_golden("kalyvas")
    ctx = build_trade_context(kalyvas, {})
    drivers = identify_cost_drivers(ctx, top_n=5)
    results = map_driver_items(drivers, kalyvas, {}, trade_ctx=ctx)
    assert len(results) == 5
    assert any(not r.verification_ok for r in results)
    failed_notes = [r.verification_note for r in results if not r.verification_ok]
    assert all(note for note in failed_notes)


def test_verification_fail_note_contains_amounts():
    """DRIVER-03: when items don't sum to category total, note has dollar amounts."""
    # Synthetic driver: category total $999,999.99, no matching items in empty payload
    ctx = TradeContext(
        primary_by_category={"Painting": 999_999.99},
        comparison_by_category={},
        source="recap_by_category",
    )
    drivers = identify_cost_drivers(ctx, top_n=1)
    assert drivers[0].category == "Painting"
    results = map_driver_items(drivers, {}, {})  # empty payload -> item sum = 0
    assert len(results) == 1
    r = results[0]
    assert r.verification_ok is False
    assert r.verification_note != "", "verification_note should be non-empty when ok=False"
    # Note should reference the dollar discrepancy
    assert any(c.isdigit() for c in r.verification_note), (
        f"verification_note should contain numbers: {r.verification_note}"
    )


def test_trade_summary_items_preferred_for_statefarm_driver():
    """Phase 34: use trade_summary supporting items when available for a selected category."""
    primary = load_golden("lachman_sf")
    comparison = {}
    ctx = build_trade_context(primary, comparison)
    driver = CostDriver(
        category="CLEANING",
        primary_total=ctx.primary_by_category["CLEANING"],
        comparison_total=0.0,
        delta=ctx.primary_by_category["CLEANING"],
    )

    results = map_driver_items([driver], primary, comparison, trade_ctx=ctx)

    assert len(results) == 1
    assert len(results[0].primary_items) > 0
    assert results[0].primary_items[0]["source"] == "trade_summary"


def test_map_driver_items_only_collects_selected_categories():
    """Phase 34: fallback payload mapping is scoped to the selected driver categories."""
    payload = {
        "sections": [
            {
                "line_items": [
                    {"type": "line_item", "cat": "PNT", "description": "Paint", "total": "100.00"},
                    {"type": "line_item", "cat": "ELE", "description": "Wire", "total": "200.00"},
                ]
            }
        ]
    }
    ctx = TradeContext(
        primary_by_category={"PAINTING": 100.0, "ELECTRICAL": 200.0},
        comparison_by_category={},
        source="recap_by_category",
    )
    driver = CostDriver(category="PAINTING", primary_total=100.0, comparison_total=0.0, delta=100.0)

    results = map_driver_items([driver], payload, {}, trade_ctx=ctx)

    assert len(results) == 1
    descriptions = [item["description"] for item in results[0].primary_items]
    assert descriptions == ["Paint"]


def test_identify_and_map_do_not_reintroduce_umbrella_categories():
    """Phase 34.1: selected drivers and mapped items stay on exact parsed category titles."""
    primary = load_golden("kalyvas")
    comparison = load_golden("lachman")
    ctx = build_trade_context(primary, comparison)

    drivers = identify_cost_drivers(ctx, top_n=10)
    categories = {driver.category for driver in drivers}

    assert "Doors / Windows / Glass" not in categories
    assert "Cabinetry / Millwork" not in categories
    assert "WINDOWS - SLIDING PATIO DOORS" in categories
    assert "PAINTING" in categories
