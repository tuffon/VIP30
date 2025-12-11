from __future__ import annotations

import json
import os
import time
import logging
from typing import Any, Dict

import httpx

from .templates import PromptTemplate, TemplateRegistry, default_registry


DEFAULT_SYSTEM_PROMPT = "You are a concise assistant for insurance claim cost comparisons."
logger = logging.getLogger("vip-parse.llm")


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
        primary_name = context.get("primary_name")
        comparison_name = context.get("comparison_name")
        user_chars = len(messages[-1].get("content") or "") if messages else 0
        try:
            category_count = len(json.loads(context.get("category_table_json") or "[]"))
        except Exception:
            category_count = None
        logger.info(
            "llm request start: model=%s template=%s primary=%s comparison=%s user_chars=%d category_rows=%s",
            self.model,
            template_id,
            primary_name,
            comparison_name,
            user_chars,
            category_count,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        prompt_bytes = len(json.dumps(body, ensure_ascii=False))
        start = time.perf_counter()
        resp = None
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            body_preview = ""
            try:
                body_preview = (exc.response.text or "")[:1000]
            except Exception:
                body_preview = "<unavailable>"
            logger.error(
                "llm request failed: model=%s template=%s primary=%s comparison=%s elapsed_ms=%d status=%s body_preview=%s error=%s",
                self.model,
                template_id,
                primary_name,
                comparison_name,
                elapsed_ms,
                exc.response.status_code if exc.response is not None else "n/a",
                body_preview,
                exc,
            )
            raise
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "llm request failed: model=%s template=%s primary=%s comparison=%s elapsed_ms=%d error=%s",
                self.model,
                template_id,
                primary_name,
                comparison_name,
                elapsed_ms,
                exc,
            )
            raise
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        usage = data.get("usage") or {}
        try:
            content = (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            content = ""
        response_preview = ""
        if resp is not None:
            try:
                response_preview = (resp.text or "")[:1000]
            except Exception:
                response_preview = "<unavailable>"
        logger.info(
            "llm request complete: model=%s template=%s primary=%s comparison=%s elapsed_ms=%d prompt_bytes=%d prompt_tokens=%s completion_tokens=%s preview=%s response_preview=%s",
            self.model,
            template_id,
            primary_name,
            comparison_name,
            elapsed_ms,
            prompt_bytes,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            content[:200],
            response_preview,
        )
        return content

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
