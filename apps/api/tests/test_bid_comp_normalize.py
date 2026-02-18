from vip_shared.bid_comp.normalize import normalize_money, normalize_label, normalize_group


def test_normalize_money():
    assert normalize_money("$1,234.56") == 1234.56
    assert normalize_money("  ") is None
    assert normalize_money(None) is None


def test_normalize_label_and_group():
    assert normalize_label("  O & p  items  ") == "O & P ITEMS"
    assert normalize_group("o&p") == "O&P ITEMS"
    assert normalize_group("Line Items") == "ITEMS"


