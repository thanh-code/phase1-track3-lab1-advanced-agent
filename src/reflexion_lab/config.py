from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.0
    timeout_seconds: float = 60.0
    input_cost_per_1m: Optional[float] = None
    output_cost_per_1m: Optional[float] = None


def _optional_float(name: str) -> Optional[float]:
    raw = os.getenv(name)
    if raw in (None, ""):
        return None
    return float(raw)


def load_settings(require_api_key: bool = False, model_override: str | None = None) -> Settings:
    load_dotenv()
    settings = Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=model_override or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0")),
        timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
        input_cost_per_1m=_optional_float("OPENAI_INPUT_COST_PER_1M"),
        output_cost_per_1m=_optional_float("OPENAI_OUTPUT_COST_PER_1M"),
    )
    if require_api_key and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --mode llm. Add it to .env first.")
    return settings
