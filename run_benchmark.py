from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich import print

from src.reflexion_lab.agents import LATSAgent, ReActAgent, ReflexionAgent
from src.reflexion_lab.config import load_settings
from src.reflexion_lab.llm_client import OpenAIClient
from src.reflexion_lab.llm_runtime import LLMRuntime
from src.reflexion_lab.logging_utils import BenchmarkLogger, utc_now_iso
from src.reflexion_lab.mock_runtime import MockRuntime
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.schemas import LATSConfig, RunRecord
from src.reflexion_lab.utils import build_dataset_manifest, load_dataset_auto, save_jsonl, write_json

app = typer.Typer(add_completion=False)

ALLOWED_AGENTS = {"react", "reflexion", "lats"}


def _run_id(dataset: str, mode: str, model: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{Path(dataset).stem}_{mode}_{model}".replace("/", "_")


def _parse_agents(value: str) -> list[str]:
    agents = [item.strip().lower() for item in value.split(",") if item.strip()]
    invalid = [agent for agent in agents if agent not in ALLOWED_AGENTS]
    if invalid:
        raise typer.BadParameter(f"Unsupported agents: {invalid}. Allowed: {sorted(ALLOWED_AGENTS)}")
    return agents


def _make_runtime(mode: str, logger: BenchmarkLogger, model_override: Optional[str] = None):
    if mode == "mock":
        return MockRuntime(), "mock"
    settings = load_settings(require_api_key=True, model_override=model_override)
    client = OpenAIClient(settings, logger=logger)
    return LLMRuntime(client), settings.openai_model


def _make_agent(agent_type: str, runtime, logger: BenchmarkLogger, reflexion_attempts: int, lats_config: LATSConfig):
    if agent_type == "react":
        return ReActAgent(runtime=runtime, logger=logger)
    if agent_type == "reflexion":
        return ReflexionAgent(max_attempts=reflexion_attempts, runtime=runtime, logger=logger)
    if agent_type == "lats":
        return LATSAgent(runtime=runtime, config=lats_config, logger=logger)
    raise ValueError(agent_type)


def _print_table(title: str, rows: list[dict], columns: list[str]) -> None:
    print(f"\n[bold]{title}[/bold]")
    print(" | ".join(columns))
    print(" | ".join("---" for _ in columns))
    for row in rows:
        print(" | ".join(str(row.get(column, "n/a")) for column in columns))


@app.command()
def main(
    dataset: str = "data/hotpot_mini.json",
    dataset_format: str = "auto",
    out_dir: str = "outputs/sample_run",
    mode: str = "mock",
    model: Optional[str] = None,
    agents: str = "react,reflexion",
    reflexion_attempts: int = 3,
    seed: int = 42,
    limit: Optional[int] = None,
    lats_branching_factor: int = 2,
    lats_max_depth: int = 2,
    lats_max_nodes: int = 5,
    lats_early_stop_score: float = 0.92,
    log_level: str = "INFO",
    run_name: Optional[str] = None,
    golden: bool = False,
    golden_submission_path: Optional[str] = None,
) -> None:
    if mode not in {"mock", "llm"}:
        raise typer.BadParameter("--mode must be mock or llm")

    settings = load_settings(require_api_key=False, model_override=model)
    selected_agents = _parse_agents(agents)
    run_id = run_name or _run_id(dataset, mode, settings.openai_model if mode == "llm" else "mock")
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    logger = BenchmarkLogger(out_path, run_id, level=log_level)

    start = time.perf_counter()
    logger.event("benchmark_start", dataset=dataset, mode=mode, agents=selected_agents, golden=golden)

    examples = load_dataset_auto(dataset, dataset_format=dataset_format)
    if limit is not None:
        examples = examples[:limit]

    lats_config = LATSConfig(
        branching_factor=lats_branching_factor,
        max_depth=lats_max_depth,
        max_nodes=lats_max_nodes,
        early_stop_score=lats_early_stop_score,
    )
    runtime, model_name = _make_runtime(mode, logger, model_override=model)
    config_payload = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "dataset_path": dataset,
        "dataset_name": Path(dataset).name,
        "dataset_format": dataset_format,
        "mode": mode,
        "agents": selected_agents,
        "seed": seed,
        "limit": limit,
        "model": model_name,
        "temperature": settings.temperature if mode == "llm" else 0.0,
        "reflexion_attempts": reflexion_attempts,
        "golden": golden,
        "lats_config": lats_config.model_dump(),
    }
    write_json(out_path / "benchmark_config.json", config_payload)
    write_json(out_path / "dataset_manifest.json", build_dataset_manifest(examples, dataset))

    all_records: list[RunRecord] = []
    records_by_agent: dict[str, list[RunRecord]] = {}
    for agent_type in selected_agents:
        agent = _make_agent(agent_type, runtime, logger, reflexion_attempts, lats_config)
        logger.event("agent_start", agent_type=agent_type, count=len(examples))
        rows: list[RunRecord] = []
        for index, example in enumerate(examples, start=1):
            try:
                logger.event("example_queued", agent_type=agent_type, qid=example.qid, index=index)
                rows.append(agent.run(example))
            except Exception as exc:
                logger.error("agent_run", exc, agent_type=agent_type, qid=example.qid, recoverable=True)
        records_by_agent[agent_type] = rows
        all_records.extend(rows)
        save_jsonl(out_path / f"{agent_type}_runs.jsonl", rows)
        logger.event("agent_end", agent_type=agent_type, records=len(rows))

    save_jsonl(out_path / "all_runs.jsonl", all_records)
    wall_time = round(time.perf_counter() - start, 4)
    report = build_report(
        all_records,
        dataset_name=Path(dataset).name,
        mode=mode,
        meta_extra={
            **config_payload,
            "num_examples": len(examples),
            "num_records": len(all_records),
            "benchmark_wall_time_seconds": wall_time,
        },
        input_cost_per_1m=settings.input_cost_per_1m,
        output_cost_per_1m=settings.output_cost_per_1m,
        golden=golden,
    )
    json_path, md_path = save_report(report, out_path)
    if golden and golden_submission_path and report.golden_submission is not None:
        target = Path(golden_submission_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out_path / "analysis" / "golden_submission.json", target)

    visual_path = out_path / "visual_report.html"
    logger.event("report_saved", report_json=str(json_path), report_md=str(md_path), visual_report=str(visual_path))
    logger.event("benchmark_end", records=len(all_records), wall_time_seconds=wall_time)

    print(f"[green]Saved report:[/green] {json_path}")
    print(f"[green]Saved markdown:[/green] {md_path}")
    print(f"[green]Saved visual report:[/green] {visual_path}")
    if golden and report.golden_submission is not None:
        print(f"[green]Saved golden submission:[/green] {out_path / 'analysis' / 'golden_submission.json'}")
    print(json.dumps(report.summary, indent=2, ensure_ascii=False))
    _print_table("ReAct vs Reflexion", report.react_vs_reflexion_table, ["metric", "react", "reflexion", "delta"])
    _print_table(
        "Cost / Runtime",
        report.cost_runtime_table,
        ["agent_type", "records", "llm_call_count", "total_tokens", "estimated_cost_usd", "total_runtime_seconds", "avg_runtime_seconds"],
    )


if __name__ == "__main__":
    app()
