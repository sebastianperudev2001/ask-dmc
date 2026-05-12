from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ApiConfig:
    vector_db_url: str
    ollama_base_url: str
    ollama_embeddings_model: str
    ollama_llm_model: str
    rag_top_k: int


def load_config() -> ApiConfig:
    vector_db_url = os.environ.get("VECTOR_DB_URL", "")
    if not vector_db_url:
        raise ValueError("VECTOR_DB_URL environment variable is required")

    return ApiConfig(
        vector_db_url=vector_db_url,
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_embeddings_model=os.environ.get("OLLAMA_EMBEDDINGS_MODEL", "nomic-embed-text"),
        ollama_llm_model=os.environ.get("OLLAMA_LLM_MODEL", "gemma4"),
        rag_top_k=int(os.environ.get("RAG_TOP_K", "5")),
    )
