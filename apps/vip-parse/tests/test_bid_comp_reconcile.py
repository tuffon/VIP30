from src.bid_comp import BidComp


def test_bid_comp_export_bytes():
    recap = {
        "carrier": {
            "Items": [
                {"name": "Widget A", "total": 1000},
                {"name": "Widget B", "total": 500},
            ],
            "Permits": [{"name": "Permit", "total": 100}],
            "Sales Tax": [{"name": "Tax", "total": 50}],
        },
        "contractor": {
            "Line Items": [
                {"name": "Widget A", "total": 1200},
                {"name": "Widget C", "total": 300},
            ],
            "Fees": [{"name": "Permit", "total": 120}],
            "Sales Tax": [{"name": "Tax", "total": 60}],
        },
    }
    bc = BidComp()
    data = bc.run(recap, job_id="test")
    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 1000


