# Application Design Plan — DMC Sales Agent

## Execution Checklist

- [x] Responder preguntas de diseño
- [x] Generar `components.md` — componentes e interfaces
- [x] Generar `component-methods.md` — firmas de métodos por componente
- [x] Generar `services.md` — capa de servicios y orquestación
- [x] Generar `component-dependency.md` — dependencias y flujo de datos
- [x] Generar `application-design.md` — documento consolidado
- [x] Validar consistencia del diseño
- [x] Actualizar checkboxes y aidlc-state.md

---

## Component Map (Propuesto)

El sistema se organiza en 5 capas:

```
┌──────────────────────────────────────────────────────┐
│                   FRONTEND LAYER                     │
│  ChatWidget (Next.js /)  │  BackofficeApp (/admin/*) │
└──────────────────────────────────────────────────────┘
                    │ WebSocket / REST
┌──────────────────────────────────────────────────────┐
│              BACKEND APPLICATION LAYER               │
│  WebSocketHandler │ LeadsAPIHandler │ AuthMiddleware  │
│       ChatSessionService │ LeadService               │
│   NotificationService │ PaymentService               │
└──────────────────────────────────────────────────────┘
                    │ invoke
┌──────────────────────────────────────────────────────┐
│                   AGENT LAYER                        │
│           StrandsAgent (AgentCore Runtime)           │
│  SearchCoursesTool │ QualifyLeadTool                 │
│  GeneratePaymentLinkTool │ GetBrochureUrlTool        │
└──────────────────────────────────────────────────────┘
                    │ via LLMProvider
┌──────────────────────────────────────────────────────┐
│               INFRASTRUCTURE LAYER                   │
│  LLMProvider (interface) → BedrockLLMProvider        │
│  VectorDBRepository │ LeadRepository                 │
│  ConversationRepository │ S3Repository               │
└──────────────────────────────────────────────────────┘
                    │ (ingestion)
┌──────────────────────────────────────────────────────┐
│               INGESTION PIPELINE                     │
│  IngestionOrchestrator │ PDFExtractor                │
│  EmbeddingGenerator │ VectorDBRepository             │
└──────────────────────────────────────────────────────┘
```

---

## Preguntas de Diseño

Responde cada `[Answer]:` antes de proceder a la generación.

---

### Q1 — WebSocket connection state management (Resuelta en conversación)

Lambda WebSocket requiere almacenar el `connectionId` de API Gateway para poder hacer push de respuestas al cliente. Opciones:

**A.** Nueva tabla DynamoDB `dmc-connections` — almacena `connectionId` + `lead_id` (si ya fue identificado) + `session_metadata`. Se crea en `$connect` y se elimina en `$disconnect`.

**B.** Campo `connection_id` en la tabla `dmc-leads` — se setea al conectar y se limpia al desconectar. Más simple pero mezcla responsabilidades.

**C.** Sin estado de conexión explícito — el agente responde sincrónicamente dentro del mismo invocation de Lambda (sin necesidad de push separado). Las respuestas en streaming se envían directamente desde el mismo handler.

[Answer]: C — Sin estado explícito. El connectionId se usa directamente desde el evento Lambda dentro del mismo invocation. Diseño síncrono.

---

### Q2 — Funnel state machine: ¿dónde vive el estado?

El flujo BIENVENIDA → IDENTIFICACIÓN → CALIFICACIÓN → RECOMENDACIÓN → CIERRE/ESCALACIÓN necesita persistirse entre turnos de conversación. Opciones:

**A.** **AgentCore Memory exclusivamente** — el agente gestiona su propio estado conversacional via `AgentCore Memory`. El backend no trackea el estado del funnel; confía en que el agente lo mantenga.

**B.** **AgentCore Memory + campo `current_state` en `dmc-conversations`** — cada mensaje guardado en `dmc-conversations` incluye el estado del funnel en ese momento. Permite observabilidad sin que el backend necesite leer el estado.

**C.** **Campo `current_state` en `dmc-connections`** — el backend trackea el estado del funnel independientemente del agente. Permite que el backend tome decisiones basadas en el estado (ej. saber cuándo persistir el lead final).

[Answer]: B — AgentCore Memory como fuente de verdad del agente + `current_state` en cada mensaje de `dmc-conversations` para observabilidad.

---

### Q3 — Estructura del proyecto Next.js

ChatWidget (`/`) y Backoffice (`/admin/*`) comparten el mismo proyecto Next.js. ¿Cómo se organiza internamente?

**A.** **Single Next.js app con separación por rutas** — `src/app/page.tsx` (widget demo), `src/app/admin/` (backoffice). Componentes compartidos en `src/components/shared/`. Simple y directo.

**B.** **Separación explícita por dominio en directorios** — `src/widget/` (todos los componentes del chat), `src/backoffice/` (todos los componentes del admin), `src/shared/` (utilidades comunes). Mismo proyecto Next.js pero con fronteras de dominio claras en el filesystem.

**C.** **Turborepo monorepo** — `apps/widget/` y `apps/backoffice/` como apps Next.js separadas, con `packages/ui/` para componentes compartidos. Mayor overhead pero máximo aislamiento.

[Answer]: C — Turborepo monorepo: `apps/widget`, `apps/backoffice`, `packages/ui`.

---

### Q4 — LLMProvider interface style (Python)

La capa agnóstica `LLMProvider` define el contrato para acceso al LLM. ¿Qué estilo de interfaz preferís para Python?

**A.** **Abstract Base Class (ABC)** — `class LLMProvider(ABC)` con `@abstractmethod`. Implementaciones heredan explícitamente. Más tradicional, mejor soporte en IDEs.

**B.** **Protocol (structural typing)** — `class LLMProvider(Protocol)` de `typing`. Duck typing: cualquier clase con los métodos correctos cumple la interfaz sin heredar. Más pythonico, compatible con Strands SDK patterns.

[Answer]: B — Protocol (structural typing).
