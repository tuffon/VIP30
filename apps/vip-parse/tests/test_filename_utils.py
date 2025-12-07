from __future__ import annotations

import pytest

from src.utils.filename import sanitize_display_name, sanitize_storage_name


def test_storage_sanitization_rejects_empty() -> None:
    with pytest.raises(ValueError):
        sanitize_storage_name("   \n\t")


def test_storage_sanitization_replaces_unsafe_chars() -> None:
    assert sanitize_storage_name("../weird\\name?.pdf") == ".._weird_name_.pdf"


def test_storage_sanitization_truncates_long_names() -> None:
    long_name = "a" * 300 + ".pdf"
    cleaned = sanitize_storage_name(long_name)
    assert len(cleaned) <= 120
    assert cleaned.startswith("a")


def test_display_sanitization_blocks_excel_formulas() -> None:
    assert sanitize_display_name("=SUM(A1:A2)") == "_SUM(A1_A2)"


def test_display_sanitization_defaults_on_empty() -> None:
    assert sanitize_display_name("") == "document"
