from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class PromptTemplate:
    id: str
    description: str
    content: str  # uses str.format(**context)


class TemplateRegistry:
    def __init__(self) -> None:
        self._by_id: Dict[str, PromptTemplate] = {}

    def register(self, tmpl: PromptTemplate) -> None:
        self._by_id[tmpl.id] = tmpl

    def get(self, tmpl_id: str) -> PromptTemplate:
        if tmpl_id not in self._by_id:
            raise KeyError(f"prompt template not found: {tmpl_id}")
        return self._by_id[tmpl_id]

    def load_from_dir(self, directory: str) -> None:
        base = Path(directory)
        if not base.exists() or not base.is_dir():
            return
        for p in base.glob("*.json"):
            try:
                with p.open("r", encoding="utf-8") as f:
                    obj = json.load(f)
                self.register(PromptTemplate(
                    id=obj["id"],
                    description=obj.get("description", ""),
                    content=obj["content"],
                ))
            except Exception:
                continue


def default_registry() -> TemplateRegistry:
    reg = TemplateRegistry()
    # Default: explain top deltas succinctly
    reg.register(PromptTemplate(
        id="explain_bid_comp",
        description="Explain key differences between carrier and contractor totals in a few sentences.",
        content=(
            "You are a cost analyst. Given these rows with large deltas, write a brief, clear explanation for a claims professional.\n"
            "Rows (JSON): {rows_json}\n"
            "Instructions:\n"
            "- Focus on categories/items with biggest absolute or percentage deltas.\n"
            "- Mention likely drivers (O&P split, fees/tax differences, missing items).\n"
            "- Keep it under 6 sentences, no numbers beyond those provided, no speculation.\n"
        ),
    ))
    # Default: map labels
    reg.register(PromptTemplate(
        id="map_labels",
        description="Map noisy labels to canonical targets.",
        content=(
            "Map these source labels to the target set. Respond JSON {{source: target}}.\n"
            "Sources: {sources}\nTargets: {targets}\n"
            "Rules: return only string-to-string mappings; do not invent numbers; skip if unsure."
        ),
    ))
    # Optional directory
    prompt_dir = os.getenv("PROMPT_DIR")
    if prompt_dir:
        reg.load_from_dir(prompt_dir)
    return reg
