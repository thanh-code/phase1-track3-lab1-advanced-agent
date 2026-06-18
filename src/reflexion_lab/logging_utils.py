from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class BenchmarkLogger:
    def __init__(self, out_dir: Path, run_id: str, level: str = "INFO") -> None:
        self.out_dir = Path(out_dir)
        self.run_id = run_id
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.out_dir / "events.jsonl"
        self.llm_calls_path = self.out_dir / "llm_calls.jsonl"
        self.errors_path = self.out_dir / "errors.jsonl"
        self.run_log_path = self.out_dir / "run.log"
        for path in (self.events_path, self.llm_calls_path, self.errors_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

        self.logger = logging.getLogger(f"reflexion_lab.{run_id}")
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.handlers.clear()
        handler = logging.FileHandler(self.run_log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def _write_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        safe = {key: value for key, value in payload.items() if "api_key" not in key.lower()}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")

    def info(self, message: str, **fields: object) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in fields.items())
        self.logger.info("%s%s%s", message, " " if suffix else "", suffix)

    def event(self, event: str, **fields: object) -> None:
        payload = {"ts": utc_now_iso(), "event": event, "run_id": self.run_id, **fields}
        self._write_jsonl(self.events_path, payload)
        self.info(event, **fields)

    def llm_call(self, **fields: object) -> None:
        payload = {"ts": utc_now_iso(), "run_id": self.run_id, **fields}
        self._write_jsonl(self.llm_calls_path, payload)

    def error(self, stage: str, error: Exception, **fields: object) -> None:
        payload = {
            "ts": utc_now_iso(),
            "run_id": self.run_id,
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error),
            **fields,
        }
        self._write_jsonl(self.errors_path, payload)
        self.logger.exception("%s failed: %s", stage, error)
