from __future__ import annotations

from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field

FailureMode = Literal[
    "none",
    "entity_drift",
    "incomplete_multi_hop",
    "wrong_final_answer",
    "looping",
    "reflection_overfit",
]
AgentType = Literal["react", "reflexion", "lats"]


class ContextChunk(BaseModel):
    title: str
    text: str


class QAExample(BaseModel):
    qid: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question: str
    gold_answer: str = ""
    context: list[ContextChunk]


class JudgeResult(BaseModel):
    score: int = Field(ge=0, le=1)
    reason: str
    missing_evidence: list[str] = Field(default_factory=list)
    spurious_claims: list[str] = Field(default_factory=list)
    normalized_gold: Optional[str] = None
    normalized_prediction: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    failure_mode: FailureMode = "wrong_final_answer"


class ReflectionEntry(BaseModel):
    attempt_id: int = Field(ge=1)
    failure_reason: str
    lesson: str
    next_strategy: str
    evidence_to_check: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RuntimeStats(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    token_estimate: int = 0
    latency_ms: int = 0
    llm_call_count: int = 0

    def __add__(self, other: "RuntimeStats") -> "RuntimeStats":
        return RuntimeStats(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            token_estimate=self.token_estimate + other.token_estimate,
            latency_ms=self.latency_ms + other.latency_ms,
            llm_call_count=self.llm_call_count + other.llm_call_count,
        )


class LLMCallResult(BaseModel):
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0

    def to_stats(self) -> RuntimeStats:
        return RuntimeStats(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            token_estimate=self.total_tokens,
            latency_ms=self.latency_ms,
            llm_call_count=1,
        )


class ActorOutput(BaseModel):
    answer: str
    evidence_titles: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""


class CandidateAnswer(BaseModel):
    candidate_id: str
    answer: str
    evidence_titles: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""


class LATSCritique(BaseModel):
    candidate_id: str
    value_score: float = Field(ge=0.0, le=1.0)
    critique: str
    missing_evidence: list[str] = Field(default_factory=list)
    supported: bool = False


class LATSNode(BaseModel):
    node_id: str
    parent_id: Optional[str] = None
    depth: int = Field(ge=0)
    answer: str = ""
    evidence_titles: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    critique: str = ""
    value_score: float = Field(default=0.0, ge=0.0, le=1.0)
    selected: bool = False


class LATSConfig(BaseModel):
    branching_factor: int = Field(default=2, ge=1, le=2)
    max_depth: int = Field(default=2, ge=1, le=2)
    top_k: int = Field(default=1, ge=1, le=1)
    max_nodes: int = Field(default=5, ge=1, le=5)
    early_stop_score: float = Field(default=0.92, ge=0.0, le=1.0)
    generator_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    critic_temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class AttemptTrace(BaseModel):
    attempt_id: int
    answer: str
    score: int
    reason: str
    reflection: Optional[ReflectionEntry] = None
    lats_nodes: list[LATSNode] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    token_estimate: int = 0
    latency_ms: int = 0
    llm_call_count: int = 0


class RunRecord(BaseModel):
    qid: str
    question: str
    gold_answer: str = ""
    agent_type: AgentType
    predicted_answer: str
    is_correct: Optional[bool]
    attempts: int
    input_tokens: int = 0
    output_tokens: int = 0
    token_estimate: int
    latency_ms: int
    llm_call_count: int = 0
    failure_mode: FailureMode
    reflections: list[ReflectionEntry] = Field(default_factory=list)
    traces: list[AttemptTrace] = Field(default_factory=list)
    lats_trace: list[LATSNode] = Field(default_factory=list)


class ReportPayload(BaseModel):
    meta: dict
    summary: dict
    failure_modes: dict
    examples: list[dict]
    comparisons: dict = Field(default_factory=dict)
    comments: list[str] = Field(default_factory=list)
    react_vs_reflexion_table: list[dict] = Field(default_factory=list)
    cost_runtime_table: list[dict] = Field(default_factory=list)
    reflection_analysis: dict = Field(default_factory=dict)
    lats_analysis: dict = Field(default_factory=dict)
    cost_latency: dict = Field(default_factory=dict)
    golden_submission: Optional[dict] = None
    extensions: list[str]
    discussion: str
    artifacts: dict = Field(default_factory=dict)


class ReflexionState(TypedDict):
    question: str
    context: list[str]
    trajectory: list[str]
    reflection_memory: list[str]
    attempt_count: int
    success: bool
    final_answer: str
