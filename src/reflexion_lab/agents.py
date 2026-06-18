from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .logging_utils import BenchmarkLogger
from .mock_runtime import MockRuntime
from .schemas import (
    AgentType,
    AttemptTrace,
    CandidateAnswer,
    JudgeResult,
    LATSConfig,
    LATSCritique,
    LATSNode,
    QAExample,
    ReflectionEntry,
    RunRecord,
    RuntimeStats,
)
from .utils import compact_reflection_memory


def _empty_judge(example: QAExample) -> JudgeResult:
    return JudgeResult(
        score=0,
        reason="Gold answer is absent; correctness was not computed.",
        confidence=0.0,
        failure_mode="none",
    )


def _is_correct(example: QAExample, judge: JudgeResult) -> Optional[bool]:
    if not example.gold_answer:
        return None
    return bool(judge.score)


@dataclass
class BaseAgent:
    agent_type: AgentType
    max_attempts: int = 1
    runtime: Any = None
    logger: Optional[BenchmarkLogger] = None

    def __post_init__(self) -> None:
        if self.runtime is None:
            self.runtime = MockRuntime()

    def run(self, example: QAExample) -> RunRecord:
        if self.agent_type == "lats":
            raise NotImplementedError("Use LATSAgent for agent_type='lats'.")

        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_judge = _empty_judge(example)

        self._event("example_start", qid=example.qid, agent_type=self.agent_type)
        for attempt_id in range(1, self.max_attempts + 1):
            self._event("attempt_start", qid=example.qid, agent_type=self.agent_type, attempt_id=attempt_id)
            answer, actor_stats = self.runtime.actor_answer(example, attempt_id, self.agent_type, reflection_memory)
            judge, judge_stats = self.runtime.evaluator(example, answer)
            trace_stats = actor_stats + judge_stats
            trace = AttemptTrace(
                attempt_id=attempt_id,
                answer=answer,
                score=judge.score,
                reason=judge.reason,
                input_tokens=trace_stats.input_tokens,
                output_tokens=trace_stats.output_tokens,
                token_estimate=trace_stats.token_estimate,
                latency_ms=trace_stats.latency_ms,
                llm_call_count=trace_stats.llm_call_count,
            )
            final_answer = answer
            final_judge = judge

            if judge.score == 1 or attempt_id >= self.max_attempts or self.agent_type != "reflexion":
                traces.append(trace)
                self._event(
                    "attempt_end",
                    qid=example.qid,
                    agent_type=self.agent_type,
                    attempt_id=attempt_id,
                    score=judge.score,
                    tokens=trace.token_estimate,
                )
                break

            reflection, reflection_stats = self.runtime.reflector(example, attempt_id, judge, answer)
            reflections.append(reflection)
            trace.reflection = reflection
            trace.input_tokens += reflection_stats.input_tokens
            trace.output_tokens += reflection_stats.output_tokens
            trace.token_estimate += reflection_stats.token_estimate
            trace.latency_ms += reflection_stats.latency_ms
            trace.llm_call_count += reflection_stats.llm_call_count
            reflection_memory = compact_reflection_memory(reflections, max_items=2)
            traces.append(trace)
            self._event(
                "reflection_created",
                qid=example.qid,
                agent_type=self.agent_type,
                attempt_id=attempt_id,
                lesson=reflection.lesson,
            )
            self._event(
                "attempt_end",
                qid=example.qid,
                agent_type=self.agent_type,
                attempt_id=attempt_id,
                score=judge.score,
                tokens=trace.token_estimate,
            )

        record = self._build_record(example, final_answer, final_judge, traces, reflections)
        self._event(
            "example_end",
            qid=example.qid,
            agent_type=self.agent_type,
            is_correct=record.is_correct,
            attempts=record.attempts,
            token_estimate=record.token_estimate,
            latency_ms=record.latency_ms,
            failure_mode=record.failure_mode,
        )
        return record

    def _build_record(
        self,
        example: QAExample,
        final_answer: str,
        final_judge: JudgeResult,
        traces: list[AttemptTrace],
        reflections: list[ReflectionEntry],
    ) -> RunRecord:
        return RunRecord(
            qid=example.qid,
            question=example.question,
            gold_answer=example.gold_answer,
            agent_type=self.agent_type,
            predicted_answer=final_answer,
            is_correct=_is_correct(example, final_judge),
            attempts=len(traces),
            input_tokens=sum(trace.input_tokens for trace in traces),
            output_tokens=sum(trace.output_tokens for trace in traces),
            token_estimate=sum(trace.token_estimate for trace in traces),
            latency_ms=sum(trace.latency_ms for trace in traces),
            llm_call_count=sum(trace.llm_call_count for trace in traces),
            failure_mode="none" if final_judge.score == 1 or not example.gold_answer else final_judge.failure_mode,
            reflections=reflections,
            traces=traces,
        )

    def _event(self, event: str, **fields: object) -> None:
        if self.logger:
            self.logger.event(event, **fields)


class ReActAgent(BaseAgent):
    def __init__(self, runtime: Any = None, logger: Optional[BenchmarkLogger] = None) -> None:
        super().__init__(agent_type="react", max_attempts=1, runtime=runtime, logger=logger)


class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3, runtime: Any = None, logger: Optional[BenchmarkLogger] = None) -> None:
        super().__init__(agent_type="reflexion", max_attempts=min(max_attempts, 3), runtime=runtime, logger=logger)


class LATSAgent:
    agent_type: AgentType = "lats"

    def __init__(
        self,
        runtime: Any = None,
        config: Optional[LATSConfig] = None,
        logger: Optional[BenchmarkLogger] = None,
    ) -> None:
        self.runtime = runtime or MockRuntime()
        self.config = config or LATSConfig()
        self.logger = logger

    def run(self, example: QAExample) -> RunRecord:
        self._event("example_start", qid=example.qid, agent_type="lats")
        nodes: list[LATSNode] = [LATSNode(node_id="root", depth=0)]
        total_stats = RuntimeStats()

        self._event("lats_depth_start", qid=example.qid, depth=1)
        candidates, stats = self.runtime.lats_generate_candidates(
            example,
            parent_answer=None,
            critique=None,
            branching_factor=self.config.branching_factor,
        )
        total_stats += stats
        critiques, stats = self.runtime.lats_critic(example, candidates)
        total_stats += stats
        depth_one_nodes = self._nodes_from_candidates(candidates, critiques, parent_id="root", depth=1, prefix="d1")
        nodes.extend(depth_one_nodes)
        best = self._select_best(depth_one_nodes)
        self._event("lats_candidates_scored", qid=example.qid, depth=1, best_answer=best.answer, best_score=best.value_score)

        if best.value_score < self.config.early_stop_score and len(nodes) < self.config.max_nodes:
            self._event("lats_depth_start", qid=example.qid, depth=2)
            refined, stats = self.runtime.lats_generate_candidates(
                example,
                parent_answer=best.answer,
                critique=best.critique,
                branching_factor=self.config.branching_factor,
            )
            total_stats += stats
            refined_critiques, stats = self.runtime.lats_critic(example, refined)
            total_stats += stats
            remaining = self.config.max_nodes - len(nodes)
            depth_two_nodes = self._nodes_from_candidates(refined, refined_critiques, parent_id=best.node_id, depth=2, prefix="d2")[:remaining]
            nodes.extend(depth_two_nodes)
            best = self._select_best([node for node in nodes if node.node_id != "root"])
            self._event("lats_candidates_scored", qid=example.qid, depth=2, best_answer=best.answer, best_score=best.value_score)

        best.selected = True
        judge, judge_stats = self.runtime.evaluator(example, best.answer)
        total_stats += judge_stats
        trace = AttemptTrace(
            attempt_id=1,
            answer=best.answer,
            score=judge.score,
            reason=judge.reason,
            lats_nodes=nodes,
            input_tokens=total_stats.input_tokens,
            output_tokens=total_stats.output_tokens,
            token_estimate=total_stats.token_estimate,
            latency_ms=total_stats.latency_ms,
            llm_call_count=total_stats.llm_call_count,
        )
        record = RunRecord(
            qid=example.qid,
            question=example.question,
            gold_answer=example.gold_answer,
            agent_type="lats",
            predicted_answer=best.answer,
            is_correct=_is_correct(example, judge),
            attempts=1,
            input_tokens=total_stats.input_tokens,
            output_tokens=total_stats.output_tokens,
            token_estimate=total_stats.token_estimate,
            latency_ms=total_stats.latency_ms,
            llm_call_count=total_stats.llm_call_count,
            failure_mode="none" if judge.score == 1 or not example.gold_answer else judge.failure_mode,
            traces=[trace],
            lats_trace=nodes,
        )
        self._event(
            "lats_final_selected",
            qid=example.qid,
            answer=best.answer,
            value_score=best.value_score,
            nodes=len(nodes),
        )
        self._event(
            "example_end",
            qid=example.qid,
            agent_type="lats",
            is_correct=record.is_correct,
            attempts=record.attempts,
            token_estimate=record.token_estimate,
            latency_ms=record.latency_ms,
            failure_mode=record.failure_mode,
        )
        return record

    def _nodes_from_candidates(
        self,
        candidates: list[CandidateAnswer],
        critiques: list[LATSCritique],
        *,
        parent_id: str,
        depth: int,
        prefix: str,
    ) -> list[LATSNode]:
        critique_by_id = {critique.candidate_id: critique for critique in critiques}
        nodes: list[LATSNode] = []
        for index, candidate in enumerate(candidates, start=1):
            critique = critique_by_id.get(
                candidate.candidate_id,
                LATSCritique(candidate_id=candidate.candidate_id, value_score=0.0, critique="Missing critique."),
            )
            nodes.append(
                LATSNode(
                    node_id=f"{prefix}_{index}",
                    parent_id=parent_id,
                    depth=depth,
                    answer=candidate.answer,
                    evidence_titles=candidate.evidence_titles,
                    reasoning_summary=candidate.reasoning_summary,
                    critique=critique.critique,
                    value_score=critique.value_score,
                )
            )
        return nodes

    def _select_best(self, nodes: list[LATSNode]) -> LATSNode:
        return sorted(nodes, key=lambda node: (node.value_score, len(node.answer) * -1), reverse=True)[0]

    def _event(self, event: str, **fields: object) -> None:
        if self.logger:
            self.logger.event(event, **fields)
