from __future__ import annotations

import json
import html
from pathlib import Path
from typing import Optional

from .evaluation import (
    build_benchmark_comments,
    build_cost_runtime_table,
    build_discussion,
    build_examples,
    build_lats_analysis,
    build_qid_comparisons,
    build_react_vs_reflexion_table,
    build_reflection_analysis,
    failure_breakdown,
    summarize_records,
)
from .schemas import ReportPayload, RunRecord
from .utils import write_json


def build_report(
    records: list[RunRecord],
    dataset_name: str,
    mode: str = "mock",
    meta_extra: Optional[dict] = None,
    input_cost_per_1m: Optional[float] = None,
    output_cost_per_1m: Optional[float] = None,
    golden: bool = False,
) -> ReportPayload:
    summary = summarize_records(records)
    failures = failure_breakdown(records)
    comparisons = build_qid_comparisons(records)
    comments = build_benchmark_comments(records, comparisons)
    react_vs_reflexion_table = build_react_vs_reflexion_table(records)
    cost_runtime_table = build_cost_runtime_table(records, input_cost_per_1m, output_cost_per_1m)
    reflection_analysis = build_reflection_analysis(records)
    lats_analysis = build_lats_analysis(records, comparisons)
    agents = sorted({record.agent_type for record in records})
    extensions = [
        "structured_evaluator",
        "reflection_memory",
        "benchmark_report_json",
        "mock_mode_for_autograding",
    ]
    if "lats" in agents:
        extensions.append("mini_lats_branching")

    meta = {
        "dataset": dataset_name,
        "mode": mode,
        "num_records": len(records),
        "agents": agents,
    }
    if meta_extra:
        meta.update(meta_extra)

    return ReportPayload(
        meta=meta,
        summary=summary,
        failure_modes=failures,
        examples=build_examples(records),
        comparisons=comparisons,
        comments=comments,
        react_vs_reflexion_table=react_vs_reflexion_table,
        cost_runtime_table=cost_runtime_table,
        reflection_analysis=reflection_analysis,
        lats_analysis=lats_analysis,
        cost_latency={"cost_runtime_table": cost_runtime_table},
        golden_submission=build_golden_submission(records, summary, comparisons, dataset_name, meta) if golden else None,
        extensions=extensions,
        discussion=build_discussion(summary, failures),
        artifacts={
            "benchmark_config": "benchmark_config.json",
            "dataset_manifest": "dataset_manifest.json",
            "events": "events.jsonl",
            "llm_calls": "llm_calls.jsonl",
            "errors": "errors.jsonl",
            "react_vs_reflexion_table": "analysis/react_vs_reflexion_table.json",
            "cost_runtime_table": "analysis/cost_runtime_table.json",
            "golden_submission": "analysis/golden_submission.json" if golden else None,
            "visual_report": "visual_report.html",
        },
    )


def build_golden_submission(
    records: list[RunRecord],
    summary: dict,
    comparisons: dict,
    dataset_name: str,
    meta: dict,
) -> dict:
    agents = [agent for agent in ("lats", "reflexion", "react") if agent in meta.get("agents", [])]
    primary = agents[0] if agents else "react"
    answers = []
    for item in comparisons.values():
        primary_row = item.get(primary, {})
        answers.append(
            {
                "qid": item["qid"],
                "question": item.get("question", ""),
                "gold_answer": item.get("gold_answer") or None,
                "react_answer": item.get("react", {}).get("answer"),
                "reflexion_answer": item.get("reflexion", {}).get("answer"),
                "lats_answer": item.get("lats", {}).get("answer"),
                "final_answer": primary_row.get("answer"),
                "final_agent": primary,
                "is_correct": primary_row.get("correct"),
            }
        )
    return {
        "run_id": meta.get("run_id"),
        "dataset": dataset_name,
        "model": meta.get("model"),
        "mode": meta.get("mode"),
        "agents": meta.get("agents", []),
        "primary_agent": primary,
        "created_at": meta.get("created_at"),
        "summary": summary,
        "answers": answers,
    }


def save_report(report: ReportPayload, out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir = out_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    html_path = out_dir / "visual_report.html"
    json_path.write_text(json.dumps(report.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    html_path.write_text(_render_visual_html(report), encoding="utf-8")

    write_json(analysis_dir / "failure_examples.json", _failure_examples(report))
    write_json(analysis_dir / "improvement_examples.json", _improvement_examples(report))
    write_json(analysis_dir / "agent_comparison.json", report.comparisons)
    write_json(analysis_dir / "react_vs_reflexion_table.json", report.react_vs_reflexion_table)
    write_json(analysis_dir / "cost_runtime_table.json", report.cost_runtime_table)
    write_json(analysis_dir / "cost_latency_summary.json", report.cost_latency)
    if report.golden_submission is not None:
        write_json(analysis_dir / "golden_submission.json", report.golden_submission)

    return json_path, md_path


def _render_markdown(report: ReportPayload) -> str:
    return f"""# Lab 16 Benchmark Report

## Metadata

- Dataset: {report.meta.get('dataset')}
- Mode: {report.meta.get('mode')}
- Records: {report.meta.get('num_records')}
- Agents: {', '.join(report.meta.get('agents', []))}
- Model: {report.meta.get('model', 'n/a')}

## Summary

{_summary_table(report.summary)}

## ReAct vs Reflexion

{_generic_table(report.react_vs_reflexion_table, ['metric', 'react', 'reflexion', 'delta', 'note'])}

## Agent Comparison

Pattern counts:

```json
{json.dumps(_pattern_counts(report.comparisons), indent=2, ensure_ascii=False)}
```

## Failure Modes

```json
{json.dumps(report.failure_modes, indent=2, ensure_ascii=False)}
```

## Reflection Analysis

```json
{json.dumps(report.reflection_analysis, indent=2, ensure_ascii=False)}
```

## Limited LATS Analysis

```json
{json.dumps(report.lats_analysis, indent=2, ensure_ascii=False)}
```

## Cost And Running Time

{_generic_table(report.cost_runtime_table, ['agent_type', 'records', 'llm_call_count', 'total_tokens', 'estimated_cost_usd', 'total_runtime_seconds', 'avg_runtime_seconds', 'p95_runtime_seconds', 'exact_match'])}

## Representative Examples

```json
{json.dumps(report.examples[:10], indent=2, ensure_ascii=False)}
```

## Automated Comments

{chr(10).join(f'- {comment}' for comment in report.comments)}

## Extensions Implemented

{chr(10).join(f'- {item}' for item in report.extensions)}

## Discussion

{report.discussion}

## Artifacts

```json
{json.dumps(report.artifacts, indent=2, ensure_ascii=False)}
```
"""


def _render_visual_html(report: ReportPayload) -> str:
    title = f"{report.meta.get('dataset', 'Benchmark')} - Agent Comparison"
    cards = _visual_kpi_cards(report)
    em_chart = _visual_bar_chart(report, "em", "Exact Match", scale=1.0, value_suffix="")
    token_chart = _visual_bar_chart(report, "total_tokens", "Total Tokens", scale=None, value_suffix=" tokens")
    runtime_chart = _visual_runtime_chart(report)
    rvf_table = _visual_table(report.react_vs_reflexion_table, ["metric", "react", "reflexion", "delta", "note"])
    cost_table = _visual_table(
        report.cost_runtime_table,
        ["agent_type", "records", "llm_call_count", "total_tokens", "estimated_cost_usd", "total_runtime_seconds", "avg_runtime_seconds", "exact_match"],
    )
    comments = "\n".join(f"<li>{html.escape(comment)}</li>" for comment in report.comments)
    failure_modes = html.escape(json.dumps(report.failure_modes, ensure_ascii=False, indent=2))
    lats_config = report.meta.get("lats_config") or {}
    lats_note = ""
    if "lats" in report.meta.get("agents", []):
        lats_note = (
            "<p class=\"note\">Limited LATS is capped for transparency: "
            f"branching_factor={html.escape(str(lats_config.get('branching_factor', 2)))}, "
            f"max_depth={html.escape(str(lats_config.get('max_depth', 2)))}, "
            f"max_nodes={html.escape(str(lats_config.get('max_nodes', 5)))}.</p>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f7f7f4;
      --panel: #ffffff;
      --ink: #1d2528;
      --muted: #5f6b70;
      --line: #d9ded9;
      --react: #2563eb;
      --reflexion: #059669;
      --lats: #d97706;
      --shadow: 0 10px 28px rgba(20, 28, 32, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }}
    header {{ margin-bottom: 22px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(28px, 5vw, 48px); letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 21px; }}
    p {{ margin: 0; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }}
    .pill {{ border: 1px solid var(--line); background: #fff; border-radius: 999px; padding: 6px 10px; color: var(--muted); font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
    .section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); padding: 18px; margin-top: 16px; }}
    .card {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; }}
    .agent {{ font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
    .big {{ font-size: 34px; font-weight: 780; margin-top: 4px; }}
    .sub {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
    .bar-row {{ display: grid; grid-template-columns: 110px minmax(180px, 1fr) 120px; gap: 10px; align-items: center; margin: 10px 0; }}
    .bar-track {{ height: 26px; background: #edf0ed; border-radius: 4px; overflow: hidden; border: 1px solid var(--line); }}
    .bar-fill {{ height: 100%; min-width: 2px; }}
    .react {{ background: var(--react); }}
    .reflexion {{ background: var(--reflexion); }}
    .lats {{ background: var(--lats); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 700; background: #fafaf8; }}
    .note, .muted {{ color: var(--muted); }}
    .insights li {{ margin: 8px 0; }}
    pre {{ white-space: pre-wrap; background: #f3f4f1; border: 1px solid var(--line); border-radius: 8px; padding: 12px; overflow: auto; }}
    @media (max-width: 820px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .bar-row {{ grid-template-columns: 86px 1fr; }}
      .bar-row .value {{ grid-column: 2; }}
      table {{ font-size: 13px; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>Agent Benchmark</h1>
    <p class="muted">Focused visual comparison of ReAct, Reflexion, and Limited LATS. Only benchmark-derived metrics are shown.</p>
    <div class="meta">
      <span class="pill">Dataset: {html.escape(str(report.meta.get('dataset', 'n/a')))}</span>
      <span class="pill">Mode: {html.escape(str(report.meta.get('mode', 'n/a')))}</span>
      <span class="pill">Model: {html.escape(str(report.meta.get('model', 'n/a')))}</span>
      <span class="pill">Records: {html.escape(str(report.meta.get('num_records', 'n/a')))}</span>
      <span class="pill">Agents: {html.escape(', '.join(report.meta.get('agents', [])))}</span>
    </div>
  </header>

  <section class="grid">
    {cards}
  </section>

  <section class="section">
    <h2>Accuracy</h2>
    {em_chart}
  </section>

  <section class="section">
    <h2>Token Use</h2>
    <p class="note">Higher token use may improve recovery/search, but it is also the main cost driver.</p>
    {token_chart}
  </section>

  <section class="section">
    <h2>Running Time</h2>
    <p class="note">Runtime is computed from recorded agent call latency, not from page rendering time.</p>
    {runtime_chart}
  </section>

  <section class="section">
    <h2>ReAct vs Reflexion</h2>
    {rvf_table}
  </section>

  <section class="section">
    <h2>Cost And Runtime Table</h2>
    <p class="note">Estimated cost is shown only when pricing environment variables are provided; otherwise it remains n/a.</p>
    {cost_table}
  </section>

  <section class="section insights">
    <h2>Evaluation Notes</h2>
    <ul>{comments}</ul>
    <p class="note">{html.escape(report.discussion)}</p>
    {lats_note}
  </section>

  <section class="section">
    <h2>Failure Modes</h2>
    <pre>{failure_modes}</pre>
  </section>
</main>
</body>
</html>
"""


def _visual_kpi_cards(report: ReportPayload) -> str:
    cards: list[str] = []
    for agent in _ordered_agents(report.summary):
        row = report.summary[agent]
        cards.append(
            f"""<article class="card">
  <div class="agent">{html.escape(agent)}</div>
  <div class="big">{_format_cell(row.get('em', 0))}</div>
  <div class="sub">EM, {html.escape(str(row.get('correct_count', 0)))} / {html.escape(str(row.get('count', 0)))} correct</div>
  <div class="sub">Avg tokens: {_format_cell(row.get('avg_token_estimate', 0))}</div>
  <div class="sub">Avg runtime: {_format_cell((row.get('avg_latency_ms', 0) or 0) / 1000)}s</div>
</article>"""
        )
    return "\n".join(cards)


def _visual_bar_chart(report: ReportPayload, metric: str, label: str, scale: Optional[float], value_suffix: str) -> str:
    agents = _ordered_agents(report.summary)
    values = [float(report.summary[agent].get(metric, 0) or 0) for agent in agents]
    max_value = scale if scale is not None else max(values or [1.0])
    max_value = max(max_value or 1.0, 1e-9)
    rows: list[str] = []
    for agent, value in zip(agents, values):
        width = max(0.0, min(100.0, value / max_value * 100))
        rows.append(
            f"""<div class="bar-row">
  <strong>{html.escape(agent)}</strong>
  <div class="bar-track"><div class="bar-fill {html.escape(agent)}" style="width:{width:.2f}%"></div></div>
  <div class="value">{_format_cell(value)}{html.escape(value_suffix)}</div>
</div>"""
        )
    return f"<p class=\"note\">{html.escape(label)}</p>" + "\n".join(rows)


def _visual_runtime_chart(report: ReportPayload) -> str:
    agents = _ordered_agents(report.summary)
    values = {agent: (report.summary[agent].get("avg_latency_ms", 0) or 0) / 1000 for agent in agents}
    max_value = max(values.values() or [1.0])
    rows = []
    for agent in agents:
        value = values[agent]
        width = max(0.0, min(100.0, value / max(max_value, 1e-9) * 100))
        rows.append(
            f"""<div class="bar-row">
  <strong>{html.escape(agent)}</strong>
  <div class="bar-track"><div class="bar-fill {html.escape(agent)}" style="width:{width:.2f}%"></div></div>
  <div class="value">{_format_cell(value)}s avg</div>
</div>"""
        )
    return "\n".join(rows)


def _visual_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "<p class=\"note\">No data.</p>"
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(_format_cell(row.get(column)))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _ordered_agents(summary: dict) -> list[str]:
    preferred = ["react", "reflexion", "lats"]
    present = [agent for agent in preferred if agent in summary and isinstance(summary[agent], dict) and "em" in summary[agent]]
    extras = [agent for agent, row in summary.items() if agent not in preferred and isinstance(row, dict) and "em" in row]
    return present + extras


def _summary_table(summary: dict) -> str:
    agents = [key for key, value in summary.items() if isinstance(value, dict) and "em" in value]
    lines = ["| Agent | Count | EM | Correct | Avg Attempts | Avg Tokens | Avg Latency (ms) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for agent in agents:
        row = summary[agent]
        lines.append(
            f"| {agent} | {row.get('count', 0)} | {row.get('em', 0)} | {row.get('correct_count', 0)} | {row.get('avg_attempts', 0)} | {row.get('avg_token_estimate', 0)} | {row.get('avg_latency_ms', 0)} |"
        )
    return "\n".join(lines)


def _generic_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "No data."
    header = "| " + " | ".join(columns) + " |"
    align = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(_format_cell(row.get(column)) for column in columns) + " |")
    return "\n".join([header, align, *body])


def _format_cell(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _pattern_counts(comparisons: dict) -> dict:
    counts: dict[str, int] = {}
    for item in comparisons.values():
        pattern = item.get("pattern", "unknown")
        counts[pattern] = counts.get(pattern, 0) + 1
    return counts


def _failure_examples(report: ReportPayload) -> dict:
    grouped: dict[str, list[dict]] = {}
    for example in report.examples:
        if example.get("is_correct") is True:
            continue
        grouped.setdefault(example["agent_type"], []).append(example)
    return {agent: rows[:10] for agent, rows in grouped.items()}


def _improvement_examples(report: ReportPayload) -> dict:
    buckets = {
        "reflexion_fixed_react": [],
        "lats_fixed_react": [],
        "lats_only_correct": [],
        "all_wrong": [],
    }
    for item in report.comparisons.values():
        pattern = item.get("pattern")
        if pattern in buckets:
            buckets[pattern].append(item)
        if pattern == "reflexion_and_lats_fixed_react":
            buckets["reflexion_fixed_react"].append(item)
            buckets["lats_fixed_react"].append(item)
    return {key: value[:10] for key, value in buckets.items()}
