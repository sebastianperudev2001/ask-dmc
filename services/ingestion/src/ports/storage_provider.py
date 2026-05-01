from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageProvider(Protocol):
    def list_brochures(self) -> list[str]:
        ...

    def get_object(self, path: str) -> bytes:
        ...
