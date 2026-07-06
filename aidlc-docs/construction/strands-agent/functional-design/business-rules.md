# Business Rules — unit-2: strands-agent

**Fecha**: 2026-07-01

---

### BR-01 — Identificación completa
La `IdentificationState.is_complete` es `True` únicamente cuando `name` no está vacío y `email` cumple un formato válido (`local@dominio.tld`, regex simple, no verificación de entregabilidad). Si el email no es válido, el agente de Identificación pide amablemente que se corrija y **no** avanza de etapa (US-02 Escenario 2).

### BR-02 — Sin re-identificación por `window.storage` en esta iteración
La Identificación siempre captura nombre y correo desde cero, sin importar si el visitante ya conversó antes (decisión del usuario, P8=B). El campo de entrada para datos ya conocidos desde el frontend (`window.storage`) queda como **TODO** explícito para cuando exista `unit-4: frontend-widget`. No se modela ahora.

### BR-03 — Una pregunta por turno
Tanto el agente de Identificación como el de Calificación hacen **una sola pregunta por turno** — nunca combinan dos solicitudes (ej. nombre + correo) en el mismo mensaje (US-01 Escenario 3, US-02 Escenario 1, US-03 Escenario 1).

### BR-04 — Calificación completa (5 dimensiones)
`QualificationState.is_complete` es `True` únicamente cuando las 5 dimensiones del PRD (sección 4.2) tienen valor: `profile_summary`, `motivation`, `objective`, `availability`, `urgency` (decisión del usuario, P5=A — fidelidad completa al PRD, sin recortar a un subconjunto).

### BR-05 — Clasificación de motivación
La motivación se clasifica en una de `growth | salary | company_requirement | academic | undefined` (PRD sección 5.1). Si la señal del usuario es vaga, el agente de Calificación **repregunta** antes de aceptar una clasificación — máximo **2 repreguntas** (`clarification_attempts <= 2`); si tras 2 intentos sigue sin poder clasificar, se acepta `undefined` como valor final para no bloquear el resto de la calificación (evita loop infinito; US-03 Escenario 2).

### BR-06 — Recomendación fake (temporal)
El tool `recommend_program` **no recibe argumentos** y siempre retorna el mismo `course_id` fijo, configurable vía variable de entorno `FAKE_RECOMMENDED_COURSE_ID` (default: `diploma_data_analyst`, resuelto contra el catálogo existente en `services/api/src/domain/metadata.json`). Ignora por completo `QualificationState` — no hay personalización de pitch en esta iteración (decisión del usuario, P2=A).

> **Nota de evolución** (no implementar ahora): la intención declarada es que este tool sea reemplazado más adelante por un agente/tool que haga búsqueda semántica real sobre el perfil calificado (US-18, cuando `unit-1`/Vector DB estén conectados a esta unidad). El nombre del tool y su rol en el flujo (llamado una sola vez al entrar a `RECOMENDACION`) no deberían cambiar; sí cambiará su firma (pasará a recibir `QualificationState` como input real, no ignorado) y su implementación interna.

### BR-07 — Guardrails diferidos (backlog)
Los guardrails US-09 (anti-alucinación), US-10 (sin promesas no fundamentadas), US-11 (sin competidores) y US-12 (scope de ventas) **no se implementan en esta iteración**, ni siquiera vía system prompt (decisión explícita del usuario, P6). Quedan registrados como pendientes para una vuelta posterior de esta misma unidad, antes de considerar `unit-2` lista para producción.

### BR-08 — Persistencia de sesión
Toda `ConversationSession` (transcript + stage + identification + qualification + recommendation) se persiste vía `SessionRepository`, indexado por `session_id`:
- **PRODUCTION**: implementación respaldada por AWS AgentCore Memory (fuente de verdad ya decidida en Inception — `application-design.md`).
- **LOCAL/dev**: implementación en memoria de proceso (`InMemorySessionRepository`), se pierde al reiniciar el servidor.
- Selección por `ENV`, mismo patrón ya usado en `services/ingestion/src/config.py` para `LLMProvider`/embeddings (decisión del usuario, P3=A).

### BR-09 — Avance de etapa determinista
El orquestador **nunca** decide libremente avanzar de `ConversationStage` — el avance ocurre únicamente cuando el sub-agente de la etapa activa señaliza `is_complete=True` sobre su estado correspondiente (`IdentificationState` o `QualificationState`). El LLM orquestador no tiene discreción sobre el orden de las etapas; solo decide *qué decir* dentro de la etapa activa.

### BR-10 — Aislamiento de responsabilidad de leads
Esta unidad no persiste leads en DynamoDB (`dmc-leads`) ni genera links de pago — eso es responsabilidad de `unit-3: backend-api` (US-05, US-06), fuera de alcance de esta iteración. `unit-2` produce y persiste únicamente `ConversationSession`.
