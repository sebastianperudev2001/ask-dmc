# Component Dependencies — DMC Sales Agent

**Fecha**: 2026-04-28

---

## Dependency Matrix

| Componente | Depende de |
|---|---|
| `WebSocketHandler` | `ChatSessionService`, API Gateway Management API |
| `LeadsAPIHandler` | `LeadRepository`, `ConversationRepository`, `AuthMiddleware` |
| `AuthMiddleware` | Cognito JWKS endpoint |
| `ChatSessionService` | `StrandsAgent`, API Gateway Management API |
| `LeadService` | `LeadRepository`, `NotificationService` |
| `NotificationService` | Amazon SES |
| `PaymentService` | Mercado Pago API, `LeadRepository` |
| `StrandsAgent` | `LLMProvider`, `SearchCoursesTool`, `QualifyLeadTool`, `GeneratePaymentLinkTool`, `GetBrochureUrlTool`, AgentCore Memory |
| `SearchCoursesTool` | `VectorDBRepository` |
| `QualifyLeadTool` | _(pure logic, no external deps)_ |
| `GeneratePaymentLinkTool` | `PaymentService` (via HTTP to Lambda endpoint) |
| `GetBrochureUrlTool` | `S3Repository` |
| `BedrockLLMProvider` | Amazon Bedrock |
| `VectorDBRepository` (impl) | Vector DB (TBD en NFR Design) |
| `LeadRepository` | DynamoDB `dmc-leads` |
| `ConversationRepository` | DynamoDB `dmc-conversations` |
| `S3Repository` | Amazon S3 |
| `IngestionOrchestrator` | `S3Repository`, `PDFExtractor`, `EmbeddingGenerator`, `VectorDBRepository` |
| `PDFExtractor` | `LLMProvider` |
| `EmbeddingGenerator` | Amazon Bedrock Embeddings |
| `ChatWidget` | Backend WebSocket API |
| `BackofficeApp` | Backend REST API, Cognito (Amplify SDK) |

---

## Data Flow Diagrams

### Flujo 1 — Mensaje de chat (runtime principal)

```
Visitante
    │ WebSocket message
    ▼
API Gateway (WebSocket)
    │ $default route → Lambda
    ▼
WebSocketHandler.handle_message(event)
    │ connectionId (in-memory), session_id, user_message
    ▼
ChatSessionService.process_message()
    │ invoke
    ▼
StrandsAgent (AgentCore Runtime)
    ├── AgentCore Memory ←→ historial de conversación
    ├── SearchCoursesTool → VectorDBRepository → Vector DB
    ├── QualifyLeadTool → LeadQualification (in-memory)
    ├── GeneratePaymentLinkTool → PaymentService → Mercado Pago API
    │                          → LeadRepository → DynamoDB dmc-leads
    └── GetBrochureUrlTool → S3Repository → S3 presigned URL
    │ streaming tokens
    ▼
ChatSessionService → post_to_connection(connectionId, token)
    │
    ▼
API Gateway → WebSocket → ChatWidget (Next.js) → Visitante
```

### Flujo 2 — Finalización de sesión y persistencia del lead

```
StrandsAgent (detecta CIERRE o ESCALACIÓN)
    │
    ▼
LeadService.finalize(lead_id)  ──OR──  LeadService.flag_escalation(lead_id)
    │                                          │
    ├── LeadRepository.update()                ├── LeadRepository.update(escalated_to_human: true)
    │   → DynamoDB dmc-leads                   └── NotificationService.notify_escalation()
    │                                                  → Amazon SES → email equipo comercial
    └── ConversationRepository.save_message()
        → DynamoDB dmc-conversations
          (includes current_state for observability)
```

### Flujo 3 — Backoffice (lista y detalle de leads)

```
Equipo Comercial (browser)
    │ GET /admin/leads  (con JWT en Authorization header)
    ▼
BackofficeApp (Next.js /admin)
    │ fetch → REST API
    ▼
API Gateway (REST) → Lambda
    │
    ▼
LeadsAPIHandler.list_leads()
    ├── AuthMiddleware.validate_token() → CognitoClaims
    └── LeadRepository.list(filters) → DynamoDB dmc-leads
    │
    ▼
LeadDetailResponse (incluye lead data)
    │ [si se accede al detalle con transcripción]
    └── ConversationRepository.get_messages(lead_id) → DynamoDB dmc-conversations
```

### Flujo 4 — Ingestion Pipeline (offline)

```
Operador DMC
    │ ejecuta script manualmente (o trigger S3)
    ▼
IngestionOrchestrator.run(bucket, prefix)
    │
    ├── S3Repository.list_brochures() → [pdf keys]
    │
    └── [por cada PDF]
            ├── S3Repository.get_object() → pdf_bytes
            │
            ├── PDFExtractor.extract()
            │       └── LLMProvider (BedrockLLMProvider) → Claude claude-sonnet-4-6
            │           → list[BrochureSection] (12 secciones estructuradas)
            │
            ├── EmbeddingGenerator.generate()
            │       └── Bedrock Embeddings API
            │           → list[EmbeddedChunk] (text + vector + metadata)
            │
            └── VectorDBRepository.upsert(chunks)
                    → Vector DB (tecnología TBD)
```

---

## Communication Patterns

| Patrón | Usado por |
|---|---|
| **WebSocket (streaming)** | ChatWidget ↔ API Gateway ↔ Lambda |
| **HTTP síncrono (REST)** | BackofficeApp ↔ API Gateway ↔ Lambda |
| **AWS SDK (boto3)** | Lambda → DynamoDB, S3, SES, Bedrock, AgentCore |
| **HTTP externo** | Lambda → Mercado Pago API |
| **Protocol / DI** | Toda la capa de infraestructura (LLMProvider, VectorDBRepository) |
| **AgentCore invoke** | ChatSessionService → StrandsAgent (AgentCore Runtime) |

---

## Coupling Rules

1. **La capa de infraestructura es la única que toca AWS SDK directamente** — servicios de aplicación solo conocen repositorios/providers via Protocol.
2. **StrandsAgent no conoce LeadService** — el agente solo usa sus tools. La persistencia del lead es responsabilidad del backend (ChatSessionService señaliza cuando el agente termina).
3. **Frontend no accede a DynamoDB** — todo pasa por el backend REST API.
4. **Ingestion Pipeline es completamente independiente del runtime de chat** — no hay dependencias compartidas en runtime.
