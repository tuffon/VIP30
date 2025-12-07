from __future__ import annotations

from src.bid_comp.core import _coerce_structured_llm_output
from src.bid_comp.export_xlsx import _extract_first_paragraph


def test_coerce_structured_llm_output_handles_single_quotes() -> None:
    raw = "{'markdown': '# Title', 'sections': {'overview_of_estimates': 'text'}}"
    payload, issues, stage = _coerce_structured_llm_output(raw)
    assert payload is not None
    assert payload["markdown"] == "# Title"
    assert "json_error:JSONDecodeError" in issues
    assert stage == "literal"


def test_coerce_structured_llm_output_handles_code_fence() -> None:
    raw = """```json\n{\n  \"markdown\": \"# Title\"\n}\n```"""
    payload, issues, stage = _coerce_structured_llm_output(raw)
    assert payload is not None
    assert payload["markdown"] == "# Title"
    assert issues == []
    assert stage == "json"


def test_coerce_structured_llm_output_handles_preamble_text() -> None:
    raw = "Here you go:\n{\n  \"markdown\": \"# Title\",\n  \"sections\": {}\n}\nThanks!"
    payload, issues, stage = _coerce_structured_llm_output(raw)
    assert payload is not None
    assert payload["markdown"] == "# Title"
    assert not any(tag.startswith("snippet_error") for tag in issues)
    assert stage == "snippet"


def test_extract_first_paragraph_skips_heading() -> None:
    blocks = [
        type("Block", (), {"kind": "heading", "text": "# Overview"})(),
        type("Block", (), {"kind": "paragraph", "text": "Summary paragraph."})(),
    ]
    assert _extract_first_paragraph(blocks) == "Summary paragraph."
