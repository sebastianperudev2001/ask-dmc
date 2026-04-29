# Unit of Work — DMC Sales Agent

**Versión**: 1.0  
**Fecha**: 2026-04-28

---

## Modelo de Descomposición

El sistema se descompone en **5 unidades de trabajo** independientemente desplegables. Cada unidad corresponde a un servicio o aplicación con fronteras claras. La construcción es **secuencial** siguiendo el orden de dependencias técnicas.

```
[1] ingestion-pipeline
        ↓ (knowledge base poblada)
[2] strands-agent
        ↓ (agente desplegado en AgentCore)
[3] backend-api
        ↓ (API disponible)
[4] frontend-widget      [5] frontend-backoffice
    (paralelo posible una vez unit-3 disponible)
```

---

## Unit 1 — ingestion-pipeline

| Campo | Valor |
|---|---|
| **Directorio** | `services/ingestion/` |
| **Runtime** | Python script (ejecución manual o trigger S3 Lambda) |
| **Deployment** | Script local / Lambda opcional |

### Responsabilidad
Procesa los PDFs de brochures desde S3, extrae secciones estructuradas via Claude (Bedrock), genera embeddings y los almacena en el Vector DB. Es un proceso offline que debe ejecutarse antes de que el agente pueda responder con información de programas.

### Componentes incluidos
- `IngestionOrchestrator` — coordina el pipeline completo
- `PDFExtractor` — extrae 12 secciones por brochure via `LLMProvider`
- `EmbeddingGenerator` — genera embeddings con metadata por sección
- `BedrockLLMProvider` — implementación activa de `LLMProvider`
- `VectorDBRepository` — upsert de chunks (implementación TBD en NFR Design)
- `S3Repository` — lectura de PDFs y listado de brochures

### Criterios de entrada
- Brochures PDF disponibles en `s3://dmc-knowledge-base/brochures/`
- Variables de entorno configuradas: `BEDROCK_MODEL_ID`, `S3_BUCKET_NAME`, `AWS_REGION`
- Vector DB aprovisionado (tecnología decidida en NFR Design de esta unidad)

### Criterios de salida
- 12 brochures procesados (todos los PDFs del catálogo)
- Chunks con embeddings almacenados en Vector DB con metadata (`course_name`, `section_type`, `keywords`)
- `IngestionReport` generado con conteo de chunks por brochure
- Tests unitarios pasando con Hypothesis (PBT para extracción y embedding)

### Stories cubiertas
- US-17 — Ingestion de brochures PDF
- US-18 — Búsqueda semántica (infrastructure base)

---

## Unit 2 — strands-agent

| Campo | Valor |
|---|---|
| **Directorio** | `services/agent/` |
| **Runtime** | Python — Strands SDK |
| **Deployment** | AWS AgentCore Runtime |

### Responsabilidad
Agente conversacional principal con 4 tools. Gestiona el flujo BIENVENIDA→CIERRE/ESCALACIÓN usando AgentCore Memory. Usa `BedrockLLMProvider` via la interfaz `LLMProvider` (Protocol). Desplegado en AgentCore Runtime — el backend lo invoca via SDK.

### Componentes incluidos
- `StrandsAgent` — agente principal con system prompt y tools wiring
- `SearchCoursesTool` — consulta Vector DB para chunks relevantes
- `QualifyLeadTool` — calcula motivación y score signals (lógica pura)
- `GeneratePaymentLinkTool` — invoca endpoint de backend para link Mercado Pago
- `GetBrochureUrlTool` — genera presigned URL de S3 del brochure recomendado
- `BedrockLLMProvider` — implementación `LLMProvider` Protocol
- `VectorDBRepository` — búsqueda semántica (misma implementación que unit-1)
- `S3Repository` — presigned URLs

### Criterios de entrada
- Unit 1 completada (Vector DB con knowledge base poblada)
- `AGENTCORE_RUNTIME_ID` configurado
- `BEDROCK_MODEL_ID` y `AWS_REGION` disponibles
- Endpoint de backend para `generate_payment_link` conocido (puede ser mock en esta etapa)

### Criterios de salida
- Agente desplegado y accesible en AgentCore Runtime
- 4 tools funcionando con tests unitarios
- Evals pasando: happy path A, happy path B, guardrails (anti-alucinación, no-competitor, scope), RAG quality
- PBT con Hypothesis para `QualifyLeadTool` (clasificación de motivación)

### Stories cubiertas
- US-01, US-02, US-03, US-04, US-05, US-06 (flujo conversacional vía tools)
- US-09, US-10, US-11, US-12 (guardrails)
- US-18 (búsqueda semántica — tool runtime)

---

## Unit 3 — backend-api

| Campo | Valor |
|---|---|
| **Directorio** | `services/backend/` |
| **Runtime** | Python — FastAPI + Mangum |
| **Deployment** | AWS Lambda + API Gateway (WebSocket + REST) |

### Responsabilidad
Capa thin de backend: gestiona conexiones WebSocket, invoca al agente en AgentCore Runtime, persiste leads y conversaciones en DynamoDB, envía notificaciones SES, genera links de pago Mercado Pago. Expone también endpoints REST para el backoffice.

### Componentes incluidos
- `WebSocketHandler` — `$connect`, `$disconnect`, `$default`
- `LeadsAPIHandler` — `GET /admin/leads`, `GET /admin/leads/{id}` (FastAPI + Mangum)
- `AuthMiddleware` — validación JWT Cognito
- `ChatSessionService` — invoca `StrandsAgent`, streaming via `post_to_connection`
- `LeadService` — create/qualify/score/finalize/flag_escalation
- `NotificationService` — SES email al equipo comercial
- `PaymentService` — Mercado Pago Checkout API
- `LeadRepository` — DynamoDB `dmc-leads`
- `ConversationRepository` — DynamoDB `dmc-conversations` (con `current_state`)
- `S3Repository` — presigned URLs (para backoffice si aplica)

### Criterios de entrada
- Unit 2 completada (agente desplegado en AgentCore Runtime, `AGENTCORE_RUNTIME_ID` disponible)
- Tablas DynamoDB `dmc-leads` y `dmc-conversations` aprovisionadas
- Cognito User Pool configurado con admin@dmc.pe
- SES verificado para `SES_FROM_EMAIL` y `SES_SALES_EMAIL`
- `MERCADO_PAGO_ACCESS_TOKEN` (sandbox) disponible

### Criterios de salida
- WebSocket API funcionando end-to-end con el agente
- REST API respondiendo a lista/detalle de leads con auth
- Lead persistido correctamente en DynamoDB al finalizar conversación
- Email SES enviado al escalar a humano
- Tests unitarios (PBT con Hypothesis para scoring, motivation detection) pasando
- Tests de integración para WebSocket handler y REST API pasando

### Stories cubiertas
- US-05 (cierre — persistencia del lead)
- US-06 (escalación — flag + SES)
- US-13 (auth Cognito — backend validation)
- US-14, US-15, US-16 (backoffice REST API)

---

## Unit 4 — frontend-widget

| Campo | Valor |
|---|---|
| **Directorio** | `apps/widget/` |
| **Runtime** | TypeScript — Next.js |
| **Deployment** | Vercel |

### Responsabilidad
Chat widget embebible (demo como página standalone `/`). Gestiona la conexión WebSocket con el backend, renderiza mensajes en streaming token a token, persiste identidad del visitante en localStorage.

### Componentes incluidos
- `ChatWidget` — root component, estado global del chat
- `MessageList` — lista scrollable de mensajes
- `MessageBubble` — burbuja individual (agent | user), soporte de markdown básico
- `InputBar` — input de texto + botón enviar + estado de loading
- `TypingIndicator` — animación de streaming en progreso
- `useWebSocket` — conexión WS, reconexión automática, recepción de tokens
- `useLocalStorage` — persistencia de `name` y `email` del visitante

### Criterios de entrada
- Unit 3 completada (WebSocket API disponible en API Gateway)
- `WS_URL` configurado en variables de entorno de Vercel

### Criterios de salida
- Widget renderiza y conecta correctamente al WebSocket
- Mensajes en streaming se muestran token a token
- Re-identificación funciona (datos de localStorage enviados al agente en primer mensaje)
- Reconexión automática en caso de desconexión

### Stories cubiertas
- US-01 (bienvenida — frontend display)
- US-02 (captura datos — localStorage)
- US-03, US-04, US-05, US-06 (flujo conversacional — UI)

---

## Unit 5 — frontend-backoffice

| Campo | Valor |
|---|---|
| **Directorio** | `apps/backoffice/` |
| **Runtime** | TypeScript — Next.js |
| **Deployment** | Vercel (mismo proyecto que widget, rutas `/admin/*`) |

### Responsabilidad
Portal de gestión de leads para el equipo comercial. Autenticación con AWS Cognito via Amplify SDK. Vistas de lista y detalle de leads con filtros, badges de score y motivación, banner de escalación y transcripción colapsable.

### Componentes incluidos
- `LoginForm` — formulario Amplify + Cognito
- Auth guard en `app/admin/layout.tsx`
- `LeadsTable` — tabla con filtros (score, motivación, fechas)
- `LeadRow` — fila con badges
- `LeadDetail` — vista completa con todos los campos del lead
- `ScoreBadge` — hot/warm/cold con colores
- `MotivationBadge` — categoría de motivación con cita textual
- `EscalationBanner` — destacado para `escalated_to_human: true`
- `TranscriptViewer` — sección colapsable con mensajes de `dmc-conversations`
- `useLeads` — fetch de lista con filtros
- `useAuth` — estado de autenticación Cognito

### Criterios de entrada
- Unit 3 completada (REST API disponible)
- Cognito User Pool configurado con admin@dmc.pe
- `NEXT_PUBLIC_API_URL` y `NEXT_PUBLIC_COGNITO_*` configurados en Vercel

### Criterios de salida
- Login/logout funcionando con Cognito
- Rutas `/admin/*` protegidas — redirigen a `/login` si no autenticado
- Lista de leads renderiza con filtros funcionales
- Detalle de lead muestra todos los campos, transcripción colapsable
- Leads escalados visualmente distinguibles

### Stories cubiertas
- US-13 (auth Cognito — frontend)
- US-14 (lista de leads)
- US-15 (detalle del lead)
- US-16 (leads escalados)
