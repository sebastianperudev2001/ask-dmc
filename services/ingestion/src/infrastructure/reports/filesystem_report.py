from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from src.domain.entities import IngestionReport


class FilesystemReportRepository:
    def __init__(self, reports_dir: str) -> None:
        self._dir = Path(reports_dir)

    def save(self, report: IngestionReport) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"report_{report.timestamp}.json"
        path.write_text(json.dumps(dataclasses.asdict(report), indent=2))
