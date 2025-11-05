from __future__ import annotations

from typing import Dict, Set


CANONICAL_GROUPS: Set[str] = {
    "ITEMS",
    "O&P ITEMS",
    "NON-O&P ITEMS",
    "PERMITS AND FEES",
    "MATERIAL SALES TAX",
    "OVERHEAD",
    "PROFIT",
    "TOTAL",
}


GROUP_ALIASES: Dict[str, str] = {
    # Items
    "ITEM": "ITEMS",
    "LINE ITEMS": "ITEMS",
    "LINE-ITEMS": "ITEMS",
    # O&P
    "O&P": "O&P ITEMS",
    "OP": "O&P ITEMS",
    "O AND P": "O&P ITEMS",
    "OVERHEAD AND PROFIT ITEMS": "O&P ITEMS",
    # Non-O&P
    "NON OP": "NON-O&P ITEMS",
    "NON-O&P": "NON-O&P ITEMS",
    "NON O&P": "NON-O&P ITEMS",
    # Permits/fees
    "PERMITS": "PERMITS AND FEES",
    "FEES": "PERMITS AND FEES",
    # Tax
    "SALES TAX": "MATERIAL SALES TAX",
    "MATERIAL TAX": "MATERIAL SALES TAX",
    # Overhead/profit subtotals (non-item O&P)
    "OH": "OVERHEAD",
    "O/H": "OVERHEAD",
    # Profit
    # Total
    "GRAND TOTAL": "TOTAL",
    "SUBTOTAL": "TOTAL",  # used only when clearly a whole-document subtotal
}


COVERAGE_ALIASES: Dict[str, str] = {
    "DWELLING": "DWELLING",
    "COVERAGE A": "DWELLING",
    "OTHER STRUCTURES": "OTHER STRUCTURES",
    "COVERAGE B": "OTHER STRUCTURES",
    "PERSONAL PROPERTY": "PERSONAL PROPERTY",
    "COVERAGE C": "PERSONAL PROPERTY",
}


def canonicalize_group(label: str) -> str:
    s = (label or "").upper().strip().replace("—", "-").replace("–", "-")
    while "  " in s:
        s = s.replace("  ", " ")
    if s in CANONICAL_GROUPS:
        return s
    mapped = GROUP_ALIASES.get(s)
    if mapped:
        return mapped
    # try removing punctuation variations
    s2 = s.replace("&", "AND").replace("'", "").replace(",", "")
    mapped = GROUP_ALIASES.get(s2)
    if mapped:
        return mapped
    return "ITEMS"


