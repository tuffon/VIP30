import pytest

from .conftest import DOCUMENTS, load_golden, run_parser


def _recaps(parsed: dict) -> dict:
    return parsed.get("recaps_and_summaries") or {}


def _recap_by_category(parsed: dict) -> dict:
    return _recaps(parsed).get("recap_by_category") or {}


def _trade_summary(parsed: dict):
    return _recaps(parsed).get("trade_summary", "__MISSING__")


def _trade_summary_expected(golden: dict) -> bool:
    trade_summary = (golden.get("recaps_and_summaries") or {}).get("trade_summary", "__MISSING__")
    return trade_summary not in ("__MISSING__", None)


def _assert_canonical_recap_shape(recap: dict) -> None:
    assert isinstance(recap, dict)
    assert "subtotals" in recap
    assert isinstance(recap["subtotals"], list)

    for subtotal in recap["subtotals"]:
        assert isinstance(subtotal, dict)
        assert "label" in subtotal
        assert "total" in subtotal
        assert "pct" in subtotal

    for key, rows in recap.items():
        if key == "subtotals":
            continue
        assert isinstance(rows, list), f"{key} should be a category row list"
        for row in rows:
            assert isinstance(row, dict)
            assert "item" in row
            assert "total" in row
            assert "pct" in row


def _assert_trade_summary_shape(trade_summary: dict) -> None:
    assert isinstance(trade_summary, dict)
    assert set(trade_summary.keys()) == {"totals", "line_items"}
    assert isinstance(trade_summary["line_items"], list)
    assert trade_summary["line_items"]

    for trade in trade_summary["line_items"]:
        assert isinstance(trade, dict)
        assert "trade_code" in trade
        assert "trade" in trade
        assert "items" in trade
        assert isinstance(trade["items"], list)


@pytest.mark.parametrize("golden_rel,pdf_rel,_doc_type", DOCUMENTS)
def test_recap_by_category_contract(golden_rel, pdf_rel, _doc_type):
    golden = load_golden(golden_rel)
    parsed = run_parser(pdf_rel)

    assert parsed is not None, f"parser did not return output for {pdf_rel}"

    recap = _recap_by_category(parsed)
    assert recap, f"{pdf_rel} is missing recaps_and_summaries.recap_by_category"
    _assert_canonical_recap_shape(recap)

    golden_recap = (golden.get("recaps_and_summaries") or {}).get("recap_by_category") or {}
    if golden_recap:
        assert recap.get("subtotals"), f"{pdf_rel} recap_by_category should preserve subtotal rows"


@pytest.mark.parametrize("golden_rel,pdf_rel,_doc_type", DOCUMENTS)
def test_trade_summary_contract(golden_rel, pdf_rel, _doc_type):
    golden = load_golden(golden_rel)
    parsed = run_parser(pdf_rel)

    assert parsed is not None, f"parser did not return output for {pdf_rel}"

    expected_present = _trade_summary_expected(golden)
    trade_summary = _trade_summary(parsed)

    assert trade_summary != "__MISSING__", f"{pdf_rel} is missing recaps_and_summaries.trade_summary"

    if expected_present:
        assert trade_summary is not None, f"{pdf_rel} should emit parsed trade_summary data"
        _assert_trade_summary_shape(trade_summary)
    else:
        assert trade_summary is None, f"{pdf_rel} should emit trade_summary=null when section is absent"
