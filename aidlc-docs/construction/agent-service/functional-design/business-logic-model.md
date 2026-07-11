# Business Logic Model — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05
**Tecnología** (confirmada en Q&A, formalizada en NFR Requirements): Azure AI Foundry + Microsoft Agent Framework, Azure Database for PostgreSQL Flexible Server + `pgvector`, Azure OpenAI (embeddings). Este documento es tecnología-agnóstico en su algoritmo; las referencias a Azure marcan las decisiones ya tomadas que impactan el diseño funcional.

---

## 1. Carga del catálogo (proceso offline, previo a cualquier recomendación)

1. Se carga el seed data de cursos (manual, BR — ver domain-entities.md `Course`), incluyendo su `curriculum` (lista de temas/módulos).
2. Para cada `Course`, se construye `embedding_text = f"{name}. {category}. {description}. Temas: {', '.join(curriculum)}"`. Incluir `curriculum` es clave: es la señal más específica para distinguir cursos de una misma `category` frente al `desired_stack` del interesado (ej. dos programas de "Data Science" pueden cubrir temas muy distintos).
3. Se llama al modelo de embeddings (Azure OpenAI `text-embedding-3-small`, 1536 dims) con `embedding_text`.
4. Se almacena el vector resultante en `Course.embedding` (columna `pgvector`).
5. Este proceso se repite solo cuando el catálogo cambia (alta de curso nuevo, edición de descripción/precio/duración) — no en cada recomendación (BR-06).

## 2. Flujo de recomendación (por mensaje WebSocket, tiempo real)
 
```
Frontend (mini-form completo)
    │  WS message: recommendation_request
    ▼
Backend (agent-service)
    │
    ├─ 1. Validar campos obligatorios (BR-09)
    │
    ├─ 2. Filtro duro SQL:
    │      SELECT * FROM courses
    │      WHERE price <= :budget AND duration_weeks <= :max_duration_weeks
    │
    ├─ 3. ¿Cero resultados? → rama de relajación con confirmación (BR-03):
    │      a. Calcular internamente candidatos con filtro ampliado (duration*1.5 AND budget*1.2), sin exponerlos aún.
    │      b. ¿Ampliado también da cero? → ir directo a 3e (catálogo completo, BR-11).
    │      c. ¿Ampliado da ≥1 candidato? → enviar WS `relax_filters_offer` y guardar estado
    │         pendiente en memoria de la conexión (session_state = "awaiting_relax_confirmation",
    │         incluye los candidatos ampliados ya calculados). El backend PAUSA aquí y espera
    │         el siguiente mensaje del cliente — este es el único punto de este incremento
    │         donde se rompe la asunción de "un solo mensaje por conversación".
    │      d. Mensaje `relax_filters_response` del frontend:
    │         - `confirm: true`  → usar los candidatos ampliados de 3a, marcar filters_relaxed=true,
    │                              continuar en paso 4 (ranking semántico + LLM)
    │         - `confirm: false` → ir a 3e (catálogo completo, BR-11)
    │      e. Catálogo completo (BR-11): tomar TODOS los cursos (sin filtro duro), continuar en
    │         paso 4-6 igual pero sin `LIMIT 3` (se listan todos, ordenados por similarity_score)
    │
    ├─ 4. Construir ProfileQuery.query_text = f"{professional_background} {desired_stack}"
    │
    ├─ 5. Generar query_embedding vía Azure OpenAI (mismo modelo que el catálogo, BR-06)
    │
    ├─ 6. Ranking sobre el set de candidatos correspondiente (filtrados / ampliados-confirmados /
    │      catálogo completo, según la rama de 3) — nunca sobre el catálogo completo salvo en 3e (BR-04):
    │      SELECT *, 1 - (embedding <=> :query_embedding) AS similarity_score
    │      FROM <candidatos>
    │      ORDER BY embedding <=> :query_embedding ASC
    │      [LIMIT 3]  -- se omite el LIMIT en la rama 3e (BR-11)
    │
    ├─ 7. Armar RecommendationCandidate[] con filters_relaxed marcado si vienen de la rama 3c/3d-confirm
    │
    ├─ 8. Invocar agente Azure AI Foundry (Agent Framework) con:
    │      - candidates (datos estructurados, únicos datos permitidos — BR-07)
    │      - profile_text (contexto para personalizar el tono/pitch)
    │      - un flag indicando si son candidatos exactos, ampliados (filters_relaxed) o catálogo completo
    │        sin filtrar, para que el LLM comunique correctamente qué está mostrando (BR-11)
    │      Prompt instruye: "Recomienda basándote únicamente en estos programas. No inventes precios, fechas
    │      ni cursos fuera de la lista."
    │
    └─ 9. Streaming de la respuesta del agente por el mismo WS (ver Sección 3.1 sobre la
           granularidad real de Agent Framework — no es "token a token" garantizado)
```

### 3.1 — Cómo transmite realmente Microsoft Agent Framework (investigado, no asumido)

El SDK Python expone streaming así:

```python
async for update in agent.run(message, thread=thread, stream=True):
    if update.text:
        print(update.text, end="")
# tras terminar el stream, se puede obtener el mensaje agregado completo:
final_response = await response_stream.get_final_response()
```

Puntos clave que cambian el diseño respecto a la versión anterior de este documento:

- Cada `update` es un `AgentRunResponseUpdate` — **no es un token individual**. `update.text` es un *delta de texto* cuyo tamaño depende del proveedor subyacente (Azure OpenAI Responses API emite eventos SSE como `response.output_text.delta`, que el framework reagrupa en estos updates). Puede venir vacío (`update.text == ""`) cuando el update contiene otro tipo de contenido (`update.contents`, ej. una llamada a función/tool).
- **En este incremento no hay tool-calling dentro del agente** — el filtrado (BR-01/02), la relajación con confirmación (BR-03) y el ranking semántico (BR-04, pgvector) ocurren en código de aplicación *antes* de invocar al agente, no como tools que el agente decide llamar. Por eso, para este incremento, se espera que el stream contenga **solo updates de texto** — no updates de tipo function-call. Esto podría cambiar en el incremento 2 (identificación/calificación conversacional), donde si se expone `recommend_courses` como tool real del agente, el stream sí podría intercalar updates de function-call.
- Por lo anterior, el contrato WS usa el campo `delta` (no `token`) y el tipo de mensaje `recommendation_delta` (no `recommendation_token`) — para no prometer una granularidad de "un token por mensaje" que el framework no garantiza.

Fuentes: [Running Agents — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/agents/running-agents), [agent_framework.ChatAgent — Microsoft Learn](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.chatagent?view=agent-framework-python-latest), [microsoft/agent-framework — GitHub](https://github.com/microsoft/agent-framework), [ADR 0013 — Python get_response simplification](https://github.com/microsoft/agent-framework/blob/main/docs/decisions/0013-python-get-response-simplification.md)

## 3. Contrato de mensajes WebSocket

### Entrada — `recommendation_request`
```json
{
  "type": "recommendation_request",
  "budget": 3500.00,
  "max_duration_weeks": 12,
  "professional_background": "Data Engineer en Yape, proyecto de recomendación de productos",
  "desired_stack": "Data Science"
}
```

### Salida — streaming normal
Cada mensaje corresponde a un `AgentRunResponseUpdate.text` recibido del agente (delta de texto, no un token individual — ver Sección 3.1). En este incremento no se esperan updates de function-call, solo texto:
```json
{ "type": "recommendation_delta", "delta": "Basado en tu perfil..." }
{ "type": "recommendation_delta", "delta": " te recomiendo el " }
...
{ "type": "recommendation_done", "candidates": [ { "course_id": "...", "name": "...", "similarity_score": 0.82 } ] }
```
`recommendation_done` se emite cuando el async iterator del agente termina (equivalente a haber consumido todo `agent.run(..., stream=True)`), adjuntando los `candidates` ya calculados en el paso 7 — no depende de parsear el texto compuesto para saber cuándo terminó.

### Salida — oferta de relajación (BR-03, rama 3c) — requiere respuesta del cliente
```json
{
  "type": "relax_filters_offer",
  "message": "No encontramos programas dentro de tu presupuesto y duración exactos. ¿Quieres ver alternativas con hasta 50% más de tiempo o 20% más de presupuesto?",
  "relaxed_max_duration_weeks": 18,
  "relaxed_budget": 4200.00
}
```

### Entrada — respuesta a la oferta de relajación (BR-03, rama 3d)
```json
{ "type": "relax_filters_response", "confirm": true }
```

### Salida — catálogo completo (BR-11, cuando el usuario declina o ni la relajación encuentra nada)
```json
{ "type": "no_exact_match_showing_all", "reason": "no_courses_match_criteria" }
```
Seguido del streaming normal (`recommendation_delta` / `recommendation_done`) pero con `candidates` cubriendo todo el catálogo y sin `filters_relaxed` marcado como válido para BR-01/02.

## 4. Manejo de errores

- Falla el servicio de embeddings (Azure OpenAI) → no se puede rankear semánticamente; se responde `no_recommendation` con `reason: "embedding_service_unavailable"` en vez de degradar silenciosamente a un orden arbitrario (evita recomendar sin criterio y llamarlo "recomendación").
- Falla el agente/LLM al componer la respuesta → se responde `no_recommendation` con `reason: "agent_unavailable"`; los `candidates` ya calculados no se pierden, quedan disponibles para reintento.
- Catálogo vacío (`Course` sin registros) → va directo a la rama 3e (catálogo completo, BR-11), que en este caso devuelve una lista vacía; el LLM no es invocado y se responde `no_exact_match_showing_all` seguido de un mensaje indicando que el catálogo no tiene programas cargados (evita alucinar cursos inexistentes).
- Timeout esperando `relax_filters_response` del cliente (BR-03, rama 3c) → si el cliente no responde dentro de **5 minutos** (definido en NFR Design), se descarta el estado pendiente de la conexión; un mensaje posterior del usuario se trata como una nueva `recommendation_request` desde cero, no como una respuesta tardía a la oferta.

## 5. Fuera de alcance de este incremento (explícito)

- Flujo conversacional de identificación (nombre/email) y calificación de 5 dimensiones — incremento 2.
- Persistencia de `RecommendationRequest`/`RecommendationResponse`/leads — BR-08. El estado "awaiting_relax_confirmation" de BR-03 es una excepción acotada: vive en memoria, atado al ciclo de vida de la conexión WS activa, y se descarta después de la confirmación o el timeout — no es persistencia en el sentido de BR-08.
- Generación de link de pago (Mercado Pago/Culqi) — mencionado por el usuario como paso posterior ("luego integro"), no parte de este incremento.
- Reprocesamiento de brochures PDF de `unit-1` como fuente del catálogo — BR (domain-entities.md, nota de fuente de datos).
- Guardrails ampliados (anti-competidor, scope de ventas) — diferidos a backlog, ver BR-07.
- Multi-turno general de refinamiento del mini-form — se mantiene la asunción de un solo envío del formulario por conversación, **salvo** el único round-trip de confirmación introducido por BR-03 (oferta de relajación → confirmación).
- Re-identificación de usuario recurrente, multi-turno de refinamiento del mini-form (se asume un envío único por conversación en este incremento).

## 6. Testable Properties (PBT-01 — extensión Property-Based Testing habilitada)

Propiedades identificadas para cobertura con Hypothesis en Code Generation (categorías de `property-based-testing.md`):

| # | Propiedad | Categoría | Componente |
|---|---|---|---|
| P1 | Todo `Course` en el resultado de BR-01/02 cumple `price <= budget AND duration_weeks <= max_duration_weeks` | Invariant | Filtro duro (paso 2) |
| P2 | El set de candidatos con criterio ampliado (BR-03, duración×1.5, presupuesto×1.2) es siempre superset-o-igual del set con criterio estricto, para la misma `Course[]` de entrada — nunca relajar produce menos candidatos que el filtro estricto | Invariant (monotonicidad) | Relajación (BR-03, paso 3a) |
| P3 | El cálculo de criterio ampliado es determinístico: mismos `budget`/`max_duration_weeks` de entrada producen siempre el mismo `relaxed_budget`/`relaxed_max_duration_weeks` | Idempotence | Relajación (BR-03, paso 3a) |
| P4 | `len(candidates) <= 3` en la rama normal (BR-05); sin este límite en la rama de catálogo completo (BR-11) | Invariant (range) | Top-K (paso 7) |
| P5 | `candidates` viene ordenado por `similarity_score` no-creciente | Invariant (ordering) | Ranking (paso 6) |
| P6 | El ranking por `pgvector` (`ORDER BY embedding <=> :query_embedding`) coincide con un cálculo de similitud coseno de referencia en NumPy puro, para un set fijo de vectores de prueba | Oracle | Ranking (paso 6) |
| P7 | `embedding_text` generado para un `Course` siempre contiene como substring cada elemento de `curriculum`, `name` y `category` | Invariant | Carga de catálogo (Sección 1, paso 2) |
| P8 | `similarity_score` siempre cae en el rango `[-1, 1]` (1 − distancia coseno de vectores normalizados) | Invariant (range) | Ranking (paso 6) |

**No PBT identificado** — el texto compuesto por el LLM (`RecommendationResponse.message_stream`, BR-07) no tiene una propiedad formalmente verificable más allá de "solo referencia campos de `candidates`", que se cubre mejor con evals de contenido (fuera del alcance de PBT) que con property-based testing tradicional.

---

# Incremento 2 — Chat conversacional + tool-calling + pago (Mercado Pago) + persistencia de leads

**Fecha**: 2026-07-06
**Basado en**: `aidlc-docs/inception/requirements/frontend-integration-requirements.md`, spike técnico real documentado en `aidlc-docs/construction/plans/agent-service-increment2-functional-design-plan.md`

Este incremento retoma BR-10 (identificación/calificación conversacional, antes diferida) y BR-08 (persistencia, antes diferida) — ver overrides en business-rules.md.

## 7. Endpoint unificado: `/ws/chat` (renombrado desde `/ws/recommendation`)

El endpoint acepta ahora, además de `recommendation_request` (incremento 1, se mantiene por compatibilidad interna), un nuevo tipo de mensaje `user_message` de chat libre. El agente decide internamente, mensaje a mensaje, si responde conversacionalmente o invoca uno de los 2 tools nuevos.

## 8. Arquitectura de tool-calling (verificada con spike real, no asumida)

Evidencia real (ver plan de Functional Design): el SDK `agent-framework-foundry` expone en el stream `Content` con `type='function_call'` (nombre + argumentos ya parseados por el framework, coincidiendo con la firma de la función Python registrada) y luego `type='function_result'`; **el framework auto-ejecuta el callable Python y continúa el loop conversacional automáticamente** dentro de un único `agent.run(stream=True)`.

### 8.1 Tool `collect_profile_data` — patrón "humano en el loop"

```python
async def collect_profile_data(budget, max_duration_weeks, professional_background, desired_stack) -> str:
    # 1. Enviar al frontend (mismo WS) un mensaje profile_data_requested con estos valores como prefill
    # 2. Crear un asyncio.Future, registrarlo en un diccionario {call_id o connection_id: future}
    # 3. await future  -- se resuelve cuando llega profile_data_submitted del cliente (ver 8.1.1)
    # 4. Retornar los datos confirmados/corregidos por el usuario (como string/dict) -- pasa a ser
    #    el function_result; el agente continua solo, sin más intervención de nuestro código
    ...
```

El agente decide **cuándo** invocar este tool (BR-16) — no es forzado por turno fijo; el system prompt lo instruye a llamarlo cuando necesite datos estructurados de calificación que no tiene aún.

#### 8.1.1 Receptor concurrente de mensajes WS

Como el hilo principal está bloqueado iterando `async for update in stream`, se necesita una tarea concurrente (`asyncio.create_task`) que reciba mensajes entrantes del WS en paralelo y resuelva el `Future` correspondiente al recibir `profile_data_submitted`. Sin timeout explícito (Clarification Q1 = C): si el usuario nunca responde, el `Future` queda pendiente hasta que la conexión WS se cierra, momento en el cual se cancela (cleanup del handler) — no hay lógica de temporizador adicional.

### 8.2 Tool `create_payment_link` — sin pausa, ejecuta pago real dentro del tool

```python
async def create_payment_link(amount, description, client_details) -> str:
    # 1. POST a la API de Preferencias de Mercado Pago (Checkout Pro) con items/back_urls/notification_url
    # 2. Retorna init_point (o sandbox_init_point en modo test) como resultado -- se convierte en
    #    function_result y el agente lo comparte con el usuario en su siguiente mensaje de texto
    # 3. Si la llamada a Mercado Pago falla, retorna un mensaje de error como resultado (BR-18) para
    #    que el agente lo comunique conversacionalmente, sin romper el stream
    ...
```

## 9. Contrato de mensajes WebSocket — Incremento 2 (adicional al de la Sección 3)

### Entrada — mensaje de chat libre
```json
{ "type": "user_message", "text": "Hola, quiero aprender data engineering" }
```

### Salida — solicitud de datos estructurados (tool `collect_profile_data` detectado)
```json
{
  "type": "profile_data_requested",
  "call_id": "call_xxx",
  "prefill": { "budget": 500.0, "max_duration_weeks": 8, "professional_background": "Analista de datos", "desired_stack": "Azure" }
}
```

### Entrada — respuesta del widget
```json
{
  "type": "profile_data_submitted",
  "call_id": "call_xxx",
  "budget": 500.0, "max_duration_weeks": 8, "professional_background": "Analista de datos", "desired_stack": "Azure"
}
```

### Salida — link de pago generado (tool `create_payment_link` resuelto)
```json
{ "type": "payment_link_created", "checkout_url": "https://www.mercadopago.com/checkout/v1/redirect?pref_id=..." }
```
Nota: este evento es informativo para que el frontend pueda, opcionalmente, resaltar el link en la UI (ej. como botón); el link también llega como parte del `recommendation_delta`/texto normal del agente, ya que es él quien lo comparte conversacionalmente.

### Salida — sesión (para persistencia entre refreshes)
```json
{ "type": "session_created", "service_session_id": "sess_xxx" }
```
Enviado una vez, al iniciar una conversación nueva (primer mensaje sin `service_session_id` de entrada). El cliente lo persiste (ej. `localStorage`) y lo reenvía en el mensaje de conexión/primer mensaje de sesiones futuras para retomar la conversación completa (`Agent.get_session(service_session_id)`).

## 10. Webhook de confirmación de pago (Mercado Pago)

Endpoint HTTP nuevo (no WS) en `agent-service`, ej. `POST /webhooks/mercadopago`:

1. Verificar firma HMAC (`x-signature` + `x-request-id` contra el secreto de la aplicación, ver NFR Requirements) — rechazar con 401 si no valida.
2. Extraer `data.id` (payment id) del payload.
3. Consultar `GET /v1/payments/{id}` (API de Mercado Pago, autenticado con el access token propio) para obtener el estado autoritativo del pago — no confiar únicamente en el payload del webhook.
4. Si `status == "approved"`, actualizar el `Lead` correspondiente en Postgres (estado de pago, `payment_confirmed_at`).
5. Responder 200/201 (requisito de Mercado Pago para no reintentar la notificación).

**Nota de alcance**: si la conversación WS que originó el pago ya se cerró (usuario cerró la pestaña), no se reabre proactivamente para notificar — la confirmación queda solo en el lead persistido. Notificar al usuario en una conversación cerrada queda fuera de alcance de este incremento.

## 11. Lead scoring y persistencia (retoma BR-08/BR-10 originales, ver overrides en business-rules.md)

Al cierre de la conversación (o periódicamente durante ella), se calcula el score (hot/warm/cold, BR-17) y se persiste el `Lead` en Postgres con su `ConversationSession` asociada (referencia al `service_session_id` de Foundry, no se duplica el historial completo de mensajes — Foundry Memory ya es la fuente de verdad de la transcripción).

## 12. Testable Properties — Incremento 2 (adicional a la Sección 6)

| # | Propiedad | Categoría | Componente |
|---|---|---|---|
| P9 | El cálculo de `LeadScore` es determinístico: mismas señales de entrada (intención de compra, motivación, fit, urgencia, datos completos) producen siempre el mismo score (hot/warm/cold) | Idempotence | Lead scoring (BR-17) |
| P10 | El score nunca es `hot` si `datos completos == False` (BR-17: dato obligatorio) | Invariant | Lead scoring (BR-17) |
| P11 | Para cualquier secuencia de fragmentos de `arguments` acumulados de un `function_call`, si la concatenación final es JSON válido y sus claves coinciden con la firma de `collect_profile_data`, el tool se invoca exactamente una vez por `call_id` | Invariant | Tool-calling (Sección 8) |

## 13. Adenda de Code Generation — 2 huecos de diseño corregidos durante la implementación

**Tercer tool, `get_course_recommendations`**: este documento (Sección 8) solo especificaba `collect_profile_data` y `create_payment_link`. Al implementar se detectó que el agente no tiene forma de invocar `RecommendationOrchestrator` sin una tool explícita — se agregó `get_course_recommendations(budget, max_duration_weeks, professional_background, desired_stack, accept_relaxed_filters=False)`, que reutiliza `RecommendationOrchestrator`/`CourseRepository`/`EmbeddingService` de incremento 1 sin modificarlos. Sin match exacto, retorna texto para que el agente ofrezca conversacionalmente el rango ampliado (Clarification 4 = A); si el usuario acepta, el agente reinvoca la misma tool con `accept_relaxed_filters=true` — sin necesitar una pausa tipo widget para este caso, a diferencia de `collect_profile_data`.

**Correlación webhook↔lead**: el webhook de Mercado Pago (Sección 10) entrega un `payment_id` de pago, distinto del `preference_id` de la orden — se agregó `external_reference` (seteado al `service_session_id` de la sesión al crear la preferencia) para que el webhook handler pueda encontrar el `Lead` correcto vía `LeadRepository.find_by_service_session_id`. Limitación conocida: si el usuario pide pagar antes de que `session_created` se haya emitido, `external_reference` es `None` y el webhook no puede auto-correlacionar (aceptable para el alcance de esta demo).

**Persistencia del Lead nunca ocurría**: se detectó que ningún punto del flujo llamaba a `LeadRepository.save()` — corregido con `ChatAgentClient._upsert_lead()`, invocado desde los 3 tools (ver `business-logic-summary-increment2.md` para el detalle completo).

**Falta señal de fin de turno (`turn_done`)**: a diferencia de incremento 1 (`recommendation_done`/`no_recommendation` señalaban explícitamente el fin), el chat libre no tenía ningún evento que le indicara al frontend "el agente terminó de responder a este mensaje". Se agregó `TurnDoneOut` (`{"type": "turn_done"}`), emitido después de cada `agent_client.stream(...)` y antes de `session_created` — necesario para que el frontend sepa cuándo re-habilitar el input sin depender de heurísticas de silencio.

## 14. Adenda de Build and Test — 2 bugs reales encontrados en verificación E2E con navegador real

**Desconexión a mitad de turno no manejada**: al cerrar el navegador mientras el agente seguía transmitiendo el último turno, `ChatWebSocketHandler` lanzaba una excepción no capturada (`RuntimeError: Unexpected ASGI message 'websocket.send', after sending 'websocket.close'`) al intentar enviar `turn_done`/`session_created` a un socket ya cerrado — el `try/except` original solo cubría el streaming del agente, no los envíos posteriores. Corregido envolviendo todo el cuerpo del turno (streaming + `turn_done` + `session_created`) en un solo `try/except (WebSocketDisconnect, RuntimeError)` que termina la conexión limpiamente.

**`service_session_id` de Foundry no es estable — fragmentaba el `Lead` en múltiples filas**: verificado con datos reales en Postgres que `AgentSession.service_session_id` (prefijo `resp_...`) es el ID de la *respuesta* del último turno, no un ID de hilo persistente — rota en cada `agent.run()`. Usarlo como clave de correlación de `Lead` (Sección 11) creaba una fila nueva por turno en vez de actualizar una sola. Corregido: `ChatWebSocketHandler` genera un `conversation_id` (UUID) una sola vez por conexión y lo pasa a `ChatAgentClient`, que lo usa para `_upsert_lead`/`external_reference` en vez de `service_session_id`. `service_session_id` sigue usándose exclusivamente para reanudar el hilo de Foundry — ahora se reenvía en **cada** turno (no solo el primero), ya que el valor cambia y el cliente necesita el más reciente para retomar correctamente. Limitación conocida documentada en el código: un reconnect (refresh de página) retoma la conversación de Foundry correctamente pero inicia una fila de `Lead` nueva (el `conversation_id` no sobrevive a un refresh) — aceptable para el alcance de esta demo.

Ambos bugs solo se manifestaban con infraestructura real (navegador real cerrando la conexión a mitad de stream; múltiples turnos reales contra Postgres) — no eran visibles en los tests con fakes, que es exactamente el valor de la verificación E2E de Build and Test.

## 15. Adenda de Build and Test (ronda 2) — bug reportado por el usuario: "el widget no se envía", investigado con `superpowers:systematic-debugging`

Reportado por el usuario tras la Sección 14: "hay un bug con respecto al widget no lo envia correctamente" y, por separado, "al crear una nueva conversación parece que guarda en memoria lo conversado en otra conversación". Investigación con Playwright real (no se asumió la causa) — 2 intentos de reproducción directa del envío del widget (edición del monto, tipeo con coma) **no reprodujeron ningún problema**; se pidió al usuario precisar el síntoma exacto ("no pasa nada al hacer clic en Confirmar"), lo cual sí se logró reproducir con un escenario concreto: **abandonar el widget sin enviarlo y hacer clic en "Nueva conversación"**.

**Causa raíz única para ambos reportes**: `collect_profile_data` (Sección 8.1) esperaba (`await future`) sin timeout, por decisión explícita de NFR Requirements (Clarification Q1 = C: "sin timeout, la desconexión del WS es el límite natural"). Esa decisión asumía que el único modo de abandono era una desconexión real del socket — pero un usuario puede abandonar el widget **sin desconectarse** (ej. escribiendo otro mensaje, o haciendo clic en "Nueva conversación"). En ese caso, el bucle principal de `ChatWebSocketHandler` queda bloqueado para siempre dentro de `agent_client.stream(...)`, `turn_done` nunca se emite, `busy` nunca vuelve a `false` en el frontend, y el Composer queda deshabilitado silenciosamente — de ahí "no pasa nada al hacer clic". Y como "Nueva conversación" solo limpiaba el estado del frontend (sin cerrar la conexión WS ni el `service_session_id` guardado en `localStorage`), la conversación de Foundry seguía siendo la misma — de ahí "parece que guarda en memoria lo conversado en otra conversación".

**Fixes aplicados** (verificados de nuevo con Playwright tras cada uno):
1. `profile_data_timeout_seconds` (nueva config, default 300s, mismo valor que `RELAX_CONFIRMATION_TIMEOUT_SECONDS` de incremento 1): `_collect_profile_data` ahora usa `asyncio.wait_for(future, timeout=...)` — si expira, retorna un texto para que el agente continúe conversacionalmente en vez de bloquear el turno para siempre. **Esto revierte parcialmente la decisión de Clarification Q1 = C** — la evidencia real mostró que era incorrecta para el caso de abandono sin desconexión.
2. `ChatWebSocketHandler._receive_loop`: al detectar `WebSocketDisconnect`, ahora llama `pending_tool_calls.cancel_all()` inmediatamente (antes solo pasaba en el `finally` de `handle_connection`, que nunca se alcanzaba porque el bucle principal seguía bloqueado).
3. **Frontend** — `useChat.clearMessages` ahora limpia `service_session_id` de `localStorage` (`WsChatService.clearStoredSessionId`, nuevo export) y fuerza `window.location.reload()` en vez de solo vaciar el array de mensajes — única forma de obtener una conexión WS genuinamente nueva, dado que la sesión se resuelve una sola vez por conexión.
4. **Bug propio encontrado durante la verificación del fix #3**: la primera versión mantuvo el guard `if (busy) return` heredado del código original — que bloqueaba exactamente el escenario que se quería arreglar (widget abandonado deja `busy` atascado en `true` para siempre). Corregido eliminando el guard — "Nueva conversación" debe funcionar siempre, precisamente porque es el mecanismo de recuperación de ese estado.

Verificado con Playwright real tras cada fix: el escenario completo (abandonar widget → "Nueva conversación" → nuevo mensaje) ahora cierra la conexión vieja, abre una nueva, y el agente responde sin memoria de la conversación anterior. Sin regresiones en la suite (42/42 backend, 19/19 frontend).

## 16. Adenda — Rehidratación de mensajes tras recargar la página (feature, no bug)

El usuario notó que, al recargar la página, no veía la conversación anterior — aunque el thread de Foundry sí se retoma correctamente (Sección 11), el estado de React (`messages`) no sobrevive un refresh. Investigado si el SDK (`agent-framework-foundry`) expone alguna API de recuperación de historial: **no la tiene** — `AgentSession`/`Agent` solo exponen `create_session`/`get_session` para continuar un `agent.run()`, sin un método de lectura de mensajes pasados.

**Decisión**: persistir la transcripción nosotros mismos, exclusivamente para rehidratar la UI — no reemplaza a Foundry Memory como fuente de verdad del razonamiento del agente (PATTERN-20 se mantiene para eso), es una caché de solo lectura para el frontend.

- **`conversation_messages`** (`migrations/003`): `conversation_id, role ('user'|'bot'), content, created_at`. Se escribe un row por mensaje de usuario y un row por respuesta completa del agente (acumulada al final del turno, no por delta).
- **`conversation_id`** (ya existente para `Lead`, Sección 14) ahora también se envía al frontend dentro de `session_created` y se le permite al cliente reenviarlo en `user_message` para retomar la MISMA transcripción y el mismo `Lead` tras un reload (antes solo se reenviaba `service_session_id`) — cierra además la limitación conocida de que un reconnect creaba una fila de `Lead` nueva.
- **`GET /conversations/{conversation_id}/messages`** (nuevo endpoint HTTP): el frontend lo consulta al montar si hay un `conversation_id` guardado, y reconstruye los mensajes visibles antes de que el usuario escriba nada. Requirió agregar `CORSMiddleware` (solo `http://localhost:3000`) — es el primer endpoint HTTP que el navegador llama directamente vía `fetch()` (el WS no está sujeto a CORS).

Verificado con Playwright real: conversar → recargar la página → el texto de la pregunta y de la respuesta originales siguen visibles, sin errores de consola. Sin regresiones (44/44 backend con Postgres real, 21/21 frontend).

## 17. Adenda — Historial real de conversaciones en el Sidebar (feature, no bug)

El usuario notó que el Sidebar seguía mostrando el historial hardcodeado de `data/mock.ts` — sin relación con las conversaciones reales que ya se persistían desde la Sección 16. Aprobado explícitamente por el usuario ("si dale") tras confirmarlo.

**Decisión de diseño clave**: el `localStorage` del navegador solo recuerda el `service_session_id` MÁS RECIENTE (Sección 11), pero el Sidebar necesita poder resumir CUALQUIER conversación pasada, no solo la última. Se resolvió introduciendo `ConversationSessionStore` (repositorio Postgres nuevo, sobre la tabla `conversation_sessions` que existía desde el diseño original del incremento 2 pero que ningún código usaba hasta ahora): mapea `conversation_id → service_session_id` de forma durable. `ChatWebSocketHandler.handle_connection` se reestructuró para resolver primero el `conversation_id` que envía el cliente, y solo si el cliente no trae también un `service_session_id` explícito, consulta el store para encontrar el correcto — permitiendo así retomar el hilo de Foundry correcto de una conversación antigua seleccionada desde el Sidebar.

- **`ConversationMessageRepository.list_conversations()`** (query nueva, `DISTINCT ON` + CTE): retorna, por conversación, el primer mensaje de usuario como `preview` y el `MAX(created_at)` como `last_activity_at`, para ordenar por actividad reciente.
- **`GET /conversations`** (nuevo endpoint): expone la lista anterior como `ConversationSummaryOut[]`.
- **Frontend**: `fetchConversations()`/`selectConversation()` (`WsChatService.ts`), función pura `groupConversationsByRecency` (agrupa en Hoy/Ayer/Anteriores, con tests), y `useChat.switchConversation()` (mismo patrón de `window.location.reload()` que `clearMessages`, pero conservando el `conversation_id` elegido en vez de descartarlo).

Verificado con Playwright real (crear 2 conversaciones nuevas, recargar, confirmar que el Sidebar las muestra con su preview real, hacer clic en la más antigua, confirmar que el `conversation_id` activo cambia al correcto y que su mensaje reaparece en el panel principal). Sin regresiones: 58/58 backend, 24/24 frontend, `tsc --noEmit` limpio.

## 18. Adenda — Bug real: `CancelledError` no manejado dejaba conversaciones sin la respuesta del bot

Reportado por el usuario: "No se estan obteniendo los mensajes dentro de una conversacion". Investigado con `superpowers:systematic-debugging`. Reproducción directa contra el backend real: las 2 conversaciones creadas en la verificación de la Sección 17 (`e2e_history.mjs`) solo tenían el mensaje de usuario persistido en `conversation_messages`, sin respuesta del bot — confirmado consultando la tabla directamente. En cambio, una conversación limpia de un solo turno y una conversación existente con datos completos cargaron y mostraron todos sus mensajes correctamente, descartando un bug general del mecanismo de fetch/rehidratación (Sección 16).

**Causa raíz**: el log real del backend mostró `asyncio.exceptions.CancelledError` sin manejar, exactamente en el momento en que el script de la Sección 17 hacía clic en "Nueva conversación" mientras el widget de `collect_profile_data` seguía pendiente. `pending_tool_calls.cancel_all()` (invocado por `_receive_loop` al detectar la desconexión, Sección 14) cancela el `Future` que el turno principal espera dentro de `agent_client.stream(...)`. `asyncio.CancelledError` hereda de `BaseException` desde Python 3.8 (no de `Exception`), por lo que escapaba tanto del `except Exception:` interno (pensado para errores reales del agente) como del `except (WebSocketDisconnect, RuntimeError):` externo (Sección 14, pensado para desconexiones a mitad de turno) — la excepción salía de `handle_connection` por completo como un crash ASGI no manejado, saltándose el código de persistencia de la respuesta del bot (nunca se alcanzaba).

Confirmado con el usuario vía `AskUserQuestion` que las conversaciones "rotas" eran justamente esas, generadas por el propio script de prueba de la Sección 17 ("ya funciona, parece que eran mensajes anteriores fallidos").

**Reproducción antes del fix (TDD)**: un primer intento con `TestClient` no reprodujo el crash (su transporte no deja escapar la excepción de fondo igual que un `uvicorn` real). Se escribió un `FakeWebSocket` de bajo nivel que llama directamente a `handler.handle_connection(...)`, sincronizado con un `asyncio.Event` para garantizar que la desconexión ocurra DESPUÉS de que `profile_data_requested` ya fue enviado (de lo contrario aparece una carrera *distinta*: la desconexión se procesa antes de crear el `Future`, dejando el turno colgado sin nada que cancelar — no corregida en esta ronda, ver nota abajo). Con esa sincronización, la prueba sí reprodujo el `CancelledError` escapando de `handle_connection`.

**Fix aplicado**: un `except asyncio.CancelledError:` explícito en `chat_websocket_handler.py`, antes del `except Exception:` existente, que registra el evento y deja que el flujo continúe hacia el código ya existente de persistencia/`turn_done`/`session_created` (que ya maneja correctamente un socket cerrado vía el `except` externo). Verificado: 60/60 backend tras el fix, sin regresiones.

**Nota — problema relacionado no corregido**: si la desconexión se procesa ANTES de que el `Future` se cree (carrera de timing pura, distinta a la de arriba), `cancel_all()` no tiene nada que cancelar y el turno queda esperando hasta que expire `profile_data_timeout_seconds` (300s) — en producción se resuelve solo con un mensaje de "no respondiste a tiempo" (Sección 15). No es el síntoma reportado ni causa un crash — documentado por si se repite.

Ver `aidlc-docs/construction/build-and-test/build-and-test-summary.md` (Ronda 5) para el detalle completo, incluyendo un hallazgo incidental no relacionado (`test_p6_pgvector_ranking_matches_numpy_oracle`, preexistente del incremento 1, no corregido por estar fuera de alcance).

---

# Incremento 3 — BackOffice: read path + broadcast en tiempo real + agente de outreach

**Fecha**: 2026-07-11
**Basado en**: `aidlc-docs/inception/application-design/backoffice-{components,component-methods,services}.md` (aprobado), respuestas de `aidlc-docs/construction/plans/agent-service-increment3-functional-design-plan.md`

## 19. Read path: `list_leads` (FR-7)

`LeadQueryService.list_leads()` delega directamente en `LeadRepository.list_leads()` (`SELECT * FROM leads ORDER BY created_at DESC` — sin paginación ni filtros, consistente con NFR-4/escala de demo). `GET /leads` serializa la lista completa de `Lead` a JSON. No existe `GET /leads/{id}` a nivel de API (decisión de Application Design, Q5) — pero `LeadRepository` gana un método interno adicional, `find_by_id(lead_id) -> Lead | None`, usado únicamente por `OutreachAgentService` (Sección 21) para resolver un lead individual antes de generar/enviar un draft. Este método no se expone por HTTP; no contradice la decisión de Application Design, que era específicamente sobre la superficie de la API pública.

## 20. Broadcast en tiempo real: `LeadEventPublisher` + `LeadBroadcaster` (FR-6, FR-8)

**`LeadEvent`** (BR-29, Q8 = B): cada evento lleva el registro `Lead` completo, no solo `lead_id`/score — evita un round-trip adicional tanto en `LeadBroadcaster` como en `KanbanBoard`.

```python
@dataclass(frozen=True)
class LeadEvent:
    event_type: Literal["created", "score_changed"]
    lead: Lead
```

**Puntos de publicación**:
- `ChatAgentClient._upsert_lead` (ya existente) publica `LeadEvent(event_type="created", lead=...)` la primera vez que un `Lead` se persiste en una conversación.
- `ChatAgentClient._apply_engagement_floor` (ya existente, BR-17b) publica `LeadEvent(event_type="score_changed", lead=...)` cada vez que persiste un cambio de `Lead.score` — sea por el piso de engagement o, en el futuro, por `score_lead()` (BR-17) si llega a wirearse.

**`LeadBroadcaster`**: mantiene el conjunto de conexiones `/ws/leads` activas en memoria (mismo patrón de gestión de conexiones que `/ws/chat`). Al aceptar una conexión — nueva o reconexión, sin distinción especial — envía primero un mensaje `snapshot` (`LeadQueryService.list_leads()`), y a partir de ahí reenvía cada `LeadEvent` publicado como un mensaje `lead_event`. Como el snapshot siempre se reenvía completo en cada conexión (BR-30), no se necesita numeración de secuencia ni buffer de replay para satisfacer el criterio de aceptación de la Story 3 ("reconcilia al estado actual del servidor, sin cards duplicadas/obsoletas").

### Contrato de mensajes WebSocket — `/ws/leads`

```json
// Salida — snapshot (al conectar/reconectar)
{ "type": "snapshot", "leads": [ { "...Lead fields...": "..." } ] }

// Salida — evento en vivo
{ "type": "lead_event", "event_type": "created" | "score_changed", "lead": { "...Lead fields...": "..." } }
```

## 21. Agente de outreach — generación de drafts con tool-calling (FR-9, FR-10, FR-11)

**Arquitectura (Q5 + follow-up = A)**: `OutreachAgentService` no es un simple wrapper de `LLMProvider.complete()` — es agentic, con el mismo patrón de tool-calling ya verificado en `ChatAgentClient`/Microsoft Agent Framework (ver Sección 8). El LLM decide invocar un tool `get_course_details(course_id) -> {name, description, curriculum}` (respaldado por el `CourseRepository` ya existente, BR-26) para enriquecer el draft con datos reales de los cursos en `Lead.recommended_programs`, en vez de que el código de orquestación pre-obtenga esos datos y los inserte en un prompt de un solo turno.

**`generate_draft(lead_id, trigger)`**:
1. `LeadRepository.find_by_id(lead_id)` → `Lead`.
2. `DraftRepository.find_active_by_lead_id(lead_id)` — si existe un draft `pending`, se retorna tal cual, **sin** generar uno nuevo ni lanzar error (BR-23, Q2 = A). Aplica igual para el trigger automático y el on-demand — es el mismo método, un único código de dedupe (Sección de Application Design ya anticipaba esto: "both triggers converge on one method").
3. Si `trigger == "auto"` y `lead.email` está vacío: se omite la generación (se loggea), sin reintento posterior — la transición a `hot` de BR-17b es monotónica/de una sola vez (BR-25, Q4 = A). El trigger on-demand **no** tiene esta restricción — el staff puede generar un draft para cualquier lead sin importar si el email ya está capturado (Story 5 permite cualquier score/estado); el email solo se vuelve obligatorio al momento de `send_draft` (Sección 22).
4. Corre el agente (system prompt de outreach + tool `get_course_details`) con `profile_summary`, `motivation`, `motivation_detail` del lead como contexto — produce `{subject, body}`.
5. Persiste `OutreachDraft(status="pending", trigger=trigger, ...)` vía `DraftRepository.save`.
6. Retorna el `OutreachDraft`.

**Trigger automático (FR-10, BR-24, Q3 = A — fire-and-forget)**: `OutreachAgentService` se suscribe a `LeadEventPublisher` en el arranque del servicio. Al recibir un evento `score_changed` donde `lead.score == LeadScore.HOT`, agenda `generate_draft(lead.id, trigger="auto")` como una tarea en background (`asyncio.create_task`, no `await` dentro del callback del publisher) — así el turno de chat en `apps/chat` que disparó el cambio de score no espera a que termine la llamada al LLM. Cualquier excepción dentro de esa tarea se loggea y se absorbe (BR-27) — nunca debe propagarse hacia el publisher ni interrumpir el turno de chat.

**Trigger on-demand (FR-11)**: mismo método `generate_draft(lead_id, trigger="on_demand")`, invocado síncronamente desde el endpoint HTTP correspondiente (ruta exacta TBD, no bloqueante para este diseño).

## 22. Revisión, envío y descarte de drafts (FR-12, FR-13, Story 6)

- **`get_active_draft(lead_id)`** → `DraftRepository.find_active_by_lead_id(lead_id)` — usado por `DraftPanel` al abrir el popup de un lead.
- **`send_draft(draft_id)`**: `DraftRepository.find_by_id(draft_id)` + `LeadRepository.find_by_id(draft.lead_id)`. Si `lead.email` está vacío, se rechaza con un error de validación (mismo espíritu que BR-09 — un campo obligatorio ausente para la operación, no un caso nuevo que requiera un tool/handling especial). Si hay email, invoca `EmailSender.send(lead.email, draft.subject, draft.body)`. Éxito: `draft.status = "sent"`, `draft.sent_at = now()`, persiste. Falla (BR-28, Q7 = A): el error se propaga a la UI, `draft.status` permanece `"pending"` — no se introduce un status `"failed"` separado; el staff simplemente reintenta la acción "Send".
- **`discard_draft(draft_id)`**: `draft.status = "discarded"`, persiste. No invoca `EmailSender` bajo ninguna circunstancia.

## 23. Testable Properties — Incremento 3 (PBT-01, extensión habilitada)

- **Dedupe (BR-22/BR-23)**: para cualquier secuencia de llamadas a `generate_draft` sobre el mismo `lead_id` sin un `send_draft`/`discard_draft` intermedio, nunca existe más de una fila con `status = "pending"` en `DraftRepository` para ese lead.
- **Serialización de `LeadEvent` (BR-29)**: todo `LeadEvent` publicado contiene un `Lead` completo y serializable — round-trip JSON sin pérdida de campos.
- **Monotonicidad del piso de engagement**: ya cubierta por BR-17b/Hypothesis (incremento 2) — sin regresión introducida por el nuevo punto de publicación en `_apply_engagement_floor`.
- **`send_draft` nunca envía sin email**: property test — para cualquier `Lead` con `email is None`, `send_draft` siempre lanza el error de validación y nunca invoca `EmailSender.send`.

Ver `aidlc-docs/construction/plans/agent-service-increment2-code-generation-plan.md` para la nota completa de estos hallazgos.
