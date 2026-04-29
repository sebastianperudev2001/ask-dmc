# Application Design — DMC Sales Agent

**Versión**: 1.0  
**Fecha**: 2026-04-28  

> Documento consolidado. Ver archivos individuales para detalle completo:
> - `components.md` — definición de cada componente
> - `component-methods.md` — firmas de métodos
> - `services.md` — orquestación y flujos de servicio
> - `component-dependency.md` — matriz de dependencias y data flow diagrams
> - `folder-structure.md` — estructura de carpetas completa (backend capas + Turborepo)

---

## Arquitectura en 5 Capas

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (Turborepo)                                           │
│  apps/widget (Next.js)          apps/backoffice (Next.js)       │
│  ChatWidget · MessageList        LeadsTable · LeadDetail        │
│  useWebSocket · useLocalStorage  ScoreBadge · LoginForm         │
│              packages/ui — Badge, design tokens                 │
└──────────────────────┬──────────────────┬───────────────────────┘
                       │ WebSocket         │ REST + JWT
┌──────────────────────▼──────────────────▼───────────────────────┐
│  BACKEND APPLICATION LAYER (FastAPI / Lambda)                   │
│                                                                 │
│  WebSocketHandler          LeadsAPIHandler   AuthMiddleware      │
│  ChatSessionService        LeadService                          │
│  NotificationService       PaymentService                       │
└──────────────────────┬──────────────────────────────────────────┘
                       │ AgentCore invoke
┌──────────────────────▼──────────────────────────────────────────┐
│  AGENT LAYER (Strands SDK / AgentCore Runtime)                  │
│                                                                 │
│  StrandsAgent                                                   │
│  SearchCoursesTool  QualifyLeadTool                             │
│  GeneratePaymentLinkTool  GetBrochureUrlTool                    │
│  AgentCore Memory (estado conversacional)                       │
└──────────────────────┬──────────────────────────────────────────┘
                       │ LLMProvider Protocol
┌──────────────────────▼──────────────────────────────────────────┐
│  INFRASTRUCTURE LAYER                                           │
│                                                                 │
│  BedrockLLMProvider     VectorDBRepository (TBD)               │
│  LeadRepository         ConversationRepository                  │
│  S3Repository                                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ (offline, independent)
┌──────────────────────▼──────────────────────────────────────────┐
│  INGESTION PIPELINE (script Python)                             │
│                                                                 │
│  IngestionOrchestrator  PDFExtractor  EmbeddingGenerator        │
│  S3Repository  VectorDBRepository  BedrockLLMProvider           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Decisiones de Diseño Clave

| Decisión | Elección | Rationale |
|---|---|---|
| LLM interface | `Protocol` (structural typing) | Pythonico, compatible con Strands SDK, no requiere herencia |
| WebSocket state | Sin persistencia de connectionId | Diseño síncrono: Lambda espera respuesta del agente y pushea tokens en el mismo invocation |
| Funnel state | AgentCore Memory + `current_state` en `dmc-conversations` | AgentCore Memory es la fuente de verdad; campo en conversaciones para observabilidad en backoffice |
| Frontend structure | Turborepo monorepo | `apps/widget`, `apps/backoffice`, `packages/ui` — máximo aislamiento por dominio |
| Dependency injection | Constructor injection | Servicios reciben repositorios/providers por constructor; facilita testing con Hypothesis (PBT) |
| Agent ↔ Backend coupling | Agente solo usa tools; backend persiste | StrandsAgent no conoce LeadService; la persistencia es responsabilidad del backend al finalizar la sesión |

---

## Units Mapping (para Construction Phase)

| Unit | Componentes incluidos |
|---|---|
| **unit-1: ingestion-pipeline** | `IngestionOrchestrator`, `PDFExtractor`, `EmbeddingGenerator`, `VectorDBRepository`, `BedrockLLMProvider` |
| **unit-2: strands-agent** | `StrandsAgent`, todas las tools, `LLMProvider` Protocol, `BedrockLLMProvider`, `VectorDBRepository`, `S3Repository` |
| **unit-3: backend-api** | `WebSocketHandler`, `LeadsAPIHandler`, `AuthMiddleware`, `ChatSessionService`, `LeadService`, `NotificationService`, `PaymentService`, `LeadRepository`, `ConversationRepository` |
| **unit-4: frontend-widget** | `apps/widget` — `ChatWidget`, `MessageList`, `MessageBubble`, `InputBar`, `TypingIndicator`, `useWebSocket`, `useLocalStorage` |
| **unit-5: frontend-backoffice** | `apps/backoffice` — `LeadsTable`, `LeadDetail`, `ScoreBadge`, `MotivationBadge`, `EscalationBanner`, `TranscriptViewer`, `LoginForm` |

---

## AWS Services por Componente

| Servicio AWS | Componente que lo usa |
|---|---|
| Amazon Bedrock | `BedrockLLMProvider`, `EmbeddingGenerator` |
| AgentCore Runtime | `StrandsAgent` |
| AgentCore Memory | `StrandsAgent` |
| DynamoDB `dmc-leads` | `LeadRepository` |
| DynamoDB `dmc-conversations` | `ConversationRepository` |
| Amazon S3 | `S3Repository` |
| Amazon SES | `NotificationService` |
| API Gateway WebSocket | `WebSocketHandler` |
| API Gateway REST | `LeadsAPIHandler` |
| AWS Lambda | `WebSocketHandler`, `LeadsAPIHandler` |
| AWS Cognito | `AuthMiddleware`, `BackofficeApp` (Amplify SDK) |
| Mercado Pago API | `PaymentService` |
| Vector DB (TBD) | `VectorDBRepository` |
