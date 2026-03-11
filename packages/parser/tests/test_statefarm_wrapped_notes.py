from .conftest import run_parser


def _get_line_item(parsed: dict, line_number: int) -> dict:
    for section in parsed.get("sections") or []:
        for item in section.get("line_items") or []:
            if item.get("line_number") == line_number:
                return item
    raise AssertionError(f"line item {line_number} not found")


def test_sf_bschacter_wrapped_lines_and_notes():
    parsed = run_parser("docs/final-drafts/statefarm/SF_BSchacter.pdf")

    assert parsed is not None

    line_2 = _get_line_item(parsed, 2)
    assert line_2["description"] == 'R&R 1" x 12" lumber (1 BF per LF)'
    assert line_2["notes"] == (
        "This line item accounts for additional slats & framing on the roof of the pergola."
    )

    line_276 = _get_line_item(parsed, 276)
    assert line_276["description"] == "Temporary toilet (per month)"
    assert line_276["notes"] == "End revisions by VAEMK8 on 10/3/2025"
