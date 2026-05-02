from __future__ import annotations

import psycopg2
from pgvector.psycopg2 import register_vector

from src.domain.entities import EmbeddedChunk

UPSERT_SQL = """
INSERT INTO brochure_chunks (id, course_name, content, embedding, keywords)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    content   = EXCLUDED.content,
    embedding = EXCLUDED.embedding,
    keywords  = EXCLUDED.keywords;
"""


class PgVectorRepository:
    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        register_vector(conn)
        self._conn = conn

    def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        if not chunks:
            return
        with self._conn.cursor() as cur:
            for chunk in chunks:
                cur.execute(UPSERT_SQL, (
                    chunk.id,
                    chunk.course_name,
                    chunk.content,
                    chunk.embedding,
                    chunk.keywords,
                ))
        self._conn.commit()
