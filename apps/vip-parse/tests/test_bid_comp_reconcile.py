from src.bid_comp import BidComp


def test_bid_comp_export_bytes():
    bid_context = {
        "carrier": {
            "sections": [
                {
                    "section_name": "Kitchen",
                    "subrooms": [],
                    "line_items": [
                        {"type": "line_item", "description": "Cabinet Replace", "qty": 1, "unit": "EA", "total": "1000"},
                        {"type": "line_item", "description": "Paint Walls", "qty": 1, "unit": "EA", "total": "500"},
                    ],
                    "section_totals": {"total": "1500"},
                }
            ],
            "recap_by_category": {
                "Items": [
                    {"name": "Kitchen", "total": 1500},
                ],
                "Permits": [{"name": "Permit", "total": 100}],
                "Sales Tax": [{"name": "Tax", "total": 50}],
            },
        },
        "contractor": {
            "sections": [
                {
                    "section_name": "Kitchen / Dining",
                    "subrooms": ["Dining"],
                    "line_items": [
                        {"type": "line_item", "description": "Cabinet Replace", "qty": 1, "unit": "EA", "total": "1200"},
                        {"type": "line_item", "description": "Install Island", "qty": 1, "unit": "EA", "total": "700"},
                    ],
                    "section_totals": {"total": "1900"},
                }
            ],
            "recap_by_category": {
                "Line Items": [
                    {"name": "Kitchen / Dining", "total": 1900},
                ],
                "Fees": [{"name": "Permit", "total": 120}],
                "Sales Tax": [{"name": "Tax", "total": 60}],
            },
        },
    }
    bc = BidComp()
    data = bc.run(bid_context, job_id="test")
    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 1000


