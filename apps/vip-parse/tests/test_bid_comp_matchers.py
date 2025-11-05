from src.bid_comp.matchers import HeuristicMatcher


def test_fuzzy_match():
    left = ["PERMITS AND FEES", "MATERIAL SALES TAX"]
    right = ["PERMITS & FEES", "SALES TAX ON MATERIALS"]
    m = HeuristicMatcher(aliases={"PERMITS & FEES": "PERMITS AND FEES", "SALES TAX ON MATERIALS": "MATERIAL SALES TAX"}, fuzzy_threshold=0.80)
    res = m.match_sets(left, right)
    assert res["PERMITS AND FEES"].right in {"PERMITS & FEES", "PERMITS AND FEES"}
    assert res["MATERIAL SALES TAX"].method.startswith("Alias") or res["MATERIAL SALES TAX"].method.startswith("Fuzzy")


