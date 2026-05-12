CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS brochure_chunks (
    id           TEXT PRIMARY KEY,
    course_name  TEXT NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(1024),
    keywords     TEXT[]
);

CREATE INDEX IF NOT EXISTS brochure_chunks_embedding_idx
    ON brochure_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
