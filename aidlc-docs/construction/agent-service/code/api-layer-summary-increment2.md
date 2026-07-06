# API Layer — Code Generation Summary (agent-service, Incremento 2)

## Generado

- **Schemas** (`src/api/schemas.py`, extendido): `UserMessageIn`, `ProfileDataSubmittedIn`, `ProfileDataPrefill`, `ProfileDataRequestedOut`, `PaymentLinkCreatedOut`, `SessionCreatedOut`, `MercadoPagoWebhookPayload`/`MercadoPagoWebhookData`.
- **`src/adapters/mercadopago_client.py`**: `MercadoPagoPaymentClient.create_preference(amount, description, client_details, external_reference)` (API de Preferencias, retorna `init_point`/`sandbox_init_point`) y `.get_payment(payment_id) -> PaymentDetails` (`GET /v1/payments/{id}`, incluye `external_reference` para correlación con `Lead`). Envuelto en `RetryPolicy` (PATTERN-14).
- **`src/adapters/mercadopago_signature.py`**: `SignatureVerifier.verify()` — HMAC-SHA256 sobre el manifest `id:{data_id};request-id:{x_request_id};ts:{ts};`, comparado contra el componente `v1` de `x-signature` (PATTERN-17).
- **`src/adapters/chat_agent_client.py`**: `ChatAgentClient` — construye el `Agent` de Microsoft Agent Framework con **3 tools**:
  - `collect_profile_data` — pausa vía `asyncio.Future` (PATTERN-15) hasta que el WS handler resuelve con `profile_data_submitted`.
  - `get_course_recommendations` — reutiliza `RecommendationOrchestrator`/`CourseRepository`/`EmbeddingService` de incremento 1 sin modificarlos; maneja la rama de relajación devolviendo texto para que el agente la ofrezca conversacionalmente (sin pausa).
  - `create_payment_link` — llama a `MercadoPagoPaymentClient.create_preference` con `external_reference=service_session_id`.
  - Expone `create_session()`/`get_session()` (PATTERN-20) y `stream()`, que traduce a `TextDelta`/`ProfileDataRequested`/`PaymentLinkCreated`/`RecommendationsReady`.
  - `_upsert_lead()` (helper interno): persiste el `Lead` incrementalmente desde los 3 tools (ver business-logic-summary-increment2.md).
- **`src/api/chat_websocket_handler.py`**: `ChatWebSocketHandler` para `/ws/chat` — un único receptor concurrente (`_receive_loop`) resuelve `profile_data_submitted` directamente contra `PendingToolCallRegistry` y encola `user_message` para el loop principal; emite `session_created` una vez por conexión cuando `service_session_id` queda disponible.
- **`src/api/webhook_handler.py`**: `MercadoPagoWebhookHandler.handle()` — verifica firma → ignora eventos que no son `payment` → re-consulta `GET /v1/payments/{id}` (BR-20) → idempotente si `Lead.payment_confirmed` ya es `True` (PATTERN-16) → actualiza el lead vía `external_reference`.
- **`main.py`**: reemplaza `/ws/recommendation` por `/ws/chat`, agrega `POST /webhooks/mercadopago`. `src/api/websocket_handler.py` (incremento 1) queda sin usar desde `main.py` pero intacto como referencia histórica (mismo tratamiento que `services/api/` tras DIV-10) — sus tests (`test_websocket_flow.py`) siguen pasando porque construyen su propia mini-app, no dependen de `main.py`.

## Tests generados

- `tests/unit/test_mercadopago_signature.py` — firma válida, `data_id` manipulado, secreto incorrecto, header malformado, `v1` ausente.
- `tests/integration/test_chat_websocket_flow.py` (`FakeChatAgentClient`, usa el `PendingToolCallRegistry` real): mensaje libre + `session_created`; pausa/resolución de `collect_profile_data`; evento `payment_link_created`; sesión retomada no se re-anuncia.
- `tests/integration/test_webhook_flow.py` (`FakeLeadRepository`, `FakePaymentClient`): webhook válido confirma pago; firma inválida → 401; webhook repetido → idempotente; evento no-`payment` → ack sin procesar.

## Gaps de diseño corregidos durante generación (ver detalle en business-logic-model.md Sección 13 y en audit.md)
1. Tool faltante para recomendación (`get_course_recommendations`, no estaba en Functional Design).
2. Correlación webhook↔lead (`external_reference`/`PaymentDetails`, no estaba en Functional Design).
3. El `Lead` nunca se creaba — agregado `_upsert_lead()` en los 3 tools (encontrado y corregido durante generación, no solo documentado).

## Cobertura de Business Rules
| BR | Cubierta en |
|---|---|
| BR-16 | System prompt de `ChatAgentClient` — decisión del LLM, no lógica de aplicación |
| BR-18 | `_create_payment_link` — error como texto, no excepción |
| BR-20 | `webhook_handler.py` — firma + re-consulta antes de confirmar |
