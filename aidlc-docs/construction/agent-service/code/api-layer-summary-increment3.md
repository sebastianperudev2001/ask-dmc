# API Layer — Code Generation Summary (agent-service, Incremento 3)

## Generado

- **Schemas** (`src/api/schemas.py`, extendido): `LeadOut` (+ `.from_lead`, única fuente de verdad del wire format de un Lead, reutilizada por `GET /leads` y por `/ws/leads`), `LeadsSnapshotOut`, `LeadEventOut`, `OutreachDraftOut` (+ `.from_draft`).
- **`src/api/lead_broadcaster.py`**: `LeadBroadcaster` — gestiona las conexiones `/ws/leads`; snapshot completo en cada conexión, luego streaming de eventos; detección perezosa de conexiones muertas (PATTERN-24, sin heartbeat).
- **`src/adapters/outreach_agent_service.py`**: `OutreachAgentService` — agente con tool-calling (`get_course_details`), `generate_draft`/`get_active_draft`/`send_draft`/`discard_draft`; se suscribe a `LeadEventPublisher` en su constructor (auto-trigger, BR-24).
- **`src/adapters/acs_email_sender.py`**: `AzureCommunicationServicesEmailSender` — cliente lazy (ver gap corregido abajo), envuelto en `RetryPolicy` (PATTERN-21).
- **`src/adapters/chat_agent_client.py`** (extendido): un parámetro nuevo (`lead_event_publisher`), un solo punto de publicación nuevo dentro de `_upsert_lead` (ver `business-logic-summary-increment3.md`).
- **`main.py`**: 5 rutas nuevas — `GET /leads`, `WS /ws/leads`, `POST /leads/{lead_id}/drafts`, `GET /leads/{lead_id}/drafts/active`, `POST /drafts/{draft_id}/send`, `POST /drafts/{draft_id}/discard`. `LeadEventPublisher`/`LeadBroadcaster`/`OutreachAgentService` instanciados como singletons de módulo (a diferencia de `ChatAgentClient`, que se construye por conexión vía `agent_client_factory`) — necesario porque su suscripción al publisher debe registrarse una sola vez, no por request (PATTERN-25 ya exige instancia única de proceso).

## Tests generados

- `tests/unit/test_outreach_agent_service.py` (13 tests) — dedupe (BR-22/BR-23), skip por email faltante solo en auto (BR-25), validación de email antes de enviar (PATTERN-26), envío idempotente cuando ya está `sent` (PATTERN-28), fallo de email deja el draft `pending` (BR-28), wiring del trigger automático vía `LeadEventPublisher` real (solo `score_changed` → `hot` dispara, `created`/`warm` no).
- `tests/unit/test_lead_broadcaster.py` (3 tests) — snapshot al conectar, broadcast a clientes conectados, conexión muerta se remueve del set (PATTERN-24) sin afectar a las demás.
- `tests/unit/test_acs_email_sender.py` (3 tests) — mensaje enviado con el formato esperado, retry-with-backoff (PATTERN-21), error tras agotar reintentos.
- `tests/integration/test_leads_websocket_flow.py` (4 tests, `TestClient.websocket_connect` real) — snapshot con leads existentes, snapshot vacío, evento publicado llega al cliente conectado, desconexión de un cliente no rompe el broadcast a otros.
- `tests/integration/test_outreach_draft_flow.py` (5 tests, HTTP real vía `TestClient`) — generar→enviar de punta a punta, generar dos veces retorna el mismo draft pending, discard→generar produce un draft nuevo, **2 eventos `score_changed`→`hot` disparados por el publisher real generan un solo draft activo** (Story 4 AC verificada a través de la suscripción real, no llamando `generate_draft` directamente), `get_active_draft` retorna `None` cuando no hay draft.

**Suite completa tras este incremento**: 94 passed, 23 skipped (Postgres-dependientes, sin `TEST_DATABASE_URL` local).

## Gap de diseño encontrado y corregido durante la generación

`AzureCommunicationServicesEmailSender.__init__` originalmente construía `EmailClient.from_connection_string(...)` de forma inmediata (eager). Como `main.py` instancia `OutreachAgentService` (y por lo tanto este sender) como singleton de módulo al importar, y `ACS_CONNECTION_STRING` está vacío hasta que el recurso real de Terraform se aplique, esto **rompía por completo el arranque local de `agent-service`** — verificado directamente (`ValueError: Invalid connection string`) al intentar importar `main.py`. Corregido haciendo la construcción del cliente perezosa (recién en el primer `.send()`), mismo criterio ya usado implícitamente por `MercadoPagoPaymentClient` (tolera un `access_token` vacío hasta que se hace una llamada real). Sin este fix, ningún desarrollador habría podido correr el servicio en local sin tener ya un recurso ACS real provisionado — contradice el patrón "local-first" ya establecido en incrementos anteriores.

## Cobertura de Business Rules / Patrones

| BR / Pattern | Cubierta en |
|---|---|
| FR-7 (`GET /leads`) | `main.py::list_leads`, `LeadQueryService` |
| FR-6/FR-8 (`/ws/leads`) | `main.py::leads_websocket`, `LeadBroadcaster` |
| FR-9/FR-10/FR-11 | `OutreachAgentService.generate_draft` + suscripción a `LeadEventPublisher` |
| FR-12/FR-13 | `main.py::send_draft`/`discard_draft`, `OutreachAgentService.send_draft` |
| PATTERN-21/22 (retry email sí, retry LLM no) | `acs_email_sender.py` vs. `outreach_agent_service.py` |
| PATTERN-24 (detección perezosa de conexiones muertas) | `lead_broadcaster.py::broadcast` |
| PATTERN-26 (validación de email antes de enviar) | `outreach_agent_service.py::send_draft` |
| PATTERN-28 (guard atómico de envío) | `postgres_draft_repository.py::mark_sent` + `send_draft`'s manejo del caso `None` |
