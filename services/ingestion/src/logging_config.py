from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(reports_dir: str, timestamp: str) -> logging.Logger:
    logger = logging.getLogger("ingestion")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    Path(reports_dir).mkdir(parents=True, exist_ok=True)
    log_path = Path(reports_dir) / f"pipeline_{timestamp}.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger
