# Business Rules — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

---

### BR-01 — Filtro duro: presupuesto
Un `Course` es candidato solo si `course.price <= request.budget`. Presupuesto es un tope máximo, no un rango — no se recomiendan cursos por encima del presupuesto declarado, aunque sean semánticamente el mejor match (decisión del usuario: filtros duros son excluyentes, P5=A).

### BR-02 — Filtro duro: duración
Un `Course` es candidato solo si `course.duration_weeks <= request.max_duration_weeks`. La disponibilidad del interesado es un tope máximo de tiempo que puede dedicar.

### BR-03 — Relajación de filtros ante cero candidatos, con confirmación explícita del usuario
Si `BR-01` + `BR-02` no producen ningún candidato, el sistema **no relaja automáticamente ni en silencio**. En su lugar:

1. Se calcula — internamente, sin mostrarlo aún — un set de candidatos con criterios ampliados **simultáneamente**: `max_duration_weeks * 1.5` y `budget * 1.2` (decisión de diseño: relajación conjunta, no secuencial una-a-una — confirmar en revisión si se prefiere ofrecer las dos alternativas por separado).
2. **Si ese cálculo ampliado sí produce candidatos**: se le avisa al usuario que no hay match exacto y se le pregunta explícitamente si quiere ver alternativas aumentando hasta 50% la duración o 20% el presupuesto (`relax_filters_offer`, ver business-logic-model.md). El flujo **espera la respuesta del usuario** antes de continuar:
   - **Confirma** → se usan esos candidatos ampliados para el ranking semántico (BR-04 en adelante), marcando `filters_relaxed` en cada uno para que el LLM lo comunique con transparencia (ej. "este programa está ligeramente sobre tu presupuesto, pero es el más cercano a lo que buscas").
   - **Declina** → se muestra el catálogo completo (BR-11).
3. **Si ni siquiera el cálculo ampliado produce candidatos** (catálogo vacío o filtros extremos): no tiene sentido ofrecer una alternativa que tampoco existe — se va directo a mostrar el catálogo completo (BR-11), sin preguntar.

> La relajación simultánea (vs. secuencial) es una decisión de diseño por defecto — confirmar en revisión si se prefiere.

### BR-11 — Catálogo completo como última alternativa
Cuando el usuario declina ver alternativas relajadas (BR-03), o cuando ni la relajación produce candidatos, se listan **todos** los cursos del catálogo (sin límite de top-K, a diferencia de BR-05) ordenados por `similarity_score` descendente contra el `ProfileQuery` ya calculado — ninguno cumple los filtros duros originales, pero mantenerlos ordenados por afinidad semántica es mejor que un orden arbitrario. Ninguno de estos candidatos tiene `filters_relaxed` marcado como válido para BR-01/02 — el LLM debe dejar explícito que son todas las opciones disponibles, no una recomendación acotada.

### BR-04 — Ranking semántico solo sobre candidatos filtrados
El ranking por similitud de embeddings (`pgvector`) se calcula **únicamente** sobre los `Course` que ya pasaron BR-01/BR-02 — nunca sobre el catálogo completo. Esto evita que un curso semánticamente muy afín pero fuera de presupuesto/duración desplace a un candidato válido, y reduce el costo de la consulta vectorial.

### BR-05 — Top-K de recomendaciones
Se entregan al máximo **3** candidatos (`RecommendationCandidate`) al LLM, ordenados por `similarity_score` descendente — consistente con RF-07 del PRD original ("recomienda 1–3 programas del catálogo").

### BR-06 — Embeddings de curso pre-calculados, no por request
El `embedding` de cada `Course` se genera **una vez**, al cargar o actualizar el catálogo (seed data) — nunca en el momento de una recomendación. Solo el `ProfileQuery.query_embedding` se calcula por request. Esto mantiene el costo de Azure OpenAI acotado y la latencia de recomendación baja.

### BR-07 — El LLM solo puede referenciar datos de los candidatos entregados
El agente/LLM que compone `RecommendationResponse.message_stream` únicamente puede mencionar precio, duración, nombre, descripción y malla curricular (`curriculum`) de los `candidates` recibidos — no puede inventar precios, fechas de inicio, descuentos, temas fuera de la malla real ni cursos fuera de esa lista (alineado con el guardrail de no-alucinación de RF-07 del PRD original). Poder citar `curriculum` es lo que permite que el pitch sea específico (ej. "este programa incluye el módulo de Machine Learning que buscas") en vez de genérico. Esta es la única regla de guardrail activa en este incremento.

> Los guardrails más amplios (anti-competidor, scope de ventas, anti-alucinación general fuera de precio/fecha) siguen diferidos a backlog, tal como se decidió para el diseño anterior de `unit-2` (ver `business-rules.md` BR-07 de `strands-agent`, superseded pero con esta decisión aún vigente).

### BR-08 — Sin persistencia en este incremento
`RecommendationRequest`, `ProfileQuery` y `RecommendationResponse` son completamente efímeros — no se guardan en ninguna base de datos. La persistencia de leads/perfiles queda fuera de alcance (consistente con la separación de responsabilidades ya decidida: BR-10 del diseño `strands-agent` superseded, que asignaba la persistencia de leads a una unidad de backend separada).

### BR-09 — Campos del mini-form obligatorios
`budget`, `max_duration_weeks`, `professional_background` y `desired_stack` son todos obligatorios — el frontend no envía el `RecommendationRequest` por WebSocket hasta que el usuario completó los 4 campos del mini-form (validación en frontend, fuera de alcance de este backend).

### BR-10 — Identificación/calificación conversacional fuera de alcance
Este incremento **no** implementa el flujo de identificación (nombre/email) ni de calificación de 5 dimensiones que tenía el diseño original de `unit-2`. El perfil llega ya armado desde un mini-form — la conversación agéntica de identificación/calificación queda para el incremento 2 de `agent-service`.

> **Override (Incremento 2)**: BR-10 queda retomado — ver BR-16 y business-logic-model.md Sección 7 en adelante. La conversación agéntica de identificación/calificación ya es parte del alcance.

---

# Incremento 2 — Chat conversacional + tool-calling + pago + persistencia

**Fecha**: 2026-07-06

### BR-16 — El agente decide cuándo invocar cada tool
Ni `collect_profile_data` ni `create_payment_link` se invocan por un turno fijo o una regla determinística de la aplicación — es el propio agente (LLM) quien decide, guiado por su system prompt, cuándo necesita datos estructurados de calificación (invoca `collect_profile_data`) o cuándo el usuario expresó intención de compra (invoca `create_payment_link`). La aplicación solo reacciona a los `function_call`/`function_result` que el framework emite, no fuerza el momento de la invocación.

### BR-17 — Lead scoring (hot/warm/cold)
Hereda sin cambios los criterios de `requirements.md` §7:

| Score | Criterio |
|---|---|
| hot | Pidió link de pago o expresó decisión de compra |
| warm | Motivación clara + interés, sin decisión de compra |
| cold | Motivación vaga o solo curiosidad |

Pesos: intención de compra (alto), motivación definida (alto), fit de perfil con programa recomendado (medio), urgencia (medio), datos completos — nombre + email — (**obligatorio**: sin datos completos, el score nunca puede ser `hot`, independientemente de las demás señales).

**Nota (2026-07-06, Ronda 7 de Build and Test)**: `score_lead()` está implementada y testeada (BR-17), pero ninguna de sus señales (`motivation`, `purchase_intent`, `profile_fits_recommendation`, `urgent`, `has_complete_data`) se extrae todavía de la conversación libre — por lo que nunca se invocaba desde el flujo real y todo `Lead` quedaba en `cold` por defecto. Ver BR-17b para el mecanismo de piso agregado mientras esa extracción no exista.

### BR-17b — Piso de engagement por conteo de mensajes (complementa BR-17, no lo reemplaza)
Mientras la extracción de `motivation`/`purchase_intent`/`has_complete_data` (BR-17) no esté implementada, `Lead.score` se eleva mediante un piso basado en señales disponibles hoy:

| Condición | Piso mínimo |
|---|---|
| Completó el formulario (`collect_profile_data` confirmado) | `warm` |
| 5+ mensajes del usuario en la conversación | `warm` |
| 10+ mensajes del usuario en la conversación | `hot` |

Reglas:
- Solo cuenta mensajes **del usuario** (no las respuestas del bot).
- Es un **piso** (override hacia arriba): se combina con el score que `score_lead()` ya haya calculado tomando el máximo de ambos — nunca reemplaza ni ignora una señal real más fuerte.
- **Monotónico**: una vez alcanzado `warm`/`hot` para un `Lead`, no vuelve a bajar en esa conversación aunque el conteo de mensajes por sí solo ya no lo sostendría (evita "perder" un lead ya calificado).
- Se reevalúa después de cada mensaje del usuario (`ChatWebSocketHandler` → `ChatAgentClient.record_user_message()`) y al completar el formulario (`_collect_profile_data`).
- Implementado en `src/domain/lead_scoring.py` (`engagement_floor`, `apply_score_floor`) + `ChatAgentClient._apply_engagement_floor`.

### BR-18 — Manejo de error en `create_payment_link`
Si la llamada a la API de Preferencias de Mercado Pago falla (error de red, credenciales, validación de payload), el tool retorna un resultado de error (no lanza una excepción no controlada que rompa el stream) — el agente lo recibe como `function_result` y lo comunica conversacionalmente al usuario (ej. "hubo un problema generando tu link de pago, ¿lo intentamos de nuevo?"), sin exponer detalles técnicos del error.

### BR-19 — Escalación: solo persistencia, sin notificación activa (retoma RF-09 parcialmente)
Cuando el usuario pide hablar con un humano, el agente responde conversacionalmente (sin dar teléfono/WhatsApp) y se persiste `escalated_to_human=true` en el `Lead`. No se dispara ninguna notificación activa (email/Slack/Teams) en este incremento — ver DIV-12, diferido explícitamente.

### BR-20 — Verificación del webhook de pago (Mercado Pago)
Ningún webhook de pago se procesa sin verificar primero la firma HMAC (`x-signature`/`x-request-id`) contra el secreto de la aplicación. Adicionalmente, el estado de pago solo se marca como confirmado tras re-consultar `GET /v1/payments/{id}` — el payload del webhook en sí nunca es la única fuente de verdad del estado final (defensa en profundidad).

### BR-21 — Persistencia de leads (override de BR-08)
A diferencia de BR-08 (incremento 1, sin persistencia), en este incremento el `Lead` y su referencia de sesión (`service_session_id` de Foundry) **sí se persisten** en Postgres — al cierre de la conversación y también de forma incremental si se detectan señales de scoring relevantes (ej. intención de compra) antes del cierre formal.

---

# Incremento 3 — BackOffice: read path + broadcast en tiempo real + agente de outreach

**Fecha**: 2026-07-11

### BR-22 — Definición de draft "activo" (dedupe, Story 4/5)
Solo un `OutreachDraft` con `status = "pending"` cuenta como activo para efectos de deduplicación. Una vez que un draft pasa a `sent` o `discarded`, deja de bloquear la generación de un draft nuevo para ese mismo lead.

### BR-23 — Regeneración on-demand cuando ya existe un draft pending
Si `generate_draft` se invoca (automático u on-demand) para un lead que ya tiene un draft `pending`, se retorna ese draft existente sin generar uno nuevo ni lanzar error — "mostrar, no regenerar." El trigger automático y el on-demand comparten exactamente el mismo método y, por lo tanto, la misma regla de dedupe.

### BR-24 — Generación automática de draft es fire-and-forget
El trigger automático (FR-10) no bloquea el turno de chat que lo originó: `LeadEventPublisher` no espera (`await`) a que el subscriber de `OutreachAgentService` termine su llamada al LLM — la generación corre como una tarea en background. Esto es necesario porque el evento se publica desde dentro de `ChatAgentClient._apply_engagement_floor`, en plena ejecución de un turno de `apps/chat`.

### BR-25 — Lead sin email al momento del trigger automático
Si el trigger automático se dispara para un lead `hot` sin `Lead.email`, la generación del draft se omite (se registra en logs) y no hay reintento automático posterior — la transición a `hot` de BR-17b es monotónica y no vuelve a dispararse para ese lead. El staff puede generar un draft on-demand más tarde si el email llega a completarse. Esta restricción **no** aplica al trigger on-demand (Story 5 permite generar un draft para cualquier lead, en cualquier score, con o sin email) — el email solo es obligatorio al momento de `send_draft` (ver BR-28).

### BR-26 — Resolución de datos de curso vía tool-calling agentic
`OutreachAgentService` no es un wrapper de una sola llamada a `LLMProvider.complete()` — es un agente con tool-calling, mismo patrón ya verificado para `ChatAgentClient`/Microsoft Agent Framework. Expone un tool `get_course_details(course_id) -> {name, description, curriculum}` respaldado por el `CourseRepository` ya existente; el LLM decide cuándo invocarlo para enriquecer el draft con datos reales de los cursos listados en `Lead.recommended_programs`, en vez de que el código de orquestación pre-resuelva esos datos y los inserte en un prompt de un solo turno.

### BR-27 — Manejo de error en generación de draft (llamada LLM/tool-calling)
Si la ejecución del agente dentro de `generate_draft` falla (timeout, error del proveedor), el comportamiento depende de quién invocó:
- **On-demand** (staff-iniciado): el error se propaga — el caller HTTP recibe una respuesta de error para mostrar en la UI.
- **Automático** (BR-24, background task): el error se registra en logs y se absorbe — nunca debe escapar hacia el publisher ni interrumpir el turno de chat al que está enganchado.

### BR-28 — Manejo de error en envío de email
Si `EmailSender.send` falla dentro de `send_draft`, el draft **permanece en `status = "pending"`** — no se introduce un status `"failed"` separado. El error se propaga a la UI para que el staff pueda reintentar la acción "Send". Adicionalmente, `send_draft` valida que `Lead.email` esté presente *antes* de invocar `EmailSender.send`; si está vacío, rechaza con un error de validación (mismo criterio que BR-09 para campos obligatorios) — `EmailSender.send` nunca se invoca con un destinatario vacío.

### BR-29 — Payload de `LeadEvent`
Cada evento publicado por `LeadEventPublisher` incluye el registro `Lead` completo (no solo `lead_id` + score) — permite que `LeadBroadcaster` reenvíe directamente sin un lookup adicional, y que `KanbanBoard` renderice una card nueva sin un round-trip extra a `GET /leads`.

### BR-30 — Snapshot de reconexión sin estado de draft
El snapshot que `LeadBroadcaster` envía al (re)conectar contiene únicamente campos de `Lead` — ningún indicador de "draft activo" se expone a nivel de card del kanban. El estado de un draft (si existe, y su contenido) solo se consulta cuando el staff abre el detail popup de ese lead específico (`DraftPanel` → `get_active_draft`).
