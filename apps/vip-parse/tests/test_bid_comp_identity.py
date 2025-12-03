from __future__ import annotations

from src.bid_comp.identity import ensure_estimate_identity


def test_existing_estimate_name_preserved() -> None:
    payload = {"estimate_name": "My Estimate", "case_metadata": {}}
    result = ensure_estimate_identity(payload, "fallback.pdf")
    assert result == "My Estimate"
    assert payload["case_metadata"]["estimate_name"] == "My Estimate"


def test_fallback_uses_truncated_filename() -> None:
    long_name = (
        "super_extraordinarily_long_filename_for_adjuster_review_version_final_really_long_name_2025_FINAL_v10.pdf"
    )
    payload = {"case_metadata": {}}
    result = ensure_estimate_identity(payload, long_name)
    assert result.endswith("...")
    assert len(result) <= 80
    assert payload["estimate_name"] == result
    assert payload["case_metadata"]["estimate_name"] == result

