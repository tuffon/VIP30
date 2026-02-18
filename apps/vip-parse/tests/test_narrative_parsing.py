from __future__ import annotations

from vip_shared.bid_comp import BidComp
from vip_shared.bid_comp.core import _coerce_structured_llm_output


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


def test_extract_overview_from_markdown_collects_section_until_next_heading() -> None:
    markdown = """# Overview of Estimates
**Total Comparison**: Primary is $10,000 higher.

**Key Takeaway**: Flooring drives 60% of variance.

## Key Cost Drivers
- Flooring: $18,000 vs $12,000
"""
    overview = BidComp()._extract_overview_from_markdown(markdown)
    assert "**Total Comparison**: Primary is $10,000 higher." in overview
    assert "**Key Takeaway**: Flooring drives 60% of variance." in overview
    assert "## Key Cost Drivers" not in overview
