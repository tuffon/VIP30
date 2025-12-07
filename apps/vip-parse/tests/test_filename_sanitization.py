from __future__ import annotations

from src.tasks import _sanitize_display_name, _ensure_preferred_estimate_name


def test_sanitize_display_name_strips_formula_prefix() -> None:
    result = _sanitize_display_name("=HYPERLINK('http://evil')")
    assert result.startswith("SAFE ")
    assert "=" in result


def test_ensure_preferred_estimate_name_overrides_temp_name() -> None:
    payload = {"estimate_name": "tmpabc123.pdf", "case_metadata": {}}
    _ensure_preferred_estimate_name(
        payload,
        preferred_name="Estimate SF Structural damage Lachman 4.15.2025.pdf",
        parser_filename="tmpabc123.pdf",
    )
    assert payload["estimate_name"].startswith("Estimate SF Structural damage")
    assert payload["case_metadata"]["estimate_name"].startswith("Estimate SF Structural damage")


def test_ensure_preferred_estimate_name_keeps_existing_real_name() -> None:
    payload = {"estimate_name": "Carrier Scope", "case_metadata": {"estimate_name": "Carrier Scope"}}
    _ensure_preferred_estimate_name(
        payload,
        preferred_name="Uploaded Name",
        parser_filename="tmp123.pdf",
    )
    assert payload["estimate_name"] == "Carrier Scope"
