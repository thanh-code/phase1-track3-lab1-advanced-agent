from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Optional

from .schemas import RunRecord


def _round(value: float | int | None, digits: int = 4) -> float | int | None:
    if value is None:
        return None
    return round(float(value), digits)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
    return ordered[index]


def group_by_agent(records: list[RunRecord]) -> dict[str, list[RunRecord]]:
    grouped: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.agent_type].append(record)
    return dict(grouped)


def summarize_records(records: list[RunRecord]) -> dict:
    summary: dict[str, dict] = {}
    for agent, rows in group_by_agent(records).items():
        correct = sum(1 for row in rows if row.is_correct is True)
        tokens = [row.token_estimate for row in rows]
        latencies = [row.latency_ms for row in rows]
        attempts = [row.attempts for row in rows]
        summary[agent] = {
            "count": len(rows),
            "em": round(correct / len(rows), 4) if rows else 0.0,
            "correct_count": correct,
            "incorrect_count": len(rows) - correct,
            "avg_attempts": round(mean(attempts), 4) if attempts else 0.0,
            "avg_token_estimate": round(mean(tokens), 2) if tokens else 0.0,
            "median_token_estimate": round(median(tokens), 2) if tokens else 0.0,
            "avg_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
            "median_latency_ms": round(median(latencies), 2) if latencies else 0.0,
            "p95_latency_ms": round(_p95([float(v) for v in latencies]), 2),
            "avg_reflection_count": round(mean(len(row.reflections) for row in rows), 4) if rows else 0.0,
            "avg_lats_node_count": round(mean(len(row.lats_trace) for row in rows), 4) if rows else 0.0,
            "total_tokens": sum(tokens),
            "total_input_tokens": sum(row.input_tokens for row in rows),
            "total_output_tokens": sum(row.output_tokens for row in rows),
            "total_latency_ms": sum(latencies),
            "llm_call_count": sum(row.llm_call_count for row in rows),
            "tokens_per_correct": round(sum(tokens) / correct, 2) if correct else None,
            "latency_per_correct_ms": round(sum(latencies) / correct, 2) if correct else None,
        }
    _add_deltas(summary, "reflexion", "react", "delta_reflexion_minus_react")
    _add_deltas(summary, "lats", "react", "delta_lats_minus_react")
    _add_deltas(summary, "lats", "reflexion", "delta_lats_minus_reflexion")
    return summary


def _add_deltas(summary: dict, left: str, right: str, key: str) -> None:
    if left not in summary or right not in summary:
        return
    lrow = summary[left]
    rrow = summary[right]
    summary[key] = {
        "em_abs": round(lrow["em"] - rrow["em"], 4),
        "correct_count_abs": lrow["correct_count"] - rrow["correct_count"],
        "attempts_abs": round(lrow["avg_attempts"] - rrow["avg_attempts"], 4),
        "tokens_abs": round(lrow["avg_token_estimate"] - rrow["avg_token_estimate"], 2),
        "latency_abs": round(lrow["avg_latency_ms"] - rrow["avg_latency_ms"], 2),
    }


def failure_breakdown(records: list[RunRecord]) -> dict:
    grouped: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        grouped[record.agent_type][record.failure_mode] += 1
    return {agent: dict(counter) for agent, counter in grouped.items()}


def build_examples(records: list[RunRecord]) -> list[dict]:
    return [
        {
            "qid": row.qid,
            "agent_type": row.agent_type,
            "gold_answer": row.gold_answer,
            "predicted_answer": row.predicted_answer,
            "is_correct": row.is_correct,
            "attempts": row.attempts,
            "failure_mode": row.failure_mode,
            "reflection_count": len(row.reflections),
            "lats_node_count": len(row.lats_trace),
            "token_estimate": row.token_estimate,
            "latency_ms": row.latency_ms,
        }
        for row in records
    ]


def build_qid_comparisons(records: list[RunRecord]) -> dict:
    by_qid: dict[str, dict[str, RunRecord]] = defaultdict(dict)
    for record in records:
        by_qid[record.qid][record.agent_type] = record
    comparisons: dict[str, dict] = {}
    for qid, rows in by_qid.items():
        pattern = _comparison_pattern(rows)
        any_row = next(iter(rows.values()))
        comparisons[qid] = {
            "qid": qid,
            "question": any_row.question,
            "gold_answer": any_row.gold_answer,
            "pattern": pattern,
            **{
                agent: {
                    "answer": row.predicted_answer,
                    "correct": row.is_correct,
                    "tokens": row.token_estimate,
                    "latency_ms": row.latency_ms,
                    "reflection_count": len(row.reflections),
                    "lats_node_count": len(row.lats_trace),
                }
                for agent, row in rows.items()
            },
        }
    return comparisons


def _comparison_pattern(rows: dict[str, RunRecord]) -> str:
    react = rows.get("react")
    reflexion = rows.get("reflexion")
    lats = rows.get("lats")
    r = react.is_correct is True if react else False
    f = reflexion.is_correct is True if reflexion else False
    l = lats.is_correct is True if lats else False
    if r and f and l:
        return "all_correct"
    if not r and not f and not l:
        return "all_wrong"
    if not r and f and l:
        return "reflexion_and_lats_fixed_react"
    if not r and f:
        return "reflexion_fixed_react"
    if not r and l:
        return "lats_fixed_react"
    if not r and not f and l:
        return "lats_only_correct"
    if not r and f and not l:
        return "reflexion_only_correct"
    if r and not f:
        return "reflexion_regressed"
    if r and not l:
        return "lats_regressed"
    return "mixed"


def build_react_vs_reflexion_table(records: list[RunRecord]) -> list[dict]:
    summary = summarize_records(records)
    react = summary.get("react")
    reflexion = summary.get("reflexion")
    if not react or not reflexion:
        return [{"metric": "status", "react": bool(react), "reflexion": bool(reflexion), "delta": None, "note": "not_available"}]

    def row(metric: str, rkey: str, note: str) -> dict:
        rvalue = react.get(rkey)
        fvalue = reflexion.get(rkey)
        delta = None if rvalue is None or fvalue is None else _round(float(fvalue) - float(rvalue), 4)
        return {"metric": metric, "react": rvalue, "reflexion": fvalue, "delta": delta, "note": note}

    return [
        row("records", "count", "Same dataset."),
        row("exact_match", "em", "Positive delta means Reflexion improved accuracy."),
        row("correct_count", "correct_count", "Number of questions answered correctly."),
        row("avg_attempts", "avg_attempts", "Reflexion normally spends more attempts."),
        row("avg_tokens", "avg_token_estimate", "Token tradeoff."),
        {
            "metric": "avg_runtime_seconds",
            "react": _round(react["avg_latency_ms"] / 1000, 4),
            "reflexion": _round(reflexion["avg_latency_ms"] / 1000, 4),
            "delta": _round((reflexion["avg_latency_ms"] - react["avg_latency_ms"]) / 1000, 4),
            "note": "Running-time tradeoff.",
        },
        row("tokens_per_correct", "tokens_per_correct", "Lower is more token-efficient."),
    ]


def build_cost_runtime_table(
    records: list[RunRecord],
    input_cost_per_1m: Optional[float] = None,
    output_cost_per_1m: Optional[float] = None,
) -> list[dict]:
    rows: list[dict] = []
    for agent, agent_records in group_by_agent(records).items():
        correct = sum(1 for row in agent_records if row.is_correct is True)
        input_tokens = sum(row.input_tokens for row in agent_records)
        output_tokens = sum(row.output_tokens for row in agent_records)
        total_tokens = sum(row.token_estimate for row in agent_records)
        latencies = [row.latency_ms / 1000 for row in agent_records]
        cost = None
        if input_cost_per_1m is not None and output_cost_per_1m is not None:
            cost = round((input_tokens / 1_000_000 * input_cost_per_1m) + (output_tokens / 1_000_000 * output_cost_per_1m), 6)
        rows.append(
            {
                "agent_type": agent,
                "records": len(agent_records),
                "llm_call_count": sum(row.llm_call_count for row in agent_records),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": cost,
                "total_runtime_seconds": round(sum(latencies), 4),
                "avg_runtime_seconds": round(mean(latencies), 4) if latencies else 0.0,
                "p95_runtime_seconds": round(_p95(latencies), 4),
                "avg_tokens_per_record": round(total_tokens / len(agent_records), 2) if agent_records else 0.0,
                "tokens_per_correct": round(total_tokens / correct, 2) if correct else None,
                "correct_count": correct,
                "exact_match": round(correct / len(agent_records), 4) if agent_records else 0.0,
            }
        )
    return sorted(rows, key=lambda row: row["agent_type"])


def build_reflection_analysis(records: list[RunRecord]) -> dict:
    rows = [row for row in records if row.agent_type == "reflexion"]
    attempted = sum(1 for row in rows if row.reflections)
    helped = sum(1 for row in rows if row.reflections and row.is_correct is True)
    failed = sum(1 for row in rows if row.reflections and row.is_correct is not True)
    lessons = Counter()
    for row in rows:
        for reflection in row.reflections:
            for word in reflection.lesson.lower().split():
                if len(word) > 4:
                    lessons[word.strip(".,;:")] += 1
    return {
        "reflection_attempted_count": attempted,
        "reflection_helped_count": helped,
        "reflection_failed_count": failed,
        "avg_reflections_per_question": round(mean(len(row.reflections) for row in rows), 4) if rows else 0.0,
        "common_reflection_terms": lessons.most_common(10),
    }


def build_lats_analysis(records: list[RunRecord], comparisons: dict) -> dict:
    rows = [row for row in records if row.agent_type == "lats"]
    helped = sum(1 for item in comparisons.values() if item.get("react", {}).get("correct") is False and item.get("lats", {}).get("correct") is True)
    regressed = sum(1 for item in comparisons.values() if item.get("react", {}).get("correct") is True and item.get("lats", {}).get("correct") is False)
    best_scores = [max((node.value_score for node in row.lats_trace), default=0.0) for row in rows]
    return {
        "avg_lats_nodes": round(mean(len(row.lats_trace) for row in rows), 4) if rows else 0.0,
        "early_stop_count": sum(1 for row in rows if len(row.lats_trace) <= 3),
        "avg_best_value_score": round(mean(best_scores), 4) if best_scores else 0.0,
        "critic_supported_count": sum(1 for row in rows for node in row.lats_trace if node.value_score >= 0.9),
        "lats_helped_over_react_count": helped,
        "lats_regressed_from_react_count": regressed,
    }


def build_benchmark_comments(records: list[RunRecord], comparisons: dict) -> list[str]:
    summary = summarize_records(records)
    comments: list[str] = []
    if "react" in summary and "reflexion" in summary:
        delta = summary.get("delta_reflexion_minus_react", {})
        comments.append(
            f"Reflexion changed exact match by {delta.get('em_abs', 0):+.4f} over ReAct and changed average tokens by {delta.get('tokens_abs', 0):+.2f}."
        )
    if "react" in summary and "lats" in summary:
        delta = summary.get("delta_lats_minus_react", {})
        comments.append(
            f"Limited LATS changed exact match by {delta.get('em_abs', 0):+.4f} over ReAct with an average token change of {delta.get('tokens_abs', 0):+.2f}."
        )
    failures = failure_breakdown(records)
    all_failures = Counter()
    for counter in failures.values():
        all_failures.update({key: value for key, value in counter.items() if key != "none"})
    if all_failures:
        mode, count = all_failures.most_common(1)[0]
        comments.append(f"The most common remaining failure mode was {mode} with {count} records.")
    reflection = build_reflection_analysis(records)
    if reflection["reflection_attempted_count"]:
        comments.append(
            f"Reflection memory was created on {reflection['reflection_attempted_count']} questions and helped recover {reflection['reflection_helped_count']} final answers."
        )
    if not comments:
        comments.append("Benchmark completed, but there was not enough comparative data to generate strong observations.")
    return comments


def build_discussion(summary: dict, failures: dict) -> str:
    agent_rows = {k: v for k, v in summary.items() if isinstance(v, dict) and "em" in v}
    best_agent = max(agent_rows.items(), key=lambda item: item[1].get("em", 0))[0] if agent_rows else "n/a"
    failure_counter = Counter()
    for counter in failures.values():
        failure_counter.update({key: value for key, value in counter.items() if key != "none"})
    top_modes = ", ".join(mode for mode, _ in failure_counter.most_common(3)) or "none"
    return (
        "This benchmark compares ReAct, Reflexion, and Limited LATS on the selected HotpotQA-style dataset. "
        "Reflexion is expected to help when the first answer stops at an intermediate entity or misses the second hop, "
        "while Limited LATS is expected to help when several plausible entities compete in the context. "
        f"The current run shows {best_agent} with the highest exact-match score among available agents. "
        "Reflexion changes the tradeoff by adding attempts and reflection calls, while LATS adds candidate generation and critic calls. "
        f"The main remaining failure modes were {top_modes}. "
        "Overall, the report should be read as an accuracy, token, and running-time tradeoff rather than a single-score ranking."
    )
