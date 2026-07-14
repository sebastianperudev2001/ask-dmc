# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`ask-dmc` is an AI-powered sales agent for DMC Institute. A Next.js chat widget talks over
WebSocket to a FastAPI backend that drives an Azure AI Foundry agent with tool-calling
(course recommendations via pgvector similarity search, a lead-capture form widget, and
Mercado Pago payment links). A second Next.js app is a BackOffice for staff to see leads
scored in real time and send AI-drafted outreach emails.

This is a demo/course project — do not over-invest in performance, scaling, or hardening
work unless explicitly asked.

## Repository layout

```
apps/
  chat/           Next.js 15 — public chat widget (port 3000)
  backoffice/     Next.js 15 — staff lead/outreach dashboard (port 3001)
services/
  agent-service/  FastAPI + Azure AI Foundry agent (port 8000) — the only backend
infra/
  agent-service/  Terraform (Azure Container Apps, Postgres, Key Vault)
knowledge_source/ Course brochure PDFs — currently unused, kept in case a RAG
                   ingestion pipeline over them is revisited later
```

There is no API gateway or BFF: both frontends talk directly to `agent-service`.

## Commands

### agent-service (FastAPI backend)

```bash
cd services/agent-service
uv sync --all-extras                     # or: pip install -e ".[dev]"
az login                                 # local dev auth -> DefaultAzureCredential
docker compose up -d                     # Postgres 16 + pgvector on localhost:5434 (postgres/demo)
psql "$DATABASE_URL" -f migrations/001_create_courses.sql
psql "$DATABASE_URL" -f migrations/002_create_leads_and_sessions.sql
psql "$DATABASE_URL" -f migrations/003_create_conversation_messages.sql
psql "$DATABASE_URL" -f migrations/004_create_outreach_drafts.sql
python -m scripts.seed_catalog           # embeds + loads the course catalog

uvicorn main:app --reload --port 8000
```

Tests (pytest, `testpaths = ["tests"]`, `asyncio_mode = "auto"`):

```bash
pytest                                          # unit + integration; skips tests needing real Postgres
TEST_DATABASE_URL=postgresql://... pytest       # also runs repository tests against real Postgres
pytest tests/unit/test_lead_scoring.py          # single file
pytest tests/unit/test_lead_scoring.py::test_x  # single test
```

`TEST_DATABASE_URL` **must** point at a database distinct from `DATABASE_URL` — several
tests `TRUNCATE TABLE courses` / `conversation_messages` / `conversation_sessions`, which
has previously wiped the real demo catalog. Create a separate DB in the same container:

```bash
docker exec -i agent-service-db psql -U postgres -d postgres -c "CREATE DATABASE agent_service_test;"
docker exec -i agent-service-db psql -U postgres -d agent_service_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
for f in migrations/*.sql; do docker exec -i agent-service-db psql -U postgres -d agent_service_test < "$f"; done
TEST_DATABASE_URL=postgresql://postgres:demo@localhost:5434/agent_service_test pytest
```

Tests that never need a database: `tests/unit/test_orchestrator_properties.py`,
`test_orchestrator_examples.py`, `test_lead_scoring.py`, `test_pending_tool_calls.py`.
`test_orchestrator_properties.py` uses Hypothesis (property-based).

Manual verification scripts (hit the real Azure Foundry agent / simulate a webhook):

```bash
python -m scripts.manual_chat_check
python -m scripts.simulate_mercadopago_webhook <payment_id>
python -m scripts.manual_leads_e2e_check
```

No linter/type-checker is configured in `pyproject.toml` for this service — don't assume
`ruff`/`mypy` gates exist.

### apps/chat and apps/backoffice (Next.js)

```bash
cd apps/chat        # or apps/backoffice
npm install
npm run dev          # chat: 3000, backoffice: 3001
npm test             # vitest run
npm run build
```

`apps/chat/.env.local` and `apps/backoffice/.env.local` need:
```
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/chat      # (backoffice: /ws/leads)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Architecture

### agent-service: hexagonal (ports & adapters)

```
src/domain/    Entities + business logic — Course, Lead, ConversationSession,
               ConversationMessage, OutreachDraft, LeadEvent, RecommendationOrchestrator,
               lead_scoring.py, pending_tool_calls.py. No I/O here.
src/ports/     Protocols the domain depends on: CourseRepository, EmbeddingService,
               LeadRepository, ConversationMessageRepository, ConversationSessionStore,
               DraftRepository, EmailSender.
src/adapters/  Implementations: Postgres repositories, AzureOpenAIEmbeddingService,
               ChatAgentClient (wraps the Foundry agent + 3 tools), MercadoPagoPaymentClient
               + SignatureVerifier, OutreachAgentService, AzureCommunicationServicesEmailSender,
               RetryPolicy, ConnectionPool.
src/api/       ChatWebSocketHandler, MercadoPagoWebhookHandler, LeadBroadcaster, schemas.py
               (Pydantic response models).
main.py        Composition root — builds every adapter/handler and wires FastAPI routes.
               Nothing else in the codebase should construct these objects directly.
```

Key asymmetry in `main.py`: `ChatAgentClient` (and everything under it) is rebuilt **per
connection** via `agent_client_factory`, but `LeadEventPublisher`, `LeadBroadcaster`, and
`OutreachAgentService` are process-wide singletons built once at import time — they must
be shared across all `/ws/leads` connections and every `ChatAgentClient` that publishes a
lead event. Don't move their construction into a per-request factory.

### Two independent surfaces sharing one backend

- **Chat** (`/ws/chat`, `/webhooks/mercadopago`, `/conversations*`): free-form
  conversational sales agent. `ChatAgentClient` gives the Foundry agent three tools:
  `collect_profile_data` (pauses the turn for a frontend form widget —
  `pending_tool_calls.py` tracks the pause/resume state and times out via
  `PROFILE_DATA_TIMEOUT_SECONDS` to avoid a permanent deadlock if the widget is
  abandoned), `get_course_recommendations` (delegates to `RecommendationOrchestrator`:
  hard budget/duration filters, then pgvector semantic ranking), and
  `create_payment_link` (Mercado Pago Checkout Pro). The Mercado Pago webhook confirms
  payment and updates the `Lead`.
- **BackOffice** (`/leads`, `/ws/leads`, `/leads/{id}/drafts*`, `/drafts/{id}/*`): staff
  view of leads with real-time score updates pushed over `LeadBroadcaster`, plus an
  `OutreachAgentService` (its own Foundry agent) that drafts outreach emails
  (human-in-the-loop: `POST /leads/{id}/drafts` generates on demand,
  `POST /drafts/{id}/send` is the only path that actually emails — nothing sends
  automatically) via Azure Communication Services.

Both `/ws/chat` and `/ws/leads` are exempt from CORS (WebSocket isn't subject to it);
CORS middleware in `main.py` exists only for the frontends' `fetch()` calls
(`GET /conversations/{id}/messages`, the leads/drafts REST endpoints) and explicitly
allowlists `http://localhost:3000` and `http://localhost:3001` — no wildcard.

### Frontend: Effect-based service pattern (both apps)

Both `apps/chat` and `apps/backoffice` isolate the WebSocket transport behind an
`effect` `Context.Tag` service interface (`lib/ChatService.ts` / `lib/LeadsService.ts`),
implemented by a `Ws*Service` (`lib/WsChatService.ts` / `lib/WsLeadsService.ts`) and
provided to components through a `RuntimeProvider`. Components/hooks depend only on the
interface, not the WebSocket implementation — when changing frontend data flow, edit the
service interface and its `Ws*` implementation together; don't reach for `WebSocket`
directly from a component. `ChatService` is bidirectional (`sendMessage`,
`submitProfileData`, plus an `events: Stream`); `LeadsService` is push-only (`events`
only — the backend never expects a client message on `/ws/leads`).

### Data model (Postgres + pgvector, `services/agent-service/migrations/`)

`001` courses (+ pgvector embeddings) → `002` leads + conversation_sessions →
`003` conversation_messages → `004` outreach_drafts. The course catalog is not RAG over
`knowledge_source/`'s PDFs — it's a curated `scripts/catalog_seed_data.json` loaded by
`scripts/seed_catalog.py`.

### Known gotchas worth knowing before touching config

- `FOUNDRY_AGENT_MODEL_DEPLOYMENT` is the Foundry **deployment name**, not necessarily
  the underlying model name — a mismatch produces a 404 `DeploymentNotFound` even though
  the deployment is running.
- `ACS_CONNECTION_STRING`/`ACS_SENDER_ADDRESS` can be left empty locally — the email
  client is built lazily on first `.send()`, so an empty config doesn't break startup,
  only outreach sending.
- Secrets in production arrive as Container Apps env vars injected from Key Vault
  (`infra/agent-service/main.tf`) — there is no in-app Key Vault client.
- The Azure AI Foundry project/agent itself is **not** provisioned by the Terraform in
  `infra/agent-service/` (azurerm support for that resource is still catching up) — it's
  provisioned separately via `azd`, see `services/agent-service/docs/provisioning-foundry-azd.md`.
