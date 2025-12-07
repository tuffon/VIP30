from __future__ import annotations

from src.bid_comp.core import _coerce_structured_llm_output


def test_coerce_structured_llm_output_handles_single_quotes() -> None:
    raw = "{'markdown': '# Title', 'sections': {'overview_of_estimates': 'text'}}"
    payload, issues = _coerce_structured_llm_output(raw)
    assert payload is not None
    assert payload["markdown"] == "# Title"
    assert "json_error:JSONDecodeError" in issues


def test_coerce_structured_llm_output_handles_code_fence() -> None:
    raw = """```json\n{\n  \"markdown\": \"# Title\"\n}\n```"""
    payload, issues = _coerce_structured_llm_output(raw)
    assert payload is not None
    assert payload["markdown"] == "# Title"
    assert issues == []
