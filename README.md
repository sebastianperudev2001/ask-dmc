# ask-dmc

AI-powered sales agent for [DMC Institute](https://dmc.pe). The agent chats freely with visitors to qualify them as leads, recommends real courses from a pgvector-indexed catalog, and generates Mercado Pago payment links — all through a WebSocket chat widget backed by an Azure AI Foundry agent. A separate BackOffice app gives staff a real-time view of leads and lets them send AI-drafted outreach emails.

> This is a demo/course project. Don't over-invest in performance, scaling, or hardening work beyond what's asked.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                              ask-dmc                                 │
│                                                                      │
│  apps/                                                              │
│  ├── chat/              Next.js 15 — public WebSocket chat widget   │
│  └── backoffice/        Next.js 15 — staff leads/outreach dashboard │
│                                                                      │
│  services/                                                          │
│  └── agent-service/     FastAPI + Azure AI Foundry agents           │
│                         (tool-calling, Postgres, Mercado Pago, ACS) │
│                                                                      │
│  infra/agent-service/   Terraform (Azure Container Apps + Postgres) │
└────────────────────────────────────────────────────────────────────┘

Request flow:
  Browser (chat) ──WS──> agent-service /ws/chat
                            │
                            ├── ChatAgentClient (Azure AI Foundry sales agent)
                            │     ├── tool: collect_profile_data        (pauses for a form widget)
                            │     ├── tool: get_course_recommendations  (pgvector similarity search)
                            │     └── tool: create_payment_link         (Mercado Pago Checkout Pro)
                            │
                            └── Postgres (courses, leads, conversation_sessions, conversation_messages)

  Mercado Pago ──webhook──> agent-service /webhooks/mercadopago (confirms payment, updates Lead)

  Browser (backoffice) ──WS──> agent-service /ws/leads   (real-time lead score push, LeadBroadcaster)
                     └──fetch──> agent-service /leads, /leads/{id}/drafts*, /drafts/{id}/send|discard
                                    │
                                    └── OutreachAgentService (Azure AI Foundry outreach agent)
                                          └── sends via Azure Communication Services Email
                                              (only on an explicit staff "send" action)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS 4, Effect (`Ws*Service` behind a `Context.Tag` interface) |
| Agent backend | FastAPI, Azure AI Foundry Persistent Agents, Microsoft Agent Framework |
| Embeddings (agent-service) | Azure OpenAI `text-embedding-3-small` |
| Vector store | PostgreSQL 16 + pgvector |
| Payments | Mercado Pago Checkout Pro |
| Outreach email | Azure Communication Services (Email) |
| Infra | Terraform → Azure Container Apps, Azure Database for PostgreSQL, Key Vault, Azure OpenAI, ACS |

---

## Repository layout

```
ask-dmc/
├── apps/
│   ├── chat/                        # Next.js public chat widget (port 3000)
│   │   ├── app/                     # page.tsx, layout.tsx
│   │   ├── components/              # ChatApp, Sidebar, ProfileDataWidget,
│   │   │                            # CourseRecommendationCard, PaymentLinkButton, ...
│   │   ├── hooks/useChat.ts
│   │   ├── lib/                     # ChatService (interface) + WsChatService (Effect impl)
│   │   └── types/
│   │
│   └── backoffice/                  # Next.js staff dashboard (port 3001)
│       ├── app/                     # page.tsx, layout.tsx
│       ├── components/              # BackofficeApp, KanbanBoard, LeadCard, LeadDetailModal,
│       │                            # DraftPanel, NotificationCenter
│       ├── hooks/useLeadsSocket.ts
│       ├── lib/                     # LeadsService (interface) + WsLeadsService (Effect impl)
│       └── types/
│
├── services/
│   └── agent-service/                # Azure AI Foundry agents — see its own README
│       ├── main.py                   # composition root; wires every route below
│       ├── src/
│       │   ├── domain/                # Course, Lead, ConversationSession, OutreachDraft,
│       │   │                          # LeadEvent, RecommendationOrchestrator, lead_scoring,
│       │   │                          # pending_tool_calls
│       │   ├── ports/                 # Protocols (CourseRepository, EmbeddingService,
│       │   │                          # LeadRepository, DraftRepository, EmailSender, ...)
│       │   ├── adapters/              # Postgres repos, Azure OpenAI, ChatAgentClient (+ 3
│       │   │                          # tools), OutreachAgentService, Mercado Pago client +
│       │   │                          # webhook signature verification, ACS email sender
│       │   └── api/                   # ChatWebSocketHandler, MercadoPagoWebhookHandler,
│       │                              # LeadBroadcaster, schemas
│       ├── migrations/                # 001 courses+pgvector, 002 leads/sessions,
│       │                              # 003 conversation_messages, 004 outreach_drafts
│       └── scripts/                   # seed_catalog.py, manual_chat_check.py,
│                                       # simulate_mercadopago_webhook.py, manual_leads_e2e_check.py
│
├── infra/agent-service/              # Terraform: Container App, Postgres, Key Vault,
│                                      # Azure OpenAI, Azure Communication Services
│
└── knowledge_source/                 # Course brochure PDFs — currently unused (see note below)
```

Routes served by `agent-service`, by surface:

| Surface | Routes |
|---|---|
| Chat | `WS /ws/chat`, `POST /webhooks/mercadopago`, `GET /conversations`, `GET /conversations/{id}/messages` |
| BackOffice | `GET /leads`, `WS /ws/leads`, `POST /leads/{id}/drafts`, `GET /leads/{id}/drafts/active`, `POST /drafts/{id}/send`, `POST /drafts/{id}/discard` |
| Both | `GET /health` |

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
                                 # MERCADOPAGO_WEBHOOK_SECRET, ACS_CONNECTION_STRING,
                                 # ACS_SENDER_ADDRESS (leave the ACS_* pair empty to skip
                                 # outreach email locally — the client builds lazily)
az login                        # local dev uses DefaultAzureCredential -> Azure CLI

docker compose up -d            # Postgres 16 + pgvector on localhost:5434 (user postgres / demo)
psql "$DATABASE_URL" -f migrations/001_create_courses.sql
psql "$DATABASE_URL" -f migrations/002_create_leads_and_sessions.sql
psql "$DATABASE_URL" -f migrations/003_create_conversation_messages.sql
psql "$DATABASE_URL" -f migrations/004_create_outreach_drafts.sql
python -m scripts.seed_catalog  # embeds and loads the course catalog

uvicorn main:app --reload --port 8000
```

- WebSocket (chat): `ws://localhost:8000/ws/chat`
- Payment webhook: `POST http://localhost:8000/webhooks/mercadopago`
- Message rehydration: `GET http://localhost:8000/conversations/{conversation_id}/messages`
- WebSocket (leads, real-time): `ws://localhost:8000/ws/leads`
- Leads / outreach drafts: `GET /leads`, `POST /leads/{id}/drafts`, `GET /leads/{id}/drafts/active`, `POST /drafts/{id}/send`, `POST /drafts/{id}/discard`
- Health check: `GET http://localhost:8000/health`

Requires access to an Azure OpenAI resource (embeddings) and an Azure AI Foundry project (chat + outreach agents) — see [`services/agent-service/docs/provisioning-foundry-azd.md`](services/agent-service/docs/provisioning-foundry-azd.md) for provisioning the Foundry agents themselves (not covered by the Terraform in `infra/agent-service/`).

### 2. `apps/chat` — the public chat widget

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

### 3. `apps/backoffice` — the staff dashboard

```bash
cd apps/backoffice
npm install
npm run dev
```

`.env.local`:
```dotenv
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/leads
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The app is available at [http://localhost:3001](http://localhost:3001). Like `apps/chat`, it connects directly to `agent-service` — no proxy route.

---

## Running tests

```bash
# agent-service (pytest)
cd services/agent-service && pytest

# chat frontend (Vitest)
cd apps/chat && npm test

# backoffice frontend (Vitest)
cd apps/backoffice && npm test
```

---

## Infrastructure

`infra/agent-service/` is Terraform for the Azure resources backing `agent-service`: Container Apps, Azure Database for PostgreSQL Flexible Server, Azure OpenAI, Azure Communication Services (outreach email), and Key Vault (secrets injected as Container Apps env vars — there's no in-app Key Vault client). The Azure AI Foundry projects/agents themselves are provisioned separately via `azd` (Terraform's `azurerm` provider support for that resource type is still catching up) — see `services/agent-service/docs/provisioning-foundry-azd.md`.
