from __future__ import annotations

from .schemas import CandidateAnswer, JudgeResult, LATSCritique, QAExample, ReflectionEntry, RuntimeStats
from .utils import normalize_answer

FIRST_ATTEMPT_WRONG = {"hp2": "London", "hp4": "Atlantic Ocean", "hp6": "Red Sea", "hp8": "Andes"}
FAILURE_MODE_BY_QID = {
    "hp2": "incomplete_multi_hop",
    "hp4": "wrong_final_answer",
    "hp6": "entity_drift",
    "hp8": "entity_drift",
}


def _stats(base_tokens: int = 100, latency_ms: int = 25) -> RuntimeStats:
    return RuntimeStats(
        input_tokens=base_tokens // 2,
        output_tokens=base_tokens // 2,
        token_estimate=base_tokens,
        latency_ms=latency_ms,
        llm_call_count=1,
    )


class MockRuntime:
    mode = "mock"
    model = "mock"

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> tuple[str, RuntimeStats]:
        if example.qid not in FIRST_ATTEMPT_WRONG:
            return example.gold_answer, _stats(180, 40)
        if agent_type == "react":
            return FIRST_ATTEMPT_WRONG[example.qid], _stats(180, 40)
        if attempt_id == 1 and not reflection_memory:
            return FIRST_ATTEMPT_WRONG[example.qid], _stats(220, 55)
        return example.gold_answer, _stats(260, 60)

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
                _stats(90, 20),
            )
        if normalized_prediction == "london":
            reason = "The answer stopped at the birthplace city and never completed the second hop to the river."
            missing = ["Need to identify the river that flows through London."]
            mode = "incomplete_multi_hop"
        else:
            reason = "The final answer selected the wrong second-hop entity."
            missing = ["Need to ground the answer in the second paragraph."]
            mode = FAILURE_MODE_BY_QID.get(example.qid, "wrong_final_answer")
        return (
            JudgeResult(
                score=0,
                reason=reason,
                missing_evidence=missing,
                spurious_claims=[answer] if answer else [],
                normalized_gold=normalized_gold,
                normalized_prediction=normalized_prediction,
                confidence=0.9,
                failure_mode=mode,
            ),
            _stats(110, 25),
        )

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        judge: JudgeResult,
        wrong_answer: str,
    ) -> tuple[ReflectionEntry, RuntimeStats]:
        strategy = (
            "Do the second hop explicitly: birthplace city -> river through that city."
            if example.qid == "hp2"
            else "Verify the final entity against the second relevant paragraph before answering."
        )
        return (
            ReflectionEntry(
                attempt_id=attempt_id,
                failure_reason=judge.reason,
                lesson="A partial first-hop answer is not enough; the final answer must complete all hops.",
                next_strategy=strategy,
                evidence_to_check=[chunk.title for chunk in example.context[:2]],
                avoid=[f"Do not repeat: {wrong_answer}"] if wrong_answer else [],
                confidence=0.85,
            ),
            _stats(140, 30),
        )

    def lats_generate_candidates(
        self,
        example: QAExample,
        parent_answer: str | None = None,
        critique: str | None = None,
        branching_factor: int = 2,
    ) -> tuple[list[CandidateAnswer], RuntimeStats]:
        wrong = FIRST_ATTEMPT_WRONG.get(example.qid, "unknown")
        candidates = [
            CandidateAnswer(
                candidate_id="c1",
                answer=parent_answer or wrong,
                evidence_titles=[chunk.title for chunk in example.context[:1]],
                reasoning_summary="A plausible but incomplete route.",
            ),
            CandidateAnswer(
                candidate_id="c2",
                answer=example.gold_answer,
                evidence_titles=[chunk.title for chunk in example.context[:2]],
                reasoning_summary="A route that checks the bridge entity and final evidence.",
            ),
        ]
        if critique:
            candidates = [
                CandidateAnswer(
                    candidate_id="r1",
                    answer=example.gold_answer,
                    evidence_titles=[chunk.title for chunk in example.context[:2]],
                    reasoning_summary="Refined answer after critic feedback.",
                ),
                CandidateAnswer(
                    candidate_id="r2",
                    answer=wrong,
                    evidence_titles=[chunk.title for chunk in example.context[:1]],
                    reasoning_summary="Alternative retained for comparison.",
                ),
            ]
        return candidates[:branching_factor], _stats(240, 55)

    def lats_critic(
        self,
        example: QAExample,
        candidates: list[CandidateAnswer],
    ) -> tuple[list[LATSCritique], RuntimeStats]:
        critiques: list[LATSCritique] = []
        for candidate in candidates:
            supported = normalize_answer(candidate.answer) == normalize_answer(example.gold_answer)
            critiques.append(
                LATSCritique(
                    candidate_id=candidate.candidate_id,
                    value_score=0.95 if supported else 0.35,
                    critique="Completes all hops." if supported else "Likely incomplete or unsupported by the final evidence.",
                    missing_evidence=[] if supported else ["Need to verify the final answer against context."],
                    supported=supported,
                )
            )
        return critiques, _stats(170, 40)


actor_answer = MockRuntime().actor_answer
evaluator = MockRuntime().evaluator
reflector = MockRuntime().reflector
