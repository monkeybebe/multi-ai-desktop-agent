"""Consensus / Decision Engine - compares agent responses and selects the best."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.agents.base import AgentResponse

logger = logging.getLogger(__name__)


@dataclass
class ConsensusResult:
    """Result of the consensus engine evaluation."""

    selected_answer: str
    selected_agent: str
    confidence: float
    agreement_score: float  # 0.0 to 1.0 - how much agents agree
    reasoning_summary: str
    all_responses: list[AgentResponse] = field(default_factory=list)
    vote_details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "selected_answer": self.selected_answer,
            "selected_agent": self.selected_agent,
            "confidence": self.confidence,
            "agreement_score": self.agreement_score,
            "reasoning_summary": self.reasoning_summary,
            "vote_details": self.vote_details,
            "responses": [r.to_dict() for r in self.all_responses],
        }


class DecisionEngine:
    """Evaluates responses from multiple agents and selects the best answer."""

    def __init__(self):
        self.similarity_threshold = 0.6  # answers above this are "similar"
        self.min_confidence = 0.3  # minimum confidence to consider

    def evaluate(self, responses: list[AgentResponse]) -> ConsensusResult:
        """Evaluate all agent responses and determine the best answer.

        Uses a multi-factor scoring approach:
        1. Self-reported confidence from each agent
        2. Agreement between agents (similar answers get boosted)
        3. Reasoning quality (length and coherence as proxy)
        """
        # Filter out errored responses
        valid_responses = [r for r in responses if not r.error and r.answer]

        if not valid_responses:
            error_msgs = [r.error or "No answer" for r in responses]
            return ConsensusResult(
                selected_answer="Unable to determine an answer.",
                selected_agent="None",
                confidence=0.0,
                agreement_score=0.0,
                reasoning_summary="All agents failed: " + "; ".join(error_msgs),
                all_responses=responses,
            )

        if len(valid_responses) == 1:
            r = valid_responses[0]
            return ConsensusResult(
                selected_answer=r.answer,
                selected_agent=r.agent_name,
                confidence=r.confidence,
                agreement_score=1.0,
                reasoning_summary=f"Only one agent responded: {r.agent_name}",
                all_responses=responses,
            )

        # Calculate pairwise similarity between answers
        similarity_matrix = self._compute_similarity_matrix(valid_responses)

        # Score each response
        scores: dict[int, float] = {}
        vote_details: dict[str, dict] = {}

        for i, resp in enumerate(valid_responses):
            # Factor 1: Self-reported confidence (weight: 0.3)
            confidence_score = resp.confidence * 0.3

            # Factor 2: Agreement with other agents (weight: 0.5)
            agreement_scores = [
                similarity_matrix[i][j]
                for j in range(len(valid_responses))
                if i != j
            ]
            avg_agreement = sum(agreement_scores) / len(agreement_scores) if agreement_scores else 0
            agreement_score = avg_agreement * 0.5

            # Factor 3: Reasoning quality proxy (weight: 0.2)
            reasoning_len = len(resp.reasoning)
            # Normalize: 100-2000 chars is good range
            reasoning_quality = min(1.0, max(0.1, reasoning_len / 1000))
            reasoning_score = reasoning_quality * 0.2

            total_score = confidence_score + agreement_score + reasoning_score
            scores[i] = total_score

            vote_details[resp.agent_name] = {
                "answer_preview": resp.answer[:200],
                "confidence": resp.confidence,
                "agreement_with_others": round(avg_agreement, 3),
                "reasoning_quality": round(reasoning_quality, 3),
                "total_score": round(total_score, 3),
                "processing_time": round(resp.processing_time, 2),
            }

        # Select the best response
        best_idx = max(scores, key=lambda k: scores[k])
        best_response = valid_responses[best_idx]

        # Calculate overall agreement score
        all_agreements = []
        for i in range(len(valid_responses)):
            for j in range(i + 1, len(valid_responses)):
                all_agreements.append(similarity_matrix[i][j])
        overall_agreement = (
            sum(all_agreements) / len(all_agreements) if all_agreements else 0.0
        )

        # Build reasoning summary
        reasoning_parts = []
        for resp in valid_responses:
            detail = vote_details[resp.agent_name]
            reasoning_parts.append(
                f"{resp.agent_name}: score={detail['total_score']}, "
                f"confidence={resp.confidence}, "
                f"agreement={detail['agreement_with_others']}"
            )

        reasoning_summary = (
            f"Selected {best_response.agent_name} (score: {scores[best_idx]:.3f}). "
            f"Overall agreement: {overall_agreement:.2f}. "
            f"Breakdown: {'; '.join(reasoning_parts)}"
        )

        return ConsensusResult(
            selected_answer=best_response.answer,
            selected_agent=best_response.agent_name,
            confidence=scores[best_idx],
            agreement_score=overall_agreement,
            reasoning_summary=reasoning_summary,
            all_responses=responses,
            vote_details=vote_details,
        )

    def _compute_similarity_matrix(
        self, responses: list[AgentResponse]
    ) -> list[list[float]]:
        """Compute pairwise text similarity between all answers."""
        n = len(responses)
        matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            matrix[i][i] = 1.0
            for j in range(i + 1, n):
                sim = self._text_similarity(
                    responses[i].answer, responses[j].answer
                )
                matrix[i][j] = sim
                matrix[j][i] = sim

        return matrix

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """Compute similarity between two text strings."""
        if not text1 or not text2:
            return 0.0

        # Normalize texts
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()

        if t1 == t2:
            return 1.0

        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, t1, t2).ratio()
