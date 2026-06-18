import json

from src.reflexion_lab.logging_utils import BenchmarkLogger


def test_benchmark_logger_writes_jsonl(tmp_path):
    logger = BenchmarkLogger(tmp_path, run_id="test_run")
    logger.event("benchmark_start", api_key="secret", mode="mock")
    logger.llm_call(call_type="actor", total_tokens=10, success=True)
    logger.error("stage", ValueError("bad"), recoverable=True)

    assert (tmp_path / "run.log").exists()
    events = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    calls = (tmp_path / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()
    errors = (tmp_path / "errors.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(events[0])["event"] == "benchmark_start"
    assert "secret" not in events[0]
    assert json.loads(calls[0])["call_type"] == "actor"
    assert json.loads(errors[0])["error_type"] == "ValueError"
