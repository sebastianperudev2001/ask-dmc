# NFR Design Patterns — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

---

## 1. Patrones de Resiliencia

### PATTERN-01 — Retry con backoff exponencial para llamadas externas
Toda llamada a Azure OpenAI (embeddings, paso 5) o al Persistent Agent de Foundry (paso 8) usa retry con backoff exponencial y jitter:
- Máx. 3 intentos
- Backoff: 0.5s → 1s → 2s (+ jitter aleatorio para evitar retries sincronizados si hay múltiples requests concurrentes)
- Tras agotar los 3 intentos, se propaga el error definido en Functional Design (Sección 4): `embedding_service_unavailable` o `agent_unavailable` — nunca se degrada silenciosamente a un resultado parcial o inventado.
- Sin circuit breaker en este incremento (decisión del usuario) — el volumen esperado (demo) no justifica la complejidad de un breaker con estado (abierto/medio-abierto/cerrado); se reevalúa si el volumen real de producción crece.

### PATTERN-02 — Timeout de estado conversacional pendiente (BR-03)
El estado `awaiting_relax_confirmation` (Functional Design, rama 3c) vive en memoria del proceso, atado a la conexión WS activa, con un timeout de **5 minutos**. Si expira sin recibir `relax_filters_response`, el estado se descarta; cualquier mensaje posterior del cliente se trata como un `recommendation_request` nuevo, no como una respuesta tardía. Implementado como una tarea de expiración (`asyncio` timeout/task) asociada al ciclo de vida de la conexión — se cancela automáticamente si la conexión se cierra antes de los 5 minutos (evita fugas de memoria).

### PATTERN-03 — Fail-safe defaults (SECURITY-15)
Todo error no manejado explícitamente en el pipeline (pasos 1-9) cae en un manejador global que responde con un mensaje WS genérico (sin stack traces ni detalles internos) y cierra el flujo de esa request de forma segura — nunca deja la conexión en un estado indefinido ni expone información interna del backend.

## 2. Patrones de Escalabilidad

### PATTERN-04 — Mínimo 1 réplica activa (sin scale-to-zero)
Azure Container Apps configurado con **`minReplicas: 1`** — decisión explícita del usuario para proteger el objetivo de primer delta ≤3s (requirements.md §9.1). Scale-to-zero se descartó porque el cold start (levantar contenedor + inicializar pool de conexiones a Postgres) puede tardar varios segundos, incumpliendo la NFR de performance en la primera request tras un período idle.
- `maxReplicas`: valor bajo (ej. 3) — el volumen esperado es de demo, no de producción; auto-scaling disponible como red de seguridad, no como necesidad primaria.
- Trigger de escalado: concurrencia de conexiones WS activas por réplica (HTTP scaling rule de Container Apps).

### PATTERN-05 — Afinidad de conexión WS (sin estado distribuido)
Cada conexión WebSocket permanece anclada a la réplica de Container Apps que la aceptó durante toda su vida — no hay necesidad de un session store distribuido (ej. Redis) para el estado `awaiting_relax_confirmation`, porque ese estado nunca necesita ser leído por una réplica distinta a la que originó la conexión. Si el volumen creciera al punto de requerir balanceo activo de conexiones WS entre réplicas con estado compartido, este patrón se reevaluaría (fuera de alcance de este incremento).

## 3. Patrones de Performance

### PATTERN-06 — Ranking vía consulta pgvector por request (sin cache en memoria)
El ranking semántico (BR-04/BR-11) se resuelve con una consulta SQL a Postgres (`ORDER BY embedding <=> :query_embedding`) en cada request, no con un cache de embeddings cargado en memoria del proceso. Decisión explícita del usuario: a la escala esperada del catálogo (seed data manual, decenas de cursos), la latencia de la consulta pgvector es marginal, y evita la complejidad de invalidar/recargar un cache cuando el catálogo cambia (alta de curso, edición de precio/descripción/malla curricular).

### PATTERN-07 — Índice HNSW sobre `Course.embedding`
Se usa un índice HNSW (Hierarchical Navigable Small World) de `pgvector` sobre la columna `embedding` — mejor balance recall/latencia que IVFFlat a la escala esperada (decenas, no millones, de vectores), y no requiere un paso de entrenamiento previo (a diferencia de IVFFlat).

### PATTERN-08 — Índices B-tree sobre columnas de filtro duro
Índices estándar sobre `Course.price` y `Course.duration_weeks` para que el filtro duro (BR-01/02, paso 2) sea rápido incluso si el catálogo crece — parte del presupuesto de tiempo que debe dejar el pipeline completo antes de invocar al agente para cumplir ≤3s.

### PATTERN-09 — Connection pooling a Postgres
El backend mantiene un pool de conexiones (ej. `asyncpg` pool) inicializado una vez al arrancar el contenedor — evita el costo de abrir una conexión TCP+TLS nueva por cada `recommendation_request`, relevante dado el mínimo de 1 réplica siempre activa (PATTERN-04).

## 4. Patrones de Seguridad

### PATTERN-10 — Managed Identity para acceso a Azure OpenAI/Foundry y Postgres (SECURITY-06)
El Container App usa una **system-assigned Managed Identity**:
- Rol `Cognitive Services OpenAI User` (o el rol específico de Foundry equivalente) scoped únicamente al recurso Azure OpenAI/Foundry de este proyecto — no a nivel de suscripción.
- Autenticación a Postgres vía Azure AD (Entra ID) auth cuando esté disponible para Flexible Server, en vez de usuario/password estático; si no es viable en esta iteración, connection string referenciada desde Key Vault (nunca hardcodeada, PATTERN-11).

### PATTERN-11 — Secrets vía Key Vault referenciado desde Container Apps
Ninguna credencial en variables de entorno en texto plano dentro de la definición del Container App — todas las referencias sensibles (connection string de Postgres si no se usa Azure AD auth, cualquier clave de API) se resuelven vía Container Apps secrets respaldados por Azure Key Vault.

### PATTERN-12 — Excepción documentada de autenticación de endpoint (SECURITY-08)
El endpoint WS es público por diseño (chat widget para visitantes anónimos) — no requiere JWT/sesión. Esta excepción ya fue evaluada y aceptada en NFR Requirements; no se re-abre aquí, solo se traduce en que no hay middleware de auth en la capa de aplicación para esta ruta.

### PATTERN-13 (pendiente, no implementado) — Rate limiting
SECURITY-11 permanece como hallazgo abierto (riesgo aceptado explícitamente por el usuario en NFR Requirements). No se diseña un patrón de rate limiting en este incremento — queda documentado como deuda técnica conocida para una vuelta futura (ej. middleware de throttling por IP en FastAPI, o una regla de Container Apps/Front Door si se agrega más adelante).

---

## Resumen de compliance (heredado de NFR Requirements, sin cambios)
Ver `nfr-requirements.md` para la tabla completa SECURITY-01 a 15 y PBT-01/09. Este documento traduce esas decisiones en patrones concretos; no reabre ni cambia el estado de compliance ya registrado.

---

# Incremento 2 — Chat conversacional + tool-calling + pago (Mercado Pago)

**Fecha**: 2026-07-06
**Nota**: por decisión del usuario ("no te preocupes tanto por performance, es una demo"), este incremento reutiliza los patrones de resiliencia/escalabilidad ya establecidos en incremento 1 sin abrir variantes nuevas de optimización.

## 5. Patrones de Resiliencia — extensiones

### PATTERN-14 — Retry con backoff para `create_payment_link` (Mercado Pago)
Misma política que PATTERN-01 (máx. 3 intentos, backoff 0.5s→1s→2s + jitter) aplicada a la llamada de creación de preferencia. Si se agotan los intentos, el tool retorna un resultado de error (BR-18) — nunca lanza una excepción no controlada que rompa el stream del agente.

### PATTERN-15 — Registro de tool-calls pendientes (`PendingToolCallRegistry`)
El patrón "humano en el loop" (`collect_profile_data`, business-logic-model.md Sección 8.1) requiere que el tool Python haga `await` sobre un `asyncio.Future`. Este `Future` se registra en un diccionario en memoria, anclado al ciclo de vida de la conexión WS (mismo principio que PATTERN-05: sin estado distribuido, la conexión que originó el tool-call es la única que puede resolverlo). Al cerrarse la conexión WS, cualquier `Future` pendiente se cancela explícitamente (evita fugas de memoria/tareas huérfanas).

> **Actualización (Build and Test, ronda 2)**: la decisión original ("sin timeout adicional — Clarification NFR Q1 = C, la desconexión del socket es el límite natural") resultó **incorrecta en la práctica** — verificado con Playwright real: un usuario puede abandonar el widget sin desconectarse (ej. clic en "Nueva conversación"), lo que bloqueaba el bucle principal de `ChatWebSocketHandler` para siempre (nunca se alcanza el punto donde se detectaría la desconexión). Se agregó `profile_data_timeout_seconds` (config, default 300s) — `asyncio.wait_for(future, timeout=...)` — y además `_receive_loop` ahora llama `pending_tool_calls.cancel_all()` inmediatamente al detectar `WebSocketDisconnect` (no solo en el `finally` de `handle_connection`, que nunca se alcanzaba). Ver `business-logic-model.md` Sección 15 para el detalle completo del bug y la investigación.

### PATTERN-16 — Webhook idempotente
Antes de procesar cualquier notificación de pago, se verifica si el `Lead` correspondiente ya tiene `payment_confirmed=true` para ese `preference_id` — si es así, se responde 200 inmediatamente sin reprocesar (confirmado en NFR Requirements). Evita efectos duplicados ante reintentos de Mercado Pago.

## 6. Patrones de Seguridad — extensiones

### PATTERN-17 — Verificación de firma HMAC del webhook (SECURITY-05/09)
Todo request a `POST /webhooks/mercadopago` se valida contra `x-signature`/`x-request-id` (HMAC con el secreto de Key Vault) **antes** de tocar cualquier lógica de negocio o base de datos — un request con firma inválida se rechaza con 401 y se loguea (sin PII) como intento sospechoso.

### PATTERN-18 — Fuente de verdad post-webhook (defensa en profundidad)
Incluso tras verificar la firma, el estado final del pago no se toma del payload del webhook — se re-consulta `GET /v1/payments/{id}` (BR-20) antes de marcar `payment_confirmed=true`. Complementa PATTERN-17: firma válida confirma *origen*, la re-consulta confirma *estado actual*.

### PATTERN-19 — Sin exposición pública del webhook en este incremento
Consistente con la decisión de NFR Requirements: no se configura túnel ni ruta pública para el webhook. Se verifica con un script de simulación local que firma payloads realistas contra `localhost` (ver `nfr-requirements.md` Sección 10 del incremento 2).

## 7. Patrones de Persistencia (nuevo)

### PATTERN-20 — Sesión de agente por referencia, no por duplicación (Foundry Memory)
`ConversationSession.service_session_id` es la única referencia a la transcripción completa (gestionada por Foundry Memory) — el backend no duplica el historial de mensajes en Postgres. Solo se persisten datos derivados (`Lead`: perfil, motivación, score) más la referencia de sesión, evitando doble fuente de verdad de la conversación.

---

# Incremento 3 — BackOffice: read path + broadcast en tiempo real + agente de outreach

**Fecha**: 2026-07-11

## 8. Patrones de Resiliencia — extensiones

### PATTERN-21 — Retry con backoff para `EmailSender.send` (Azure Communication Services)
Consistente con `PATTERN-01`/`PATTERN-14` (no con la excepción deliberada de la llamada LLM de `generate_draft`, ver más abajo): `send_draft` envuelve `EmailSender.send` con el mismo `RetryPolicy` (backoff exponencial) ya usado para otras llamadas externas. Solo tras agotar los reintentos el draft permanece en `status = "pending"` y el error se propaga a la UI (NFR Requirements Sección 16) — los reintentos ocurren primero, el fallback manual (botón "Send") sigue siendo el mismo.

### PATTERN-22 — Sin retry automático para la llamada LLM de `generate_draft` (excepción explícita a PATTERN-21)
A diferencia de `EmailSender.send`, la llamada agentic dentro de `generate_draft` (Functional Design, Sección 21) **no** se envuelve en `RetryPolicy` — un solo intento fallido propaga el error de inmediato (on-demand) o se loggea y absorbe (trigger automático, BR-27). Decisión explícita del usuario en Functional Design (Question 6 = A), mantenida deliberadamente distinta del tratamiento de `EmailSender.send` — la llamada LLM ya es más costosa/lenta, y el patrón fire-and-forget (`PATTERN-23`) del trigger automático hace que un reintento automático agregue latencia sin un beneficio claro para el caso de uso.

### PATTERN-23 — Generación de draft en background (fire-and-forget) para el trigger automático
El subscriber de `OutreachAgentService` a `LeadEventPublisher` no bloquea al publisher: `generate_draft(lead_id, trigger="auto")` se agenda como `asyncio.create_task(...)` en vez de ser `await`ado dentro del callback (BR-24). Esto desacopla la latencia de la llamada agentic (Sección 21 de business-logic-model.md) del turno de chat en `apps/chat` que disparó el cambio de score.

### PATTERN-24 — Detección perezosa de conexiones muertas en `/ws/leads`
A diferencia de `/ws/chat` (bidireccional), `/ws/leads` es un canal solo de push — el servidor transmite snapshots/eventos, el cliente no envía mensajes de aplicación. `LeadBroadcaster` no implementa heartbeat/ping-pong activo: una conexión caída se detecta y se remueve del set de broadcast recién en el próximo intento de envío fallido. Simple y consistente con el sesgo de infraestructura mínima del proyecto — aceptable porque reconectar es barato (el cliente siempre recibe un snapshot fresco al reconectar, Story 3 AC), aunque la limpieza del set de conexiones pueda demorar levemente tras una caída silenciosa.

## 9. Patrones de Escalabilidad — extensiones

### PATTERN-25 — Instancia única obligatoria (`min=max=1` réplica) para correctitud de `/ws/leads`
Extiende `PATTERN-04` (que solo garantizaba "mínimo 1 réplica" por costo/cold-start): en este incremento, `agent-service` debe fijarse en **exactamente 1 réplica** (`minReplicas = maxReplicas = 1` en Container Apps), porque `LeadEventPublisher`/`LeadBroadcaster` son en memoria y de un solo proceso — un evento publicado en una réplica nunca llega a un cliente conectado a otra. A diferencia de `PATTERN-05` (afinidad de conexión WS, que toleraba escalar mientras cada conexión individual quedara pegada a su réplica), este patrón bloquea el escalado horizontal por completo hasta que se introduzca un pub/sub externo (fuera de alcance, ver `nfr-requirements.md` Sección 17).

## 10. Patrones de Seguridad — extensiones

### PATTERN-26 — Validación de email antes de enviar (fail-safe default)
Extiende el espíritu de `PATTERN-03`: `send_draft` valida que `Lead.email` no esté vacío *antes* de invocar `EmailSender.send` — si está vacío, rechaza con un error de validación sin siquiera intentar el envío (BR-28). `EmailSender.send` nunca se invoca con un destinatario vacío, por diseño, no por manejo de excepción reactivo.

### PATTERN-27 — Redacción de contenido de draft en logs
Extiende `PATTERN`s de logging sin PII ya establecidos (`SECURITY-03`): `OutreachDraft.subject`/`body` nunca se escriben en texto plano en logs de aplicación — solo `draft_id`/`lead_id`/`status`/`trigger`.

## 11. Patrones de Confiabilidad — extensiones

### PATTERN-28 — Guard atómico de envío único (`send_draft`)
`send_draft` ejecuta `UPDATE outreach_drafts SET status = 'sent', sent_at = now() WHERE draft_id = :id AND status = 'pending'` — si la actualización afecta 0 filas, no se invoca `EmailSender.send` una segunda vez; se retorna el draft ya actualizado. Complementa (no reemplaza) el estado de carga en el frontend (`DraftPanel`, mecanismo primario de UX) — mismo espíritu de defensa en profundidad que `PATTERN-18` (fuente de verdad post-webhook).

## Resumen de compliance — Incremento 3 (heredado de NFR Requirements, sin cambios)
Ver `nfr-requirements.md` Sección 19 (tabla SECURITY-01/03/06/11 + NFR-1) — todas las filas siguen aplicando sin cambios a los nuevos componentes de este incremento.
