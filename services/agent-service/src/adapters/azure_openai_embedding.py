"""AzureOpenAIEmbeddingService — text-embedding-3-small (1536 dims), used both for the
catalog seed (scripts/seed_catalog.py) and per-request ProfileQuery (chat_agent_client.py).
Wrapped in RetryPolicy (PATTERN-01); raises EmbeddingServiceUnavailableError once retries
are exhausted (mapped to the `embedding_service_unavailable` WS error)."""
from __future__ import annotations

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from src.adapters.retry_policy import RetryPolicy
from src.domain.errors import EmbeddingServiceUnavailableError

_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureOpenAIEmbeddingService:
    def __init__(
        self,
        endpoint: str,
        deployment: str,
        credential: DefaultAzureCredential,
        retry_policy: RetryPolicy,
    ) -> None:
        token_provider = get_bearer_token_provider(credential, _COGNITIVE_SERVICES_SCOPE)
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        )
        self._deployment = deployment
        self._retry_policy = retry_policy

    async def embed(self, text: str) -> tuple[float, ...]:
        async def _call() -> tuple[float, ...]:
            response = await self._client.embeddings.create(input=text, model=self._deployment)
            return tuple(response.data[0].embedding)

        try:
            return await self._retry_policy.run(_call)
        except Exception as exc:
            raise EmbeddingServiceUnavailableError(str(exc)) from exc
