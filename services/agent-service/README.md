# agent-service

Backend de recomendación de cursos por perfil — `unit-2` redefinida sobre Azure (ver
`aidlc-docs/aidlc-state.md`, DIV-10).

- **Incremento 1**: catálogo de cursos + recomendación por perfil (filtros duros de
  presupuesto/duración + ranking semántico vía pgvector). Su endpoint dedicado
  (`/ws/recommendation`) y el agente de un solo turno que lo componía fueron
  eliminados tras el incremento 2 (código muerto: ya no se enrutaban desde
  `main.py`); la lógica de matching sobrevive dentro de `RecommendationOrchestrator`,
  reutilizada como la tool `get_course_recommendations`.
- **Incremento 2 (activo)**: chat conversacional libre con tool-calling (`/ws/chat`),
  pago real vía Mercado Pago Checkout Pro, webhook de confirmación, persistencia de
  leads en Postgres.

No implementa (todavía): notificación activa de escalación a humano (DIV-12, solo se
persiste el flag), Backoffice Portal, rate limiting (SECURITY-11, riesgo aceptado),
extracción de nombre/email/motivación desde la conversación libre (ver limitación en
`aidlc-docs/construction/agent-service/code/business-logic-summary-increment2.md`).

## Requisitos

- Python 3.11+
- Postgres con extensión `pgvector` (local: Docker; Azure: Database for PostgreSQL Flexible Server)
- `az login` para desarrollo local (usa `DefaultAzureCredential` → Azure CLI credential)
- Acceso a un recurso Azure OpenAI (embeddings) y un proyecto Azure AI Foundry (agente)
- Credenciales de Mercado Pago sandbox (access token + secreto de verificación de webhook)

## Setup local

```bash
cd services/agent-service
uv sync --all-extras   # o: pip install -e ".[dev]"
cp .env.example .env    # completar DATABASE_URL, AZURE_OPENAI_ENDPOINT, FOUNDRY_PROJECT_ENDPOINT,
                         # MERCADOPAGO_ACCESS_TOKEN, MERCADOPAGO_WEBHOOK_SECRET
az login
```

### Base de datos

```bash
docker compose up -d    # Postgres 16 + pgvector en localhost:5434 (user postgres / demo)
psql "$DATABASE_URL" -f migrations/001_create_courses.sql
psql "$DATABASE_URL" -f migrations/002_create_leads_and_sessions.sql
psql "$DATABASE_URL" -f migrations/003_create_conversation_messages.sql
psql "$DATABASE_URL" -f migrations/004_create_outreach_drafts.sql
python -m scripts.seed_catalog   # genera embeddings y carga el catálogo (catalog_seed_data.json)
```

### Correr el servicio

```bash
uvicorn main:app --reload --port 8000
# WebSocket (chat conversacional, incremento 2): ws://localhost:8000/ws/chat
# Webhook de pago (sin exposición pública en este incremento): POST http://localhost:8000/webhooks/mercadopago
# Rehidratación de mensajes tras un reload del frontend: GET http://localhost:8000/conversations/{conversation_id}/messages
# Health check: http://localhost:8000/health
```

CORS habilitado solo para `http://localhost:3000` (necesario para que el navegador llame al endpoint de rehidratación vía `fetch()` — el WS no está sujeto a CORS).

### Verificación manual (incremento 2)

```bash
python -m scripts.manual_chat_check                    # chat + tool-calling contra el agente real
python -m scripts.simulate_mercadopago_webhook <payment_id>  # simula el webhook contra localhost
```

## Tests

```bash
pytest                          # unit + integration (excluye tests que requieren Postgres real)
TEST_DATABASE_URL=postgresql://... pytest   # incluye tests contra Postgres real (repos de courses/leads/conversation_messages)
```

Los tests de `tests/unit/test_orchestrator_properties.py`, `test_orchestrator_examples.py`,
`test_lead_scoring.py` y `test_pending_tool_calls.py` no requieren base de datos.

**IMPORTANTE**: `TEST_DATABASE_URL` debe apuntar a una base de datos DISTINTA de la que
usa el demo (`DATABASE_URL`) — varios tests hacen `TRUNCATE TABLE courses` /
`conversation_messages` / `conversation_sessions`. Usar la misma base borra el catálogo
real y las conversaciones en curso (encontrado en producción: un `TRUNCATE TABLE courses`
dejó un único curso sintético con embedding cero, causando `NaN` en `similarity_score` y
rompiendo el chat con un `ParseError` en el frontend — ver `build-and-test-summary.md`
Ronda 6). Setup recomendado (mismo contenedor Docker, base separada):

```bash
docker exec -i agent-service-db psql -U postgres -d postgres -c "CREATE DATABASE agent_service_test;"
docker exec -i agent-service-db psql -U postgres -d agent_service_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
for f in migrations/*.sql; do docker exec -i agent-service-db psql -U postgres -d agent_service_test < "$f"; done

TEST_DATABASE_URL=postgresql://postgres:demo@localhost:5434/agent_service_test pytest
```

## Estructura

```
src/
  domain/       — modelos (Course, Lead, ConversationSession, ConversationMessage, ...),
                  RecommendationOrchestrator, lead_scoring.py (BR-17), pending_tool_calls.py (PATTERN-15)
  ports/        — Protocols: CourseRepository, EmbeddingService, LeadRepository,
                  ConversationMessageRepository
  adapters/     — Postgres, Azure OpenAI, RetryPolicy, Mercado Pago (client + firma),
                  ChatAgentClient (Agent + 3 tools: collect_profile_data,
                  get_course_recommendations, create_payment_link)
  api/          — ChatWebSocketHandler (/ws/chat), MercadoPagoWebhookHandler, schemas Pydantic
migrations/     — 001 (courses + pgvector), 002 (leads + conversation_sessions), 003 (conversation_messages), 004 (outreach_drafts)
scripts/        — seed_catalog.py, manual_chat_check.py, simulate_mercadopago_webhook.py
tests/unit/     — dominio + adaptadores (property-based con Hypothesis)
tests/integration/ — flujo WS completo y flujo de webhook, con fakes
```

Secrets en producción (Mercado Pago, DB URL, etc.) llegan como variables de entorno
inyectadas por Container Apps directamente desde Key Vault (`infra/agent-service/main.tf`) —
no hay un cliente de Key Vault a nivel de aplicación.

## Provisionar Azure AI Foundry

El proyecto/agente de Foundry no está cubierto por el Terraform de `infra/agent-service/`
(soporte de `azurerm` para ese tipo de recurso todavía en desarrollo) — ver
[`docs/provisioning-foundry-azd.md`](docs/provisioning-foundry-azd.md) para los comandos
de `azd` a correr.

## Notas de diseño

Ver `aidlc-docs/construction/agent-service/` para el diseño completo (Functional Design,
NFR Requirements/Design, Infrastructure Design) — en particular:
- Contrato de mensajes WebSocket: `functional-design/business-logic-model.md` Sección 3
- Business Rules (BR-01 a BR-11): `functional-design/business-rules.md`
- Decisiones de infraestructura Azure: `infrastructure-design/infrastructure-design.md`
