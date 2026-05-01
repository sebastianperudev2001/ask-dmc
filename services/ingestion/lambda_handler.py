import dataclasses
import json
from typing import Any

from src.config import load_config
from src.pipeline.orchestrator import IngestionOrchestrator
from src.pipeline.provider_factory import create_providers


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    config = load_config()
    providers = create_providers(config)
    try:
        report = IngestionOrchestrator(config, providers).run()
        return {
            "statusCode": 200,
            "body": json.dumps({
                "processed": report.processed,
                "failed": report.failed,
                "total_chunks_upserted": report.total_chunks_upserted,
                "duration_seconds": report.duration_seconds,
                "errors": [dataclasses.asdict(e) for e in report.errors],
            }),
        }
    finally:
        providers.close()
