from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

from .normalize import normalize_label


@dataclass
class MatchResult:
    left: str
    right: Optional[str]
    score: Optional[float]
    method: str  # "Exact" | "Alias" | "Fuzzy=x.xx" | "LLM" | "Unmatched"


class HeuristicMatcher:
    def __init__(self, aliases: Dict[str, str] | None = None, fuzzy_threshold: float = 0.90) -> None:
        self.aliases = {normalize_label(k): normalize_label(v) for k, v in (aliases or {}).items()}
        self.fuzzy_threshold = float(fuzzy_threshold)

    def _alias(self, key: str) -> Optional[str]:
        return self.aliases.get(normalize_label(key))

    def _activity_parts(self, label: str, item: Optional[dict]) -> Optional[tuple[str, str, str]]:
        if isinstance(item, dict):
            cat = str(item.get("cat") or "").strip().upper()
            sel = str(item.get("sel") or "").strip().upper()
            act = str(item.get("act") or "").strip().upper()
            if cat and sel:
                return (cat, sel, act)

        match = re.match(r"^\s*([A-Z]{2,4})\s+([A-Z0-9\-]{1,20})(?:\s+([A-Z0-9+\-]{1,10}))?", label or "")
        if not match:
            return None
        cat = (match.group(1) or "").upper()
        sel = (match.group(2) or "").upper()
        act = (match.group(3) or "").upper()
        if not cat or not sel:
            return None
        return (cat, sel, act)

    def match_sets(
        self,
        left_labels: List[str],
        right_labels: List[str],
        left_items: Optional[List[dict]] = None,
        right_items: Optional[List[dict]] = None,
    ) -> Dict[str, MatchResult]:
        left_norm = [normalize_label(x) for x in left_labels]
        right_norm = [normalize_label(x) for x in right_labels]
        unused_right: set[str] = set(right_norm)
        results: Dict[str, MatchResult] = {}

        # Pass 0: activity-code and cat+sel matches (if both sides have code data)
        left_codes: Dict[str, tuple[str, str, str]] = {}
        right_codes: Dict[str, tuple[str, str, str]] = {}
        for idx, key in enumerate(left_norm):
            label = left_labels[idx] if idx < len(left_labels) else ""
            item = left_items[idx] if isinstance(left_items, list) and idx < len(left_items) else None
            parts = self._activity_parts(label, item)
            if parts:
                left_codes[key] = parts
        for idx, key in enumerate(right_norm):
            label = right_labels[idx] if idx < len(right_labels) else ""
            item = right_items[idx] if isinstance(right_items, list) and idx < len(right_items) else None
            parts = self._activity_parts(label, item)
            if parts:
                right_codes[key] = parts

        if left_codes and right_codes:
            by_full_right: Dict[tuple[str, str, str], List[str]] = {}
            by_cat_sel_right: Dict[tuple[str, str], List[str]] = {}
            for key, parts in right_codes.items():
                by_full_right.setdefault(parts, []).append(key)
                by_cat_sel_right.setdefault((parts[0], parts[1]), []).append(key)

            for left_key in left_norm:
                if left_key in results or left_key not in left_codes:
                    continue
                parts = left_codes[left_key]
                full_matches = [r for r in by_full_right.get(parts, []) if r in unused_right]
                if full_matches:
                    right_key = sorted(full_matches)[0]
                    results[left_key] = MatchResult(left=left_key, right=right_key, score=1.0, method="activity_code")
                    unused_right.remove(right_key)

            for left_key in left_norm:
                if left_key in results or left_key not in left_codes:
                    continue
                cat, sel, _ = left_codes[left_key]
                cat_sel_matches = [r for r in by_cat_sel_right.get((cat, sel), []) if r in unused_right]
                if cat_sel_matches:
                    right_key = sorted(cat_sel_matches)[0]
                    results[left_key] = MatchResult(left=left_key, right=right_key, score=1.0, method="cat_sel")
                    unused_right.remove(right_key)

        # Pass 1: exact matches
        for l in left_norm:
            if l in results:
                continue
            if l in unused_right:
                results[l] = MatchResult(left=l, right=l, score=1.0, method="Exact")
                unused_right.remove(l)

        # Pass 2: alias map
        for l in left_norm:
            if l in results:
                continue
            alias = self._alias(l)
            if alias and alias in unused_right:
                results[l] = MatchResult(left=l, right=alias, score=1.0, method="Alias")
                unused_right.remove(alias)

        # Pass 3: fuzzy
        remaining_left = [l for l in left_norm if l not in results]
        if remaining_left and unused_right:
            # Build a lookup for fuzzy choices
            choices = list(unused_right)
            for l in remaining_left:
                match = process.extractOne(
                    l,
                    choices,
                    scorer=fuzz.WRatio,
                )
                if match is None:
                    continue
                r, score, _ = match
                if score >= self.fuzzy_threshold * 100.0 and r in unused_right:
                    results[l] = MatchResult(left=l, right=r, score=score / 100.0, method=f"Fuzzy={score/100.0:.2f}")
                    unused_right.remove(r)

        # Rest: unmatched
        for l in left_norm:
            if l not in results:
                results[l] = MatchResult(left=l, right=None, score=None, method="Unmatched")

        return results


