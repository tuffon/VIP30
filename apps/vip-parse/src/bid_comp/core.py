from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .normalize import normalize_group, normalize_label, normalize_money
from .matchers import HeuristicMatcher
from .export_xlsx import export_xlsx
from ..llm.adapter import LLMAdapterBase  # type: ignore


logger = logging.getLogger("vip-parse.bid-comp")

DEFAULT_CATEGORY = "GENERAL"
MAX_LINE_ITEMS_CONTEXT = 12
MAX_GROUPS_FOR_NARRATIVE = 6


@dataclass
class SectionLineItem:
    index: int
    description: str
    total: Optional[float]
    category: str
    qty: Optional[float]
    unit: Optional[str]
    notes: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SectionScope:
    index: int
    original_name: str
    subrooms: List[str]
    metadata: Dict[str, Any]
    line_items: List[SectionLineItem]
    category_totals: Dict[str, float]
    total: Optional[float]
    raw: Dict[str, Any] = field(default_factory=dict)
    canonical_signature: Tuple[str, ...] = field(default_factory=tuple)
    canonical_name: Optional[str] = None


@dataclass
class EstimateScope:
    sections: List[SectionScope] = field(default_factory=list)
    recap_by_category: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SectionMatchGroup:
    group_id: str
    display_name: str
    canonical_key: str
    carrier_indices: List[int]
    contractor_indices: List[int]
    method: str = "LLM"
    confidence: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class BidComp:
    matcher_mode: str = "hybrid"  # "heuristic" | "llm" | "hybrid"
    fuzzy_threshold: float = 0.90
    delta_abs_alert: float = 10000.0
    delta_pct_alert: float = 20.0
    llm_adapter: Optional[LLMAdapterBase] = None

    def __post_init__(self) -> None:
        if self.matcher_mode not in {"heuristic", "llm", "hybrid"}:
            raise ValueError("matcher_mode must be one of {'heuristic','llm','hybrid'}")
        self.fuzzy_threshold = float(self.fuzzy_threshold)
        self.delta_abs_alert = float(self.delta_abs_alert)
        self.delta_pct_alert = float(self.delta_pct_alert)

    def run(self, bid_context: dict, job_id: str) -> bytes:
        carrier_scope = self._parse_estimate_scope(bid_context.get("carrier") or {})
        contractor_scope = self._parse_estimate_scope(bid_context.get("contractor") or {})

        match_groups = self._match_sections(carrier_scope, contractor_scope)
        section_rows, section_infos = self._build_section_rows(match_groups, carrier_scope, contractor_scope)

        carrier_recap = carrier_scope.recap_by_category
        contractor_recap = contractor_scope.recap_by_category
        recap_rows = self._build_recap_rows(carrier_recap, contractor_recap)

        rows: List[Dict[str, Any]] = section_rows + recap_rows
        rows.extend(self._reconciliation_rows(carrier_recap, side="Carrier"))
        rows.extend(self._reconciliation_rows(contractor_recap, side="Contractor"))

        if section_infos and self.llm_adapter is not None and self.matcher_mode in {"llm", "hybrid"}:
            self._apply_section_narratives(section_infos)

        for row in rows:
            row.pop("_group_id", None)

        structure_text = self._structure_summary(carrier_recap, contractor_recap)
        carrier_total = self._sum_total(carrier_recap)
        contractor_total = self._sum_total(contractor_recap)

        return export_xlsx(
            rows=rows,
            carrier_total=carrier_total,
            contractor_total=contractor_total,
            structure_text=structure_text,
            delta_abs_alert=self.delta_abs_alert,
            delta_pct_alert=self.delta_pct_alert,
        )

    # ---------- section parsing ----------
    def _parse_estimate_scope(self, estimate_ctx: Dict[str, Any]) -> EstimateScope:
        if not isinstance(estimate_ctx, dict):
            return EstimateScope()
        sections: List[SectionScope] = []
        sections_raw = estimate_ctx.get("sections")
        if isinstance(sections_raw, list):
            for idx, section_obj in enumerate(sections_raw):
                parsed = self._parse_section(section_obj, idx)
                if parsed is not None:
                    sections.append(parsed)
        recap_map = self._extract_recap_from_context(estimate_ctx)
        return EstimateScope(sections=sections, recap_by_category=recap_map)

    def _parse_section(self, raw_section: Any, index: int) -> Optional[SectionScope]:
        if not isinstance(raw_section, dict):
            return None
        name = str(raw_section.get("section_name") or "").strip() or f"Section {index + 1}"
        metadata = raw_section.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        subrooms: List[str] = []
        for sr in raw_section.get("subrooms") or []:
            if isinstance(sr, dict):
                sr_name = sr.get("subroom_name")
                if sr_name:
                    subrooms.append(str(sr_name).strip())
        line_items_raw = raw_section.get("line_items")
        line_items, category_totals = self._parse_line_items(line_items_raw)
        section_totals = raw_section.get("section_totals") or {}
        total = normalize_money(section_totals.get("total"))
        return SectionScope(
            index=index,
            original_name=name,
            subrooms=subrooms,
            metadata=metadata,
            line_items=line_items,
            category_totals=category_totals,
            total=total,
            raw=raw_section,
        )

    def _parse_line_items(self, line_items_raw: Any) -> Tuple[List[SectionLineItem], Dict[str, float]]:
        items: List[SectionLineItem] = []
        category_totals: Dict[str, float] = {}
        current_category = DEFAULT_CATEGORY
        if not isinstance(line_items_raw, list):
            return items, category_totals
        for idx, entry in enumerate(line_items_raw):
            if not isinstance(entry, dict):
                continue
            entry_type = str(entry.get("type") or "line_item").lower()
            if entry_type == "header":
                header_text = normalize_label(entry.get("text") or "")
                if header_text:
                    current_category = header_text
                continue
            if entry_type != "line_item":
                continue
            total_value = normalize_money(entry.get("total"))
            qty_raw = entry.get("qty")
            qty: Optional[float] = None
            if isinstance(qty_raw, (int, float)):
                qty = float(qty_raw)
            elif isinstance(qty_raw, str):
                try:
                    qty = float(qty_raw)
                except Exception:
                    qty = None
            unit_value = entry.get("unit")
            unit = str(unit_value).strip().upper() if isinstance(unit_value, str) else None
            notes_value = entry.get("notes")
            notes = str(notes_value).strip() if isinstance(notes_value, str) else None
            description = str(entry.get("description") or "").strip()
            category_label = current_category or DEFAULT_CATEGORY
            if total_value is not None:
                category_totals[category_label] = round(category_totals.get(category_label, 0.0) + total_value, 2)
            items.append(
                SectionLineItem(
                    index=idx,
                    description=description,
                    total=total_value,
                    category=category_label,
                    qty=qty,
                    unit=unit,
                    notes=notes,
                    raw=entry,
                )
            )
        return items, category_totals

    def _extract_recap_from_context(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(ctx, dict):
            return {}
        recaps = ctx.get("recaps_and_summaries")
        if isinstance(recaps, dict):
            rb = recaps.get("recap_by_category")
            if isinstance(rb, dict):
                return rb
        rb = ctx.get("recap_by_category")
        if isinstance(rb, dict):
            return rb
        if any(key in ctx for key in ("O&P Items", "Non-O&P Items", "Items")):
            return ctx  # already appears to be recap-shaped
        return {}

    # ---------- section matching ----------
    def _match_sections(self, carrier_scope: EstimateScope, contractor_scope: EstimateScope) -> List[SectionMatchGroup]:
        if not carrier_scope.sections and not contractor_scope.sections:
            return []

        groups: List[SectionMatchGroup] = []
        if self.llm_adapter is not None and self.matcher_mode in {"llm", "hybrid"}:
            groups = self._llm_match_sections(carrier_scope, contractor_scope)
        if not groups:
            groups = self._fallback_section_groups(carrier_scope, contractor_scope)
        return groups

    def _section_descriptor(self, scope: SectionScope) -> Dict[str, Any]:
        line_items = [
            {
                "description": li.description,
                "total": li.total,
                "category": li.category,
            }
            for li in scope.line_items[:MAX_LINE_ITEMS_CONTEXT]
        ]
        return {
            "index": scope.index,
            "name": scope.original_name,
            "subrooms": scope.subrooms,
            "line_items": line_items,
            "total": scope.total,
        }

    def _llm_match_sections(self, carrier_scope: EstimateScope, contractor_scope: EstimateScope) -> List[SectionMatchGroup]:
        carrier_desc = [self._section_descriptor(sec) for sec in carrier_scope.sections]
        contractor_desc = [self._section_descriptor(sec) for sec in contractor_scope.sections]
        context = {
            "carrier_json": json.dumps(carrier_desc, ensure_ascii=False),
            "contractor_json": json.dumps(contractor_desc, ensure_ascii=False),
        }
        try:
            raw = self.llm_adapter.generate("match_sections_llm", context)
        except Exception as exc:  # noqa: BLE001
            logger.warning("match_sections_llm failed: %s", exc)
            return []
        groups, used_left, used_right = self._parse_llm_section_groups(raw, len(carrier_desc), len(contractor_desc))
        self._append_unmatched_groups(groups, used_left, used_right, carrier_scope, contractor_scope, method="LLM")
        return groups

    def _parse_llm_section_groups(
        self,
        raw: str,
        carrier_count: int,
        contractor_count: int,
    ) -> Tuple[List[SectionMatchGroup], set[int], set[int]]:
        try:
            data = json.loads(raw)
        except Exception:
            logger.warning("match_sections_llm returned non-JSON payload")
            return [], set(), set()

        groups: List[SectionMatchGroup] = []
        used_left: set[int] = set()
        used_right: set[int] = set()
        if not isinstance(data, dict):
            return groups, used_left, used_right

        for idx, entry in enumerate(data.get("groups") or []):
            if not isinstance(entry, dict):
                continue
            display = str(entry.get("canonical") or entry.get("name") or f"Group {idx + 1}").strip()
            display = display or f"Group {idx + 1}"
            canonical_key = normalize_label(display) or display.upper()
            left_indices = self._safe_index_list(entry.get("carrier"), carrier_count)
            right_indices = self._safe_index_list(entry.get("contractor"), contractor_count)
            if not left_indices and not right_indices:
                continue
            used_left.update(left_indices)
            used_right.update(right_indices)
            group_id = str(entry.get("id") or f"group_{idx}")
            groups.append(
                SectionMatchGroup(
                    group_id=group_id,
                    display_name=display,
                    canonical_key=canonical_key,
                    carrier_indices=left_indices,
                    contractor_indices=right_indices,
                    method="LLM",
                    confidence=self._safe_float(entry.get("confidence")),
                    notes=entry.get("notes"),
                )
            )
        return groups, used_left, used_right

    def _safe_index_list(self, value: Any, upper_bound: int) -> List[int]:
        indices: List[int] = []
        if isinstance(value, list):
            for v in value:
                try:
                    idx = int(v)
                except Exception:
                    continue
                if 0 <= idx < upper_bound:
                    indices.append(idx)
        elif value is not None:
            try:
                idx = int(value)
            except Exception:
                idx = -1
            if 0 <= idx < upper_bound:
                indices.append(idx)
        return indices

    def _safe_float(self, value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except Exception:
                return None
        return None

    def _append_unmatched_groups(
        self,
        groups: List[SectionMatchGroup],
        used_left: set[int],
        used_right: set[int],
        carrier_scope: EstimateScope,
        contractor_scope: EstimateScope,
        method: str,
    ) -> None:
        for idx, section in enumerate(carrier_scope.sections):
            if idx in used_left:
                continue
            display = section.original_name or f"Carrier Section {idx + 1}"
            canonical_key = normalize_label(display) or display.upper()
            groups.append(
                SectionMatchGroup(
                    group_id=f"carrier_only_{idx}",
                    display_name=display,
                    canonical_key=canonical_key,
                    carrier_indices=[idx],
                    contractor_indices=[],
                    method=method,
                    notes="Unmatched carrier section",
                )
            )
        for idx, section in enumerate(contractor_scope.sections):
            if idx in used_right:
                continue
            display = section.original_name or f"Contractor Section {idx + 1}"
            canonical_key = normalize_label(display) or display.upper()
            groups.append(
                SectionMatchGroup(
                    group_id=f"contractor_only_{idx}",
                    display_name=display,
                    canonical_key=canonical_key,
                    carrier_indices=[],
                    contractor_indices=[idx],
                    method=method,
                    notes="Unmatched contractor section",
                )
            )

    def _fallback_section_groups(self, carrier_scope: EstimateScope, contractor_scope: EstimateScope) -> List[SectionMatchGroup]:
        left_map: Dict[str, List[int]] = {}
        for idx, section in enumerate(carrier_scope.sections):
            key = normalize_label(section.original_name) or f"carrier_{idx}"
            left_map.setdefault(key, []).append(idx)
        right_map: Dict[str, List[int]] = {}
        for idx, section in enumerate(contractor_scope.sections):
            key = normalize_label(section.original_name) or f"contractor_{idx}"
            right_map.setdefault(key, []).append(idx)

        groups: List[SectionMatchGroup] = []
        used_left: set[int] = set()
        used_right: set[int] = set()
        for key in sorted(set(left_map.keys()) | set(right_map.keys())):
            left_indices = left_map.get(key, [])
            right_indices = right_map.get(key, [])
            if not left_indices and not right_indices:
                continue
            display = ""
            if left_indices:
                display = carrier_scope.sections[left_indices[0]].original_name
            elif right_indices:
                display = contractor_scope.sections[right_indices[0]].original_name
            display = display or key.title()
            groups.append(
                SectionMatchGroup(
                    group_id=f"fallback_{key}",
                    display_name=display,
                    canonical_key=key,
                    carrier_indices=left_indices,
                    contractor_indices=right_indices,
                    method="Heuristic",
                )
            )
            used_left.update(left_indices)
            used_right.update(right_indices)

        self._append_unmatched_groups(groups, used_left, used_right, carrier_scope, contractor_scope, method="Heuristic")
        return groups

    # ---------- section summarisation ----------
    def _aggregate_sections(self, sections: List[SectionScope]) -> Tuple[Optional[float], Dict[str, float], List[Dict[str, Any]]]:
        if not sections:
            return None, {}, []

        total_value = 0.0
        has_total = False
        category_totals: Dict[str, float] = {}
        line_items: List[Dict[str, Any]] = []

        for section in sections:
            if section.total is not None:
                total_value += section.total
                has_total = True
            else:
                subtotal = sum(li.total or 0.0 for li in section.line_items)
                if subtotal:
                    total_value += subtotal
                    has_total = True
            for cat, val in section.category_totals.items():
                category_totals[cat] = round(category_totals.get(cat, 0.0) + val, 2)
            for li in section.line_items:
                if li.total is None:
                    continue
                line_items.append(
                    {
                        "description": li.description,
                        "total": li.total,
                        "category": li.category,
                    }
                )

        aggregated_total = round(total_value, 2) if has_total else None
        line_items_sorted = sorted(line_items, key=lambda x: abs(x["total"] or 0.0), reverse=True)[:MAX_LINE_ITEMS_CONTEXT]
        return aggregated_total, category_totals, line_items_sorted

    def _build_section_rows(
        self,
        match_groups: List[SectionMatchGroup],
        carrier_scope: EstimateScope,
        contractor_scope: EstimateScope,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        summaries: List[Dict[str, Any]] = []
        for group in match_groups:
            summary = self._summarize_group(group, carrier_scope, contractor_scope)
            if summary is not None:
                summaries.append(summary)

        summaries.sort(key=lambda s: abs(s["delta_abs"]), reverse=True)

        rows: List[Dict[str, Any]] = []
        for summary in summaries:
            rows.append(summary["section_row"])
            rows.extend(summary["category_rows"])

        return rows, summaries

    def _summarize_group(
        self,
        group: SectionMatchGroup,
        carrier_scope: EstimateScope,
        contractor_scope: EstimateScope,
    ) -> Optional[Dict[str, Any]]:
        carrier_sections = [carrier_scope.sections[i] for i in group.carrier_indices if 0 <= i < len(carrier_scope.sections)]
        contractor_sections = [
            contractor_scope.sections[i] for i in group.contractor_indices if 0 <= i < len(contractor_scope.sections)
        ]

        carrier_total, carrier_categories, carrier_items = self._aggregate_sections(carrier_sections)
        contractor_total, contractor_categories, contractor_items = self._aggregate_sections(contractor_sections)

        delta_abs = (contractor_total or 0.0) - (carrier_total or 0.0)
        delta_pct = (delta_abs / carrier_total) if (carrier_total or 0) else None

        carrier_names = "; ".join(sec.original_name for sec in carrier_sections) or ""
        contractor_names = "; ".join(sec.original_name for sec in contractor_sections) or ""
        source_groups = f"carrier={carrier_names or '-'} | contractor={contractor_names or '-'}"

        flags = None
        if carrier_sections and not contractor_sections:
            flags = "CarrierOnly"
        elif contractor_sections and not carrier_sections:
            flags = "ContractorOnly"

        section_row = {
            "TYPE": "SECTION",
            "CANONICAL GROUP": group.display_name,
            "NAME": group.display_name,
            "CARRIER TOTAL ($)": carrier_total,
            "CONTRACTOR TOTAL ($)": contractor_total,
            "Δ ($)": delta_abs,
            "Δ (% OF CARRIER)": delta_pct,
            "SOURCE GROUPS": source_groups,
            "COVERAGE NOTE": None,
            "MATCHING NOTE": group.method,
            "FLAGS": flags,
            "COMMENTS": group.notes,
            "NARRATIVE": None,
            "_group_id": group.group_id,
        }

        canonical_tuple = (group.canonical_key,) if group.canonical_key else ()
        for sec in carrier_sections:
            sec.canonical_signature = canonical_tuple
            sec.canonical_name = group.display_name
        for sec in contractor_sections:
            sec.canonical_signature = canonical_tuple
            sec.canonical_name = group.display_name

        category_rows: List[Dict[str, Any]] = []
        all_categories = set(carrier_categories.keys()) | set(contractor_categories.keys())
        for category in sorted(all_categories):
            left_val = carrier_categories.get(category)
            right_val = contractor_categories.get(category)
            delta_cat = (right_val or 0.0) - (left_val or 0.0)
            pct_cat = (delta_cat / left_val) if (left_val or 0) else None
            category_rows.append(
                {
                    "TYPE": "CATEGORY",
                    "CANONICAL GROUP": group.display_name,
                    "NAME": f"{group.display_name} :: {category}",
                    "CARRIER TOTAL ($)": left_val,
                    "CONTRACTOR TOTAL ($)": right_val,
                    "Δ ($)": delta_cat,
                    "Δ (% OF CARRIER)": pct_cat,
                    "SOURCE GROUPS": source_groups,
                    "COVERAGE NOTE": None,
                    "MATCHING NOTE": group.method,
                    "FLAGS": None,
                    "COMMENTS": None,
                    "NARRATIVE": None,
                }
            )

        return {
            "group": group,
            "section_row": section_row,
            "category_rows": category_rows,
            "carrier_items": carrier_items,
            "contractor_items": contractor_items,
            "delta_abs": delta_abs,
        }

    # ---------- recap logic ----------
    def _build_recap_rows(self, carrier: dict, contractor: dict) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        c_groups = self._collect_groups(carrier)
        k_groups = self._collect_groups(contractor)
        if not c_groups and not k_groups:
            return rows
        matcher = HeuristicMatcher(aliases={}, fuzzy_threshold=self.fuzzy_threshold)
        match_map = matcher.match_sets(list(c_groups.keys()), list(k_groups.keys()))
        for left_norm, mr in match_map.items():
            left_group = c_groups.get(left_norm)
            right_group = k_groups.get(mr.right or "")
            if left_group is None and right_group is None:
                continue
            if left_group is not None and right_group is not None:
                rows.extend(self._rows_for_category_pair(left_group, right_group, mr))
            else:
                rows.extend(self._rows_item_fallback(left_group, right_group, mr))
        rows.extend(self._subtotal_rows(carrier, contractor))
        return rows

    def _collect_groups(self, recap: dict) -> Dict[str, Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        for raw_group, items in recap.items():
            canon = normalize_group(raw_group)
            if canon in {"O&P ITEMS", "NON-O&P ITEMS"}:
                canon = "O&P ITEMS"
            groups.setdefault(canon, {"name": canon, "items": [], "source": set()})
            bucket = groups[canon]
            bucket["source"].add(normalize_label(raw_group))
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
        return [
            {
                "TYPE": "RECAP",
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
                "NARRATIVE": None,
            }
        ]

    def _rows_item_fallback(self, left_group: Optional[dict], right_group: Optional[dict], mr) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        left_items = (left_group or {}).get("items") or []
        right_items = (right_group or {}).get("items") or []
        right_map = {it.get("name"): it for it in right_items if it.get("name")}
        used_right: set[str] = set()
        for it in left_items:
            nm = it.get("name")
            ltot = it.get("total")
            rtot = None
            note = "Unmatched"
            if nm in right_map:
                rtot = right_map[nm].get("total")
                used_right.add(nm)
                note = "Exact"
            delta_abs = (rtot or 0.0) - (ltot or 0.0)
            delta_pct = (delta_abs / ltot) if (ltot or 0) > 0 else None
            rows.append(
                {
                    "TYPE": "RECAP-ITEM",
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
                    "NARRATIVE": None,
                }
            )
        for it in right_items:
            nm = it.get("name")
            if not nm or nm in used_right:
                continue
            rtot = it.get("total")
            rows.append(
                {
                    "TYPE": "RECAP-ITEM",
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
                    "NARRATIVE": None,
                }
            )
        return rows

    def _source_groups(self, left_group: Optional[dict], right_group: Optional[dict]) -> str:
        l = ",".join(sorted((left_group or {}).get("source", []))) or ""
        r = ",".join(sorted((right_group or {}).get("source", []))) or ""
        return f"carrier={l} | contractor={r}"

    def _structure_summary(self, carrier_recap: dict, contractor_recap: dict) -> str:
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

        return f"Carrier {summarize(carrier_recap)}; Contractor {summarize(contractor_recap)}"

    def _subtotal_rows(self, carrier: dict, contractor: dict) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
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
                            "SOURCE GROUPS": side_name,
                            "COVERAGE NOTE": None,
                            "MATCHING NOTE": "",
                            "FLAGS": None,
                            "COMMENTS": None,
                            "NARRATIVE": None,
                        }
                    )
        return rows

    def _reconciliation_rows(self, recap: dict, side: str) -> List[Dict[str, Any]]:
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
        if abs((lhs or 0.0) - (total or 0.0)) <= 0.02:
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
                "NARRATIVE": None,
            }
        ]

    def _sum_total(self, recap: dict) -> float:
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

    # ---------- narratives ----------
    def _apply_section_narratives(self, section_infos: List[Dict[str, Any]]) -> None:
        top_infos = sorted(section_infos, key=lambda info: abs(info["delta_abs"]), reverse=True)[:MAX_GROUPS_FOR_NARRATIVE]
        if not top_infos:
            return
        payload = []
        for info in top_infos:
            section_row = info["section_row"]
            group = info["group"]
            payload.append(
                {
                    "group_id": group.group_id,
                    "name": group.display_name,
                    "carrier_total": section_row.get("CARRIER TOTAL ($)"),
                    "contractor_total": section_row.get("CONTRACTOR TOTAL ($)"),
                    "delta": section_row.get("Δ ($)"),
                    "carrier_line_items": info["carrier_items"],
                    "contractor_line_items": info["contractor_items"],
                }
            )
        try:
            response = self.llm_adapter.generate(
                "section_delta_narrative",
                {"groups_json": json.dumps(payload, ensure_ascii=False)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("section_delta_narrative failed: %s", exc)
            return
        try:
            mapping = json.loads(response)
        except Exception:
            logger.warning("section_delta_narrative returned non-JSON payload")
            return
        if not isinstance(mapping, dict):
            return
        for info in top_infos:
            section_row = info["section_row"]
            group = info["group"]
            narrative = mapping.get(group.group_id) or mapping.get(group.display_name) or mapping.get(group.canonical_key)
            if isinstance(narrative, str) and narrative.strip():
                section_row["NARRATIVE"] = narrative.strip()

