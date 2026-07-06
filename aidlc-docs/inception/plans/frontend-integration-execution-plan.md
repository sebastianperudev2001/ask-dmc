# Execution Plan — Agent-Service Incremento 2 + Integración apps/chat

**Fecha**: 2026-07-06
**Basado en**: `aidlc-docs/inception/requirements/frontend-integration-requirements.md`

---

## Detailed Analysis Summary

### Transformation Scope (Brownfield)
- **Transformation Type**: Arquitectural, dentro de las fronteras de 2 componentes ya existentes (no se crean nuevas unidades)
- **Primary Changes**:
  - `services/agent-service`: nuevo protocolo conversacional multi-turno con tool-calling sobre `/ws/chat` (renombrado desde `/ws/recommendation`), 2 tools nuevos (`collect_profile_data`, `create_payment_link`), integración Culqi (Orders API v2 + webhook), persistencia de leads/conversaciones en Postgres, lead scoring, uso de Azure AI Foundry Agent Memory para persistencia de sesión
  - `apps/chat`: nuevo componente de widget de recolección de datos (detecta tool-call en streaming), nueva UI de tarjetas de recomendación de curso (reemplaza `SourceChips`), nueva página de checkout (`/pagar`) que integra Culqi Checkout v4 JS
- **Related Components**: Ninguna unidad nueva — el trabajo cae dentro de `unit-2` (agent-service, redefinida por DIV-10) y de lo que originalmente era `unit-4: frontend-widget` (ahora implementado como `apps/chat`, fuera del tracking formal de unidades hasta ahora — se formaliza en este plan)

### Change Impact Assessment
- **User-facing changes**: Sí — nueva UI de widget de datos, tarjetas de recomendación, página de checkout; el chat pasa de "una pregunta → una recomendación" a una conversación de ventas completa
- **Structural changes**: Sí — protocolo WS extendido con tool-calling; nuevo endpoint HTTP de webhook en `agent-service`
- **Data model changes**: Sí — nuevas tablas Postgres para leads/conversaciones/scoring (reemplazan el diseño DynamoDB original, DIV-13)
- **API changes**: Sí — `/ws/recommendation` → `/ws/chat` con mensajes nuevos (`user_message`, `profile_data_submitted`) + webhook HTTP nuevo
- **NFR impact**: Sí — nuevo secreto externo (Culqi) en Key Vault, verificación de autenticidad de webhook, PII en Postgres (nombre/email de leads) bajo la extensión Security Baseline ya habilitada

### Component Relationships
```
apps/chat (frontend, ex "unit-4: frontend-widget")
    │  WebSocket /ws/chat (tool-calling, streaming)
    ▼
services/agent-service (unit-2 redefinida, Azure)
    │  usa: Azure AI Foundry Persistent Agent + Memory (ya existente, incremento 1)
    │  usa: Postgres (ya existente, incremento 1 — se agregan tablas leads/conversaciones)
    │  nuevo: Azure Key Vault (secreto Culqi)
    │  nuevo: llamadas salientes a Culqi Orders API v2
    │  nuevo: webhook entrante desde Culqi (order.status.changed)
    ▼
Culqi (proveedor de pago externo, fuera del control del proyecto)
```

### Risk Assessment
- **Risk Level**: **Medium-High**
- **Rollback Complexity**: Moderada — cambios aditivos en su mayoría (nuevas tablas, nuevo endpoint), pero el renombre de `/ws/recommendation` → `/ws/chat` y el cambio de protocolo son breaking changes para cualquier cliente existente (mitigado: el único cliente es `apps/chat`, actualizado en el mismo incremento)
- **Testing Complexity**: Compleja — requiere verificar en la práctica que el Agent Framework de Azure expone eventos de tool-call distinguibles durante streaming (riesgo técnico no confirmado aún; el historial de este proyecto ya mostró divergencias entre la documentación asumida y el SDK real de `agent-framework-foundry`, ver hallazgos previos en `audit.md` sobre `FoundryChatClient`). **Recomendación**: verificar esto con un spike técnico al inicio de Functional Design, antes de comprometer el diseño del protocolo de streaming.

---

## Phases to Execute

### 🔵 INCEPTION PHASE
- [x] Workspace Detection — reutilizado (proyecto existente)
- [x] Requirements Analysis — COMPLETED and APPROVED (2026-07-06)
- [ ] User Stories — SKIPPED
  - **Rationale**: comportamiento de usuario ya cubierto por `stories.md` de la visión original; este incremento reimplementa esa visión sobre Azure, no agrega funcionalidad nueva de cara al usuario
- [x] Workflow Planning — IN PROGRESS (este documento)
- [ ] Application Design — **SKIP**
  - **Rationale**: no se crean nuevas unidades ni servicios; los cambios (tools, webhook, componentes de UI) caen dentro de las fronteras de los 2 componentes existentes (agent-service, apps/chat)
- [ ] Units Generation — **SKIP**
  - **Rationale**: se reutilizan las unidades ya definidas en `unit-of-work.md` (unit-2 agent-service redefinida por DIV-10; `apps/chat` corresponde a la antigua `unit-4: frontend-widget`, ahora formalizada como unidad activa en este plan)

### 🟢 CONSTRUCTION PHASE

**Unit: agent-service (incremento 2) — se construye primero (dependencia: apps/chat consume su contrato)**
- [ ] Functional Design — **EXECUTE**
  - **Rationale**: nueva lógica de negocio sustancial — tools (`collect_profile_data`, `create_payment_link`), lógica de sales-advisor system prompt, lead scoring, schema de mensajes WS, modelo de datos Postgres para leads/conversaciones, lógica del webhook de Culqi. Incluye spike técnico de verificación de tool-calling en streaming con Azure Agent Framework antes de finalizar el diseño del protocolo
- [ ] NFR Requirements — **EXECUTE**
  - **Rationale**: nuevo secreto externo (Culqi) requiere decisión de Key Vault; PII de leads en Postgres bajo Security Baseline; verificación de autenticidad de webhooks es una NFR de seguridad nueva no cubierta en incremento 1
- [ ] NFR Design — **EXECUTE**
  - **Rationale**: incorporar patrones para idempotencia/reintentos del webhook, gestión de threads de Foundry Memory, y el patrón de tool-calling en streaming
- [ ] Infrastructure Design — **EXECUTE**
  - **Rationale**: nuevo recurso Azure Key Vault; nuevas tablas/migración Postgres; nueva ruta HTTP (webhook) en el Container App existente — sin nuevos recursos de cómputo dado que el alcance de despliegue sigue siendo local por decisión del usuario
- [ ] Code Generation — **EXECUTE (ALWAYS)**

**Unit: apps/chat (ex "frontend-widget") — se construye después, consumiendo el contrato de agent-service**
- [ ] Functional Design — **EXECUTE (ligero)**
  - **Rationale**: nuevos componentes de UI con lógica de interacción (detección de tool-call en el stream, widget de datos, tarjetas de recomendación, página de checkout) — no son cambios triviales de estilo, requieren definir el flujo de estado del componente
- [ ] NFR Requirements — **SKIP**
  - **Rationale**: sin nuevas NFRs — sigue sin auth, sin CORS/producción (alcance local decidido en Requirements Analysis), sin requisitos de escalabilidad nuevos para un frontend de demo
- [ ] NFR Design — **SKIP** (consecuencia de NFR Requirements skip)
- [ ] Infrastructure Design — **SKIP**
  - **Rationale**: sin infraestructura nueva — sigue siendo `next dev` local; Culqi Checkout v4 se carga como script externo desde el navegador, sin backend propio adicional
- [ ] Code Generation — **EXECUTE (ALWAYS)**

- [ ] Build and Test — **EXECUTE (ALWAYS)**
  - **Rationale**: verificación end-to-end del flujo conversacional completo (chat libre → tool-call → widget → recomendación → pago Culqi sandbox → webhook → escalación), igual que se hizo para incremento 1

### 🟡 OPERATIONS PHASE
- [ ] Operations — PLACEHOLDER

---

## Estimated Timeline
- **Total Stages a ejecutar**: 9 (Functional Design ×2, NFR Requirements ×1, NFR Design ×1, Infrastructure Design ×1, Code Generation ×2, Build and Test ×1)
- **Estimated Duration**: Comparable o mayor al incremento 1 (que incluyó las mismas 5 etapas para un alcance más acotado) — el mayor riesgo de tiempo es el spike de verificación de tool-calling en streaming

## Success Criteria
- **Primary Goal**: Un usuario puede sostener una conversación de ventas libre en `apps/chat`, ser guiado a completar sus datos vía widget cuando el agente lo requiera, recibir una recomendación de curso, generar un link de pago Culqi real (sandbox) y completar el pago, con el lead persistido y scored en Postgres
- **Key Deliverables**: Endpoint `/ws/chat` funcional con tool-calling; tools `collect_profile_data` y `create_payment_link`; página `/pagar`; webhook de confirmación de Culqi; tablas Postgres de leads/conversaciones; UI de widget y tarjetas de recomendación en `apps/chat`
- **Quality Gates**: Suite de tests (unit + integración) en verde para ambos componentes; verificación manual end-to-end similar a la realizada para incremento 1 (con Culqi en modo sandbox real, no mockeado)
- **Integration Testing**: Flujo completo frontend↔backend↔Culqi verificado de punta a punta en local
