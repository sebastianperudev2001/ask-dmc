# Build Instructions — ingestion-pipeline

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python --version` |
| Docker Desktop | Latest | Required for pgvector |
| Ollama | Latest | Required for LOCAL env embeddings + keywords |
| pip | Latest | `pip install --upgrade pip` |

---

## Build Steps

### 1. Navigate to service directory

```bash
cd services/ingestion
```

### 2. Create and activate virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
# Runtime only
pip install -r requirements.txt

# Runtime + dev/test tools
pip install -r requirements-dev.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your local values (VECTOR_DB_URL, OLLAMA models, etc.)
```

### 5. Start PostgreSQL with pgvector (Docker)

```bash
docker compose up -d
# Verify: docker compose ps  → should show "healthy" or "running"
# The migrations/001_create_brochure_chunks.sql runs automatically on first start
```

### 6. Pull Ollama models (LOCAL env only)

```bash
ollama pull nomic-embed-text   # embeddings model
ollama pull gemma3:4b          # keywords model
```

### 7. Verify build

```bash
# Syntax check all source files
PYTHONPATH=. python -m py_compile src/domain/entities.py
PYTHONPATH=. python -m py_compile src/pipeline/orchestrator.py
PYTHONPATH=. python -m py_compile cli.py
echo "Build OK"
```

---

## Expected Output

A successful setup produces:
- Virtual environment in `.venv/`
- Installed packages matching `requirements-dev.txt`
- PostgreSQL container running on `localhost:5432` with `brochure_chunks` table created
- Ollama serving on `http://localhost:11434`

---

## Troubleshooting

### `psycopg2` install fails on macOS
```bash
pip install psycopg2-binary==2.9.9   # use binary wheel, avoids libpq dep
```

### Docker port 5432 already in use
```bash
# Check what's using it
lsof -i :5432
# Or change host port in docker-compose.yml: "5433:5432"
# Then update VECTOR_DB_URL in .env accordingly
```

### Ollama model not found
```bash
ollama list     # show pulled models
ollama pull gemma3:4b
```

### `pgvector` Python package import error
```bash
pip install pgvector==0.3.2
```

---

# Build Instructions — agent-service (Azure)

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python --version` |
| Docker | Latest | Solo para Postgres+pgvector local (`pgvector/pgvector:pg16`) |
| Azure CLI | Latest | `az login` — usado por `DefaultAzureCredential` en LOCAL |
| Acceso a Azure OpenAI + Azure AI Foundry | — | Endpoints en `.env` (ver `.env.example`) |

---

## Build Steps

### 1. Navigate to service directory
```bash
cd services/agent-service
```

### 2. Create and activate virtual environment
```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
```

### 3. Install dependencies
```bash
pip install -e ".[dev]"
```

### 4. Configure environment
```bash
cp .env.example .env
# Completar DATABASE_URL, AZURE_OPENAI_ENDPOINT, FOUNDRY_PROJECT_ENDPOINT
az login
```

### 5. Start PostgreSQL with pgvector (Docker, para desarrollo/tests con DB real)
```bash
docker run -d --name agent-service-db -p 5432:5432 -e POSTGRES_PASSWORD=test pgvector/pgvector:pg16
psql "postgresql://postgres:test@localhost:5432/postgres" -f migrations/001_create_courses.sql
```

### 6. Cargar el catálogo (genera embeddings vía Azure OpenAI)
```bash
python -m scripts.seed_catalog
```

### 7. Verify build
```bash
python -m py_compile $(find . -name "*.py" -not -path "*/.venv/*")
echo "Build OK"
```

**Verificado en esta sesión**: `py_compile` sobre los 33 archivos `.py` generados — sin errores de sintaxis.

---

## Expected Output
- Entorno virtual en `.venv/` con `fastapi`, `asyncpg`, `agent-framework`, `azure-identity`, `openai`, `hypothesis`, `pytest`, etc. instalados
- Postgres corriendo en `localhost:5432` con la tabla `courses` creada (extensión `pgvector`, índice HNSW)
- Catálogo cargado con 10 programas y sus embeddings (`text-embedding-3-small`)

---

## Troubleshooting

### `asyncpg` falla al conectar con `sslmode=require` contra Postgres local sin TLS
```bash
# En local, usar DATABASE_URL sin forzar SSL (el docker run de arriba no expone TLS):
DATABASE_URL=postgresql://postgres:test@localhost:5432/postgres  # sin ?sslmode=require
```

### `az login` no disponible / CI sin credenciales interactivas
```bash
# Usar un Service Principal para DefaultAzureCredential en CI:
export AZURE_CLIENT_ID=... AZURE_CLIENT_SECRET=... AZURE_TENANT_ID=...
```

### Import error en `agent_framework.azure` / `azure.ai.agents`
- Verificar la versión instalada del paquete `agent-framework` contra `pyproject.toml` — la superficie del SDK de Foundry está en evolución activa (ver nota en `repository-layer-summary.md`).
