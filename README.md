# ask-dmc

AI-powered sales agent for [DMC Institute](https://dmc.pe). The agent chats freely with visitors to qualify them as leads, recommends real courses from a pgvector-indexed catalog, and generates Mercado Pago payment links — all through a WebSocket chat widget backed by an Azure AI Foundry agent.

> This is a demo/course project. It has gone through a couple of architecture pivots — see `aidlc-docs/aidlc-state.md` (Known Divergences table) for the full history if you're wondering why something looks different from an older commit or doc.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                            ask-dmc                                │
│                                                                    │
│  apps/                                                            │
│  └── chat/            Next.js 15 — WebSocket chat widget          │
│                                                                    │
│  services/                                                        │
│  └── agent-service/   FastAPI + Azure AI Foundry agent            │
│                       (tool-calling, Postgres, Mercado Pago)      │
│                                                                    │
│  infra/agent-service/ Terraform (Azure Container Apps + Postgres) │
└──────────────────────────────────────────────────────────────────┘

Request flow:
  Browser ──WS──> agent-service /ws/chat
                     │
                     ├── ChatAgentClient (Azure AI Foundry "dmc-sales-advisor" agent)
                     │     ├── tool: collect_profile_data        (pauses for a form widget)
                     │     ├── tool: get_course_recommendations  (pgvector similarity search)
                     │     └── tool: create_payment_link         (Mercado Pago Checkout Pro)
                     │
                     └── Postgres (courses, leads, conversation_sessions, conversation_messages)

  Mercado Pago ──webhook──> agent-service /webhooks/mercadopago (confirms payment, updates Lead)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS 4, Effect (WsChatService) |
| Agent backend | FastAPI, Azure AI Foundry Persistent Agent, Microsoft Agent Framework |
| Embeddings (agent-service) | Azure OpenAI `text-embedding-3-small` |
| Vector store | PostgreSQL 16 + pgvector |
| Payments | Mercado Pago Checkout Pro |
| Infra | Terraform → Azure Container Apps, Azure Database for PostgreSQL, Key Vault |

---

## Repository layout

```
ask-dmc/
├── apps/
│   └── chat/                        # Next.js chat widget
│       ├── app/                     # page.tsx, layout.tsx
│       ├── components/              # ChatApp, Sidebar, ProfileDataWidget,
│       │                            # CourseRecommendationCard, PaymentLinkButton, ...
│       ├── hooks/useChat.ts
│       ├── lib/                     # ChatService (interface) + WsChatService (Effect impl)
│       └── types/
│
├── services/
│   ├── agent-service/                # Azure AI Foundry sales agent — see its own README
│   │   ├── main.py                   # wires WS /ws/chat, POST /webhooks/mercadopago,
│   │   │                             # GET /conversations, GET /conversations/{id}/messages
│   │   ├── src/
│   │   │   ├── domain/                # Course, Lead, RecommendationOrchestrator, lead_scoring
│   │   │   ├── ports/                 # Protocols (CourseRepository, EmbeddingService, ...)
│   │   │   ├── adapters/              # Postgres, Azure OpenAI, ChatAgentClient (+ 3 tools),
│   │   │   │                         # Mercado Pago client + webhook signature verification
│   │   │   └── api/                   # ChatWebSocketHandler, MercadoPagoWebhookHandler
│   │   ├── migrations/                # 001 courses+pgvector, 002 leads/sessions, 003 messages
│   │   └── scripts/                   # seed_catalog.py, manual_chat_check.py, ...
│
├── infra/agent-service/              # Terraform: Container App, Postgres, Key Vault
│
└── knowledge_source/                 # Course brochure PDFs — currently unused (see note below)
```

> `knowledge_source/` predates `agent-service`: it fed a PDF→embeddings→pgvector ingestion
> pipeline (`services/ingestion`, the project's original `unit-1`) that was removed because
> it no longer connected to anything — the live catalog is a curated
> `services/agent-service/scripts/catalog_seed_data.json`, not RAG over these brochures.
> The PDFs are kept here only in case that RAG approach gets revisited.

---

## Local setup

### 1. `services/agent-service` — the sales agent (main service)

Full instructions live in [`services/agent-service/README.md`](services/agent-service/README.md). Short version:

```bash
cd services/agent-service
uv sync --all-extras            # or: pip install -e ".[dev]"
cp .env.example .env            # fill in DATABASE_URL, AZURE_OPENAI_ENDPOINT,
                                 # FOUNDRY_PROJECT_ENDPOINT, MERCADOPAGO_ACCESS_TOKEN,
                                 # MERCADOPAGO_WEBHOOK_SECRET
az login                        # local dev uses DefaultAzureCredential -> Azure CLI

psql "$DATABASE_URL" -f migrations/001_create_courses.sql
psql "$DATABASE_URL" -f migrations/002_create_leads_and_sessions.sql
psql "$DATABASE_URL" -f migrations/003_create_conversation_messages.sql
python -m scripts.seed_catalog  # embeds and loads the course catalog

uvicorn main:app --reload --port 8000
```

- WebSocket (chat): `ws://localhost:8000/ws/chat`
- Payment webhook: `POST http://localhost:8000/webhooks/mercadopago`
- Message rehydration: `GET http://localhost:8000/conversations/{conversation_id}/messages`
- Health check: `GET http://localhost:8000/health`

Requires access to an Azure OpenAI resource (embeddings) and an Azure AI Foundry project (agent) — see [`services/agent-service/docs/provisioning-foundry-azd.md`](services/agent-service/docs/provisioning-foundry-azd.md) for provisioning the Foundry agent itself (not covered by the Terraform in `infra/agent-service/`).

### 2. `apps/chat` — the frontend

```bash
cd apps/chat
npm install
npm run dev
```

`.env.local`:
```dotenv
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/chat
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The app is available at [http://localhost:3000](http://localhost:3000). The browser connects directly to `agent-service`'s WebSocket — there is no Next.js API proxy route.

---

## Running tests

```bash
# agent-service (pytest)
cd services/agent-service && pytest

# chat frontend (Vitest)
cd apps/chat && npm test
```

---

## Infrastructure

`infra/agent-service/` is Terraform for the Azure resources backing `agent-service`: Container Apps, Azure Database for PostgreSQL Flexible Server, and Key Vault (secrets injected as Container Apps env vars — there's no in-app Key Vault client). The Azure AI Foundry project/agent itself is provisioned separately via `azd` (Terraform's `azurerm` provider support for that resource type is still catching up) — see `services/agent-service/docs/provisioning-foundry-azd.md`.
