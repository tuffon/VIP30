from __future__ import annotations

import json
import os
from typing import Any, Dict

import httpx

from .templates import TemplateRegistry, default_registry


class LLMAdapterBase:
    def generate(self, template_id: str, context: Dict[str, Any]) -> str:  # pragma: no cover
        raise NotImplementedError


class OpenAIChatAdapter(LLMAdapterBase):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None, registry: TemplateRegistry | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or ""
        self.registry = registry or default_registry()
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

    def generate(self, template_id: str, context: Dict[str, Any]) -> str:
        tmpl = self.registry.get(template_id)
        prompt = tmpl.content.format(**context)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a concise assistant for insurance claim cost comparisons."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=60) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            return ""
