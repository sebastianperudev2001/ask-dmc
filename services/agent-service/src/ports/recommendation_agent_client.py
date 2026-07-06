from __future__ import annotations

from typing import AsyncIterator, Protocol

from src.domain.models import RecommendationBranch, RecommendationCandidate


class RecommendationAgentClient(Protocol):
    """Port for the Azure AI Foundry Persistent Agent (gpt-5.4-nano) that composes the
    final recommendation text (step 8). Only ever receives structured candidate data —
    BR-07: the agent must not reference anything outside `candidates`."""

    def stream_recommendation(
        self,
        candidates: list[RecommendationCandidate],
        profile_text: str,
        branch: RecommendationBranch,
    ) -> AsyncIterator[str]:
        """Yield text deltas (AgentRunResponseUpdate.text) as the agent composes its
        response. See business-logic-model.md Section 3.1 — deltas, not tokens."""
        ...
