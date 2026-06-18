# IMPLEMENTATION PLAN - Lab 16 Reflexion Agent + Limited LATS

Tai lieu nay la spec duy nhat de AI code tiep theo co the hoan thien repo `phase1-track3-lab1-advanced-agent`.

Muc tieu: hoan thien scaffold Reflexion Agent, dung GPT-4o-mini qua `.env`, benchmark tren 50 cau HotpotQA random, va them mot bien the LATS nho gon de tang chat luong nhung khong no token/cost.

## 0. Nguyen Tac Bat Buoc

- Khong leak `gold_answer` vao Actor, Reflector, Reflection memory, LATS generator, LATS critic.
- `gold_answer` chi duoc dung trong evaluator benchmark de cham diem cuoi.
- Giu duoc `mock` mode de test/autograde nhanh.
- Them `llm` mode de goi OpenAI GPT-4o-mini.
- Tat ca output LLM quan trong phai parse ve JSON theo schema.
- Moi run record phai co token va latency that neu dung LLM.
- LATS phai bi gioi han nho gon:
  - `branching_factor = 2`
  - `max_depth = 2`
  - `top_k = 1`
  - `max_nodes = 5`
  - Khong expand tat ca node. Chi expand node tot nhat moi depth.
- Toi uu cho HotpotQA: cau hoi multi-hop, context dai, de sai entity o hop 1/hop 2.

## 1. Trang Thai Hien Co

Da co:

- `data/hotpot_mini.json`: 8 mau mock.
- `data/hotpotqa_random50.json`: 50 mau HotpotQA random, seed 42.
- `.env`: placeholder cho OpenAI key va model.
- `.gitignore`: da ignore `.env`.
- `scripts/prepare_hotpotqa_random50.py`: script sample 50 mau.

Dang can hoan thien:

- `src/reflexion_lab/schemas.py`: `JudgeResult`, `ReflectionEntry` dang `pass`.
- `src/reflexion_lab/prompts.py`: prompt con placeholder.
- `src/reflexion_lab/agents.py`: Reflexion loop chua xong, token/latency dang fake.
- Chua co OpenAI LLM client.
- Chua co `llm_runtime.py`.
- Chua co `LATSAgent`.
- `run_benchmark.py` chua support `--mode llm` va `--agents`.
- `reporting.py` can mo rong cho LATS va meta ro hon.

## 2. Ket Qua Cuoi Can Dat

Sau khi code xong, cac lenh sau phai chay duoc:

```bash
python run_benchmark.py \
  --dataset data/hotpot_mini.json \
  --out-dir outputs/mock_smoke \
  --mode mock \
  --agents react,reflexion,lats \
  --reflexion-attempts 3
```

```bash
python run_benchmark.py \
  --dataset data/hotpotqa_random50.json \
  --out-dir outputs/hotpotqa_random50_gpt4o_mini \
  --mode llm \
  --agents react,reflexion,lats \
  --reflexion-attempts 3
```

```bash
python autograde.py --report-path outputs/hotpotqa_random50_gpt4o_mini/report.json
```

Voi 50 cau:

- ReAct + Reflexion = 100 records, dat dieu kien autograder `num_records >= 100`.
- Neu them LATS thi tong records = 150.

## 3. Cau Truc File Can Co Sau Khi Code

```text
phase1-track3-lab1-advanced-agent/
  .env
  requirements.txt
  run_benchmark.py
  autograde.py
  data/
    hotpot_mini.json
    hotpotqa_random50.json
  scripts/
    prepare_hotpotqa_random50.py
  src/reflexion_lab/
    __init__.py
    agents.py
    config.py
    llm_client.py
    llm_runtime.py
    mock_runtime.py
    prompts.py
    reporting.py
    schemas.py
    utils.py
  tests/
    test_utils.py
    test_schemas.py
    test_agents_mock.py
    test_reporting.py
```

## 4. Environment Va Requirements

### `.env`

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0
OPENAI_TIMEOUT_SECONDS=60
HOTPOTQA_SAMPLE_SEED=42
```

### `requirements.txt`

Can co toi thieu:

```txt
pydantic>=2.7
rich>=13.7
typer>=0.12
pandas>=2.2
python-dotenv>=1.0
datasets>=2.19
openai>=1.0
tenacity>=8.2
```

Khong them `kaggle` tru khi that su dung Kaggle API.

## 5. Schema Can Hoan Thien

File: `src/reflexion_lab/schemas.py`

### 5.1. Failure mode type

Dung chung Literal:

```python
FailureMode = Literal[
    "none",
    "entity_drift",
    "incomplete_multi_hop",
    "wrong_final_answer",
    "looping",
    "reflection_overfit",
]
```

### 5.2. `JudgeResult`

Input tao object:

```json
{
  "score": 0,
  "reason": "The answer stopped at the first-hop entity.",
  "missing_evidence": ["Need the second-hop relation."],
  "spurious_claims": ["London"],
  "normalized_gold": "river thames",
  "normalized_prediction": "london",
  "confidence": 0.92,
  "failure_mode": "incomplete_multi_hop"
}
```

Schema:

- `score: int = Field(ge=0, le=1)`
- `reason: str`
- `missing_evidence: list[str] = Field(default_factory=list)`
- `spurious_claims: list[str] = Field(default_factory=list)`
- `normalized_gold: str | None = None`
- `normalized_prediction: str | None = None`
- `confidence: float = Field(default=0.0, ge=0.0, le=1.0)`
- `failure_mode: FailureMode = "wrong_final_answer"`

### 5.3. `ReflectionEntry`

Input tao object:

```json
{
  "attempt_id": 1,
  "failure_reason": "The answer used the first-hop city as the final answer.",
  "lesson": "Finish both hops before giving the final answer.",
  "next_strategy": "Identify the intermediate entity, then answer the property requested about it.",
  "evidence_to_check": ["Ada Lovelace", "London"],
  "avoid": ["Do not answer with the intermediate entity."],
  "confidence": 0.85
}
```

Schema:

- `attempt_id: int = Field(ge=1)`
- `failure_reason: str`
- `lesson: str`
- `next_strategy: str`
- `evidence_to_check: list[str] = Field(default_factory=list)`
- `avoid: list[str] = Field(default_factory=list)`
- `confidence: float = Field(default=0.0, ge=0.0, le=1.0)`

### 5.4. `LLMCallResult`

Can them schema nho de truyen token/latency:

- `content: str`
- `input_tokens: int = 0`
- `output_tokens: int = 0`
- `total_tokens: int = 0`
- `latency_ms: int = 0`

### 5.5. `ActorOutput`

- `answer: str`
- `evidence_titles: list[str] = []`
- `reasoning_summary: str = ""`

### 5.6. `CandidateAnswer`

Dung cho LATS:

- `candidate_id: str`
- `answer: str`
- `evidence_titles: list[str] = []`
- `reasoning_summary: str = ""`

### 5.7. `LATSCritique`

- `candidate_id: str`
- `value_score: float = Field(ge=0.0, le=1.0)`
- `critique: str`
- `missing_evidence: list[str] = []`
- `supported: bool = False`

### 5.8. `LATSNode`

- `node_id: str`
- `parent_id: str | None = None`
- `depth: int`
- `answer: str`
- `evidence_titles: list[str] = []`
- `reasoning_summary: str = ""`
- `critique: str = ""`
- `value_score: float = 0.0`
- `selected: bool = False`

### 5.9. `AttemptTrace`

Giu fields cu, them optional:

- `reflection: ReflectionEntry | None = None`
- `lats_nodes: list[LATSNode] = Field(default_factory=list)`

Neu khong muon thay doi qua nhieu, co the khong them `lats_nodes` vao `AttemptTrace`, nhung `RunRecord` nen co `lats_trace`.

### 5.10. `RunRecord`

Sua `agent_type` thanh:

```python
Literal["react", "reflexion", "lats"]
```

Them optional:

- `lats_trace: list[LATSNode] = Field(default_factory=list)`

## 6. Config Va LLM Client

### 6.1. `config.py`

Tra ve config tu `.env`:

```python
@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.0
    timeout_seconds: float = 60.0
```

Ham:

- `load_settings() -> Settings`

Behavior:

- Goi `load_dotenv()`.
- Neu mode `llm` ma thieu `OPENAI_API_KEY`, raise error ro rang.
- Khong in API key ra console/log.

### 6.2. `llm_client.py`

Class:

```python
class OpenAIClient:
    def __init__(self, settings: Settings): ...
    def complete_json(self, system: str, user: str, temperature: float | None = None) -> LLMCallResult: ...
    def complete_text(self, system: str, user: str, temperature: float | None = None) -> LLMCallResult: ...
```

Behavior:

- Dung OpenAI Python SDK.
- Do latency bang `time.perf_counter()`.
- Lay usage:
  - `prompt_tokens` -> `input_tokens`
  - `completion_tokens` -> `output_tokens`
  - `total_tokens` -> `total_tokens`
- `complete_json` phai yeu cau JSON object.
- Neu parse JSON fail:
  - thu extract substring tu `{` den `}`.
  - neu van fail thi retry toi da 1 lan voi prompt "Return valid JSON only."
- Moi LLM call tra `LLMCallResult`, khong tra string thuan.

## 7. Prompt Spec

File: `src/reflexion_lab/prompts.py`

Can co cac constant:

- `ACTOR_SYSTEM`
- `EVALUATOR_SYSTEM`
- `REFLECTOR_SYSTEM`
- `LATS_GENERATOR_SYSTEM`
- `LATS_CRITIC_SYSTEM`
- `LATS_REFINER_SYSTEM`

### 7.1. Actor System Prompt

Muc tieu: tra loi cau hoi HotpotQA dua tren context, hoan thanh multi-hop, output JSON.

Prompt:

```text
You are the Actor in a HotpotQA multi-hop question answering system.
Use only the provided context. Do not use outside knowledge.
Find the intermediate entity first, then answer the final requested property.
If reflection memory is provided, apply it carefully.
Return exactly one JSON object with this schema:
{
  "answer": "short final answer only",
  "evidence_titles": ["context title used"],
  "reasoning_summary": "brief explanation of the hops, no hidden chain-of-thought"
}
Rules:
- The answer must be concise.
- Do not include markdown.
- Do not include unsupported facts.
- If evidence is insufficient, answer with the best context-supported answer and explain the uncertainty in reasoning_summary.
```

### 7.2. Actor User Input

Format:

```text
Question:
{question}

Context:
[1] {title}: {text}
[2] {title}: {text}

Reflection memory:
- {memory item}

Attempt: {attempt_id}
Agent type: {agent_type}
```

### 7.3. Actor Output

```json
{
  "answer": "River Thames",
  "evidence_titles": ["Ada Lovelace", "London"],
  "reasoning_summary": "Ada Lovelace was born in London; London is crossed by the River Thames."
}
```

### 7.4. Evaluator System Prompt

Muc tieu: cham predicted answer voi gold answer. Evaluator duoc phep thay gold.

Prompt:

```text
You are a strict benchmark evaluator for short-answer HotpotQA.
Compare the predicted answer to the gold answer.
Treat minor casing, punctuation, articles, and equivalent aliases as correct.
Return exactly one JSON object with this schema:
{
  "score": 0 or 1,
  "reason": "short reason",
  "missing_evidence": ["what was missing"],
  "spurious_claims": ["unsupported or wrong claims"],
  "confidence": number between 0 and 1,
  "failure_mode": "none | entity_drift | incomplete_multi_hop | wrong_final_answer | looping | reflection_overfit"
}
Failure mode guidance:
- "none": answer is correct.
- "incomplete_multi_hop": answer stops at an intermediate entity or misses a required hop.
- "entity_drift": answer follows a wrong entity/person/place.
- "wrong_final_answer": final answer is wrong but not clearly another category.
- "looping": answer repeats prior failed answer without new evidence.
- "reflection_overfit": answer follows reflection memory over the provided context.
```

### 7.5. Evaluator User Input

```text
Question:
{question}

Gold answer:
{gold_answer}

Predicted answer:
{predicted_answer}

Optional context:
{compact_context}
```

### 7.6. Evaluator Output

```json
{
  "score": 0,
  "reason": "The prediction is the intermediate city rather than the river through that city.",
  "missing_evidence": ["Need to use the London paragraph to identify the river."],
  "spurious_claims": ["London"],
  "confidence": 0.94,
  "failure_mode": "incomplete_multi_hop"
}
```

### 7.7. Reflector System Prompt

Muc tieu: tao bai hoc cho attempt sau, khong lay gold lam dap an.

Prompt:

```text
You are the Reflector for a Reflexion Agent.
Given the question, context, wrong answer, and evaluator feedback, write a compact lesson for the next attempt.
Do not reveal or copy the gold answer unless it is already explicitly supported by the provided context.
Focus on how to fix the reasoning process.
Return exactly one JSON object with this schema:
{
  "attempt_id": integer,
  "failure_reason": "why the previous answer failed",
  "lesson": "general lesson to remember",
  "next_strategy": "concrete strategy for the next answer",
  "evidence_to_check": ["context titles or facts to re-check"],
  "avoid": ["mistake to avoid"],
  "confidence": number between 0 and 1
}
Rules:
- Keep lesson and strategy short.
- Prefer multi-hop strategies: identify bridge entity, then verify final entity.
- Do not add facts that are not in context.
```

### 7.8. Reflector User Input

```text
Question:
{question}

Context:
{compact_context}

Attempt id:
{attempt_id}

Wrong answer:
{answer}

Evaluator reason:
{judge.reason}

Missing evidence:
{judge.missing_evidence}

Spurious claims:
{judge.spurious_claims}
```

### 7.9. Reflector Output

```json
{
  "attempt_id": 1,
  "failure_reason": "The answer stopped at the birthplace city.",
  "lesson": "Do not stop after finding the bridge entity.",
  "next_strategy": "Use the bridge entity to answer the property asked in the question.",
  "evidence_to_check": ["Ada Lovelace", "London"],
  "avoid": ["Do not use the intermediate city as final answer."],
  "confidence": 0.88
}
```

## 8. Limited LATS Spec

Ten agent: `LATSAgent`

Muc tieu: tao search tree nho de thu 2 ung vien, cham, chi expand ung vien tot nhat, roi chon final.

Khong dung LATS day du voi nhieu branch vi 50 cau HotpotQA se ton token. Ban nay la `mini_lats_branching`, du tinh du bonus va de benchmark hop ly.

### 8.1. LATS Config Mac Dinh

```python
branching_factor = 2
max_depth = 2
top_k = 1
max_nodes = 5
early_stop_score = 0.92
generator_temperature = 0.2
critic_temperature = 0.0
```

### 8.2. Gioi Han LLM Call Moi Cau

Toi da:

- Depth 1 generator: 1 call, sinh 2 candidates.
- Depth 1 critic: 1 call, cham 2 candidates.
- Depth 2 refiner/generator: 1 call, sinh 2 refined candidates tu node tot nhat.
- Depth 2 critic: 1 call, cham 2 refined candidates.
- Final benchmark evaluator: 1 call.

Tong LATS noi bo toi da 4 call + 1 evaluator call moi cau.

Neu depth 1 best score >= `early_stop_score`, dung som:

- Chi ton 2 call noi bo + 1 evaluator call.

### 8.3. LATS Tree Shape

Gioi han tree:

```text
root
  candidate_1
    refined_1a
    refined_1b
  candidate_2
```

Chi candidate tot nhat o depth 1 duoc expand. Node con cua candidate con lai khong tao.

So node toi da:

- 1 root
- 2 candidates depth 1
- 2 refined candidates depth 2
- Total = 5 nodes

### 8.4. LATS Generator Prompt

System:

```text
You are a candidate generator for a limited Language Agent Tree Search on HotpotQA.
Use only the provided context.
Generate exactly 2 diverse candidate answers.
Each candidate must follow a different plausible multi-hop path or evidence focus.
Return exactly one JSON object:
{
  "candidates": [
    {
      "candidate_id": "c1",
      "answer": "short final answer",
      "evidence_titles": ["title"],
      "reasoning_summary": "brief hop summary"
    },
    {
      "candidate_id": "c2",
      "answer": "short final answer",
      "evidence_titles": ["title"],
      "reasoning_summary": "brief hop summary"
    }
  ]
}
Rules:
- Return exactly 2 candidates.
- Do not use outside knowledge.
- Keep each answer short.
- Do not include markdown.
```

User:

```text
Question:
{question}

Context:
{compact_context}

Existing best node, if any:
{best_node_or_none}

Critique to address, if any:
{critique_or_none}
```

Output:

```json
{
  "candidates": [
    {
      "candidate_id": "c1",
      "answer": "Pacific Ocean",
      "evidence_titles": ["Lima", "Peru"],
      "reasoning_summary": "Lima is the capital of Peru; Peru borders the Pacific Ocean."
    },
    {
      "candidate_id": "c2",
      "answer": "Peru",
      "evidence_titles": ["Lima"],
      "reasoning_summary": "Lima is the capital of Peru."
    }
  ]
}
```

### 8.5. LATS Critic Prompt

System:

```text
You are a context-grounded critic for limited LATS.
You do not know the gold answer.
Score each candidate only by whether the provided context supports it as the final answer to the question.
Return exactly one JSON object:
{
  "critiques": [
    {
      "candidate_id": "c1",
      "value_score": number between 0 and 1,
      "critique": "short critique",
      "missing_evidence": ["missing evidence"],
      "supported": true or false
    }
  ]
}
Scoring guide:
- 0.90-1.00: fully answers all hops and is directly supported.
- 0.60-0.89: plausible but one hop or wording is weak.
- 0.30-0.59: uses some right evidence but likely incomplete.
- 0.00-0.29: unsupported or wrong entity.
```

User:

```text
Question:
{question}

Context:
{compact_context}

Candidates:
{candidates_json}
```

Output:

```json
{
  "critiques": [
    {
      "candidate_id": "c1",
      "value_score": 0.95,
      "critique": "Completes both hops and answers the requested ocean.",
      "missing_evidence": [],
      "supported": true
    },
    {
      "candidate_id": "c2",
      "value_score": 0.42,
      "critique": "This is the country, not the ocean bordering it.",
      "missing_evidence": ["Need the Peru paragraph to identify the ocean."],
      "supported": false
    }
  ]
}
```

### 8.6. LATS Final Selection

Khong can GPT call rieng neu da co critic:

- Merge candidates + critiques thanh `LATSNode`.
- Chon node co `value_score` cao nhat.
- Neu tie:
  - Uu tien node co `supported=True`.
  - Uu tien node depth lon hon neu critique tot hon.
  - Uu tien answer ngan hon de tranh giai thich lan vao answer.

Final answer:

```python
best_node.answer
```

### 8.7. LATS RunRecord

Trong `RunRecord`:

- `agent_type = "lats"`
- `attempts = 1`
- `predicted_answer = best_node.answer`
- `lats_trace = all_nodes`
- `token_estimate = sum internal calls + evaluator call`
- `latency_ms = sum internal calls + evaluator call`
- `failure_mode = judge.failure_mode if wrong else "none"`

## 9. Agent Runtime Design

### 9.1. Runtime interface

Tao protocol/class trong `agents.py` hoac file rieng:

```python
class AgentRuntime(Protocol):
    def actor_answer(...) -> tuple[str, RuntimeStats]: ...
    def evaluator(...) -> tuple[JudgeResult, RuntimeStats]: ...
    def reflector(...) -> tuple[ReflectionEntry, RuntimeStats]: ...
    def lats_generate_candidates(...) -> tuple[list[CandidateAnswer], RuntimeStats]: ...
    def lats_critic(...) -> tuple[list[LATSCritique], RuntimeStats]: ...
```

Co the don gian hon: runtime method tra object co `.stats`.

### 9.2. `RuntimeStats`

- `token_estimate: int`
- `latency_ms: int`

Mock runtime:

- Tra stats fake/deterministic de tests on dinh.

LLM runtime:

- Lay stats tu `LLMCallResult`.

### 9.3. ReAct flow

Input:

- `QAExample`

Flow:

1. Goi actor 1 lan.
2. Goi evaluator.
3. Tao `AttemptTrace`.
4. Tao `RunRecord`.

Output:

- `RunRecord(agent_type="react", attempts=1, ...)`

### 9.4. Reflexion flow

Input:

- `QAExample`
- `max_attempts=3`

Flow:

1. `reflection_memory = []`
2. For attempt in `1..max_attempts`:
   - Goi actor voi memory.
   - Goi evaluator.
   - Tao trace.
   - Neu dung: append trace, break.
   - Neu sai va con attempt:
     - Goi reflector.
     - Gan reflection vao trace.
     - Append reflection vao `reflections`.
     - Append compact memory string:
       - `lesson`
       - `next_strategy`
       - `avoid`
     - Gioi han memory toi da 2 item gan nhat.
   - Append trace.
3. Tao `RunRecord`.

Output:

- `RunRecord(agent_type="reflexion", attempts=len(traces), reflections=reflections, ...)`

### 9.5. Adaptive attempts

Co the lam sau, neu don gian thi de `max_attempts=3`.

Neu lam:

- easy: toi da 2
- medium/hard: toi da 3

Khong de qua 3 de tiet kiem chi phi.

### 9.6. LATS flow

Input:

- `QAExample`
- LATS config mac dinh

Flow:

1. Tao root `LATSNode(node_id="root", depth=0, answer="")`.
2. Depth 1:
   - `generate_candidates(question, context, best_node=None, critique=None)` -> 2 candidates.
   - `critic(question, context, candidates)` -> 2 critiques.
   - Tao 2 child nodes.
   - Chon best depth 1.
3. Early stop:
   - Neu best score >= 0.92 thi dung, final = best depth 1.
4. Depth 2:
   - Generate 2 refined candidates dua tren best node va critique cua no.
   - Critic 2 refined candidates.
   - Tao 2 child nodes cua best depth 1.
5. Final:
   - Chon best node trong tat ca non-root nodes.
   - Goi benchmark evaluator voi final answer.
   - Tao `RunRecord`.

Output:

- `RunRecord(agent_type="lats", attempts=1, lats_trace=nodes, ...)`

## 10. LLM Runtime Input/Output

File: `src/reflexion_lab/llm_runtime.py`

### 10.1. `actor_answer`

Signature:

```python
def actor_answer(
    example: QAExample,
    attempt_id: int,
    agent_type: str,
    reflection_memory: list[str],
) -> tuple[str, RuntimeStats]:
```

Input user payload includes:

- question
- compact context
- reflection memory
- attempt id
- agent type

Output:

- answer string
- stats

Parse:

- Parse JSON as `ActorOutput`.
- Return `ActorOutput.answer.strip()`.

### 10.2. `evaluator`

Signature:

```python
def evaluator(example: QAExample, answer: str) -> tuple[JudgeResult, RuntimeStats]:
```

Input:

- question
- gold_answer
- predicted answer
- optional compact context

Output:

- `JudgeResult`
- stats

Fallback:

- Truoc hoac sau LLM, co the dung `normalize_answer` exact match:
  - Neu exact match thi return `score=1` ngay de tiet kiem call.
  - Neu khong exact match, goi GPT evaluator.

### 10.3. `reflector`

Signature:

```python
def reflector(
    example: QAExample,
    attempt_id: int,
    judge: JudgeResult,
    wrong_answer: str,
) -> tuple[ReflectionEntry, RuntimeStats]:
```

Input:

- question
- compact context
- attempt id
- wrong answer
- judge reason/missing evidence/spurious claims

Output:

- `ReflectionEntry`
- stats

### 10.4. `lats_generate_candidates`

Signature:

```python
def lats_generate_candidates(
    example: QAExample,
    parent_node: LATSNode | None,
    critique: str | None,
    branching_factor: int = 2,
) -> tuple[list[CandidateAnswer], RuntimeStats]:
```

Output exactly 2 candidates.

If model returns more:

- keep first 2.

If model returns fewer:

- fill fallback candidate from parent answer or `"unknown"` with low confidence, but better retry once.

### 10.5. `lats_critic`

Signature:

```python
def lats_critic(
    example: QAExample,
    candidates: list[CandidateAnswer],
) -> tuple[list[LATSCritique], RuntimeStats]:
```

Output one critique per candidate.

## 11. Context Formatting

File: `utils.py`

Them helper:

```python
def format_context(example: QAExample, max_chars: int = 12000) -> str:
    ...
```

Rules:

- Format moi chunk:
  - `[1] Title: text`
- Cat context neu qua dai:
  - Uu tien giu cac title/facts dau tien nhu dataset distractor.
  - Cat tung text chunk theo max per chunk neu can.
- Khong cat den muc mat het evidence. Mac dinh 12000 chars de GPT-4o-mini du context.

Them helper:

```python
def compact_reflection_memory(reflections: list[ReflectionEntry], max_items: int = 2) -> list[str]:
    ...
```

Format memory item:

```text
Lesson: {lesson}; Strategy: {next_strategy}; Avoid: {avoid}
```

## 12. Reporting

File: `reporting.py`

### 12.1. Summary

Support all agent types:

- react
- reflexion
- lats

Metrics:

- `count`
- `em`
- `avg_attempts`
- `avg_token_estimate`
- `avg_latency_ms`

Delta:

- `delta_reflexion_minus_react`
- `delta_lats_minus_react`
- `delta_lats_minus_reflexion`

### 12.2. Examples

Moi example trong report:

```json
{
  "qid": "...",
  "agent_type": "lats",
  "gold_answer": "...",
  "predicted_answer": "...",
  "is_correct": true,
  "attempts": 1,
  "failure_mode": "none",
  "reflection_count": 0,
  "lats_node_count": 5,
  "token_estimate": 1234,
  "latency_ms": 3210
}
```

### 12.3. Extensions

Report `extensions` nen gom:

- `structured_evaluator`
- `reflection_memory`
- `benchmark_report_json`
- `mock_mode_for_autograding`
- `mini_lats_branching`

Neu lam adaptive attempts:

- `adaptive_max_attempts`

### 12.4. Discussion

Can >= 250 ky tu.

Noi dung can co:

- Reflexion tot khi sai do incomplete multi-hop.
- LATS tot khi co nhieu entity distractor va can so sanh candidates.
- LATS ton token/latency hon ReAct.
- Limited LATS da gioi han branch/node de phu hop 50 mau.
- Cac loi con lai: entity drift, wrong final answer, evaluator ambiguity.

## 13. Benchmark CLI

File: `run_benchmark.py`

### 13.1. Arguments

Them:

- `--mode`: `"mock"` hoac `"llm"`, default `"mock"`.
- `--agents`: string CSV, default `"react,reflexion"`.
- `--reflexion-attempts`: default `3`.
- `--lats-max-depth`: default `2`.
- `--lats-branching-factor`: default `2`.
- `--lats-max-nodes`: default `5`.

### 13.2. Agent selection

Input:

```bash
--agents react,reflexion,lats
```

Behavior:

- Split CSV.
- Validate allowed agents.
- Chay theo thu tu input.
- Ghi file rieng:
  - `react_runs.jsonl`
  - `reflexion_runs.jsonl`
  - `lats_runs.jsonl`

### 13.3. Report meta

`meta`:

```json
{
  "dataset": "hotpotqa_random50.json",
  "mode": "llm",
  "num_examples": 50,
  "num_records": 150,
  "agents": ["lats", "react", "reflexion"],
  "model": "gpt-4o-mini",
  "seed": 42,
  "lats_config": {
    "branching_factor": 2,
    "max_depth": 2,
    "top_k": 1,
    "max_nodes": 5,
    "early_stop_score": 0.92
  }
}
```

Autograder chi can `num_records`, nhung them `num_examples` de ro hon.

## 14. Mock Runtime

File: `mock_runtime.py`

Muc tieu:

- Van deterministic.
- Ho tro schema moi.
- Ho tro LATS mock.

Can sua:

- `evaluator()` tra `JudgeResult` day du.
- `reflector()` tra `ReflectionEntry` day du.
- Neu agents.py doi runtime return tuple, mock cung return tuple.

Mock LATS:

- Neu qid co trong `FIRST_ATTEMPT_WRONG`, LATS nen tim dung answer bang candidate 2 hoac refined candidate.
- Tao nodes fake du de test report.

Khong can goi GPT trong mock.

## 15. Tests

Can viet/cap nhat:

### 15.1. `tests/test_schemas.py`

- Tao `JudgeResult` valid.
- Reject `score=2`.
- Tao `ReflectionEntry` valid.
- Tao `LATSNode` valid.

### 15.2. `tests/test_agents_mock.py`

- ReAct mock chay duoc.
- Reflexion mock voi qid sai lan dau co:
  - attempts > 1
  - reflections >= 1
  - memory duoc dung de sua answer
- LATS mock chay duoc:
  - agent_type = "lats"
  - lats_trace khong rong
  - token_estimate > 0

### 15.3. `tests/test_reporting.py`

- Build report co required keys.
- Summary co react/reflexion/lats.
- Examples co >= records.

### 15.4. Smoke test commands

```bash
pytest
```

```bash
python run_benchmark.py --dataset data/hotpot_mini.json --out-dir outputs/mock_smoke --mode mock --agents react,reflexion,lats
```

```bash
python autograde.py --report-path outputs/mock_smoke/report.json
```

## 16. Thu Tu Code Chuan

Lam theo thu tu nay de tranh vo nhieu file cung luc:

1. Cap nhat `requirements.txt`.
2. Hoan thien `schemas.py`.
3. Them helper trong `utils.py`.
4. Viet `prompts.py`.
5. Tao `config.py`.
6. Tao `llm_client.py`.
7. Sua `mock_runtime.py` de match schema/stat moi.
8. Tao `llm_runtime.py`.
9. Refactor `agents.py`:
   - runtime injection
   - ReAct
   - Reflexion
   - LATS
10. Sua `run_benchmark.py`.
11. Sua `reporting.py`.
12. Viet tests.
13. Chay `pytest`.
14. Chay mock benchmark.
15. Neu `.env` da co key, chay LLM benchmark 50 mau.

## 17. Acceptance Criteria

Hoan thanh khi:

- [ ] `schemas.py` khong con `pass`.
- [ ] `prompts.py` khong con TODO placeholder.
- [ ] `mock` benchmark chay duoc voi `react,reflexion,lats`.
- [ ] `llm` benchmark dung `OPENAI_MODEL=gpt-4o-mini`.
- [ ] `data/hotpotqa_random50.json` co dung 50 mau.
- [ ] `run_benchmark.py --agents react,reflexion,lats` tao 3 JSONL files.
- [ ] Report co `meta`, `summary`, `failure_modes`, `examples`, `extensions`, `discussion`.
- [ ] Report co `num_records >= 100` khi chay 50 mau voi it nhat ReAct + Reflexion.
- [ ] LATS trace toi da 5 nodes moi cau.
- [ ] LATS noi bo toi da 4 LLM calls moi cau tru evaluator benchmark.
- [ ] Token va latency trong LLM mode la so do that, khong hardcoded.
- [ ] `pytest` pass.

## 18. Viec Khong Lam Trong Lan Code Nay

- Khong implement LATS full MCTS/UCB phuc tap.
- Khong them retrieval/vector database.
- Khong fine-tune model.
- Khong dung Kaggle neu Hugging Face dataset da co.
- Khong log full `.env` hoac API key.
- Khong sua autograder tru khi bat buoc.

## 19. Ghi Chu Cho AI Code Sau

Uu tien code chay on dinh hon la phuc tap.

Neu can cat scope:

1. Bat buoc hoan thien schema + prompt + Reflexion loop.
2. Bat buoc giu mock benchmark pass.
3. Sau do moi them LLM runtime.
4. Cuoi cung them LATS limited.

LATS limited nen duoc xem la extension co kiem soat cost, khong phai search tree lon. Moi cau HotpotQA chi tao toi da 5 node. Dieu nay quan trong vi dataset co 50 cau va GPT call se nhan len rat nhanh.
