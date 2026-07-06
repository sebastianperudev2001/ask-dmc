# Business Logic — Code Generation Summary (agent-service, Incremento 2)

## Generado

- **Dominio** (`src/domain/models.py`, extendido): `Motivation`, `LeadScore`, `PaymentStatus`, `PaymentOrder`, `Lead` (mutable, actualizado incrementalmente — BR-21), `ConversationSession`.
- **Scoring** (`src/domain/lead_scoring.py`): `score_lead(ScoringSignals) -> (LeadScore, str)` — BR-17, pura y determinística.
- **Pausa "humano en el loop"** (`src/domain/pending_tool_calls.py`): `PendingToolCallRegistry` — PATTERN-15.
- **Errores nuevos** (`src/domain/errors.py`): `PaymentServiceUnavailableError`, `InvalidWebhookSignatureError`.

## Tests generados

- `tests/unit/test_lead_scoring.py` — P9 (determinismo, Hypothesis), P10 (invariante: `hot` requiere datos completos), casos de ejemplo (intención de compra → hot, motivación indefinida → cold).
- `tests/unit/test_pending_tool_calls.py` — registro, resolución (incluida doble-resolución), cancelación (incluida sobre futures ya resueltos).

## Cobertura de Business Rules

| BR | Cubierta en |
|---|---|
| BR-16 (el agente decide invocar tools) | `src/adapters/chat_agent_client.py` — el system prompt instruye, no hay lógica de aplicación forzando el momento |
| BR-17 (lead scoring) | `lead_scoring.py` + P9/P10 |
| BR-18 (error de pago) | `chat_agent_client.py._create_payment_link` — resultado de texto, no excepción sin manejar |
| BR-19 (escalación solo persistencia) | **Limitación conocida** — ver abajo |
| BR-20 (verificación de webhook) | Ver `api-layer-summary-increment2.md` |
| BR-21 (persistencia de leads) | `ChatAgentClient._upsert_lead()` (invocado desde los 3 tools) + `src/adapters/postgres_lead_repository.py` — ver `repository-layer-summary-increment2.md` |

## Gap de diseño corregido (ver detalle en business-logic-model.md Sección 13 y en el plan de código)

El Functional Design original no incluía una tool de recomendación — se agregó `get_course_recommendations` (documentado en `api-layer-summary-increment2.md`, ya que vive en el mismo adaptador que expone la API del agente al WS).

## Persistencia incremental del Lead (BR-21)

`ChatAgentClient._upsert_lead(**fields)` — helper interno invocado desde los 3 tools, no un tool propio: busca (o crea) el `Lead` por `service_session_id` y actualiza solo los campos relevantes a cada punto de la conversación:
- `collect_profile_data` → `profile_summary`
- `get_course_recommendations` → `recommended_programs`
- `create_payment_link` → `payment_link_sent`, `payment_checkout_url`, `payment_preference_id`

Esto es lo que hace posible que el webhook de Mercado Pago encuentre el `Lead` correcto vía `find_by_service_session_id` (sin esto, el `Lead` nunca se habría creado y la confirmación de pago no tendría a quién actualizar).

## Limitación conocida: BR-19 (escalación) sin persistencia del flag

No se agregó un tool para "pedir hablar con un humano" — el agente responde conversacionalmente por instrucción del system prompt (BR-19), pero **el flag `escalated_to_human` nunca se persiste en el `Lead`**, porque no hay un punto del flujo que lo detecte y llame a `_upsert_lead(escalated_to_human=True)`. Tampoco se persisten `name`/`email`/`motivation` (RF-02/04/06 del documento original) — no hay un tool ni lógica que los extraiga de la conversación libre. Documentado aquí explícitamente como pendiente para un incremento futuro, no oculto — `PostgresLeadRepository` ya soporta estos campos, falta la lógica de extracción/tool que los llene.
