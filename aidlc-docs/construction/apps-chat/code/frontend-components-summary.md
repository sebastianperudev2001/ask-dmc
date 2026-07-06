# Frontend Components — Code Generation Summary (apps/chat, Incremento 2)

## Generado

- **`types/chat.ts`** (reescrito): `ChatPhase`, `ToolCallInfo`, `BotMsg` extendido, `ProfileData`/`ProfileDataPrefill`, `CourseRecommendation` (reemplaza `Source`).
- **`lib/ChatService.ts`** (interfaz rediseñada): `ChatEvent` unión discriminada de 6 variantes; el servicio pasa de `stream(question)` (una llamada por pregunta) a `events` (stream persistente) + `sendMessage`/`submitProfileData` (efectos sobre la misma conexión).
- **`lib/WsChatService.ts`** (nuevo): implementación real sobre `WebSocket` del navegador. `Layer.effect` bloquea hasta que el socket abre (`Effect.async` sobre el evento `open`) antes de retornar el servicio — evita que `sendMessage` se dispare contra un socket `CONNECTING`. `events` usa `Stream.asyncPush` (patrón documentado de Effect) para traducir `onmessage` a `ChatEvent`. Persiste `service_session_id` en `localStorage` internamente al ver `session_created` (RF-I05).
- **`lib/runtime.ts`**: usa `WsChatServiceLive`.
- **`hooks/useChat.ts`** (reescrito): un único listener del stream persistente por el ciclo de vida del componente (antes: uno por pregunta) — el diseño de "un turno = una burbuja que acumula eventos" se mantiene: `applyDelta`, `applyRecommendations`, `applyProfileRequest`/`clearProfileRequest`, `applyPaymentLink`, `markTurnDone` (helpers puros, exportados para test).
- **`components/ProfileDataWidget.tsx`** (nuevo): formulario inline con prefill de los valores que el agente ya infirió; `data-testid` por campo (`profile-data-widget-{budget,duration,background,stack}-input`, `-submit-button`).
- **`components/CourseRecommendationCard.tsx`** (nuevo, reemplaza `components/SourceChips.tsx`, eliminado): tarjetas de curso recomendado (nombre + % de match), deduplicadas por `courseId`.
- **`components/BotMessage.tsx`** (modificado): ya no usa el `ToolCallBlock` hardcodeado de `search_brochures` con datos falsos — ahora `ToolCallBlock` (componente preexistente, sin cambios) se reutiliza con datos reales del tool `create_payment_link`; se agregan `ProfileDataWidget` y `CourseRecommendationCard`.
- **`components/MessageList.tsx`/`ChatApp.tsx`**: propagan `onSubmitProfileData` desde `useChat` hasta `BotMessage`.

## Limpieza (brownfield)
Eliminados: `lib/HttpChatService.ts`, `lib/HttpChatService.test.ts`, `app/api/ask/route.ts` (proxy Next.js ya no necesario — el navegador conecta directo al WS de `agent-service`), `components/SourceChips.tsx`.

## Tests generados
- `lib/ChatService.test.ts` (reescrito): contrato del nuevo `ChatService` Tag vía un layer fake.
- `lib/WsChatService.test.ts` (nuevo): traducción de los 6 tipos de evento de wire (`toChatEvent`, exportado) + tipos desconocidos → `null`; gate de apertura del socket antes de enviar (con un `FakeWebSocket` mínimo, dado que `vitest.config.ts` usa `environment: 'node'` sin `WebSocket` global). El lado de recepción en vivo (registro del listener `message` dentro de un fiber `fork`-eado) no se testeó de punta a punta por timing de fibers real vs. simulado — se prefirió mantener el test robusto (sin flakiness) y confiar en `toChatEvent` (ya cubierto) + verificación manual contra el backend real.
- `hooks/useChat.test.ts` (reescrito): los 7 helpers puros de estado.

## Verificación
- `npx tsc --noEmit`: limpio.
- `npx vitest run`: 19/19 tests verdes.
- `npx next build`: build de producción exitoso.

## Gap de diseño encontrado y corregido en el backend durante esta etapa
El protocolo de chat libre no emitía ninguna señal de "fin de turno" — se agregó `turn_done` (`TurnDoneOut`) al backend (ver nota en el plan de código y en `business-logic-model.md` Sección 13), necesario para que `useChat` sepa cuándo re-habilitar el input sin depender de heurísticas de silencio.

## Pendiente explícito (no cubierto en este incremento)
- Backoffice Portal (RF-I18, diferido).
- Reconexión automática de WebSocket tras desconexión (fuera de alcance — demo/local; un refresh de página reabre la conexión).
- Recuperación de un `profileRequest` pendiente si el usuario refresca la página exactamente mientras el widget está abierto (caso borde no cubierto, ya anotado en `frontend-components.md` de Functional Design).
