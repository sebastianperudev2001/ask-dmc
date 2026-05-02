from __future__ import annotations

import requests


class OllamaLLMProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def complete(self, prompt: str, format: dict | None = None) -> str:
        url = f"{self._base_url}/api/generate"
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
        }
        if format is not None:
            payload["format"] = format
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["response"]
