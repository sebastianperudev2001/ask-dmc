from unittest.mock import MagicMock, patch

import pytest

from src.domain.entities import (
    ENV,
    IngestionConfig,
    IngestionError,
    IngestionReport,
    PDFResult,
)
from src.pipeline.orchestrator import IngestionOrchestrator, _course_name_from_path


def make_config(workers: int = 1) -> IngestionConfig:
    return IngestionConfig(
        env=ENV.LOCAL,
        vector_db_url="postgresql://test",
        local_knowledge_dir="knowledge_source",
        local_reports_dir="reports",
        keywords_model="gemma3:4b",
        ingestion_workers=workers,
    )


def make_providers(pdf_entries: list[str], pdf_bytes: bytes = b"fake") -> MagicMock:
    providers = MagicMock()
    providers.storage.list_brochures.return_value = pdf_entries
    providers.storage.get_object.return_value = pdf_bytes
    providers.embeddings.embed.return_value = [0.1] * 1536
    providers.llm.complete.return_value = '["kw1", "kw2"]'
    providers.connection_pool.getconn.return_value = MagicMock()
    return providers


class TestOrchestratorReportTotals:
    def test_total_pdfs_matches_entry_count(self):
        config = make_config()
        providers = make_providers(["a.pdf", "b.pdf", "c.pdf"])
        orch = IngestionOrchestrator(config, providers)

        with patch.object(orch, "_process_pdf", return_value=PDFResult("x", True, 5, 3)):
            with patch("src.pipeline.orchestrator.configure_logging"):
                report = orch.run()

        assert report.total_pdfs == 3

    def test_processed_plus_failed_equals_total(self):
        config = make_config()
        entries = ["a.pdf", "b.pdf", "c.pdf"]
        providers = make_providers(entries)
        orch = IngestionOrchestrator(config, providers)

        side_effects = [
            PDFResult("a", True, 3, 2),
            PDFResult("b", False, error=IngestionError("b", "parse", "err")),
            PDFResult("c", True, 4, 3),
        ]

        with patch.object(orch, "_process_pdf", side_effect=side_effects):
            with patch("src.pipeline.orchestrator.configure_logging"):
                report = orch.run()

        assert report.processed + report.failed == report.total_pdfs

    def test_errors_accumulated_from_failed_pdfs(self):
        config = make_config()
        providers = make_providers(["fail.pdf"])
        orch = IngestionOrchestrator(config, providers)
        err = IngestionError("fail", "parse", "boom")

        with patch.object(orch, "_process_pdf", return_value=PDFResult("fail", False, error=err)):
            with patch("src.pipeline.orchestrator.configure_logging"):
                report = orch.run()

        assert len(report.errors) == 1
        assert report.errors[0].course_name == "fail"

    def test_report_saved_after_run(self):
        config = make_config()
        providers = make_providers(["a.pdf"])
        orch = IngestionOrchestrator(config, providers)

        with patch.object(orch, "_process_pdf", return_value=PDFResult("a", True, 2, 1)):
            with patch("src.pipeline.orchestrator.configure_logging"):
                orch.run()

        providers.report_repo.save.assert_called_once()


class TestCourseNameFromPath:
    def test_strips_extension(self):
        assert _course_name_from_path("power-bi.pdf") == "power-bi"

    def test_handles_nested_path(self):
        assert _course_name_from_path("knowledge_source/diploma-da.pdf") == "diploma-da"
