from __future__ import annotations

from pathlib import Path


class FilesystemStorageProvider:
    def __init__(self, knowledge_dir: str) -> None:
        self._dir = Path(knowledge_dir)

    def list_brochures(self) -> list[str]:
        return [str(p) for p in sorted(self._dir.glob("*.pdf"))]

    def get_object(self, path: str) -> bytes:
        return Path(path).read_bytes()
