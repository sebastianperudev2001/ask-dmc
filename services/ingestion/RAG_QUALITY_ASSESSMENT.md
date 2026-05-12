# RAG Quality Assessment — DMC Ingestion Pipeline

**Date**: 2026-05-03  
**Pipeline**: `services/ingestion/`  
**Embedding Model**: `nomic-embed-text` (768-dim, via Ollama)  
**Vector Store**: PostgreSQL + pgvector (`brochure_chunks` table)

---

## Summary

The retrieval pipeline has three compounding issues. Listed by expected impact:

| Priority | Issue                                               | File                                    | Effort |
| -------- | --------------------------------------------------- | --------------------------------------- | ------ |
| 1        | Missing `nomic-embed-text` asymmetric prefixes      | `embedding_generator.py`, `test_rag.py` | Low    |
| 2        | Character-based chunking breaks sentence boundaries | `embedding_generator.py`                | Medium |
| 3        | IVFFlat index under-probed at query time            | `test_rag.py`                           | Low    |
| 4        | No retrieval diagnostics — flying blind             | `test_rag.py`                           | Low    |

---

## Issue 1 — Missing Asymmetric Query Prefixes (Highest Impact)

`nomic-embed-text` is an asymmetric model: it expects different prefixes for documents vs. queries. Without them, cosine similarity scores degrade significantly.

**Current behavior** (`embedding_generator.py`):

```python
embedding = embeddings_provider.embed(chunk_text)  # raw text, no prefix
```

**Current behavior** (`test_rag.py`):

```python
question_embedding = embeddings_provider.embed(question)  # raw text, no prefix
```

**Fix — indexing** (`src/pipeline/embedding_generator.py`):

```python
embedding = embeddings_provider.embed(f"search_document: {chunk_text}")
```

**Fix — querying** (`scripts/test_rag.py`):

```python
question_embedding = embeddings_provider.embed(f"search_query: {question}")
```

> After this fix, re-run ingestion to recompute all stored embeddings, then re-test.

---

## Issue 2 — Character-Based Chunking (High Impact)

**Current parameters** (`src/pipeline/embedding_generator.py`):

```python
_MAX_CHARS = 2000
_OVERLAP = 200  # 10% overlap
```

The splitter cuts every 1,800 characters regardless of sentence or paragraph structure. This means:

- Sentences are truncated mid-way, breaking semantic meaning
- Overlap of 200 chars is too small to recover lost context across boundaries

**Verify the problem**:

```sql
SELECT id, LEFT(content, 400) FROM brochure_chunks LIMIT 20;
```

Look for chunks that start or end in the middle of a sentence.

**Recommended fix**: Replace character splitting with sentence-aware splitting using `nltk` or `spacy`, then group sentences up to the token limit.

```python
import nltk
nltk.download("punkt", quiet=True)

def _split_text(text: str, max_chars: int = 2000, overlap_sentences: int = 1) -> list[str]:
    sentences = nltk.sent_tokenize(text)
    chunks, current, current_len = [], [], 0
    for sent in sentences:
        if current_len + len(sent) > max_chars and current:
            chunks.append(" ".join(current))
            current = current[-overlap_sentences:]  # carry over last N sentences
            current_len = sum(len(s) for s in current)
        current.append(sent)
        current_len += len(sent)
    if current:
        chunks.append(" ".join(current))
    return chunks
```

---

## Issue 3 — IVFFlat Under-Probed at Query Time (Medium Impact)

**Schema** (`migrations/001_create_brochure_chunks.sql`):

```sql
CREATE INDEX brochure_chunks_embedding_idx
    ON brochure_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
```

The index uses 10 centroid lists. The default `nprobe` (number of lists searched at query time) is **1**, meaning only 10% of the index is scanned per query. This trades recall for speed — fine at scale, harmful for small datasets where exhaustive search is cheap.

**Fix** — set `nprobe` before each query in `test_rag.py`:

```python
with conn.cursor() as cur:
    cur.execute("SET ivfflat.probes = 5;")
    cur.execute("""
        SELECT course_name, content, embedding <=> %s::vector AS distance
        FROM brochure_chunks
        ORDER BY distance ASC
        LIMIT 10;
    """, (question_embedding,))
```

For a small dataset (< 10k chunks), switching the index to `hnsw` eliminates this tradeoff entirely:

```sql
CREATE INDEX brochure_chunks_embedding_idx
    ON brochure_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

---

## Issue 4 — No Retrieval Diagnostics

The test script returns results but doesn't surface enough signal to diagnose poor retrieval.

**Add to `scripts/test_rag.py` after fetching results**:

```python
print(f"\n--- Retrieved Sources (top {len(results)}) ---")
for idx, (course_name, content, distance) in enumerate(results, 1):
    print(f"{idx}. dist={distance:.4f} | {course_name}")
    print(f"   {content[:120].replace(chr(10), ' ')}...")
```

**Interpreting distances** (cosine distance, lower = more similar):

| Distance    | Interpretation                           |
| ----------- | ---------------------------------------- |
| < 0.10      | Near-exact match                         |
| 0.10 – 0.25 | Strong semantic match                    |
| 0.25 – 0.40 | Weak match — retrieval may be unreliable |
| > 0.40      | No meaningful match found                |

If all distances are > 0.30, the embedding alignment is the root cause (see Issue 1).

---

## Diagnostic Checklist

Run these in order to isolate the failure layer:

```sql
-- 1. Check chunk count and coverage
SELECT COUNT(*) AS total_chunks, COUNT(DISTINCT course_name) AS courses
FROM brochure_chunks;

-- 2. Inspect chunk boundaries
SELECT id, LEFT(content, 400) AS preview
FROM brochure_chunks
ORDER BY id
LIMIT 20;

-- 3. Check for null embeddings
SELECT COUNT(*) FROM brochure_chunks WHERE embedding IS NULL;
```

Then in `test_rag.py`, test the same question with and without the `search_query:` prefix and compare distances.

---

## Current Architecture (Reference)

```
PDF
 └── pdfplumber → raw text
      └── section parser (12 section types)
           └── _split_text() [character-based, 2000 chars / 200 overlap]
                └── OllamaEmbeddingsProvider.embed() [nomic-embed-text, 768-dim]
                     └── pgvector upsert → brochure_chunks
                          └── cosine distance query → top 10 chunks → Ollama LLM
```

**Section types parsed**: `PRESENTACION`, `SOBRE_ESTE_DIPLOMA`, `COMO_IMPULSAMOS`, `POR_QUE_ESTUDIAR`, `OBJETIVO`, `A_QUIEN_DIRIGIDO`, `REQUISITOS`, `HERRAMIENTAS`, `MALLA_CURRICULAR`, `PROPUESTA_CAPACITACION`, `CERTIFICACION`, `DOCENTES`

---

## Recommended Fix Order

1. **Add asymmetric prefixes** — 30 min, re-run ingestion, re-test. Highest ROI.
2. **Add distance logging** — 10 min, gives you data to validate fix #1.
3. **Set `ivfflat.probes = 5`** — 5 min, quick win at query time.
4. **Switch to sentence-aware chunking** — 2-3 hours, structural improvement.
5. **Switch IVFFlat → HNSW** — 30 min, eliminates recall/speed tradeoff for current dataset size.
