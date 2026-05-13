# ask-dmc

AI-powered sales agent for [DMC Institute](https://dmc.pe). The agent qualifies leads conversationally, recommends courses from a RAG-indexed PDF knowledge base, and generates Mercado Pago payment links — all within an embeddable chat widget backed by a FastAPI + pgvector stack.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       ask-dmc                           │
│                                                         │
│  apps/                                                  │
│  └── chat/          Next.js 15 — chat widget + admin    │
│                                                         │
│  services/                                              │
│  ├── api/           FastAPI — RAG query endpoint        │
│  └── ingestion/     PDF ingestion pipeline              │
└─────────────────────────────────────────────────────────┘

Request flow:
  Browser → Next.js /api/ask → FastAPI /ask
                                  ├── Ollama embeddings
                                  ├── pgvector similarity search
                                  └── Ollama LLM (streaming)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS 4 |
| API backend | FastAPI, Uvicorn |
| Vector store | PostgreSQL 16 + pgvector (Docker) |
| Embeddings | Ollama `Multilingual-E5-Large-Instruct` (local) / AWS Bedrock Titan (prod) |
| LLM | Ollama `gemma4` (local) / Claude via Bedrock (prod) |
| Knowledge base | PDF brochures parsed and chunked by the ingestion service |

---

## Prerequisites

| Tool | Version |
|---|---|
| Node.js | >= 18 |
| Python | >= 3.11 |
| Docker + Docker Compose | any recent version |
| Ollama | >= 0.3 |

Install and pull the required Ollama models:

```bash
ollama pull Multilingual-E5-Large-Instruct
ollama pull gemma4
```

---

## Repository layout

```
ask-dmc/
├── apps/
│   └── chat/                   # Next.js app (widget + backoffice)
│       ├── app/
│       │   ├── api/ask/        # Proxy route to FastAPI
│       │   ├── layout.tsx
│       │   └── page.tsx
│       ├── components/         # React UI components
│       ├── hooks/              # useChat, useDarkMode
│       ├── lib/                # API client
│       ├── types/
│       └── package.json
│
├── services/
│   ├── api/                    # FastAPI RAG backend
│   │   ├── main.py
│   │   ├── src/config.py
│   │   ├── requirements.txt
│   │   └── .env.example
│   │
│   └── ingestion/              # PDF ingestion pipeline
│       ├── cli.py              # Entry point
│       ├── src/
│       │   ├── pipeline/       # PDF parser, embeddings, orchestrator
│       │   ├── infrastructure/ # pgvector, S3, Ollama/Bedrock adapters
│       │   └── ports/          # Abstractions (embeddings, LLM, storage)
│       ├── migrations/         # SQL schema (auto-applied by Docker)
│       ├── docker-compose.yml  # pgvector database
│       ├── requirements.txt
│       └── .env.example
│
└── knowledge_source/           # Place PDF brochures here
```

---

## Local setup

### 1. Start the vector database

```bash
cd services/ingestion
docker compose up -d
```

This starts a PostgreSQL container with the pgvector extension on port **5433**. The migration in `migrations/001_create_brochure_chunks.sql` runs automatically on first start, creating the `brochure_chunks` table and HNSW index.

### 2. Run the ingestion pipeline

The pipeline reads PDFs from `knowledge_source/`, chunks and embeds them, then stores vectors in pgvector.

```bash
cd services/ingestion

# Copy and configure environment
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Run the pipeline
python cli.py
```

**Ingestion `.env` reference:**

```dotenv
INGESTION_ENV=local          # local | production
INGESTION_WORKERS=4

# PostgreSQL
VECTOR_DB_URL=postgresql://ask_dmc:ask_dmc@localhost:5433/ask_dmc

# Ollama (local mode)
LOCAL_KNOWLEDGE_DIR=knowledge_source
LOCAL_REPORTS_DIR=reports
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDINGS_MODEL=Multilingual-E5-Large-Instruct
KEYWORDS_MODEL=gemma3:4b
```

Re-run the pipeline whenever new PDFs are added. To wipe and re-index from scratch, the migration `002_truncate_brochure_chunks.sql` truncates the table.

### 3. Start the FastAPI backend

```bash
cd services/api

# Copy and configure environment
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Start the server (reload for development)
uvicorn main:app --reload --port 8000
```

**API `.env` reference:**

```dotenv
VECTOR_DB_URL=postgresql://ask_dmc:ask_dmc@localhost:5433/ask_dmc
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDINGS_MODEL=Multilingual-E5-Large-Instruct
OLLAMA_LLM_MODEL=gemma4
RAG_TOP_K=5
```

Verify the API is healthy:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### 4. Start the Next.js frontend

```bash
cd apps/chat

# Create the environment file
echo "API_URL=http://localhost:8000" > .env.local

# Install dependencies
npm install

# Start the dev server
npm run dev
```

**Chat `.env.local` reference:**

```dotenv
API_URL=http://localhost:8000
```

The app is available at [http://localhost:3000](http://localhost:3000).

---

## Environment variables summary

| Service | Variable | Description | Default |
|---|---|---|---|
| `apps/chat` | `API_URL` | FastAPI base URL | — |
| `services/api` | `VECTOR_DB_URL` | PostgreSQL connection string | — |
| `services/api` | `OLLAMA_BASE_URL` | Ollama base URL | `http://localhost:11434` |
| `services/api` | `OLLAMA_EMBEDDINGS_MODEL` | Embeddings model name | `Multilingual-E5-Large-Instruct` |
| `services/api` | `OLLAMA_LLM_MODEL` | LLM model name | `gemma4` |
| `services/api` | `RAG_TOP_K` | Number of chunks retrieved per query | `5` |
| `services/ingestion` | `INGESTION_ENV` | Runtime environment (`local`/`production`) | `local` |
| `services/ingestion` | `INGESTION_WORKERS` | Parallel ingestion workers | `4` |
| `services/ingestion` | `VECTOR_DB_URL` | PostgreSQL connection string | — |
| `services/ingestion` | `LOCAL_KNOWLEDGE_DIR` | Directory containing source PDFs | `knowledge_source` |
| `services/ingestion` | `OLLAMA_BASE_URL` | Ollama base URL | `http://localhost:11434` |
| `services/ingestion` | `OLLAMA_EMBEDDINGS_MODEL` | Embeddings model name | `Multilingual-E5-Large-Instruct` |
| `services/ingestion` | `KEYWORDS_MODEL` | Model used for keyword extraction | `gemma3:4b` |

---

## API reference

### `POST /ask`

Accepts a question, retrieves the top-K relevant chunks from pgvector, and streams the LLM response.

**Request body:**
```json
{ "question": "¿Cuánto cuesta el diploma de Data Scientist?" }
```

**Response:** `text/plain` streamed token by token.

**Response headers:**
- `X-Sources` — JSON array of the retrieved chunks used as context:
  ```json
  [{"course": "...", "section": "...", "distance": 0.1234}]
  ```

### `GET /health`

Returns `{"status": "ok"}` when the service and database connection are healthy.

---

## Running tests

**Frontend (Vitest):**
```bash
cd apps/chat
npm test
```

**Ingestion pipeline (pytest):**
```bash
cd services/ingestion
pip install -r requirements-dev.txt
pytest
```

---

## Production notes

Set `INGESTION_ENV=production` to switch the ingestion pipeline to AWS adapters:

| Variable | Description |
|---|---|
| `S3_BUCKET` | S3 bucket containing PDF brochures |
| `S3_BROCHURES_PREFIX` | Key prefix for brochure PDFs |
| `S3_REPORTS_PREFIX` | Key prefix for ingestion reports |
| `BEDROCK_EMBEDDINGS_MODEL` | Bedrock model ID (e.g. `amazon.titan-embed-text-v2:0`) |
| `KEYWORDS_MODEL` | Bedrock model for keyword extraction (e.g. `claude-haiku-4-5`) |

AWS credentials must be available in the environment (IAM role, `AWS_PROFILE`, or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`).
