from __future__ import annotations

import psycopg2
import psycopg2.pool

from src.domain.entities import ENV, IngestionConfig
from src.infrastructure.embeddings.bedrock_embeddings import BedrockEmbeddingsProvider
from src.infrastructure.embeddings.ollama_embeddings import OllamaEmbeddingsProvider
from src.infrastructure.llm.bedrock_llm import BedrockLLMProvider
from src.infrastructure.llm.ollama_llm import OllamaLLMProvider
from src.infrastructure.reports.filesystem_report import FilesystemReportRepository
from src.infrastructure.reports.s3_report import S3ReportRepository
from src.infrastructure.storage.filesystem_storage import FilesystemStorageProvider
from src.infrastructure.storage.s3_storage import S3StorageProvider
from src.infrastructure.vector_db.pgvector_repository import PgVectorRepository
from src.ports.embeddings_provider import EmbeddingsProvider
from src.ports.llm_provider import LLMProvider
from src.ports.report_repository import ReportRepository
from src.ports.storage_provider import StorageProvider


class Providers:
    def __init__(
        self,
        storage: StorageProvider,
        embeddings: EmbeddingsProvider,
        llm: LLMProvider,
        report_repo: ReportRepository,
        connection_pool: psycopg2.pool.ThreadedConnectionPool,
    ) -> None:
        self.storage = storage
        self.embeddings = embeddings
        self.llm = llm
        self.report_repo = report_repo
        self.connection_pool = connection_pool

    def get_vector_db(self) -> PgVectorRepository:
        conn = self.connection_pool.getconn()
        return PgVectorRepository(conn)

    def release_conn(self, conn: psycopg2.extensions.connection) -> None:
        self.connection_pool.putconn(conn)

    def close(self) -> None:
        self.connection_pool.closeall()


def create_providers(config: IngestionConfig) -> Providers:
    pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=config.ingestion_workers,
        dsn=config.vector_db_url,
    )

    if config.env == ENV.LOCAL:
        storage: StorageProvider = FilesystemStorageProvider(config.local_knowledge_dir)
        embeddings: EmbeddingsProvider = OllamaEmbeddingsProvider(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
        )
        llm: LLMProvider = OllamaLLMProvider(
            base_url=config.ollama_base_url,
            model=config.keywords_model,
        )
        report_repo: ReportRepository = FilesystemReportRepository(config.local_reports_dir)
    else:
        storage = S3StorageProvider(
            bucket=config.s3_bucket,
            prefix=config.s3_prefix,
        )
        embeddings = BedrockEmbeddingsProvider(model_id=config.bedrock_embeddings_model)
        llm = BedrockLLMProvider(model_id=config.keywords_model)
        report_repo = S3ReportRepository(
            bucket=config.s3_bucket,
            prefix=config.s3_reports_prefix,
        )

    return Providers(
        storage=storage,
        embeddings=embeddings,
        llm=llm,
        report_repo=report_repo,
        connection_pool=pool,
    )
