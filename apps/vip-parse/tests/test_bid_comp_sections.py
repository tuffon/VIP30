from __future__ import annotations

import json

from src.bid_comp import BidComp
from src.llm.adapter import LLMAdapterBase


class StubLLM(LLMAdapterBase):
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str]]] = []

    def generate(self, template_id: str, context: dict[str, str]) -> str:
        self.calls.append((template_id, context))
        return self.responses.get(template_id, "{}")


def test_parse_estimate_scope_builds_sections():
    bc = BidComp()
    context = {
        "sections": [
            {
                "section_name": "Living Room",
                "subrooms": [{"subroom_name": "Hall"}],
                "line_items": [
                    {"type": "line_item", "description": "Paint walls", "qty": 1, "unit": "EA", "total": "250.00"},
                    {"type": "header", "text": "Ceiling"},
                    {"type": "line_item", "description": "Paint ceiling", "qty": 1, "unit": "EA", "total": "150.00"},
                ],
                "section_totals": {"total": "400"},
            }
        ],
    }
    scope = bc._parse_estimate_scope(context)  # type: ignore[attr-defined]
    assert len(scope.sections) == 1
    section = scope.sections[0]
    assert section.original_name == "Living Room"
    assert section.subrooms == ["Hall"]
    assert section.total == 400.0
    assert section.category_totals  # headers captured category rollups


def test_llm_match_and_narrative_flow():
    responses = {
        "match_sections_llm": json.dumps(
            {
                "groups": [
                    {"id": "g1", "canonical": "Kitchen", "carrier": [0], "contractor": [0], "confidence": 0.9},
                ],
                "unmatched_carrier": [],
                "unmatched_contractor": [],
            }
        ),
        "section_delta_narrative": json.dumps(
            {"g1": "Contractor includes island and lighting not present in the carrier scope."}
        ),
    }
    stub = StubLLM(responses)
    bc = BidComp(llm_adapter=stub)

    carrier_context = {
        "sections": [
            {
                "section_name": "Kitchen",
                "line_items": [
                    {"type": "line_item", "description": "Replace cabinets", "qty": 1, "unit": "EA", "total": "5000"},
                    {"type": "line_item", "description": "Paint walls", "qty": 1, "unit": "EA", "total": "800"},
                ],
                "section_totals": {"total": "5800"},
            }
        ],
        "recap_by_category": {"Items": [{"name": "Kitchen", "total": 5800}]},
    }
    contractor_context = {
        "sections": [
            {
                "section_name": "Kitchen / Dining",
                "line_items": [
                    {"type": "line_item", "description": "Replace cabinets", "qty": 1, "unit": "EA", "total": "5200"},
                    {"type": "line_item", "description": "Install island", "qty": 1, "unit": "EA", "total": "2000"},
                ],
                "section_totals": {"total": "7200"},
            }
        ],
        "recap_by_category": {"Line Items": [{"name": "Kitchen / Dining", "total": 7200}]},
    }

    carrier_scope = bc._parse_estimate_scope(carrier_context)  # type: ignore[attr-defined]
    contractor_scope = bc._parse_estimate_scope(contractor_context)  # type: ignore[attr-defined]

    groups = bc._match_sections(carrier_scope, contractor_scope)  # type: ignore[attr-defined]
    assert len(groups) == 1
    assert groups[0].display_name == "Kitchen"
    assert groups[0].carrier_indices == [0]
    assert groups[0].contractor_indices == [0]

    rows, infos = bc._build_section_rows(groups, carrier_scope, contractor_scope)  # type: ignore[attr-defined]
    assert any(row["TYPE"] == "SECTION" for row in rows)

    bc._apply_section_narratives(infos)  # type: ignore[attr-defined]
    narratives = [info["section_row"]["NARRATIVE"] for info in infos]
    assert any("island" in (text or "").lower() for text in narratives)

