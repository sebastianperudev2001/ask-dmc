# Folder Structure — DMC Sales Agent

**Fecha**: 2026-04-28  
**Referencia canónica para Code Generation — cada unidad sigue esta estructura exacta.**

---

## Monorepo Root

```
ask-dmc/
├── apps/                        # Turborepo — Next.js apps
│   ├── widget/                  # unit-4: chat widget
│   └── backoffice/              # unit-5: backoffice portal
├── packages/
│   └── ui/                      # Shared React components
├── services/                    # Python backend services (fuera de Turborepo)
│   ├── agent/                   # unit-2: Strands Agent (AgentCore Runtime)
│   ├── backend/                 # unit-3: FastAPI (Lambda + API Gateway)
│   └── ingestion/               # unit-1: ingestion pipeline
├── turbo.json
├── package.json                 # Turborepo root workspace
└── aidlc-docs/                  # AIDLC documentation only
```

---

## services/backend/ — FastAPI en Lambda

Patrón: **Domain → Ports → Infrastructure → Services → Handlers**

```
services/backend/
├── src/
│   ├── domain/                          # Entidades de negocio puras (sin deps externas)
│   │   ├── __init__.py
│   │   ├── lead.py                      # Lead, LeadScore (hot/warm/cold), Motivation enum,
│   │   │                                # ScoringSignals, LeadQualification, LeadFilters
│   │   ├── conversation.py              # ConversationMessage, FunnelState enum
│   │   │                                # (BIENVENIDA|IDENTIFICACION|CALIFICACION|
│   │   │                                #  RECOMENDACION|CIERRE|ESCALACION)
│   │   └── course.py                    # CourseChunk (para presigned URL lookup)
│   │
│   ├── ports/                           # Interfaces (Protocol) — inversión de dependencias
│   │   ├── __init__.py
│   │   ├── lead_repository.py           # LeadRepository Protocol
│   │   ├── conversation_repository.py   # ConversationRepository Protocol
│   │   └── s3_repository.py             # S3Repository Protocol
│   │
│   ├── infrastructure/                  # Implementaciones concretas de ports
│   │   ├── __init__.py
│   │   ├── dynamo/
│   │   │   ├── __init__.py
│   │   │   ├── lead_repository.py       # DynamoDB dmc-leads
│   │   │   └── conversation_repository.py # DynamoDB dmc-conversations
│   │   └── s3/
│   │       └── s3_repository.py         # Presigned URLs, list brochures
│   │
│   ├── services/                        # Lógica de aplicación (orquestación)
│   │   ├── __init__.py
│   │   ├── chat_session_service.py      # Invoca AgentCore, streaming via post_to_connection
│   │   ├── lead_service.py              # CRUD leads, scoring, escalation flag
│   │   ├── notification_service.py      # SES email al equipo comercial
│   │   └── payment_service.py           # Mercado Pago Checkout API
│   │
│   ├── handlers/                        # Entry points Lambda
│   │   ├── __init__.py
│   │   ├── websocket.py                 # handle_connect / handle_disconnect / handle_message
│   │   ├── leads_api.py                 # FastAPI app + Mangum adapter (REST /admin/leads)
│   │   └── middleware/
│   │       ├── __init__.py
│   │       └── auth.py                  # Cognito JWT validation (JWKS, claims)
│   │
│   └── config.py                        # Pydantic BaseSettings — env vars tipadas
│                                        # (DYNAMODB_TABLE_LEADS, S3_BUCKET_NAME, etc.)
│
├── tests/
│   ├── unit/
│   │   ├── domain/                      # Tests de entidades puras
│   │   │   ├── test_lead_scoring.py     # PBT con Hypothesis: score logic
│   │   │   └── test_motivation.py       # PBT con Hypothesis: motivation detection
│   │   ├── services/
│   │   │   ├── test_lead_service.py
│   │   │   └── test_notification_service.py
│   │   └── infrastructure/
│   │       └── test_repositories.py     # Unit tests con mocks de DynamoDB
│   └── integration/
│       ├── test_websocket_flow.py       # End-to-end WebSocket handler
│       └── test_leads_api.py            # REST endpoints con TestClient
│
├── requirements.txt                     # Runtime deps: fastapi, mangum, boto3, strands-sdk
├── requirements-dev.txt                 # Dev deps: pytest, hypothesis, pytest-asyncio
├── Makefile                             # test, lint, deploy targets
└── Dockerfile                           # Para despliegue en Lambda (image-based)
```

### Capas y reglas de dependencia

```
handlers/   →   services/   →   ports/   ←   infrastructure/
                    ↓
                domain/          (sin dependencias externas)
```

- `domain/` no importa nada fuera de stdlib
- `ports/` solo importa `domain/` y `typing`
- `infrastructure/` implementa `ports/` e importa boto3
- `services/` importa `ports/` (nunca `infrastructure/` directamente)
- `handlers/` importa `services/` y hace wiring de `infrastructure/` via DI en `config.py`

---

## services/agent/ — Strands Agent (AgentCore Runtime)

```
services/agent/
├── src/
│   ├── agent.py                         # StrandsAgent: definición, system prompt, tools wiring
│   │
│   ├── tools/                           # Strands Tools
│   │   ├── __init__.py
│   │   ├── search_courses.py            # SearchCoursesTool → VectorDBRepository
│   │   ├── qualify_lead.py              # QualifyLeadTool → pure logic
│   │   ├── generate_payment_link.py     # GeneratePaymentLinkTool → HTTP a backend Lambda
│   │   └── get_brochure_url.py          # GetBrochureUrlTool → S3Repository
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── bedrock_llm.py               # BedrockLLMProvider (LLMProvider Protocol)
│   │   ├── s3_repository.py             # Presigned URLs
│   │   └── vector_db/                   # Implementación decidida en NFR Design
│   │       └── __init__.py
│   │
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── llm_provider.py              # LLMProvider Protocol
│   │   └── vector_db.py                 # VectorDBRepository Protocol
│   │
│   └── config.py                        # Env vars: BEDROCK_MODEL_ID, S3_BUCKET_NAME, etc.
│
├── tests/
│   ├── unit/
│   │   └── tools/
│   │       ├── test_qualify_lead.py     # PBT: motivation classification
│   │       └── test_search_courses.py
│   └── evals/
│       ├── test_happy_path_a.py         # Happy path: lead calificado → recomendación → pago
│       ├── test_happy_path_b.py         # Happy path: re-identificación desde localStorage
│       ├── test_guardrails.py           # Guardrails: anti-alucinación, no-competitor, scope
│       └── test_rag_quality.py          # RAG quality: relevancia de chunks recuperados
│
├── requirements.txt
├── requirements-dev.txt
└── Dockerfile                           # Para despliegue en AgentCore Runtime
```

---

## services/ingestion/ — Pipeline de Ingestion

```
services/ingestion/
├── src/
│   ├── orchestrator.py                  # IngestionOrchestrator: coordina todo el pipeline
│   ├── pdf_extractor.py                 # PDFExtractor: PDF bytes → list[BrochureSection]
│   │                                    # Usa LLMProvider (BedrockLLMProvider)
│   ├── embedding_generator.py           # EmbeddingGenerator: sections → list[EmbeddedChunk]
│   │                                    # Usa Bedrock Embeddings API
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── bedrock_llm.py               # BedrockLLMProvider (mismo pattern que agent/)
│   │   ├── s3_repository.py             # S3: listar y leer PDFs
│   │   └── vector_db/                   # VectorDBRepository implementation (TBD)
│   │       └── __init__.py
│   ├── ports/
│   │   ├── llm_provider.py
│   │   └── vector_db.py
│   └── config.py
│
├── tests/
│   └── unit/
│       ├── test_pdf_extractor.py
│       └── test_embedding_generator.py
│
├── requirements.txt
└── run.py                               # CLI: python run.py --bucket dmc-knowledge-base
```

---

## apps/widget/ — Chat Widget (Next.js)

```
apps/widget/
├── src/
│   ├── app/
│   │   ├── layout.tsx                   # Root layout
│   │   ├── page.tsx                     # Demo page — monta <ChatWidget />
│   │   └── globals.css
│   │
│   ├── components/
│   │   ├── ChatWidget.tsx               # Root: gestiona estado global del chat
│   │   ├── MessageList.tsx              # Lista scrollable de mensajes
│   │   ├── MessageBubble.tsx            # Burbuja individual (agent | user)
│   │   ├── InputBar.tsx                 # Input + botón enviar
│   │   └── TypingIndicator.tsx          # Animación de streaming en progreso
│   │
│   ├── hooks/
│   │   ├── useWebSocket.ts              # Conexión WS, reconnect automático, streaming
│   │   └── useLocalStorage.ts           # Persistencia de name + email del visitante
│   │
│   └── lib/
│       ├── types.ts                     # Message, VisitorIdentity, FunnelState
│       └── constants.ts                 # WS_URL, RECONNECT_DELAY, etc.
│
├── package.json
├── next.config.ts
└── tsconfig.json
```

---

## apps/backoffice/ — Backoffice Portal (Next.js)

```
apps/backoffice/
├── src/
│   ├── app/
│   │   ├── layout.tsx                   # Root layout
│   │   ├── login/
│   │   │   └── page.tsx                 # Página de login (Amplify + Cognito)
│   │   └── admin/
│   │       ├── layout.tsx               # Auth guard — redirige a /login si no autenticado
│   │       ├── page.tsx                 # Lista de leads (LeadsTable)
│   │       └── [id]/
│   │           └── page.tsx             # Detalle del lead (LeadDetail)
│   │
│   ├── components/
│   │   ├── LeadsTable.tsx               # Tabla con filtros (score, motivación, fechas)
│   │   ├── LeadRow.tsx                  # Fila de la tabla con badges
│   │   ├── LeadDetail.tsx               # Vista completa del lead
│   │   ├── ScoreBadge.tsx               # hot=rojo, warm=amarillo, cold=azul
│   │   ├── MotivationBadge.tsx          # growth/salary/company_requirement/academic/undefined
│   │   ├── EscalationBanner.tsx         # Banner destacado para escalated_to_human: true
│   │   ├── TranscriptViewer.tsx         # Transcripción colapsable desde dmc-conversations
│   │   └── LoginForm.tsx                # Form de usuario/contraseña con Amplify SDK
│   │
│   ├── hooks/
│   │   ├── useLeads.ts                  # Fetch lista de leads con filtros
│   │   └── useAuth.ts                   # Estado de autenticación Cognito
│   │
│   └── lib/
│       ├── api.ts                       # Fetch wrapper con Authorization header
│       ├── auth.ts                      # Amplify configure + getCurrentUser + signOut
│       └── types.ts                     # Lead, ConversationMessage, LeadFilters
│
├── package.json
├── next.config.ts
└── tsconfig.json
```

---

## packages/ui/ — Shared Components

```
packages/ui/
├── src/
│   ├── Badge.tsx                        # Badge base (text + color variant)
│   ├── Button.tsx                       # Button base (primary/secondary/ghost)
│   └── tokens.ts                        # Design tokens: colors, spacing, typography
├── package.json
└── tsconfig.json
```

---

## Resumen de Reglas por Capa (Backend Python)

| Capa | Puede importar | No puede importar |
|---|---|---|
| `domain/` | stdlib, typing | Todo lo demás |
| `ports/` | `domain/`, typing | `infrastructure/`, `services/`, `handlers/` |
| `infrastructure/` | `ports/`, `domain/`, boto3, libs externas | `services/`, `handlers/` |
| `services/` | `ports/`, `domain/` | `infrastructure/` (recibe por DI), `handlers/` |
| `handlers/` | `services/`, `infrastructure/` (solo para DI wiring), `config` | — |
