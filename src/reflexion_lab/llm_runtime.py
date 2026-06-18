from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import ValidationError

from .llm_client import OpenAIClient
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, LATS_CRITIC_SYSTEM, LATS_GENERATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import ActorOutput, CandidateAnswer, JudgeResult, LATSCritique, QAExample, ReflectionEntry, RuntimeStats
from .utils import format_context, normalize_answer


class LLMRuntime:
    mode = "llm"

    def __init__(self, client: OpenAIClient) -> None:
        self.client = client
        self.model = client.settings.openai_model

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> tuple[str, RuntimeStats]:
        user = f"""Question:
{example.question}

Context:
{format_context(example)}

Reflection memory:
{json.dumps(reflection_memory, ensure_ascii=False)}

Attempt: {attempt_id}
Agent type: {agent_type}
"""
        result = self.client.complete_json(
            ACTOR_SYSTEM,
            user,
            metadata={"qid": example.qid, "agent_type": agent_type, "call_type": "actor", "attempt_id": attempt_id},
        )
        try:
            output = ActorOutput.model_validate(self.client.parse_json(result.content))
            answer = output.answer.strip()
        except (ValidationError, json.JSONDecodeError, KeyError):
            answer = result.content.strip()
        return answer, result.to_stats()

    def evaluator(self, example: QAExample, answer: str) -> tuple[JudgeResult, RuntimeStats]:
        normalized_gold = normalize_answer(example.gold_answer)
        normalized_prediction = normalize_answer(answer)
        if not example.gold_answer:
            return (
                JudgeResult(
                    score=0,
                    reason="Gold answer is absent; correctness was not computed.",
                    normalized_gold=normalized_gold,
                    normalized_prediction=normalized_prediction,
                    confidence=0.0,
                    failure_mode="none",
                ),
                RuntimeStats(),
            )
        if normalized_gold == normalized_prediction:
            return (
                JudgeResult(
                    score=1,
                    reason="Final answer matches the gold answer after normalization.",
                    normalized_gold=normalized_gold,
                    normalized_prediction=normalized_prediction,
                    confidence=1.0,
                    failure_mode="none",
                ),
                RuntimeStats(),
            )

        user = f"""Question:
{example.question}

Gold answer:
{example.gold_answer}

Predicted answer:
{answer}

Optional context:
{format_context(example, max_chars=6000)}
"""
        result = self.client.complete_json(
            EVALUATOR_SYSTEM,
            user,
            metadata={"qid": example.qid, "agent_type": "benchmark", "call_type": "evaluator", "attempt_id": 0},
        )
        payload = self.client.parse_json(result.content)
        payload.setdefault("normalized_gold", normalized_gold)
        payload.setdefault("normalized_prediction", normalized_prediction)
        judge = JudgeResult.model_validate(payload)
        return judge, result.to_stats()

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        judge: JudgeResult,
        wrong_answer: str,
    ) -> tuple[ReflectionEntry, RuntimeStats]:
        user = f"""Question:
{example.question}

Context:
{format_context(example, max_chars=7000)}

Attempt id:
{attempt_id}

Wrong answer:
{wrong_answer}

Evaluator reason:
{judge.reason}

Missing evidence:
{json.dumps(judge.missing_evidence, ensure_ascii=False)}

Spurious claims:
{json.dumps(judge.spurious_claims, ensure_ascii=False)}
"""
        result = self.client.complete_json(
            REFLECTOR_SYSTEM,
            user,
            metadata={"qid": example.qid, "agent_type": "reflexion", "call_type": "reflector", "attempt_id": attempt_id},
        )
        payload = self.client.parse_json(result.content)
        payload["attempt_id"] = attempt_id
        reflection = ReflectionEntry.model_validate(payload)
        return reflection, result.to_stats()

    def lats_generate_candidates(
        self,
        example: QAExample,
        parent_answer: Optional[str] = None,
        critique: Optional[str] = None,
        branching_factor: int = 2,
    ) -> tuple[list[CandidateAnswer], RuntimeStats]:
        user = f"""Question:
{example.question}

Context:
{format_context(example)}

Existing best answer, if any:
{parent_answer or "none"}

Critique to address, if any:
{critique or "none"}
"""
        result = self.client.complete_json(
            LATS_GENERATOR_SYSTEM,
            user,
            temperature=0.2,
            metadata={"qid": example.qid, "agent_type": "lats", "call_type": "lats_generator", "attempt_id": 1},
        )
        payload = self.client.parse_json(result.content)
        candidates = [CandidateAnswer.model_validate(item) for item in payload.get("candidates", [])]
        if len(candidates) < branching_factor:
            candidates.extend(
                CandidateAnswer(candidate_id=f"fallback_{idx}", answer=parent_answer or "unknown")
                for idx in range(len(candidates), branching_factor)
            )
        return candidates[:branching_factor], result.to_stats()

    def lats_critic(
        self,
        example: QAExample,
        candidates: list[CandidateAnswer],
    ) -> tuple[list[LATSCritique], RuntimeStats]:
        user = f"""Question:
{example.question}

Context:
{format_context(example, max_chars=9000)}

Candidates:
{json.dumps([candidate.model_dump() for candidate in candidates], ensure_ascii=False, indent=2)}
"""
        result = self.client.complete_json(
            LATS_CRITIC_SYSTEM,
            user,
            metadata={"qid": example.qid, "agent_type": "lats", "call_type": "lats_critic", "attempt_id": 1},
        )
        payload = self.client.parse_json(result.content)
        critiques = [LATSCritique.model_validate(item) for item in payload.get("critiques", [])]
        critique_by_id = {critique.candidate_id: critique for critique in critiques}
        filled: list[LATSCritique] = []
        for candidate in candidates:
            filled.append(
                critique_by_id.get(
                    candidate.candidate_id,
                    LATSCritique(
                        candidate_id=candidate.candidate_id,
                        value_score=0.0,
                        critique="No critique returned by model.",
                        supported=False,
                    ),
                )
            )
        return filled, result.to_stats()
