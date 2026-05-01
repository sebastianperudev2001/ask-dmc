from __future__ import annotations

import time

import requests

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0


class OllamaEmbeddingsProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def embed(self, text: str) -> list[float]:
        url = f"{self._base_url}/api/embeddings"
        payload = {"model": self._model, "prompt": text}
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = requests.post(url, json=payload, timeout=60)
                response.raise_for_status()
                return response.json()["embedding"]
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)))
        raise last_exc  # type: ignore[misc]
