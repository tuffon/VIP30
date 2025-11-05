from __future__ import annotations

from dataclasses import dataclass
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

    def match_sets(self, left_labels: List[str], right_labels: List[str]) -> Dict[str, MatchResult]:
        left_norm = [normalize_label(x) for x in left_labels]
        right_norm = [normalize_label(x) for x in right_labels]
        unused_right: set[str] = set(right_norm)
        results: Dict[str, MatchResult] = {}

        # Pass 1: exact matches
        for l in left_norm:
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


