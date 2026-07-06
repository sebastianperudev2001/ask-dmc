"""Manual, standalone check for FoundryPersistentAgentClient — isolates the agent
integration from the rest of the stack (no Postgres, no WebSocket server needed).

Requires a real Azure AI Foundry project with a gpt-5.4-nano deployment already
provisioned — there is no local emulator for Foundry Agent Service, this script talks
to the real cloud endpoint.

Usage:
    az login
    export FOUNDRY_PROJECT_ENDPOINT=https://<your-foundry-project>.services.ai.azure.com/
    export FOUNDRY_AGENT_MODEL_DEPLOYMENT=gpt-5.4-nano   # optional, this is the default
    python -m scripts.manual_agent_check
"""
from __future__ import annotations

import asyncio
import os
from decimal import Decimal

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# This script intentionally does NOT go through src.config.load_config() (which requires
# DATABASE_URL) — it isolates the agent integration and needs nothing else. Load .env
# directly instead, same as config.py does for the rest of the app.
load_dotenv()

from src.adapters.foundry_agent_client import FoundryPersistentAgentClient
from src.adapters.retry_policy import RetryPolicy
from src.domain.models import Course, RecommendationBranch, RecommendationCandidate

FAKE_CANDIDATES = [
    RecommendationCandidate(
        course=Course(
            course_id="diploma-data-scientist",
            name="Diploma en Data Science",
            description="Formación profunda en ciencia de datos: estadística, machine learning y despliegue de modelos.",
            category="Data Science",
            curriculum=("Python", "Estadística Inferencial", "Machine Learning", "Deep Learning", "MLOps"),
            price=Decimal("3800.00"),
            duration_weeks=16,
        ),
        similarity_score=0.87,
    ),
]


async def main() -> None:
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]  # KeyError if unset — fail fast
    model_deployment = os.environ.get("FOUNDRY_AGENT_MODEL_DEPLOYMENT", "gpt-5.4-nano")

    credential = DefaultAzureCredential()
    retry_policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.5)
    agent_client = FoundryPersistentAgentClient(
        project_endpoint=project_endpoint,
        model_deployment=model_deployment,
        credential=credential,
        retry_policy=retry_policy,
    )

    print("--- streaming response ---")
    async for delta in agent_client.stream_recommendation(
        FAKE_CANDIDATES,
        profile_text="Data Engineer en Yape, quiero profundizar en Data Science",
        branch=RecommendationBranch.EXACT_MATCH,
    ):
        print(delta, end="", flush=True)
    print("\n--- done ---")


if __name__ == "__main__":
    asyncio.run(main())
