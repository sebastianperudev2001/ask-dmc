# Functional Design Plan — agent-service Incremento 2 (chat conversacional + tool-calling + pago)

**Basado en**: `aidlc-docs/inception/requirements/frontend-integration-requirements.md`

## Hallazgos del Spike Técnico (ya ejecutado, con evidencia real)

Antes de diseñar, se verificó contra el SDK real instalado (`agent-framework-foundry`) y el agente Foundry ya provisionado (`gpt-5.4-nano-dmc-bicep`), no contra documentación asumida:

1. **Tool-calling en streaming SÍ es distinguible**: cada `AgentResponseUpdate.contents` puede traer `Content` con `type='function_call'` (con `name`, `call_id`, fragmentos de `arguments` que se acumulan) y luego `type='function_result'` — confirmado con una llamada real de extremo a extremo (prompt real → el agente invocó `collect_profile_data` con los 4 argumentos correctamente parseados: `budget=500.0, max_duration_weeks=8, professional_background='Analista de datos', desired_stack='Azure (Data Engineering)'`).
2. **El framework auto-ejecuta e itera automáticamente**: si el tool se registra como un callable Python real (`Agent(tools=[fn])`), el SDK lo invoca solo, inyecta el `function_result` en la conversación, y continúa generando texto final — todo dentro de un único `agent.run(stream=True)`.
3. **Implicación de diseño clave**: para lograr el patrón "humano en el loop" (pausar hasta que el frontend envíe `profile_data_submitted`), la función Python del tool `collect_profile_data` debe:
   - Recibir los argumentos ya parseados por el framework (no requerimos parsear JSON manualmente)
   - Enviar por el WS un mensaje `profile_data_requested` con esos valores como prefill
   - Hacer `await` sobre un `asyncio.Future` que se resuelve cuando llega `profile_data_submitted` desde el cliente (un receptor concurrente en el mismo handler WS)
   - Retornar los datos (confirmados/corregidos por el usuario) como resultado — el agente continúa automáticamente sin cambios adicionales en el loop
   - El tool `create_payment_link` no necesita pausa: ejecuta la llamada real a Culqi dentro de la misma función async y retorna el resultado (o error) directamente
4. **Persistencia de sesión SÍ está soportada nativamente**: `Agent.create_session(session_id=...)` / `Agent.get_session(service_session_id, ...)` + `AgentSession.to_dict()/from_dict()`. `service_session_id` es el identificador gestionado por el servicio (Foundry) — se persiste del lado del cliente (ej. `localStorage`) y se usa para retomar la conversación completa tras un refresh, confirmando la decisión de Clarification 3.
5. ~~Culqi — verificación de webhook~~ **SUPERADO**: el usuario descartó Culqi (requiere negocio formal) y pivoteó de vuelta a **Mercado Pago** (DIV-11 revertido). Investigación de reemplazo: Mercado Pago Checkout Pro expone una API de Preferencias que retorna `init_point`/`sandbox_init_point` — una URL de checkout **ya hospedada por Mercado Pago**, eliminando la necesidad de una página de checkout propia que sí requería Culqi. Mercado Pago además documenta oficialmente verificación de firma HMAC de webhooks (`x-signature` + `x-request-id` contra un secreto de la aplicación) — más robusto que lo encontrado para Culqi. Diseño: verificar firma → usar `data.id` del payload para consultar `GET /v1/payments/{id}` (estado autoritativo) → actualizar lead en Postgres.

### Respuestas del usuario
- **Q1 (timeout del widget)**: **C** — sin timeout explícito; la desconexión del WS es el límite natural. El `asyncio.Future` que la tool `collect_profile_data` espera se cancela si la conexión WS se cierra (cleanup en el handler), sin lógica de temporizador adicional.
- **Q2 (verificación de webhook)**: **Reemplazada por el pivote a Mercado Pago** — ya no aplica el enfoque de re-consulta como mitigación principal (Mercado Pago sí tiene firma verificable oficial), aunque se mantiene la re-consulta a `GET /v1/payments/{id}` como buena práctica adicional de todas formas.

---

## Plan de Diseño (checkboxes)

- [ ] Domain entities: `Lead`, `ConversationSession` (o equivalente), `PaymentOrder`, extensión de `RecommendationCandidate` existente, `LeadScore`
- [ ] Business rules: reglas de scoring (hot/warm/cold, heredadas de §7 requirements.md), reglas de cuándo el agente invoca cada tool, reglas de guardrails heredados (RF-12/13/17/18)
- [ ] Business logic model: flujo completo del endpoint `/ws/chat` (mensajes de entrada/salida, ciclo de vida de una conversación, manejo de sesión/thread, lógica de los 2 tools, lógica del webhook de Culqi)
- [ ] Frontend components (ligero, para `apps/chat`): estructura de `useChat`/nuevo hook de WS con tool-calling, componente de widget de recolección de datos, tarjetas de recomendación, página `/pagar`

## Preguntas de Clarificación

### Question 1: Timeout del widget de recolección de datos
Cuando el agente invoca `collect_profile_data` y el frontend muestra el widget, la función tool queda esperando (`await`) la respuesta del usuario. Si el usuario abandona la conversación sin completar el widget, ¿cuánto tiempo debe esperar el backend antes de abortar esa espera?

A) 5 minutos — luego el tool retorna un resultado de "timeout" y el agente continúa conversacionalmente (ej. "¿seguimos? no vi tu respuesta")
B) 15 minutos
C) Sin timeout — la conexión WS ya se cierra sola si el cliente se desconecta (el timeout natural es la desconexión del socket, no uno explícito adicional)
D) Other (please describe after [Answer]: tag below)

[Answer]: C

### Question 2: Verificación del webhook de Culqi
Dado que la documentación pública de Culqi no confirma un mecanismo de firma verificable, propongo: al recibir el webhook, no confiar en su payload — usar el `order.id` recibido para volver a consultar el estado real de la orden directamente contra la API de Culqi (autenticado con nuestra propia `sk_test`/`sk_live`) antes de marcar el pago como confirmado en Postgres. ¿Estás de acuerdo?

A) Sí, proceder con ese enfoque (re-consultar la API de Culqi como fuente de verdad)
B) Prefiero que investigues más a fondo la documentación/soporte de Culqi antes de decidir (puede haber firma HMAC que no encontramos)
C) Other (please describe after [Answer]: tag below)

[Answer]: Olvidate de Culquii, necesito un negocio oficial, pivoteemos a Mercado Pago
