from __future__ import annotations

import json
import time
from typing import Any, Optional

from .config import Settings
from .logging_utils import BenchmarkLogger
from .schemas import LLMCallResult


class OpenAIClient:
    def __init__(self, settings: Settings, logger: Optional[BenchmarkLogger] = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is required for --mode llm. Run pip install -r requirements.txt.") from exc
        self.settings = settings
        self.logger = logger
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=settings.timeout_seconds)

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> LLMCallResult:
        result = self._complete(
            system,
            user,
            temperature=self.settings.temperature if temperature is None else temperature,
            response_format={"type": "json_object"},
            metadata=metadata,
        )
        self._parse_json(result.content)
        return result

    def complete_text(
        self,
        system: str,
        user: str,
        *,
        temperature: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> LLMCallResult:
        return self._complete(
            system,
            user,
            temperature=self.settings.temperature if temperature is None else temperature,
            response_format=None,
            metadata=metadata,
        )

    def _complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        response_format: Optional[dict[str, str]],
        metadata: Optional[dict[str, Any]],
    ) -> LLMCallResult:
        start = time.perf_counter()
        success = False
        error_type = None
        content = ""
        usage = None
        try:
            kwargs: dict[str, Any] = {
                "model": self.settings.openai_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            usage = response.usage
            success = True
            return LLMCallResult(
                content=content,
                input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            if self.logger:
                meta = metadata or {}
                self.logger.llm_call(
                    **meta,
                    model=self.settings.openai_model,
                    temperature=temperature,
                    input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                    total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
                    latency_ms=latency_ms,
                    success=success,
                    error_type=error_type,
                    prompt_chars=len(system) + len(user),
                    response_chars=len(content),
                    response_preview=content[:200],
                )

    def parse_json(self, text: str) -> dict[str, Any]:
        return self._parse_json(text)

    def _parse_json(self, text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise
