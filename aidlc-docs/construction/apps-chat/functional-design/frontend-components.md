# Frontend Components — apps/chat (integración con agent-service incremento 2)

**Fecha**: 2026-07-06
**Unidad**: `apps/chat` (equivalente a la antigua `unit-4: frontend-widget` del diseño original, formalizada en `frontend-integration-execution-plan.md`)
**Basado en**: `aidlc-docs/inception/requirements/frontend-integration-requirements.md`, protocolo definido en `aidlc-docs/construction/agent-service/functional-design/business-logic-model.md` Sección 9

---

## 1. Cambios sobre la arquitectura Effect existente

`apps/chat` ya usa Effect (`lib/ChatService.ts`, `lib/HttpChatService.ts`, `lib/runtime.ts`, `hooks/useChat.ts`) con un contrato HTTP POST + streaming de texto que **ya no aplica** (RF-I01: el transporte pasa a ser WebSocket `/ws/chat`). Esto implica:

- `lib/HttpChatService.ts` se reemplaza por un `WsChatService.ts` (misma interfaz `ChatService.stream`, nueva implementación sobre WebSocket) — se mantiene el patrón de `Context.Tag` + `ManagedRuntime` ya establecido.
- `app/api/ask/route.ts` (proxy Next.js a `/ask`) deja de usarse para el flujo conversacional — no hay proxy HTTP intermedio; el navegador conecta el WebSocket directamente a `agent-service` (alcance local, sin CORS, ver RF NFR 4.1).
- El stream que consume el frontend deja de ser solo texto — ahora es una unión discriminada de eventos (`recommendation_delta`, `profile_data_requested`, `payment_link_created`, `session_created`, etc., ver protocolo en business-logic-model.md Sección 9), no un stream de bytes plano.

## 2. Jerarquía de componentes (nuevos/modificados)

```
ChatPage (app/page.tsx, existente)
 └─ ChatWindow (existente, adaptado)
     ├─ MessageList (existente)
     │   ├─ MessageBubble (existente)
     │   └─ CourseRecommendationCard[]  ── NUEVO, reemplaza SourceChips
     ├─ ProfileDataWidget                ── NUEVO
     └─ InputBar (existente)

/pagar  ── ELIMINADO del alcance (RF-I11: ya no se necesita, Mercado Pago Checkout Pro
           entrega un init_point ya hospedado; el link se muestra como parte del texto
           del agente / opcionalmente como botón al recibir payment_link_created)
```

## 3. `CourseRecommendationCard` (reemplaza `SourceChips`, RF-I16)

**Props**:
```ts
type CourseRecommendationCardProps = {
  courseId: string
  name: string
  similarityScore: number
}
```
**Estado**: sin estado propio (presentacional puro).
**Fuente de datos**: se popula desde el evento `recommendation_done.candidates` (mismo shape que incremento 1: `{course_id, name, similarity_score}`).
**Interacción**: ninguna en este incremento (solo lectura) — deduplicación por `course_id` (análogo a como `SourceChips` deduplicaba por `course`).

## 4. `ProfileDataWidget` (nuevo, RF-I17)

**Props**:
```ts
type ProfileDataWidgetProps = {
  callId: string
  prefill: { budget: number; maxDurationWeeks: number; professionalBackground: string; desiredStack: string }
  onSubmit: (data: ProfileData) => void
}
```
**Estado**: form state local (controlado), inicializado desde `prefill` (los valores que el agente ya infirió de la conversación — el usuario los corrige en vez de partir de cero).
**Trigger de aparición**: el hook de chat detecta un evento de stream `profile_data_requested` y renderiza este componente en línea dentro de `MessageList`, en el punto de la conversación donde ocurrió (no como modal separado — mantiene el flujo de chat visualmente continuo).
**Al enviar**: dispara `onSubmit`, que envía por el WS `{ type: "profile_data_submitted", call_id, budget, max_duration_weeks, professional_background, desired_stack }` (RF-I04) y oculta el widget, reanudando el chat normal (los siguientes eventos del stream retoman automáticamente, sin acción adicional del frontend, dado que el backend continúa el mismo `agent.run()` una vez resuelto el `Future`, ver business-logic-model.md Sección 8.1).

## 5. Hook de chat — `useChat` (reescrito sobre WebSocket)

**Responsabilidades nuevas** respecto a la versión HTTP actual:
- Abrir/mantener la conexión WebSocket a `/ws/chat` (con reconexión, análogo al `useWebSocket` del diseño original de `unit-4`).
- Parsear cada mensaje entrante por `type` (unión discriminada) y despachar a un reducer de estado de conversación con casos: `recommendation_delta` (texto), `profile_data_requested` (mostrar widget), `payment_link_created` (resaltar link), `session_created` (persistir `service_session_id`), `relax_filters_offer`/`no_exact_match_showing_all`/`no_recommendation` (mensajes informativos de texto, sin UI especial — RF-I07/Clarification 4).
- Persistir `service_session_id` en `localStorage` al recibir `session_created`; al montar, si existe un valor guardado, enviarlo en el primer mensaje de conexión para retomar la conversación (RF-I05).
- Enviar `user_message` por cada mensaje de texto libre del usuario (RF-I02).

## 6. Fuera de alcance de este documento

- Backoffice / visualización de leads (RF-I18, diferido).
- Página de checkout propia (descartada junto con Culqi, RF-I11 revisado — Mercado Pago Checkout Pro no la requiere).
- Manejo de reconexión con recuperación de un `profile_data_requested` pendiente a mitad de completar (si el usuario refresca la página exactamente mientras el widget está abierto, se asume que retoma la conversación desde el último estado estable — el widget no persiste su estado local no enviado; caso borde no cubierto en este incremento).
