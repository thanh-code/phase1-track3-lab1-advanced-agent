import pytest
from pydantic import ValidationError

from src.reflexion_lab.schemas import JudgeResult, LATSConfig, LATSNode, ReflectionEntry, RunRecord


def test_judge_result_schema():
    judge = JudgeResult(score=1, reason="ok", confidence=1.0, failure_mode="none")
    assert judge.score == 1
    with pytest.raises(ValidationError):
        JudgeResult(score=2, reason="bad")


def test_reflection_entry_schema():
    reflection = ReflectionEntry(
        attempt_id=1,
        failure_reason="stopped early",
        lesson="finish both hops",
        next_strategy="check bridge entity then final property",
    )
    assert reflection.attempt_id == 1


def test_lats_defaults_are_limited():
    config = LATSConfig()
    assert config.branching_factor == 2
    assert config.max_depth == 2
    assert config.max_nodes == 5


def test_lats_run_record_schema():
    record = RunRecord(
        qid="q1",
        question="question",
        gold_answer="answer",
        agent_type="lats",
        predicted_answer="answer",
        is_correct=True,
        attempts=1,
        token_estimate=10,
        latency_ms=5,
        failure_mode="none",
        lats_trace=[LATSNode(node_id="root", depth=0)],
    )
    assert record.agent_type == "lats"
