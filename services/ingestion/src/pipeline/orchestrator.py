from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from src.domain.entities import (
    IngestionConfig,
    IngestionError,
    IngestionReport,
    PDFResult,
)
from src.logging_config import configure_logging
from src.pipeline.embedding_generator import EmbeddingGenerator
from src.pipeline.keywords_extractor import KeywordsExtractor
from src.pipeline.pdf_parser import PDFParser
from src.pipeline.provider_factory import Providers

logger = logging.getLogger("ingestion")


def _course_name_from_path(path: str) -> str:
    return Path(path).stem


class IngestionOrchestrator:
    def __init__(self, config: IngestionConfig, providers: Providers) -> None:
        self._config = config
        self._providers = providers
        self._parser = PDFParser()
        self._keywords_extractor = KeywordsExtractor(providers.llm)
        self._embedding_generator = EmbeddingGenerator(providers.embeddings)

    def run(self) -> IngestionReport:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        configure_logging(self._config.local_reports_dir, timestamp)

        report = IngestionReport(
            env=self._config.env,
            timestamp=timestamp,
        )

        entries = self._providers.storage.list_brochures()
        report.total_pdfs = len(entries)
        logger.info("Starting ingestion: %d PDFs found", len(entries))

        start = time.monotonic()
        results = self._process_parallel(entries)

        for result in results:
            if result.success:
                report.processed += 1
                report.total_chunks_upserted += result.chunks_upserted
                report.total_sections_extracted += result.sections_extracted
            else:
                report.failed += 1
                if result.error:
                    report.errors.append(result.error)

        report.duration_seconds = round(time.monotonic() - start, 2)
        logger.info(
            "Ingestion complete: %d processed, %d failed, %.2fs",
            report.processed,
            report.failed,
            report.duration_seconds,
        )

        self._providers.report_repo.save(report)
        return report

    def _process_parallel(self, entries: list[str]) -> list[PDFResult]:
        workers = self._config.ingestion_workers
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._process_pdf, entry): entry for entry in entries}
            return [future.result() for future in as_completed(futures)]

    def _process_pdf(self, entry: str) -> PDFResult:
        course_name = _course_name_from_path(entry)
        logger.info("[%s] Processing PDF", course_name)
        conn = None
        try:
            pdf_bytes = self._providers.storage.get_object(entry)

            sections = self._parser.parse(pdf_bytes, course_name)
            present_sections = [s for s in sections if s.present and s.content]

            present_sections = self._keywords_extractor.extract_keywords(present_sections)
            chunks = self._embedding_generator.generate(present_sections)

            conn = self._providers.connection_pool.getconn()
            from src.infrastructure.vector_db.pgvector_repository import PgVectorRepository
            vector_db = PgVectorRepository(conn)
            vector_db.upsert(chunks)

            logger.info("[%s] Done: %d chunks upserted", course_name, len(chunks))
            return PDFResult(
                course_name=course_name,
                success=True,
                chunks_upserted=len(chunks),
                sections_extracted=len(present_sections),
            )
        except Exception as exc:
            logger.error("[%s] Failed: %s", course_name, exc)
            step = _detect_step(exc)
            return PDFResult(
                course_name=course_name,
                success=False,
                error=IngestionError(
                    course_name=course_name,
                    step=step,
                    message=str(exc),
                ),
            )
        finally:
            if conn is not None:
                self._providers.connection_pool.putconn(conn)


def _detect_step(exc: Exception) -> str:
    msg = str(exc).lower()
    if "parse" in msg or "pdf" in msg:
        return "parse"
    if "keyword" in msg or "llm" in msg:
        return "keywords"
    if "embed" in msg:
        return "embedding"
    if "upsert" in msg or "insert" in msg or "pg" in msg:
        return "upsert"
    return "unknown"
