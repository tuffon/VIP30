from __future__ import annotations

import json
import os
from typing import Any, Dict

import httpx

from .templates import PromptTemplate, TemplateRegistry, default_registry


DEFAULT_SYSTEM_PROMPT = "You are a concise assistant for insurance claim cost comparisons."


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
        messages = self._build_messages(tmpl, context)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
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

    def _build_messages(self, tmpl: PromptTemplate, context: Dict[str, Any]) -> list[Dict[str, str]]:
        if tmpl.system or tmpl.user:
            system_prompt = (tmpl.system or DEFAULT_SYSTEM_PROMPT).format(**context)
            user_prompt = (tmpl.user or "").format(**context)
            messages: list[Dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if user_prompt:
                messages.append({"role": "user", "content": user_prompt})
            return messages

        prompt = (tmpl.content or "").format(**context)
        return [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
