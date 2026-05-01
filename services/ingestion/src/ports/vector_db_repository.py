from typing import Protocol, runtime_checkable

from src.domain.entities import EmbeddedChunk


@runtime_checkable
class VectorDBRepository(Protocol):
    def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        ...
