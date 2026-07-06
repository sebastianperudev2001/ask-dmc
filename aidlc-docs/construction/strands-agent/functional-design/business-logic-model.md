# Business Logic Model — unit-2: strands-agent

**Fecha**: 2026-07-01
**Patrón de arquitectura**: Agents-as-tools (decisión P1=C — ver razonamiento completo en `aidlc-docs/construction/plans/strands-agent-functional-design-plan.md`, Pregunta 1)

---

## 1. Componentes de esta unidad

| Componente | Tipo | Responsabilidad |
|---|---|---|
| `OrchestratorAgent` | Strands `Agent` | Mantiene la conversación real con el visitante turno a turno. Enruta determinísticamente a `identification_assistant` o `qualification_assistant` según `ConversationSession.stage`; llama a `recommend_program` al entrar a `RECOMENDACION`. Es el único agente cuyo historial se persiste (BR-08). |
| `identification_assistant` | Tool que envuelve un `Agent` especializado | Conduce la captura conversacional de nombre + correo (una pregunta a la vez, BR-03). Devuelve el texto para el usuario y actualiza `IdentificationState`. |
| `qualification_assistant` | Tool que envuelve un `Agent` especializado | Conduce la calificación conversacional de las 5 dimensiones (BR-04) y clasifica motivación (BR-05). Devuelve el texto para el usuario y actualiza `QualificationState`. |
| `recommend_program` | Tool simple (no-agente) | Fake — retorna siempre el mismo `course_id` (BR-06). |
| `SessionRepository` | Protocol / interfaz | Carga y guarda `ConversationSession` por `session_id` (BR-08). Dos implementaciones: `AgentCoreMemorySessionRepository` (PRODUCTION), `InMemorySessionRepository` (LOCAL). |
| WS dev server | Script/servidor de desarrollo (no-producción) | Expone un endpoint WebSocket de streaming (`@app.websocket`) para poder conversar con el agente mientras se construye. No tiene auth ni persiste leads — eso es `unit-3` (decisión P7=D, nota en P4). |

No hay `Graph`, `Swarm` ni `GraphBuilder` en esta unidad — descartados en la Pregunta 1 del plan de Functional Design.

---

## 2. Flujo de una sesión completa

```
BIENVENIDA ──▶ IDENTIFICACION ──▶ CALIFICACION ──▶ RECOMENDACION ──▶ FIN_ITERACION
   (saludo,       (nombre + email,      (5 dimensiones,      (tool fake,
   sin captura)    BR-01, BR-02, BR-03)  BR-04, BR-05)        BR-06)
```

- `BIENVENIDA` no es un estado con lógica propia en esta iteración: es simplemente el primer turno del `OrchestratorAgent`, cuyo system prompt lo instruye a presentarse como IA de DMC Institute (US-01 Escenario 1) y luego transicionar inmediatamente a `IDENTIFICACION`.
- `FIN_ITERACION` es un estado terminal explícito para esta ronda de construcción — **no** es `CIERRE` ni `ESCALACIÓN` del PRD (esos siguen sin implementarse; ver BR-07 y BR-10). Al llegar aquí, el orquestador simplemente confirma la recomendación entregada y cierra la conversación sin generar link de pago ni persistir un lead.

El avance de etapa es determinista (BR-09): ocurre solo cuando el sub-agente activo marca su estado como `is_complete`.

---

## 3. Algoritmo de procesamiento de un turno (por mensaje entrante en el WS)

```
on_message(session_id, user_message):
    session = SessionRepository.load(session_id)
        if not exists: session = new ConversationSession(stage=BIENVENIDA)

    session.messages.append(ConversationTurn(role="user", content=user_message))

    match session.stage:
        BIENVENIDA:
            # primer turno de la sesión: el propio OrchestratorAgent saluda
            # y transiciona a IDENTIFICACION sin necesitar sub-agente
            reply = OrchestratorAgent.welcome_and_transition()
            session.stage = IDENTIFICACION

        IDENTIFICACION:
            result = identification_assistant(context=session.identification,
                                                user_message=user_message)
            reply = result.reply_text
            session.identification = result.updated_state
            if session.identification.is_complete:       # BR-01
                session.stage = CALIFICACION

        CALIFICACION:
            result = qualification_assistant(context=session.qualification,
                                               user_message=user_message)
            reply = result.reply_text
            session.qualification = result.updated_state
            if session.qualification.is_complete:         # BR-04
                session.stage = RECOMENDACION

        RECOMENDACION:
            # se ejecuta una sola vez al entrar a esta etapa
            if session.recommendation is None:
                session.recommendation = recommend_program()   # BR-06, sin args
            reply = OrchestratorAgent.present_recommendation(session.recommendation)
            session.stage = FIN_ITERACION

        FIN_ITERACION:
            reply = OrchestratorAgent.closing_message()  # sin más lógica en esta iteración

    session.messages.append(ConversationTurn(role="assistant", content=reply))
    SessionRepository.save(session)
    stream reply token-by-token over the WebSocket connection
```

**Nota de implementación**: en la práctica, el `OrchestratorAgent` no es un `match` explícito en Python sino un `Agent` de Strands cuyo **system prompt** recibe `session.stage` como contexto (vía `invocation_state`, mismo mecanismo que `ToolContext.invocation_state` de la doc de Strands) y tiene instrucciones explícitas de qué tool invocar para cada valor de `stage`. El pseudocódigo de arriba describe el comportamiento esperado, que se verifica con tests, no la implementación literal del prompt.

---

## 4. Contrato de los sub-agentes (tools)

### `identification_assistant(context: IdentificationState, user_message: str) -> IdentificationResult`
- Construye internamente un `Agent` de Strands con system prompt enfocado únicamente en captura de nombre/correo (BR-01, BR-03).
- No mantiene su propia sesión persistida — recibe el `IdentificationState` parcial como contexto en cada llamada (el `OrchestratorAgent`/`SessionRepository` es la única fuente persistida, BR-08).
- Retorna: el texto de respuesta a mostrar al usuario + el `IdentificationState` actualizado (potencialmente con `name`/`email` recién extraídos y `is_complete` recalculado).

### `qualification_assistant(context: QualificationState, user_message: str) -> QualificationResult`
- Mismo patrón: system prompt enfocado en las 5 dimensiones (BR-04) y clasificación de motivación (BR-05), incluyendo el contador `clarification_attempts`.
- Retorna: texto de respuesta + `QualificationState` actualizado.

### `recommend_program() -> Recommendation`
- Sin argumentos (BR-06). No es un agente — es una función determinista que lee `FAKE_RECOMMENDED_COURSE_ID` de configuración y resuelve el título contra el catálogo (`metadata.json`, ya usado por el stub actual en `services/api/src/tools.py`).

---

## 5. Streaming sobre WebSocket

- El `OrchestratorAgent` transmite su respuesta token a token (`stream_async`, mismo mecanismo que ya usa el stub actual en `services/api/main.py`).
- Cada token se envía como un mensaje WS de tipo `{"type": "token", "data": "..."}`; al finalizar el turno se envía `{"type": "done", "stage": session.stage}` para que un cliente de prueba pueda observar transiciones de etapa sin necesitar acceso directo al backend.
- El servidor WS de desarrollo (sin auth, decisión P4) resuelve `session_id` desde el primer mensaje de la conexión (o genera uno nuevo si no se provee), y llama a `on_message` por cada mensaje entrante hasta que el cliente cierra la conexión.

---

## 6. Manejo de errores

- Si el LLM o un tool falla durante el procesamiento de un turno: no se corrompe `ConversationSession` — el `stage` y los estados parciales ya guardados permanecen sin cambios, se loggea el error, y se envía al usuario un mensaje de fallback (mismo patrón que el stub actual: *"Error al generar la respuesta. Por favor intenta de nuevo."*). El usuario puede reintentar su mensaje sin perder progreso.
- Si `email` no pasa la validación de formato (BR-01), no se considera un error de sistema — es un resultado normal de `identification_assistant` que mantiene `is_complete=False` y pide corrección.

---

## 7. Fuera de alcance de esta iteración (explícito)

- Guardrails (US-09 a US-12) — BR-07.
- CIERRE (link de pago Mercado Pago) y ESCALACIÓN (contacto humano) — BR-10, siguen siendo responsabilidad futura de `unit-2` (lógica conversacional) + `unit-3` (persistencia/pagos/SES).
- Re-identificación vía `window.storage` — BR-02.
- Búsqueda semántica real en `recommend_program` — BR-06 (nota de evolución).
- Autenticación del endpoint WebSocket — el endpoint de desarrollo de esta unidad no la implementa; `AuthMiddleware`/JWT Cognito es alcance de `unit-3` (US-13), y ese endpoint de producción ni siquiera es responsabilidad de `unit-2`.
