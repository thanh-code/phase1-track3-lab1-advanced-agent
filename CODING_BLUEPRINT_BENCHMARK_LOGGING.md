# CODING BLUEPRINT - Benchmark, Evaluation, Logging, Reflexion, Limited LATS

Day la file chi dan code chi tiet cho lan trien khai tiep theo. Khi code, uu tien bam theo file nay hon viec tu suy dien them kien truc moi.

Muc tieu cua file nay:

- Xac dinh benchmark "chuan" cho lab.
- Them danh gia, nhan xet, failure analysis.
- Them logging va artifact day du de debug/cham diem.
- Hoan thien schema, prompt, runtime, Reflexion Agent, Limited LATS.
- Giu cost hop ly khi dung GPT-4o-mini tren 50 cau HotpotQA.

## 0. Ket Luan Hien Tai

Repo hien tai CHUA co benchmark chuan day du.

Dang co:

- `run_benchmark.py` chay ReAct + Reflexion tren dataset input.
- `reporting.py` tinh EM, avg attempts, avg token estimate, avg latency.
- `autograde.py` cham report JSON theo cac key bat buoc.
- `data/hotpotqa_random50.json` da co 50 mau HotpotQA random.

Dang thieu:

- Chua co mode `llm`.
- Chua co agent selection `--agents react,reflexion,lats`.
- Chua co LATS.
- Chua co benchmark config/manifest luu lai seed, model, mode, command, start/end time.
- Chua co logging file `run.log`, `events.jsonl`, `llm_calls.jsonl`, `errors.jsonl`.
- Chua co per-example detailed analysis.
- Chua co nhan xet tu dong theo agent, failure mode, token/latency tradeoff.
- Chua co cost/token summary thuc.
- Chua co report so sanh ReAct vs Reflexion vs LATS.
- Chua co evaluation chuan hon cho HotpotQA: EM, token, latency, attempt, failure mode, reflection usefulness, LATS node quality.

Do do, lan code sau phai them cac thanh phan ben duoi.

## 1. Dinh Nghia Benchmark Chuan Cho Lab Nay

Benchmark chuan la mot lan chay co day du cac dac diem:

1. Reproducible:
   - Dataset co dinh: `data/hotpotqa_random50.json`.
   - Seed co dinh: `42`.
   - Model ghi ro: `gpt-4o-mini`.
   - Mode ghi ro: `mock` hoac `llm`.
   - Agent list ghi ro: `react,reflexion,lats`.

2. Fair:
   - Cung dataset cho tat ca agent.
   - Cung context input cho tat ca agent.
   - Actor/Reflector/LATS khong thay `gold_answer`.
   - Evaluator moi duoc thay `gold_answer`.
   - LATS bi gioi han node/call de khong bat cong ve compute.

3. Observable:
   - Moi record co token, latency, attempts.
   - Moi record co answer, gold, correctness, failure mode.
   - Moi Reflexion record co reflection trace.
   - Moi LATS record co lats trace.
   - Moi LLM call co log event rieng.

4. Comparable:
   - Summary co ReAct, Reflexion, LATS.
   - Co delta Reflexion - ReAct.
   - Co delta LATS - ReAct.
   - Co delta LATS - Reflexion.
   - Co nhan xet tradeoff quality/cost/latency.

5. Auditable:
   - Luu `benchmark_config.json`.
   - Luu `dataset_manifest.json`.
   - Luu `run.log`.
   - Luu `events.jsonl`.
   - Luu `llm_calls.jsonl`.
   - Luu `errors.jsonl`.
   - Luu agent runs JSONL.
   - Luu `report.json` va `report.md`.

## 2. Benchmark Output Standard

Moi lan benchmark ghi vao mot folder output:

```text
outputs/{run_name}/
  benchmark_config.json
  dataset_manifest.json
  run.log
  events.jsonl
  llm_calls.jsonl
  errors.jsonl
  react_runs.jsonl
  reflexion_runs.jsonl
  lats_runs.jsonl
  all_runs.jsonl
  report.json
  report.md
  analysis/
    failure_examples.json
    improvement_examples.json
    agent_comparison.json
    react_vs_reflexion_table.json
    cost_runtime_table.json
    cost_latency_summary.json
    golden_submission.json
```

Neu chay chi `react,reflexion`, khong tao `lats_runs.jsonl` cung duoc, nhung `all_runs.jsonl` va `report.*` bat buoc co.

`golden_submission.json` chi bat buoc khi chay golden test set.

## 3. Benchmark CLI Can Ho Tro

File: `run_benchmark.py`

Command mock:

```bash
python run_benchmark.py \
  --dataset data/hotpot_mini.json \
  --out-dir outputs/mock_smoke \
  --mode mock \
  --agents react,reflexion,lats \
  --reflexion-attempts 3 \
  --seed 42
```

Command LLM:

```bash
python run_benchmark.py \
  --dataset data/hotpotqa_random50.json \
  --out-dir outputs/hotpotqa_random50_gpt4o_mini \
  --mode llm \
  --agents react,reflexion,lats \
  --reflexion-attempts 3 \
  --seed 42 \
  --lats-branching-factor 2 \
  --lats-max-depth 2 \
  --lats-max-nodes 5
```

Command Golden Test Set:

```bash
python run_benchmark.py \
  --dataset data/golden_test_set.json \
  --dataset-format auto \
  --out-dir outputs/golden_test_set_gpt4o_mini \
  --mode llm \
  --agents react,reflexion,lats \
  --reflexion-attempts 3 \
  --seed 42 \
  --golden
```

Muc tieu cua command golden:

- Khi thay dua file golden test set, chi can dat vao `data/golden_test_set.json`.
- Chay command tren de co ngay:
  - `report.json`
  - `report.md`
  - `all_runs.jsonl`
  - `analysis/golden_submission.json`
  - bang so sanh ReAct vs Reflexion
  - bang cost/runtime
- Neu golden test set da dung schema lab thi chay thang.
- Neu golden test set o format HotpotQA raw, code phai auto-convert sang `QAExample`.

Arguments can co:

- `dataset: str = "data/hotpot_mini.json"`
- `dataset_format: Literal["auto", "qaexample", "hotpotqa_raw"] = "auto"`
- `out_dir: str = "outputs/sample_run"`
- `mode: Literal["mock", "llm"] = "mock"`
- `agents: str = "react,reflexion"`
- `reflexion_attempts: int = 3`
- `seed: int = 42`
- `limit: int | None = None`
- `lats_branching_factor: int = 2`
- `lats_max_depth: int = 2`
- `lats_max_nodes: int = 5`
- `lats_early_stop_score: float = 0.92`
- `log_level: str = "INFO"`
- `run_name: str | None = None`
- `golden: bool = False`
- `golden_submission_path: str | None = None`

Behavior:

- Load dataset.
- Neu `dataset_format=auto`, tu detect:
  - Lab format neu co `qid`, `question`, `gold_answer`, `context`.
  - HotpotQA raw format neu co `_id/id`, `question`, `answer`, `context.title`, `context.sentences`.
- Neu `golden=True`, bat buoc sinh `analysis/golden_submission.json`.
- Neu `limit` co gia tri thi chi chay n mau dau tien, dung cho smoke test.
- Validate agents nam trong `react`, `reflexion`, `lats`.
- Tao output dir.
- Luu benchmark config truoc khi chay.
- Setup logging truoc khi tao agents.
- Chay tung agent tren tung example.
- Neu co loi tren 1 record:
  - log vao `errors.jsonl`.
  - tiep tuc record khac neu co the.
  - record loi co the bo qua report hoac tao failed run record voi `failure_mode="wrong_final_answer"`.
- Luu JSONL tung agent.
- Luu `all_runs.jsonl`.
- Build report.
- Save report.
- In summary ngan ra terminal.

Terminal output sau benchmark phai in toi thieu:

```text
Saved report: outputs/.../report.json
Saved markdown: outputs/.../report.md
Saved golden submission: outputs/.../analysis/golden_submission.json

ReAct vs Reflexion:
| Metric | ReAct | Reflexion | Delta |
| ... |

Cost / Runtime:
| Agent | Records | Total Tokens | Est. Cost USD | Total Runtime | Avg Runtime |
| ... |
```

## 4. Benchmark Config Artifact

File: `benchmark_config.json`

Example:

```json
{
  "run_id": "20260618_153000_hotpotqa_random50_gpt4o_mini",
  "created_at": "2026-06-18T15:30:00+07:00",
  "dataset_path": "data/hotpotqa_random50.json",
  "dataset_name": "hotpotqa_random50.json",
  "mode": "llm",
  "agents": ["react", "reflexion", "lats"],
  "seed": 42,
  "limit": null,
  "model": "gpt-4o-mini",
  "temperature": 0.0,
  "reflexion_attempts": 3,
  "lats_config": {
    "branching_factor": 2,
    "max_depth": 2,
    "top_k": 1,
    "max_nodes": 5,
    "early_stop_score": 0.92,
    "generator_temperature": 0.2,
    "critic_temperature": 0.0
  }
}
```

Code task:

- Tao schema/dataclass `BenchmarkConfig`.
- Save bang JSON indent 2.
- Khong include API key.

## 5. Dataset Manifest Artifact

File: `dataset_manifest.json`

Example:

```json
{
  "dataset_path": "data/hotpotqa_random50.json",
  "num_examples": 50,
  "qid_count": 50,
  "duplicate_qids": [],
  "difficulty_counts": {
    "easy": 0,
    "medium": 12,
    "hard": 38
  },
  "avg_context_chunks": 10.0,
  "min_context_chunks": 10,
  "max_context_chunks": 10,
  "avg_question_chars": 82.4,
  "has_empty_context": false,
  "schema_valid": true
}
```

Code task:

- Them function `build_dataset_manifest(examples, dataset_path) -> dict`.
- Luu truoc khi chay benchmark.
- Neu dataset invalid thi raise loi ro rang.

## 6. Logging Standard

Can them file moi:

- `src/reflexion_lab/logging_utils.py`

### 6.1. Log files

Trong output dir:

- `run.log`: human-readable logs.
- `events.jsonl`: structured event logs.
- `llm_calls.jsonl`: structured LLM call logs.
- `errors.jsonl`: structured errors.

### 6.2. `run.log`

Muc dich: doc nhanh bang mat.

Format goi y:

```text
2026-06-18 15:30:01 INFO benchmark_start run_id=... dataset=... agents=react,reflexion,lats mode=llm
2026-06-18 15:30:04 INFO example_start index=1 qid=5add... agent=react
2026-06-18 15:30:09 INFO example_done qid=5add... agent=react correct=false tokens=742 latency_ms=4201 failure=wrong_final_answer
2026-06-18 15:31:10 INFO benchmark_done records=150 em_react=0.42 em_reflexion=0.50 em_lats=0.54
```

### 6.3. `events.jsonl`

Moi dong la JSON object.

Events can log:

- `benchmark_start`
- `benchmark_end`
- `agent_start`
- `agent_end`
- `example_start`
- `example_end`
- `attempt_start`
- `attempt_end`
- `reflection_created`
- `lats_depth_start`
- `lats_candidates_generated`
- `lats_candidates_scored`
- `lats_final_selected`
- `report_saved`

Example:

```json
{
  "ts": "2026-06-18T15:30:04+07:00",
  "event": "example_end",
  "run_id": "20260618_153000_hotpotqa_random50_gpt4o_mini",
  "agent_type": "reflexion",
  "qid": "5add1d575542992c1e3a2540",
  "is_correct": true,
  "attempts": 2,
  "token_estimate": 1840,
  "latency_ms": 9120,
  "failure_mode": "none"
}
```

### 6.4. `llm_calls.jsonl`

Moi LLM call ghi 1 dong.

Fields:

- `ts`
- `run_id`
- `qid`
- `agent_type`
- `call_type`: `actor`, `evaluator`, `reflector`, `lats_generator`, `lats_critic`
- `attempt_id`
- `model`
- `temperature`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `latency_ms`
- `success`
- `error_type`
- `prompt_chars`
- `response_chars`
- `response_preview`

Khong log:

- API key.
- Full `.env`.

Co the log prompt full khong?

- Mac dinh khong log full prompt de giam file size.
- Neu can debug sau, them flag `--log-prompts`, default false.

Example:

```json
{
  "ts": "2026-06-18T15:30:05+07:00",
  "run_id": "20260618_153000_hotpotqa_random50_gpt4o_mini",
  "qid": "5add1d575542992c1e3a2540",
  "agent_type": "lats",
  "call_type": "lats_generator",
  "attempt_id": 1,
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "input_tokens": 2210,
  "output_tokens": 210,
  "total_tokens": 2420,
  "latency_ms": 3821,
  "success": true,
  "error_type": null,
  "prompt_chars": 9240,
  "response_chars": 712,
  "response_preview": "{\"candidates\":[{\"candidate_id\":\"c1\"..."
}
```

### 6.5. `errors.jsonl`

Example:

```json
{
  "ts": "2026-06-18T15:31:00+07:00",
  "run_id": "20260618_153000_hotpotqa_random50_gpt4o_mini",
  "qid": "5add1d575542992c1e3a2540",
  "agent_type": "reflexion",
  "stage": "actor",
  "error_type": "JSONDecodeError",
  "message": "Could not parse model response as JSON",
  "recoverable": true
}
```

### 6.6. Logging API

Implement:

```python
class BenchmarkLogger:
    def __init__(self, out_dir: Path, run_id: str, level: str = "INFO") -> None: ...
    def info(self, message: str, **fields: object) -> None: ...
    def event(self, event: str, **fields: object) -> None: ...
    def llm_call(self, **fields: object) -> None: ...
    def error(self, stage: str, error: Exception, **fields: object) -> None: ...
```

Use:

- `logger.info(...)` cho `run.log`.
- `logger.event(...)` cho `events.jsonl`.
- `logger.llm_call(...)` cho `llm_calls.jsonl`.
- `logger.error(...)` cho `errors.jsonl`.

## 7. Evaluation Standard

Can them file moi:

- `src/reflexion_lab/evaluation.py`

Muc dich:

- Tinh metrics chuan hon.
- Tao nhan xet tu dong.
- Tao failure/improvement examples.

### 7.1. Metrics can co

Aggregate per agent:

- `count`
- `em`: exact match rate.
- `correct_count`
- `incorrect_count`
- `avg_attempts`
- `avg_token_estimate`
- `avg_latency_ms`
- `median_token_estimate`
- `median_latency_ms`
- `p95_latency_ms`
- `avg_reflection_count`
- `avg_lats_node_count`
- `total_tokens`
- `total_latency_ms`
- `tokens_per_correct`
- `latency_per_correct_ms`

Delta metrics:

- `delta_reflexion_minus_react`
- `delta_lats_minus_react`
- `delta_lats_minus_reflexion`

Delta fields:

- `em_abs`
- `correct_count_abs`
- `tokens_abs`
- `latency_abs`
- `attempts_abs`
- `efficiency_note`

### 7.2. Per-question comparison

Build by qid:

```json
{
  "qid": "5add...",
  "gold_answer": "Prussian",
  "react": {
    "answer": "...",
    "correct": false,
    "tokens": 700,
    "latency_ms": 3900
  },
  "reflexion": {
    "answer": "...",
    "correct": true,
    "tokens": 1800,
    "latency_ms": 9400,
    "reflection_count": 1
  },
  "lats": {
    "answer": "...",
    "correct": true,
    "tokens": 3200,
    "latency_ms": 15000,
    "lats_node_count": 5
  },
  "pattern": "reflexion_and_lats_fixed_react"
}
```

Pattern categories:

- `all_correct`
- `all_wrong`
- `reflexion_fixed_react`
- `lats_fixed_react`
- `lats_only_correct`
- `reflexion_only_correct`
- `react_only_correct`
- `reflexion_regressed`
- `lats_regressed`
- `mixed`

### 7.3. Failure mode analysis

For each agent:

- Count failure mode.
- Percent failure mode.
- Representative examples.

Example:

```json
{
  "reflexion": {
    "entity_drift": {
      "count": 8,
      "rate": 0.16,
      "example_qids": ["...", "..."],
      "comment": "Most entity drift errors happen when distractor titles share a person or place name."
    }
  }
}
```

### 7.4. Reflection usefulness

For Reflexion:

- `reflection_attempted_count`
- `reflection_helped_count`: attempt 1 wrong, later correct.
- `reflection_failed_count`: reflection happened but final wrong.
- `avg_reflections_per_question`
- `common_reflection_lessons`: top recurring terms.

Heuristic:

- Reflection helped if `attempts > 1` and final `is_correct=True`.

### 7.5. LATS usefulness

For LATS:

- `avg_lats_nodes`
- `early_stop_count`
- `avg_best_value_score`
- `critic_supported_count`
- `lats_helped_over_react_count`
- `lats_regressed_from_react_count`

Heuristic:

- LATS helped if LATS correct and ReAct wrong for same qid.
- LATS regressed if LATS wrong and ReAct correct.

### 7.6. Automated comments

Build function:

```python
def build_benchmark_comments(records: list[RunRecord], comparisons: dict) -> list[str]:
    ...
```

Output example:

```json
[
  "Reflexion improved exact match by 8.0 percentage points over ReAct, mainly by fixing incomplete multi-hop answers.",
  "Limited LATS had the best EM but used 1.9x more tokens than ReAct on average.",
  "The most common remaining failure mode was entity_drift, suggesting the agent still follows distractor context too often.",
  "Reflection memory helped on 7 questions and failed to recover on 12 questions."
]
```

Rules:

- Comments are deterministic, no LLM needed.
- Avoid pretending causality if data does not support it.
- Mention tradeoff if token/latency increases.

### 7.7. ReAct vs Reflexion comparison table

Bat buoc co bang rieng so sanh ReAct va Reflexion Agent, vi day la trong tam cua lab.

Build function:

```python
def build_react_vs_reflexion_table(records: list[RunRecord]) -> list[dict]:
    ...
```

Output JSON luu vao:

- `analysis/react_vs_reflexion_table.json`
- `report.json["react_vs_reflexion_table"]`
- bang Markdown trong `report.md`

Metrics bat buoc:

```json
[
  {
    "metric": "records",
    "react": 50,
    "reflexion": 50,
    "delta": 0,
    "note": "Same dataset."
  },
  {
    "metric": "exact_match",
    "react": 0.42,
    "reflexion": 0.54,
    "delta": 0.12,
    "note": "Positive delta means Reflexion improved accuracy."
  },
  {
    "metric": "correct_count",
    "react": 21,
    "reflexion": 27,
    "delta": 6,
    "note": "Number of questions answered correctly."
  },
  {
    "metric": "avg_attempts",
    "react": 1.0,
    "reflexion": 1.8,
    "delta": 0.8,
    "note": "Reflexion normally spends more attempts."
  },
  {
    "metric": "avg_tokens",
    "react": 850,
    "reflexion": 1650,
    "delta": 800,
    "note": "Token tradeoff."
  },
  {
    "metric": "avg_runtime_seconds",
    "react": 3.4,
    "reflexion": 7.9,
    "delta": 4.5,
    "note": "Running-time tradeoff."
  },
  {
    "metric": "tokens_per_correct",
    "react": 2023.8,
    "reflexion": 3055.6,
    "delta": 1031.8,
    "note": "Lower is more token-efficient."
  }
]
```

Markdown table required:

```markdown
## ReAct vs Reflexion

| Metric | ReAct | Reflexion | Delta | Note |
|---|---:|---:|---:|---|
| Exact Match | 0.42 | 0.54 | +0.12 | Positive means Reflexion improved accuracy |
| Correct Count | 21 | 27 | +6 | Number of correct answers |
| Avg Attempts | 1.00 | 1.80 | +0.80 | Reflexion spends more attempts |
| Avg Tokens | 850 | 1650 | +800 | Token tradeoff |
| Avg Runtime (s) | 3.40 | 7.90 | +4.50 | Runtime tradeoff |
| Tokens / Correct | 2023.8 | 3055.6 | +1031.8 | Lower is better |
```

Rules:

- Neu thieu ReAct hoac Reflexion, van tao section nhung ghi `not_available`.
- Delta = Reflexion - ReAct.
- Runtime lay tu `latency_ms / 1000`.
- Neu `correct_count = 0`, `tokens_per_correct = null`.

### 7.8. Cost and running-time table

Bat buoc co bang uoc tinh cost gom ca running time.

Build function:

```python
def build_cost_runtime_table(records: list[RunRecord], pricing: PricingConfig | None = None) -> list[dict]:
    ...
```

Output JSON luu vao:

- `analysis/cost_runtime_table.json`
- `report.json["cost_runtime_table"]`
- bang Markdown trong `report.md`

Metrics bat buoc moi agent:

- `agent_type`
- `records`
- `llm_call_count`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `total_runtime_seconds`
- `avg_runtime_seconds`
- `p95_runtime_seconds`
- `avg_tokens_per_record`
- `tokens_per_correct`
- `correct_count`
- `exact_match`

Example JSON:

```json
[
  {
    "agent_type": "react",
    "records": 50,
    "llm_call_count": 100,
    "input_tokens": 42000,
    "output_tokens": 8500,
    "total_tokens": 50500,
    "estimated_cost_usd": null,
    "total_runtime_seconds": 220.4,
    "avg_runtime_seconds": 4.41,
    "p95_runtime_seconds": 8.72,
    "avg_tokens_per_record": 1010.0,
    "tokens_per_correct": 2404.76,
    "correct_count": 21,
    "exact_match": 0.42
  }
]
```

Markdown table required:

```markdown
## Cost And Running Time

| Agent | Records | LLM Calls | Total Tokens | Est. Cost USD | Total Runtime | Avg Runtime | P95 Runtime | EM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ReAct | 50 | 100 | 50,500 | n/a | 220.4s | 4.41s | 8.72s | 0.42 |
| Reflexion | 50 | 180 | 92,000 | n/a | 510.0s | 10.20s | 18.10s | 0.54 |
| LATS | 50 | 240 | 150,000 | n/a | 790.0s | 15.80s | 28.00s | 0.58 |
```

Cost rules:

- Neu env co `OPENAI_INPUT_COST_PER_1M` va `OPENAI_OUTPUT_COST_PER_1M`, tinh cost.
- Neu thieu pricing env, hien `estimated_cost_usd = null` va Markdown la `n/a`.
- Running time bat buoc co du:
  - total runtime
  - average runtime
  - p95 runtime
- Running time lay tu tong `latency_ms` trong records, khong lay wall-clock folder run.
- Co the them `benchmark_wall_time_seconds` vao meta rieng.

## 8. Report JSON Standard

File: `report.json`

Must include autograder keys:

- `meta`
- `summary`
- `failure_modes`
- `examples`
- `extensions`
- `discussion`

Add more keys:

- `comparisons`
- `comments`
- `react_vs_reflexion_table`
- `cost_runtime_table`
- `reflection_analysis`
- `lats_analysis`
- `cost_latency`
- `golden_submission`
- `artifacts`

Example top-level:

```json
{
  "meta": {},
  "summary": {},
  "failure_modes": {},
  "examples": [],
  "comparisons": {},
  "comments": [],
  "react_vs_reflexion_table": [],
  "cost_runtime_table": [],
  "reflection_analysis": {},
  "lats_analysis": {},
  "cost_latency": {},
  "golden_submission": null,
  "extensions": [],
  "discussion": "...",
  "artifacts": {
    "benchmark_config": "benchmark_config.json",
    "dataset_manifest": "dataset_manifest.json",
    "events": "events.jsonl",
    "llm_calls": "llm_calls.jsonl",
    "errors": "errors.jsonl",
    "react_vs_reflexion_table": "analysis/react_vs_reflexion_table.json",
    "cost_runtime_table": "analysis/cost_runtime_table.json",
    "golden_submission": "analysis/golden_submission.json"
  }
}
```

Autograder se bo qua key thua, nen an toan.

## 9. Report MD Standard

File: `report.md`

Structure:

```markdown
# Lab 16 Benchmark Report

## Metadata

## Dataset Manifest

## Summary

## ReAct vs Reflexion

## Agent Comparison

## Failure Modes

## Reflection Analysis

## Limited LATS Analysis

## Cost And Running Time

## Representative Examples

## Automated Comments

## Discussion

## Artifacts
```

Representative examples:

- 3 examples where Reflexion fixed ReAct.
- 3 examples where LATS fixed ReAct.
- 3 examples where all agents failed.
- 2 examples where LATS regressed.

If not enough examples, show fewer and mention count.

## 10. Discussion Standard

`discussion` must be >= 250 chars.

Generate deterministic discussion using metrics.

Template:

```text
This benchmark compares ReAct, Reflexion, and Limited LATS on 50 random HotpotQA examples. Reflexion is expected to help when the first answer stops at an intermediate entity or misses the second hop, while Limited LATS is expected to help when several plausible entities compete in the context. The results show that {best_agent} achieved the highest EM. Reflexion changed the tradeoff by adding attempts and reflection calls, while LATS added candidate generation and critic calls. The main remaining failure modes were {top_failure_modes}. Overall, the benchmark suggests that reflection memory is useful for recoverable multi-hop mistakes, while limited tree search can improve candidate selection at the cost of more tokens and latency.
```

Need fill variables from actual report.

## 11. Cost And Latency Summary

Can them approximate cost neu muon, nhung khong bat buoc vi gia model co the thay doi.

De tranh sai gia hien hanh, mac dinh khong tinh USD neu khong co env:

```env
OPENAI_INPUT_COST_PER_1M=
OPENAI_OUTPUT_COST_PER_1M=
```

Neu env co gia tri, tinh:

- `input_cost = input_tokens / 1_000_000 * input_cost_per_1m`
- `output_cost = output_tokens / 1_000_000 * output_cost_per_1m`
- `total_cost = input_cost + output_cost`

Neu env trong, report:

```json
"estimated_cost_usd": null
```

Metric:

- total tokens per agent.
- total input/output tokens per agent if available.
- avg tokens per record.
- tokens per correct.
- total latency.
- avg latency.
- p95 latency.

## 12. Golden Test Set Ready-Run Support

Muc tieu: khi thay dua file golden test set vao cuoi buoi, code phai chay ra ket qua ngay bang 1 command, khong can sua code.

### 12.1. Golden input path

Mac dinh:

```text
data/golden_test_set.json
```

Command:

```bash
python run_benchmark.py \
  --dataset data/golden_test_set.json \
  --dataset-format auto \
  --out-dir outputs/golden_test_set_gpt4o_mini \
  --mode llm \
  --agents react,reflexion,lats \
  --reflexion-attempts 3 \
  --golden
```

### 12.2. Supported golden formats

Support 2 format:

1. Lab QAExample format:

```json
{
  "qid": "gold_001",
  "difficulty": "medium",
  "question": "...",
  "gold_answer": "...",
  "context": [
    {
      "title": "...",
      "text": "..."
    }
  ]
}
```

2. HotpotQA raw format:

```json
{
  "_id": "...",
  "question": "...",
  "answer": "...",
  "level": "hard",
  "context": {
    "title": ["Title 1", "Title 2"],
    "sentences": [["sent 1", "sent 2"], ["sent 3"]]
  }
}
```

Also support list fields where id key is `id` instead of `_id`.

### 12.3. Dataset auto-detect

Add helper in `utils.py`:

```python
def load_dataset_auto(path: str | Path, dataset_format: str = "auto") -> list[QAExample]:
    ...
```

Behavior:

- If `dataset_format="qaexample"`, validate as current lab schema.
- If `dataset_format="hotpotqa_raw"`, convert HotpotQA raw to `QAExample`.
- If `dataset_format="auto"`:
  - inspect first item.
  - if has `gold_answer`, treat as lab schema.
  - if has `answer` and `context.title/context.sentences`, convert HotpotQA raw.
  - if cannot detect, raise clear error.

### 12.4. Golden output

When `--golden` is set, create:

```text
outputs/golden_test_set_gpt4o_mini/
  report.json
  report.md
  all_runs.jsonl
  analysis/golden_submission.json
  analysis/react_vs_reflexion_table.json
  analysis/cost_runtime_table.json
```

### 12.5. Golden submission file

File: `analysis/golden_submission.json`

Purpose: nộp nhanh hoặc gửi thầy ngay.

Format:

```json
{
  "run_id": "20260618_160000_golden_test_set_gpt4o_mini",
  "dataset": "golden_test_set.json",
  "model": "gpt-4o-mini",
  "mode": "llm",
  "agents": ["react", "reflexion", "lats"],
  "primary_agent": "lats",
  "created_at": "2026-06-18T16:00:00+07:00",
  "summary": {
    "react": {},
    "reflexion": {},
    "lats": {}
  },
  "answers": [
    {
      "qid": "gold_001",
      "question": "...",
      "gold_answer": "...",
      "react_answer": "...",
      "reflexion_answer": "...",
      "lats_answer": "...",
      "final_answer": "...",
      "final_agent": "lats",
      "is_correct": true
    }
  ],
  "react_vs_reflexion_table": [],
  "cost_runtime_table": []
}
```

Rules:

- `primary_agent` default:
  - If LATS was run, use `lats`.
  - Else if Reflexion was run, use `reflexion`.
  - Else use `react`.
- `final_answer` = answer from primary agent.
- Include `gold_answer` only if golden file includes answers. If teacher gives hidden-answer golden without gold, set `gold_answer=null` and skip evaluator metrics that require gold.
- If no `gold_answer`, still produce predictions and runtime/cost table, but correctness fields become `null`.

### 12.6. Golden no-gold mode

Some golden files may hide answers. Code must handle both:

- With gold:
  - Run evaluator.
  - Compute EM/failure mode.
  - Full report.
- Without gold:
  - Do not call benchmark evaluator requiring gold.
  - Still run Actor/Reflexion/LATS.
  - `is_correct = null`.
  - `failure_mode = "wrong_final_answer"` is not meaningful; use `"none"` or omit in golden submission, but keep report schema valid.
  - Report discussion says correctness cannot be computed because gold answers are absent.

Implementation option:

- Make `QAExample.gold_answer` optional only if needed.
- Safer for current lab: create separate `GoldenExample` schema or during no-gold mode use empty string and avoid evaluator. Prefer `GoldenExample` if time allows.

### 12.7. Golden quick script optional

Optional convenience file:

```text
run_golden_benchmark.py
```

It simply calls the same benchmark logic with:

```python
dataset="data/golden_test_set.json"
dataset_format="auto"
out_dir="outputs/golden_test_set_gpt4o_mini"
mode="llm"
agents="react,reflexion,lats"
golden=True
```

This file is optional because `run_benchmark.py --golden` is enough.

## 13. Schema Updates Needed

File: `src/reflexion_lab/schemas.py`

### 13.1. Types

Add:

```python
FailureMode = Literal[
    "none",
    "entity_drift",
    "incomplete_multi_hop",
    "wrong_final_answer",
    "looping",
    "reflection_overfit",
]

AgentType = Literal["react", "reflexion", "lats"]
```

### 13.2. `JudgeResult`

Fields:

- `score: int = Field(ge=0, le=1)`
- `reason: str`
- `missing_evidence: list[str] = Field(default_factory=list)`
- `spurious_claims: list[str] = Field(default_factory=list)`
- `normalized_gold: str | None = None`
- `normalized_prediction: str | None = None`
- `confidence: float = Field(default=0.0, ge=0.0, le=1.0)`
- `failure_mode: FailureMode = "wrong_final_answer"`

### 13.3. `ReflectionEntry`

Fields:

- `attempt_id: int = Field(ge=1)`
- `failure_reason: str`
- `lesson: str`
- `next_strategy: str`
- `evidence_to_check: list[str] = Field(default_factory=list)`
- `avoid: list[str] = Field(default_factory=list)`
- `confidence: float = Field(default=0.0, ge=0.0, le=1.0)`

### 13.4. Runtime and LATS schemas

Add:

- `RuntimeStats`
- `LLMCallResult`
- `ActorOutput`
- `CandidateAnswer`
- `LATSCritique`
- `LATSNode`
- `LATSConfig`

`RuntimeStats`:

- `input_tokens: int = 0`
- `output_tokens: int = 0`
- `token_estimate: int = 0`
- `latency_ms: int = 0`

`LATSConfig`:

- `branching_factor: int = 2`
- `max_depth: int = 2`
- `top_k: int = 1`
- `max_nodes: int = 5`
- `early_stop_score: float = 0.92`
- `generator_temperature: float = 0.2`
- `critic_temperature: float = 0.0`

### 13.5. `AttemptTrace`

Keep current fields, add:

- `input_tokens: int = 0`
- `output_tokens: int = 0`
- `llm_call_count: int = 0`
- `reflection: ReflectionEntry | None = None`
- `lats_nodes: list[LATSNode] = Field(default_factory=list)`

### 13.6. `RunRecord`

Update:

- `agent_type: AgentType`
- `input_tokens: int = 0`
- `output_tokens: int = 0`
- `llm_call_count: int = 0`
- `reflections: list[ReflectionEntry] = Field(default_factory=list)`
- `traces: list[AttemptTrace] = Field(default_factory=list)`
- `lats_trace: list[LATSNode] = Field(default_factory=list)`

## 14. LATS Must Stay Limited

This is important.

Do not implement full MCTS. Do not implement UCB. Do not branch recursively over many nodes.

LATS config:

```python
LATSConfig(
    branching_factor=2,
    max_depth=2,
    top_k=1,
    max_nodes=5,
    early_stop_score=0.92,
)
```

Max tree:

```text
root
  c1
    c1_refined_a
    c1_refined_b
  c2
```

Or if c2 is better:

```text
root
  c1
  c2
    c2_refined_a
    c2_refined_b
```

Maximum non-root candidates:

- 2 initial candidates.
- 2 refined candidates.
- Total non-root: 4.
- Total nodes including root: 5.

Maximum internal LLM calls:

- generator depth 1: 1
- critic depth 1: 1
- generator/refiner depth 2: 1
- critic depth 2: 1
- Total internal: 4

Then benchmark evaluator call:

- evaluator: 1

Total LATS max per question:

- 5 LLM calls.

If early stop:

- 3 LLM calls total: generator, critic, evaluator.

## 15. Agent Flow Details

### 14.1. ReAct

Per question:

1. Log `example_start`.
2. Actor call.
3. Evaluator call.
4. Build `AttemptTrace`.
5. Build `RunRecord`.
6. Log `example_end`.

### 14.2. Reflexion

Per question:

1. Empty memory.
2. For attempt 1..max:
   - Log `attempt_start`.
   - Actor call with memory.
   - Evaluator call.
   - If correct: stop.
   - If wrong and attempts remain:
     - Reflector call.
     - Save reflection.
     - Add compact memory.
     - Keep max 2 memory items.
   - Log `attempt_end`.
3. Build record.
4. Log `example_end`.

Reflection helped metric:

- attempt 1 wrong, final correct.

### 14.3. LATS

Per question:

1. Log `lats_depth_start depth=1`.
2. Generate 2 candidates.
3. Critic scores 2 candidates.
4. Build child nodes.
5. Select best.
6. If best score >= 0.92, final = best.
7. Else depth 2:
   - Generate 2 refined candidates from best.
   - Critic scores refined candidates.
   - Build child nodes.
8. Select best node among all non-root nodes.
9. Evaluator call for final answer.
10. Build record.
11. Log `lats_final_selected`.

## 16. Prompt Requirements

Prompts are in `src/reflexion_lab/prompts.py`.

Need constants:

- `ACTOR_SYSTEM`
- `EVALUATOR_SYSTEM`
- `REFLECTOR_SYSTEM`
- `LATS_GENERATOR_SYSTEM`
- `LATS_CRITIC_SYSTEM`

All LLM prompts must return JSON only.

### 15.1. Actor output

```json
{
  "answer": "short final answer",
  "evidence_titles": ["title 1", "title 2"],
  "reasoning_summary": "brief hop summary"
}
```

### 15.2. Evaluator output

```json
{
  "score": 0,
  "reason": "short reason",
  "missing_evidence": ["..."],
  "spurious_claims": ["..."],
  "confidence": 0.9,
  "failure_mode": "incomplete_multi_hop"
}
```

### 15.3. Reflector output

```json
{
  "attempt_id": 1,
  "failure_reason": "...",
  "lesson": "...",
  "next_strategy": "...",
  "evidence_to_check": ["..."],
  "avoid": ["..."],
  "confidence": 0.85
}
```

### 15.4. LATS generator output

```json
{
  "candidates": [
    {
      "candidate_id": "c1",
      "answer": "...",
      "evidence_titles": ["..."],
      "reasoning_summary": "..."
    },
    {
      "candidate_id": "c2",
      "answer": "...",
      "evidence_titles": ["..."],
      "reasoning_summary": "..."
    }
  ]
}
```

### 15.5. LATS critic output

```json
{
  "critiques": [
    {
      "candidate_id": "c1",
      "value_score": 0.92,
      "critique": "...",
      "missing_evidence": [],
      "supported": true
    },
    {
      "candidate_id": "c2",
      "value_score": 0.41,
      "critique": "...",
      "missing_evidence": ["..."],
      "supported": false
    }
  ]
}
```

## 17. Runtime Design

Create:

- `src/reflexion_lab/config.py`
- `src/reflexion_lab/llm_client.py`
- `src/reflexion_lab/llm_runtime.py`
- `src/reflexion_lab/logging_utils.py`
- `src/reflexion_lab/evaluation.py`

### 16.1. Config

Load:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_TEMPERATURE`
- `OPENAI_TIMEOUT_SECONDS`
- optional cost env vars.

Raise clear error if `mode=llm` and no API key.

### 16.2. LLM client

Use OpenAI SDK.

Requirements:

- Return content.
- Return input/output/total tokens.
- Return latency.
- Retry once for invalid JSON.
- Log LLM call through `BenchmarkLogger`.

### 16.3. Runtime abstraction

Mock and LLM runtime must expose same methods:

- `actor_answer`
- `evaluator`
- `reflector`
- `lats_generate_candidates`
- `lats_critic`

Return value:

- Domain object.
- RuntimeStats.

## 18. Reporting Implementation

Refactor `src/reflexion_lab/reporting.py`.

Functions:

```python
def summarize(records: list[RunRecord]) -> dict: ...
def failure_breakdown(records: list[RunRecord]) -> dict: ...
def build_examples(records: list[RunRecord]) -> list[dict]: ...
def build_report(
    records: list[RunRecord],
    dataset_name: str,
    mode: str,
    meta_extra: dict | None = None,
) -> ReportPayload: ...
def save_report(report: ReportPayload, out_dir: str | Path) -> tuple[Path, Path]: ...
```

Move complex analysis to `evaluation.py`, call it from `build_report`.

## 19. Analysis Artifacts

Create files in `analysis/`.

### 18.1. `failure_examples.json`

Contains top wrong examples per agent:

```json
{
  "react": [
    {
      "qid": "...",
      "question": "...",
      "gold_answer": "...",
      "predicted_answer": "...",
      "failure_mode": "entity_drift",
      "reason": "..."
    }
  ]
}
```

### 18.2. `improvement_examples.json`

Examples where one advanced method fixed baseline:

```json
{
  "reflexion_fixed_react": [],
  "lats_fixed_react": [],
  "lats_only_correct": []
}
```

### 18.3. `agent_comparison.json`

Per-qid matrix:

```json
{
  "qid": {
    "react_correct": false,
    "reflexion_correct": true,
    "lats_correct": true,
    "pattern": "reflexion_and_lats_fixed_react"
  }
}
```

### 18.4. `cost_latency_summary.json`

Per agent cost/latency:

```json
{
  "react": {
    "total_tokens": 50000,
    "avg_tokens": 1000,
    "total_latency_ms": 200000,
    "avg_latency_ms": 4000,
    "p95_latency_ms": 9000,
    "estimated_cost_usd": null
  }
}
```

## 20. Quality Gates

Before saying done, these must pass:

```bash
pytest
```

```bash
python run_benchmark.py \
  --dataset data/hotpot_mini.json \
  --out-dir outputs/mock_smoke \
  --mode mock \
  --agents react,reflexion,lats \
  --reflexion-attempts 3
```

```bash
python autograde.py --report-path outputs/mock_smoke/report.json
```

If `.env` has API key:

```bash
python run_benchmark.py \
  --dataset data/hotpotqa_random50.json \
  --out-dir outputs/hotpotqa_random50_gpt4o_mini \
  --mode llm \
  --agents react,reflexion,lats \
  --reflexion-attempts 3
```

Then:

```bash
python autograde.py --report-path outputs/hotpotqa_random50_gpt4o_mini/report.json
```

## 21. Tests To Add

### 20.1. Schema tests

File: `tests/test_schemas.py`

- `JudgeResult(score=1)` valid.
- `JudgeResult(score=2)` invalid.
- `ReflectionEntry(attempt_id=1)` valid.
- `LATSConfig` defaults match limited LATS.
- `RunRecord(agent_type="lats")` valid.

### 20.2. Logging tests

File: `tests/test_logging_utils.py`

- Create temp out dir.
- Write event.
- Write llm call.
- Write error.
- Assert files exist and JSONL parse.
- Assert API key does not appear.

### 20.3. Evaluation tests

File: `tests/test_evaluation.py`

- Summary handles react/reflexion/lats.
- Delta handles missing lats gracefully.
- Comments generated and non-empty.
- Reflection helped count works.
- LATS helped count works.

### 20.4. Mock agent tests

File: `tests/test_agents_mock.py`

- ReAct run returns RunRecord.
- Reflexion creates reflection when first wrong.
- LATS trace <= 5 nodes.
- LATS record has token/latency > 0.

### 20.5. Benchmark smoke tests

Could be a lightweight test around `build_report`, not necessarily shelling full Typer command.

## 22. Error Handling Rules

LLM JSON parse error:

- Retry once with stricter instruction.
- If still fail:
  - Log `errors.jsonl`.
  - Return safe fallback if possible.

Actor fallback:

- Answer: empty string or `"unknown"`.
- Evaluator will mark wrong.

Evaluator fallback:

- Use exact normalize match.
- If not match and evaluator LLM fails, return:
  - `score=0`
  - `failure_mode="wrong_final_answer"`
  - reason mentions evaluator failure.

Reflector fallback:

- Create generic reflection:
  - lesson: complete both hops.
  - next_strategy: identify bridge entity then final property.

LATS generator fallback:

- Retry once.
- If still fail, create candidates:
  - parent answer if any.
  - `"unknown"`.

LATS critic fallback:

- Assign low score 0.0 and supported false.

Benchmark error per example:

- Log.
- Continue next example if possible.

## 23. Acceptance Criteria

Complete only when all are true:

- [ ] `report.json` has autograder required keys.
- [ ] `report.json` has additional benchmark keys: `comments`, `comparisons`, `cost_latency`, `artifacts`.
- [ ] `report.md` has readable sections and automated comments.
- [ ] `run.log` exists.
- [ ] `events.jsonl` exists.
- [ ] `llm_calls.jsonl` exists in LLM mode.
- [ ] `errors.jsonl` exists, even if empty.
- [ ] `benchmark_config.json` exists.
- [ ] `dataset_manifest.json` exists.
- [ ] ReAct, Reflexion, LATS can be selected from CLI.
- [ ] Limited LATS never creates more than 5 nodes per question.
- [ ] LATS internal call count never exceeds 4 before final evaluator.
- [ ] Reflexion uses max 3 attempts.
- [ ] Reflection memory keeps max 2 recent items.
- [ ] No API key is logged.
- [ ] Mock benchmark passes.
- [ ] Tests pass.

## 24. Priority Order For Coding

Implement in this exact order:

1. `schemas.py`
2. `utils.py` helpers for context and JSONL.
3. `logging_utils.py`
4. `evaluation.py`
5. `prompts.py`
6. `config.py`
7. `llm_client.py`
8. `mock_runtime.py` update to new schema/stats.
9. `llm_runtime.py`
10. `agents.py` refactor and add LATS.
11. `reporting.py` refactor.
12. `run_benchmark.py` CLI.
13. tests.
14. mock benchmark.
15. LLM benchmark if API key exists.

Reason:

- Schema first stabilizes all objects.
- Logging/evaluation next so agents can emit useful traces while being built.
- Mock runtime before LLM runtime so tests are cheap.
- LATS after ReAct/Reflexion.
- Reporting and CLI after agents are stable.

## 25. Do Not Do

- Do not implement full MCTS.
- Do not implement retrieval database.
- Do not mutate dataset during benchmark.
- Do not store API key in report/logs.
- Do not use `gold_answer` inside Actor/Reflector/LATS.
- Do not hardcode GPT result.
- Do not silently ignore failed LLM calls.
- Do not make LATS branch more than configured limits.

## 26. Final Run Notes

When running the real 50-sample LLM benchmark:

- Make sure `.env` has `OPENAI_API_KEY`.
- Use `gpt-4o-mini`.
- Expect LATS to cost more tokens.
- If cost/time is high, first run:

```bash
python run_benchmark.py \
  --dataset data/hotpotqa_random50.json \
  --out-dir outputs/hotpotqa_random50_llm_limit5 \
  --mode llm \
  --agents react,reflexion,lats \
  --limit 5
```

Then full:

```bash
python run_benchmark.py \
  --dataset data/hotpotqa_random50.json \
  --out-dir outputs/hotpotqa_random50_gpt4o_mini \
  --mode llm \
  --agents react,reflexion,lats
```

The final report for submission should be the full 50-sample run, not the limit-5 smoke run.
