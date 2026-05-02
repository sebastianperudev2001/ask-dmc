from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class OllamaEmbeddingsProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def embed(self, text: str) -> list[float]:
        url = f"{self._base_url}/api/embeddings"
        payload = {"model": self._model, "prompt": text, "keep_alive": "10m"}
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise RuntimeError(f"Ollama error: {body['error']}")
        if "embedding" not in body:
            raise RuntimeError(f"Ollama returned unexpected response: {body}")
        return body["embedding"]
