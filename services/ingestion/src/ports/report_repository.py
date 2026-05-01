from typing import Protocol, runtime_checkable

from src.domain.entities import IngestionReport


@runtime_checkable
class ReportRepository(Protocol):
    def save(self, report: IngestionReport) -> None:
        ...
