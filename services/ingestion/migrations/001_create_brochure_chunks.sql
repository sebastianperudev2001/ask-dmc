CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS brochure_chunks (
    id           TEXT PRIMARY KEY,
    course_name  TEXT NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(768),
    keywords     TEXT[]
);

CREATE INDEX IF NOT EXISTS brochure_chunks_embedding_idx
    ON brochure_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
