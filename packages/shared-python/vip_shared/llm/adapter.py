from __future__ import annotations

import json
import os
import time
import logging
from typing import Any, Dict, Type, TypeVar

import httpx
from pydantic import BaseModel

from .templates import PromptTemplate, TemplateRegistry, default_registry


DEFAULT_SYSTEM_PROMPT = "You are a concise assistant for insurance claim cost comparisons."
logger = logging.getLogger("vip-parse.llm")
T = TypeVar("T", bound=BaseModel)


class LLMAdapterBase:
    def generate(self, template_id: str, context: Dict[str, Any]) -> str:  # pragma: no cover
        raise NotImplementedError

    def generate_structured(
        self, template_id: str, context: Dict[str, Any], response_model: Type[T]
    ) -> T:  # pragma: no cover
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
            # Large estimate payloads (100k+ tokens) can take 2-3 minutes to process
            with httpx.Client(timeout=180) as client:
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

    def generate_structured(self, template_id: str, context: Dict[str, Any], response_model: Type[T]) -> T:
        try:
            from openai import OpenAI
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("openai package is required for generate_structured") from exc

        tmpl = self.registry.get(template_id)
        messages = self._build_messages(tmpl, context)
        primary_name = context.get("primary_name")
        comparison_name = context.get("comparison_name")
        start = time.perf_counter()
        logger.info(
            "llm structured request start: model=%s template=%s primary=%s comparison=%s response_model=%s",
            self.model,
            template_id,
            primary_name,
            comparison_name,
            response_model.__name__,
        )
        client = OpenAI(api_key=self.api_key)
        completion = client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=response_model,
            temperature=0.2,
            timeout=180,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        message = completion.choices[0].message
        if getattr(message, "refusal", None):
            raise ValueError(f"LLM refused structured output: {message.refusal}")
        parsed = getattr(message, "parsed", None)
        if parsed is None:
            raise ValueError("Structured output missing parsed payload")
        logger.info(
            "llm structured request complete: model=%s template=%s primary=%s comparison=%s elapsed_ms=%d",
            self.model,
            template_id,
            primary_name,
            comparison_name,
            elapsed_ms,
        )
        return parsed

    def _build_messages(self, tmpl: PromptTemplate, context: Dict[str, Any]) -> list[Dict[str, str]]:
        system_append = str(context.get("_system_append") or "").strip()
        user_append = str(context.get("_user_append") or "").strip()
        if tmpl.system or tmpl.user:
            system_prompt = (tmpl.system or DEFAULT_SYSTEM_PROMPT).format(**context)
            user_prompt = (tmpl.user or "").format(**context)
            if system_append:
                system_prompt = f"{system_prompt}\n\n{system_append}" if system_prompt else system_append
            if user_append:
                user_prompt = f"{user_prompt}\n\n{user_append}" if user_prompt else user_append
            messages: list[Dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if user_prompt:
                messages.append({"role": "user", "content": user_prompt})
            return messages

        prompt = (tmpl.content or "").format(**context)
        if user_append:
            prompt = f"{prompt}\n\n{user_append}"
        system_prompt = DEFAULT_SYSTEM_PROMPT
        if system_append:
            system_prompt = f"{system_prompt}\n\n{system_append}"
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
