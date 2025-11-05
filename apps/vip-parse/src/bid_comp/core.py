from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .normalize import normalize_group, normalize_label, normalize_money, normalize_coverage_label
from .matchers import HeuristicMatcher
from .export_xlsx import export_xlsx
from ..llm.adapter import LLMAdapterBase  # type: ignore


class LLMAdapter:
    def map_labels(self, labels: List[str]) -> Dict[str, str]:  # pragma: no cover
        raise NotImplementedError


@dataclass
class BidComp:
    matcher_mode: str = "hybrid"  # "heuristic" | "llm" | "hybrid"
    fuzzy_threshold: float = 0.90
    delta_abs_alert: float = 10000.0
    delta_pct_alert: float = 20.0
    llm_adapter: Optional[LLMAdapterBase] = None

    def __post_init__(self) -> None:
        # lightweight validation without external deps
        if self.matcher_mode not in {"heuristic", "llm", "hybrid"}:
            raise ValueError("matcher_mode must be one of {'heuristic','llm','hybrid'}")
        self.fuzzy_threshold = float(self.fuzzy_threshold)
        self.delta_abs_alert = float(self.delta_abs_alert)
        self.delta_pct_alert = float(self.delta_pct_alert)

    def run(self, recap_by_category: dict, job_id: str) -> bytes:
        carrier = recap_by_category.get("carrier") or {}
        contractor = recap_by_category.get("contractor") or {}

        # Extract categories and items from both sides; normalize totals
        c_groups = self._collect_groups(carrier)
        k_groups = self._collect_groups(contractor)

        # Try group-level matching first
        matcher = HeuristicMatcher(aliases={}, fuzzy_threshold=self.fuzzy_threshold)
        match_map = matcher.match_sets(list(c_groups.keys()), list(k_groups.keys()))

        rows: List[Dict[str, Any]] = []
        structure_text = self._structure_summary(c_groups, k_groups)

        # Build rows per matched group or fallback to item-level when unmatched
        for left_norm, mr in match_map.items():
            left_group = c_groups.get(left_norm)
            right_group = k_groups.get(mr.right or "")
            if left_group is None and right_group is None:
                continue
            if left_group is not None and right_group is not None:
                # category-level compare
                rows.extend(self._rows_for_category_pair(left_group, right_group, mr))
            else:
                # fallback to item-level rollup under ITEMS
                rows.extend(self._rows_item_fallback(left_group, right_group, mr))

        # Add recognizable subtotals if present on either side
        rows.extend(self._subtotal_rows(carrier, contractor))

        # Reconciliation checks
        rows.extend(self._reconciliation_rows(carrier, side="Carrier"))
        rows.extend(self._reconciliation_rows(contractor, side="Contractor"))

        # Optional LLM notes
        if self.llm_adapter is not None and self.matcher_mode in {"llm", "hybrid"}:
            try:
                # Build compact rows context: top 6 by abs delta
                def delta_abs_value(r: Dict[str, Any]) -> float:
                    v = r.get("Δ ($)")
                    return abs(float(v)) if isinstance(v, (int, float)) else 0.0
                top = sorted([r for r in rows if r.get("Δ ($)") is not None], key=delta_abs_value, reverse=True)[:6]
                context = {"rows_json": __import__("json").dumps(top, ensure_ascii=False)}
                notes = self.llm_adapter.generate("explain_bid_comp", context).strip()
                if notes:
                    rows.insert(0, {
                        "TYPE": "SUBTOTAL",
                        "CANONICAL GROUP": "TOTAL",
                        "NAME": "LLM Notes",
                        "CARRIER TOTAL ($)": None,
                        "CONTRACTOR TOTAL ($)": None,
                        "Δ ($)": None,
                        "Δ (% OF CARRIER)": None,
                        "SOURCE GROUPS": None,
                        "COVERAGE NOTE": None,
                        "MATCHING NOTE": "LLM",
                        "FLAGS": None,
                        "COMMENTS": notes,
                    })
            except Exception:
                # fail-closed: no LLM output
                pass

        # Totals for summary rows
        carrier_total = self._sum_total(carrier)
        contractor_total = self._sum_total(contractor)

        return export_xlsx(
            rows=rows,
            carrier_total=carrier_total,
            contractor_total=contractor_total,
            structure_text=structure_text,
            delta_abs_alert=self.delta_abs_alert,
            delta_pct_alert=self.delta_pct_alert,
        )

    # ---------------- internals ----------------
    def _collect_groups(self, recap: dict) -> Dict[str, Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        # Expect recap structure: {"O&P Items": [..], "Non-O&P Items": [..], ...}
        for raw_group, items in recap.items():
            canon = normalize_group(raw_group)
            groups.setdefault(canon, {"name": canon, "items": [], "source": set()})
            bucket = groups[canon]
            bucket["source"].add(normalize_label(raw_group))
            # item could be dicts with name/total; keep as-is with normalization later
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        name = normalize_label(str(it.get("name") or it.get("item") or ""))
                        total = normalize_money(it.get("total") or it.get("amount"))
                        if name:
                            bucket["items"].append({"name": name, "total": total})
        return groups

    def _rows_for_category_pair(self, left_group: dict, right_group: dict, mr) -> List[Dict[str, Any]]:
        left_total = sum(x.get("total") or 0.0 for x in left_group["items"]) or None
        right_total = sum(x.get("total") or 0.0 for x in right_group["items"]) or None
        delta_abs = (right_total or 0.0) - (left_total or 0.0)
        delta_pct = (delta_abs / left_total) if (left_total or 0) > 0 else None
        src_groups = f"carrier={','.join(sorted(left_group['source']))} | contractor={','.join(sorted(right_group['source']))}"
        rows = [
            {
                "TYPE": "CATEGORY",
                "CANONICAL GROUP": left_group["name"],
                "NAME": left_group["name"],
                "CARRIER TOTAL ($)": left_total,
                "CONTRACTOR TOTAL ($)": right_total,
                "Δ ($)": delta_abs,
                "Δ (% OF CARRIER)": delta_pct,
                "SOURCE GROUPS": src_groups,
                "COVERAGE NOTE": None,
                "MATCHING NOTE": mr.method,
                "FLAGS": None,
                "COMMENTS": None,
            }
        ]
        return rows

    def _rows_item_fallback(self, left_group: Optional[dict], right_group: Optional[dict], mr) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        left_items = (left_group or {}).get("items") or []
        right_items = (right_group or {}).get("items") or []
        # Map by name for simple equal-name comparison (deterministic)
        right_map = {it.get("name"): it for it in right_items if it.get("name")}
        used_right: set[str] = set()
        # Emit pairs for left items
        for it in left_items:
            nm = it.get("name")
            ltot = it.get("total")
            rtot = None
            if nm in right_map:
                rtot = right_map[nm].get("total")
                used_right.add(nm)
                note = "Exact"
            else:
                note = "Unmatched"
            delta_abs = (rtot or 0.0) - (ltot or 0.0)
            delta_pct = (delta_abs / ltot) if (ltot or 0) > 0 else None
            rows.append(
                {
                    "TYPE": "ITEM",
                    "CANONICAL GROUP": "ITEMS",
                    "NAME": nm,
                    "CARRIER TOTAL ($)": ltot,
                    "CONTRACTOR TOTAL ($)": rtot,
                    "Δ ($)": delta_abs,
                    "Δ (% OF CARRIER)": delta_pct,
                    "SOURCE GROUPS": self._source_groups(left_group, right_group),
                    "COVERAGE NOTE": None,
                    "MATCHING NOTE": note,
                    "FLAGS": None,
                    "COMMENTS": None,
                }
            )
        # Emit unmatched right-only items
        for it in right_items:
            nm = it.get("name")
            if not nm or nm in used_right:
                continue
            rtot = it.get("total")
            rows.append(
                {
                    "TYPE": "ITEM",
                    "CANONICAL GROUP": "ITEMS",
                    "NAME": nm,
                    "CARRIER TOTAL ($)": None,
                    "CONTRACTOR TOTAL ($)": rtot,
                    "Δ ($)": rtot or 0.0,
                    "Δ (% OF CARRIER)": None,
                    "SOURCE GROUPS": self._source_groups(left_group, right_group),
                    "COVERAGE NOTE": None,
                    "MATCHING NOTE": "Unmatched",
                    "FLAGS": None,
                    "COMMENTS": None,
                }
            )
        return rows

    def _source_groups(self, left_group: Optional[dict], right_group: Optional[dict]) -> str:
        l = ",".join(sorted((left_group or {}).get("source", []))) or ""
        r = ",".join(sorted((right_group or {}).get("source", []))) or ""
        return f"carrier={l} | contractor={r}"

    def _structure_summary(self, c_groups: Dict[str, Any], k_groups: Dict[str, Any]) -> str:
        def summarize(groups: Dict[str, Any]) -> str:
            has_split = any(g in groups for g in ("O&P ITEMS", "NON-O&P ITEMS"))
            has_items = "ITEMS" in groups
            if has_split and not has_items:
                return "split O&P/Non-O&P"
            if has_items and not has_split:
                return "only Items"
            if has_split and has_items:
                return "Items plus O&P split"
            return "unknown"

        c_txt = summarize(c_groups)
        k_txt = summarize(k_groups)
        return f"Carrier {c_txt}; Contractor {k_txt}"

    def _subtotal_rows(self, carrier: dict, contractor: dict) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        # Recognizable labels are groups like OVERHEAD, PROFIT, TAX, PERMITS/FEES
        for side_name, recap in (("Carrier", carrier), ("Contractor", contractor)):
            for grp_label, items in recap.items():
                canon = normalize_group(grp_label)
                if canon in {"OVERHEAD", "PROFIT", "MATERIAL SALES TAX", "PERMITS AND FEES"}:
                    total = sum(normalize_money(it.get("total")) or 0.0 for it in (items or []) if isinstance(it, dict))
                    rows.append(
                        {
                            "TYPE": "SUBTOTAL",
                            "CANONICAL GROUP": canon,
                            "NAME": f"{canon} ({side_name})",
                            "CARRIER TOTAL ($)": total if side_name == "Carrier" else None,
                            "CONTRACTOR TOTAL ($)": total if side_name == "Contractor" else None,
                            "Δ ($)": None,
                            "Δ (% OF CARRIER)": None,
                            "SOURCE GROUPS": f"{side_name}",
                            "COVERAGE NOTE": None,
                            "MATCHING NOTE": "",
                            "FLAGS": None,
                            "COMMENTS": None,
                        }
                    )
        return rows

    def _reconciliation_rows(self, recap: dict, side: str) -> List[Dict[str, Any]]:
        # Heuristic check: TOTAL should approx sum of key components
        total = self._sum_total(recap)
        buckets = {normalize_group(k): v for k, v in recap.items()}
        base_items = buckets.get("ITEMS") or []
        items_total = sum(normalize_money(it.get("total")) or 0.0 for it in base_items if isinstance(it, dict))
        ono_total = sum(
            sum(normalize_money(it.get("total")) or 0.0 for it in (buckets.get(g) or []) if isinstance(it, dict))
            for g in ("O&P ITEMS", "NON-O&P ITEMS")
        )
        fees_total = sum(
            sum(normalize_money(it.get("total")) or 0.0 for it in (buckets.get(g) or []) if isinstance(it, dict))
            for g in ("PERMITS AND FEES", "MATERIAL SALES TAX", "OVERHEAD", "PROFIT")
        )
        lhs = (ono_total if ono_total > 0 else items_total) + fees_total
        ok = abs((lhs or 0.0) - (total or 0.0)) <= 0.02
        if ok:
            return []
        explain = f"Reconciliation mismatch on {side}: computed={lhs:.2f} vs total={total:.2f}"
        return [
            {
                "TYPE": "SUBTOTAL",
                "CANONICAL GROUP": "TOTAL",
                "NAME": f"Reconciliation ({side})",
                "CARRIER TOTAL ($)": total if side == "Carrier" else None,
                "CONTRACTOR TOTAL ($)": total if side == "Contractor" else None,
                "Δ ($)": None,
                "Δ (% OF CARRIER)": None,
                "SOURCE GROUPS": side,
                "COVERAGE NOTE": None,
                "MATCHING NOTE": "",
                "FLAGS": "ReconciliationError",
                "COMMENTS": explain,
            }
        ]

    def _sum_total(self, recap: dict) -> float:
        # If a TOTAL bucket exists, prefer summing it; otherwise sum all items
        buckets = {normalize_group(k): v for k, v in recap.items()}
        if "TOTAL" in buckets:
            return sum(normalize_money(it.get("total")) or 0.0 for it in (buckets["TOTAL"] or []) if isinstance(it, dict))
        total = 0.0
        for items in buckets.values():
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict):
                    total += normalize_money(it.get("total")) or 0.0
        return round(total, 2)


