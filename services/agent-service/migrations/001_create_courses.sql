CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS courses (
    course_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    category        TEXT NOT NULL,
    curriculum      TEXT[] NOT NULL,
    price           NUMERIC(10, 2) NOT NULL CHECK (price > 0),
    duration_weeks  INTEGER NOT NULL CHECK (duration_weeks > 0),
    embedding       vector(1536)
);

-- PATTERN-07: HNSW — mejor balance recall/latencia que IVFFlat a la escala esperada
-- (decenas de cursos), sin requerir un paso de entrenamiento previo.
CREATE INDEX IF NOT EXISTS courses_embedding_idx
    ON courses USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- PATTERN-08: índices B-tree sobre las columnas de filtro duro (BR-01/BR-02).
CREATE INDEX IF NOT EXISTS courses_price_idx ON courses (price);
CREATE INDEX IF NOT EXISTS courses_duration_weeks_idx ON courses (duration_weeks);
