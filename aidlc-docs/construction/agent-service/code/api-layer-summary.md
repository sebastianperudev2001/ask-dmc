# API Layer — Code Generation Summary (agent-service, Incremento 1)

## Generado

- `services/agent-service/src/api/schemas.py` — Pydantic v2 schemas para los mensajes WS entrantes (`RecommendationRequestMessage`, `RelaxFiltersResponseMessage`) con bounds explícitos (SECURITY-05: `budget`/`max_duration_weeks` acotados, `professional_background`/`desired_stack` con `max_length=2000`) y salientes (`RecommendationDeltaMessage`, `RecommendationDoneMessage`, `RelaxFiltersOfferMessage`, `NoExactMatchShowingAllMessage`, `NoRecommendationMessage`).
- `services/agent-service/src/api/websocket_handler.py` — `WebSocketConnectionHandler`, implementa el flujo completo de business-logic-model.md Sección 2: valida input, genera `ProfileQuery`, invoca al orquestador, maneja la rama de confirmación de relajación (con timeout vía `asyncio.wait_for`, PATTERN-02), sirve candidatos vía streaming del agente, y captura errores de forma genérica (SECURITY-09/15) sin exponer detalles internos.
- `services/agent-service/main.py` — wiring de FastAPI, `DefaultAzureCredential` (Managed Identity en prod / Azure CLI en local), lifespan que abre/cierra el `ConnectionPool`, endpoint `/health`.
- `services/agent-service/src/logging_config.py` — logging JSON estructurado (SECURITY-03), sin PII (nunca se loguea el contenido de `professional_background`/`desired_stack`).

## Tests generados

- `tests/integration/fakes.py` — `FakeEmbeddingService`, `FakeRecommendationAgentClient`.
- `tests/integration/test_websocket_flow.py` — match exacto (streaming completo), oferta de relajación confirmada, oferta declinada (catálogo completo), catálogo vacío (sin invocar al agente), request inválido (error genérico).

## Gap conocido (no implementado)
No se incluyó un test de **timeout real** de `_await_relax_confirmation` (PATTERN-02, 5 min) — las pruebas de temporización real son inherentemente frágiles en un test suite; el comportamiento de timeout se implementó (`asyncio.wait_for`) y se ejercitó manualmente, pero no vía un test automatizado con reloj real. Candidato a cubrir con un reloj inyectable (`asyncio` loop time mockeado) en una vuelta futura.

## Cobertura de seguridad en esta capa
SECURITY-05 (validación de input vía Pydantic), SECURITY-08 (endpoint público documentado, sin middleware de auth), SECURITY-09 (`reason` codificado, nunca detalles internos), SECURITY-15 (manejador global de excepciones en `handle_connection`, fail-safe).
