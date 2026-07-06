"""FoundryPersistentAgentClient — invokes the Azure AI Foundry Persistent Agent
(gpt-5.4-nano) via the Microsoft Agent Framework Python SDK. Only composes text (step 8)
from structured `candidates` data — BR-07: the agent must never reference anything
outside that list. No tool-calling in this increment, so the stream is expected to
contain only text deltas (business-logic-model.md Section 3.1).

Verified against the installed SDK (agent-framework-foundry) in this session:
- `agent_framework.foundry.FoundryChatClient` (not `agent_framework.azure.AzureAIAgentsProvider`
  — that import path does not exist in the shipped package; `agent-framework-foundry` depends
  on `azure-ai-projects`, not `azure-ai-agents`).
- `agent_framework.Agent(client=..., name=..., instructions=...)`.
- `Agent.run(messages, stream=True)` is a plain (non-async) call that returns a
  `ResponseStream` directly — no `await` before the `async for`. Network I/O only starts
  once the stream is iterated, which is why retry wraps fetching the first update, not
  the `run(...)` call itself.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from src.adapters.retry_policy import RetryPolicy
from src.domain.errors import AgentUnavailableError
from src.domain.models import RecommendationBranch, RecommendationCandidate

_AGENT_NAME = "dmc-course-recommender"
_AGENT_INSTRUCTIONS = (
    "Eres el asistente de recomendación de programas de DMC Institute. "
    "Recomienda basándote UNICAMENTE en los programas listados en 'candidates' — "
    "nunca inventes precios, fechas, descuentos ni programas fuera de esa lista. "
    "Si branch es 'relaxed_match', menciona con transparencia que el programa está "
    "ligeramente fuera del presupuesto/duración originales. Si branch es 'full_catalog', "
    "deja claro que no hubo un match exacto y que estás mostrando todas las opciones "
    "disponibles, ordenadas por afinidad con el perfil."
)


def _build_prompt(
    candidates: list[RecommendationCandidate], profile_text: str, branch: RecommendationBranch
) -> str:
    candidates_payload = [
        {
            "course_id": c.course.course_id,
            "name": c.course.name,
            "description": c.course.description,
            "curriculum": list(c.course.curriculum),
            "price": str(c.course.price),
            "duration_weeks": c.course.duration_weeks,
            "similarity_score": c.similarity_score,
            "filters_relaxed": list(c.filters_relaxed),
        }
        for c in candidates
    ]
    return json.dumps(
        {"profile": profile_text, "branch": branch.value, "candidates": candidates_payload},
        ensure_ascii=False,
    )


class FoundryPersistentAgentClient:
    def __init__(
        self,
        project_endpoint: str,
        model_deployment: str,
        credential: DefaultAzureCredential,
        retry_policy: RetryPolicy,
    ) -> None:
        client = FoundryChatClient(
            project_endpoint=project_endpoint, model=model_deployment, credential=credential
        )
        self._agent = Agent(client=client, name=_AGENT_NAME, instructions=_AGENT_INSTRUCTIONS)
        self._retry_policy = retry_policy

    async def stream_recommendation(
        self,
        candidates: list[RecommendationCandidate],
        profile_text: str,
        branch: RecommendationBranch,
    ) -> AsyncIterator[str]:
        prompt = _build_prompt(candidates, profile_text, branch)

        async def _start() -> tuple:
            stream = self._agent.run(prompt, stream=True)
            first_update = await stream.__anext__()
            return stream, first_update

        try:
            stream, first_update = await self._retry_policy.run(_start)
        except Exception as exc:
            raise AgentUnavailableError(str(exc)) from exc

        if first_update.text:
            yield first_update.text
        try:
            async for update in stream:
                if update.text:
                    yield update.text
        except Exception as exc:
            # Stream failed mid-way — not retried (NFR Design: retry only covers the
            # initial invocation), surfaces as agent_unavailable like any other failure.
            raise AgentUnavailableError(str(exc)) from exc
