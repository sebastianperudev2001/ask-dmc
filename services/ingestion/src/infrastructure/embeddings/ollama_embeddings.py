import requests


class OllamaEmbeddingsProvider:
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def embed(self, text: str) -> list[float]:
        url = f"{self._base_url}/api/embeddings"
        payload = {"model": self._model, "prompt": text}
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["embedding"]
