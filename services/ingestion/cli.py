#!/usr/bin/env python3
import sys

from src.config import load_config
from src.pipeline.orchestrator import IngestionOrchestrator
from src.pipeline.provider_factory import create_providers


def main() -> int:
    config = load_config()
    providers = create_providers(config)
    try:
        report = IngestionOrchestrator(config, providers).run()
        return 0 if report.failed == 0 else 1
    finally:
        providers.close()


if __name__ == "__main__":
    sys.exit(main())
