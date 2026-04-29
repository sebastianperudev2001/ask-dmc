# Components — DMC Sales Agent

**Fecha**: 2026-04-28

---

## Capa: Infrastructure

### LLMProvider (Protocol)
**Responsabilidad**: Define el contrato de acceso al LLM. Ningún módulo fuera de esta capa invoca a Bedrock directamente.  
**Tipo**: Interface (Python `typing.Protocol`)  
**Interfaces expuestas**:
- `complete(messages, system, **kwargs) -> str`
- `stream(messages, system, **kwargs) -> AsyncIterator[str]`

### BedrockLLMProvider
**Responsabilidad**: Implementación activa de `LLMProvider` usando Amazon Bedrock (`anthropic.claude-sonnet-4-6`).  
**Tipo**: Concrete class implementing `LLMProvider` Protocol  
**Dependencias**: `boto3.client("bedrock-runtime")`

### VectorDBRepository (Protocol)
**Responsabilidad**: Abstracción de la base de datos vectorial. Tecnología concreta se decide en NFR Design.  
**Tipo**: Interface (Protocol)  
**Interfaces expuestas**:
- `search(query, profile, top_k) -> list[Chunk]`
- `upsert(chunks) -> None`
- `delete(chunk_ids) -> None`

### LeadRepository
**Responsabilidad**: CRUD sobre la tabla DynamoDB `dmc-leads`.  
**Tipo**: Concrete class  
**Interfaces expuestas**:
- `save(lead) -> None`
- `get_by_id(lead_id) -> Lead | None`
- `get_by_email(email) -> Lead | None`
- `list(filters) -> list[Lead]`
- `update(lead_id, updates) -> None`

### ConversationRepository
**Responsabilidad**: Persistencia de mensajes individuales en `dmc-conversations`. Cada mensaje incluye `current_state` del funnel para observabilidad.  
**Tipo**: Concrete class  
**Interfaces expuestas**:
- `save_message(lead_id, message) -> None`
- `get_messages(lead_id) -> list[ConversationMessage]`

### S3Repository
**Responsabilidad**: Operaciones sobre S3 — generación de presigned URLs y listado de brochures.  
**Tipo**: Concrete class  
**Interfaces expuestas**:
- `generate_presigned_url(key, expiry_seconds) -> str`
- `list_brochures() -> list[str]`

---

## Capa: Agent

### StrandsAgent
**Responsabilidad**: Agente conversacional principal. Gestiona el flujo BIENVENIDA→CIERRE/ESCALACIÓN usando AgentCore Memory como fuente de verdad del estado conversacional. Desplegado en AgentCore Runtime.  
**Tipo**: Strands Agent (AgentCore Runtime)  
**Interfaces expuestas**:
- `invoke(session_id, user_message) -> AsyncIterator[str]`

### SearchCoursesTool
**Responsabilidad**: Tool del agente para consultar la knowledge base con perfil del visitante y retornar chunks relevantes de brochures.  
**Tipo**: Strands Tool  
**Interfaces expuestas**:
- `execute(query, user_profile) -> list[CourseChunk]`

### QualifyLeadTool
**Responsabilidad**: Tool del agente para calcular motivación detectada y score del lead basado en el contexto conversacional acumulado.  
**Tipo**: Strands Tool  
**Interfaces expuestas**:
- `execute(conversation_context) -> LeadQualification`

### GeneratePaymentLinkTool
**Responsabilidad**: Tool del agente para generar un link de pago Mercado Pago (sandbox) cuando el visitante muestra intención de compra.  
**Tipo**: Strands Tool  
**Interfaces expuestas**:
- `execute(course_name, lead_id) -> str`

### GetBrochureUrlTool
**Responsabilidad**: Tool del agente para obtener una presigned URL de S3 del brochure PDF del programa recomendado.  
**Tipo**: Strands Tool  
**Interfaces expuestas**:
- `execute(course_name) -> str`

---

## Capa: Ingestion Pipeline

### IngestionOrchestrator
**Responsabilidad**: Coordina el pipeline completo: leer PDFs de S3 → extraer secciones → generar embeddings → guardar en VectorDB.  
**Tipo**: Script Python (ejecución manual o trigger S3)  
**Interfaces expuestas**:
- `run(bucket, prefix) -> IngestionReport`

### PDFExtractor
**Responsabilidad**: Usa `LLMProvider` para extraer las secciones estructuradas de cada brochure PDF según el schema definido (12 secciones).  
**Tipo**: Concrete class  
**Interfaces expuestas**:
- `extract(pdf_bytes, course_name) -> list[BrochureSection]`

### EmbeddingGenerator
**Responsabilidad**: Genera embeddings por sección de brochure con metadata (`course_name`, `section_type`, `keywords`).  
**Tipo**: Concrete class  
**Interfaces expuestas**:
- `generate(sections) -> list[EmbeddedChunk]`

---

## Capa: Backend Application (Lambda)

### WebSocketHandler
**Responsabilidad**: Handler Lambda para rutas WebSocket (`$connect`, `$disconnect`, `$default`). Gestiona el ciclo de vida de la conexión y delega mensajes a `ChatSessionService`. El `connectionId` se obtiene del evento y se usa en memoria — no se persiste.  
**Tipo**: Lambda handler function  
**Interfaces expuestas**:
- `handle_connect(event) -> dict`
- `handle_disconnect(event) -> dict`
- `handle_message(event) -> dict`

### LeadsAPIHandler
**Responsabilidad**: Handler Lambda para endpoints REST del backoffice (lista y detalle de leads). Protegido por `AuthMiddleware`.  
**Tipo**: Lambda handler function (FastAPI + Mangum)  
**Interfaces expuestas**:
- `list_leads(event) -> dict`
- `get_lead(lead_id, event) -> dict`

### AuthMiddleware
**Responsabilidad**: Valida JWT de Cognito en cada request al backoffice. Rechaza requests sin token o con token inválido/expirado.  
**Tipo**: FastAPI middleware / decorator  
**Interfaces expuestas**:
- `validate_token(token) -> CognitoClaims`
- `require_auth(handler) -> Callable`

### ChatSessionService
**Responsabilidad**: Orquesta el flujo de un mensaje WebSocket: invoca al `StrandsAgent` en AgentCore Runtime, hace streaming de tokens al cliente via `post_to_connection`, y señaliza a `LeadService` cuando la sesión finaliza.  
**Tipo**: Service class  
**Interfaces expuestas**:
- `process_message(connection_id, session_id, message) -> AsyncIterator[str]`

### LeadService
**Responsabilidad**: Lógica de negocio de leads — creación, actualización de calificación, scoring, finalización y flagging de escalación.  
**Tipo**: Service class  
**Interfaces expuestas**:
- `create_or_get(email, name) -> Lead`
- `update_qualification(lead_id, qualification) -> None`
- `score_lead(lead_id, signals) -> LeadScore`
- `finalize(lead_id) -> None`
- `flag_escalation(lead_id) -> None`

### NotificationService
**Responsabilidad**: Envía email de notificación via Amazon SES al equipo comercial cuando un lead solicita contacto humano.  
**Tipo**: Service class  
**Interfaces expuestas**:
- `notify_escalation(lead) -> None`

### PaymentService
**Responsabilidad**: Genera links de pago via Mercado Pago Checkout API (sandbox).  
**Tipo**: Service class  
**Interfaces expuestas**:
- `create_payment_link(course_name, lead_id) -> str`

---

## Capa: Frontend (Turborepo)

### apps/widget — ChatWidget (Next.js)
**Responsabilidad**: Interfaz de chat flotante embebible. Gestiona la conexión WebSocket, renderiza la conversación en streaming, persiste identidad del visitante en localStorage.  
**Componentes principales**: `ChatWidget`, `MessageList`, `MessageBubble`, `InputBar`, `TypingIndicator`  
**Hooks**: `useWebSocket`, `useLocalStorage`

### apps/backoffice — BackofficeApp (Next.js)
**Responsabilidad**: Portal `/admin/*` para el equipo comercial. Auth con Cognito via Amplify SDK, lista y detalle de leads, filtros, vista de escalados.  
**Componentes principales**: `LeadsTable`, `LeadDetail`, `ScoreBadge`, `MotivationBadge`, `EscalationBanner`, `TranscriptViewer`, `LoginForm`

### packages/ui — Shared UI
**Responsabilidad**: Componentes de UI compartidos entre widget y backoffice (design tokens, Badge base, utilidades).  
**Componentes**: `Badge`, `Button`, design tokens (colors, spacing, typography)
