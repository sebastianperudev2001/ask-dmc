from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingsProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        ...
