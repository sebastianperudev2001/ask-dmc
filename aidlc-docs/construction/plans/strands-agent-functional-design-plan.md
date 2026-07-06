# Functional Design Plan — unit-2: strands-agent

**Fecha**: 2026-07-01
**Unit**: unit-2 — strands-agent (ver `aidlc-docs/inception/application-design/unit-of-work.md`)
**Stories cubiertas por esta iteración**: US-01, US-02 (identificación), US-03 (calificación), US-04 (recomendación — versión fake), US-09, US-10, US-11, US-12 (guardrails aplicables al alcance actual)
**Fuera de alcance de esta iteración** (quedan para una vuelta posterior de esta misma unidad o para unit-3): US-05 (pago real), US-06 (escalación con SES), persistencia en DynamoDB, búsqueda semántica real (US-18 — se reemplaza por un tool fake).

---

## Contexto

El PRD (`PRD.md`) y los artefactos de Inception (`components.md`, `unit-of-work.md`, `stories.md`) ya definieron un diseño de alto nivel para unit-2: un único `StrandsAgent` con 4 tools (`SearchCoursesTool`, `QualifyLeadTool`, `GeneratePaymentLinkTool`, `GetBrochureUrlTool`), gestionando el flujo BIENVENIDA→CIERRE/ESCALACIÓN con AgentCore Memory.

El request actual del usuario ajusta el alcance de esta iteración:
- **Identificación y Calificación deben ser genuinamente agénticas** (el LLM razona y conduce la conversación, no un formulario disfrazado).
- **Recomendación se fakea**: el tool de recomendación siempre devuelve el mismo programa X, sin búsqueda semántica real todavía.
- `poc-multi-agent-demo/backend` se usa como referencia de patrones de Strands SDK (no como plantilla a copiar) — en particular expone: `strands.multiagent.GraphBuilder` para orquestar múltiples agentes como grafo, un `BaseAgent` ABC por agente, y tools de estado compartido (`write_state_key`) entre nodos del grafo.

Ya existe un stub parcial en `services/api/` (FastAPI + un único `Agent` de Strands con tools `list_courses`/`get_course_details`) que es más simple que lo que Inception había especificado.

## Tareas de este Functional Design

- [ ] Definir el modelo de negocio de la conversación (estados, transiciones, qué agente/tool es responsable de cada estado)
- [ ] Definir el/los modelo(s) de dominio: `Lead`, `IdentificationResult`, `QualificationResult`, `Recommendation` (fake), etc.
- [ ] Definir las reglas de negocio de calificación (motivación, dimensiones, cuándo se considera "completa" la calificación)
- [ ] Definir el contrato del tool de recomendación fake (input/output) de forma que sea reemplazable después sin romper el resto del flujo
- [ ] Definir los guardrails aplicables (anti-alucinación, scope, sin competidores) en este alcance reducido
- [ ] Definir puntos de integración y manejo de errores (LLM no disponible, respuestas ambiguas del usuario, etc.)

---

## Preguntas de Clarificación

Por favor responde cada pregunta llenando la letra elegida después de `[Answer]:`. Si ninguna opción calza, usa la última opción (Other) y describe tu respuesta.

### Pregunta 1 — Arquitectura del agente para Identificación y Calificación

¿Cómo deben implementarse las etapas de Identificación y Calificación para que sean "agénticas"?

A) **Un solo Strands `Agent`** con system prompt + tools, que internamente conduce ambas etapas conversacionalmente (como estaba especificado originalmente en `components.md`, sin cambios estructurales)
B) **Dos agentes Strands separados** (`IdentificationAgent`, `QualificationAgent`), cada uno con su propio system prompt y responsabilidad única, orquestados secuencialmente con `strands.multiagent.GraphBuilder` (patrón visto en `poc-multi-agent-demo`) — el tool de recomendación fake se ejecuta como un tercer nodo o como tool final
C) **Un agente orquestador** que usa "agents-as-tools": invoca a un `IdentificationAgent` y a un `QualificationAgent` como tools/handoffs desde un system prompt principal, sin usar `GraphBuilder`
D) Other (please describe after [Answer]: tag below)

> **Recomendación del AI**: **C — Agents-as-tools**, por estas razones (basadas en la doc oficial de Strands, [multi-agent-patterns](https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)):
> - **Graph** es técnicamente el patrón "correcto" para un proceso de negocio determinista con flowchart fijo (la doc lo recomienda explícitamente para "Interactive Customer Support: Routing a conversation based on user intent"), y soporta ciclos + edges condicionales, que calzarían bien con el guardrail de scope (US-12: desviarse y volver al mismo estado). **Pero** un `Graph` de Strands está pensado para ejecutarse de principio a fin en una sola invocación; para un chat multi-turno vía HTTP (un request por mensaje del usuario) necesitarías pausar la ejecución del grafo entre turnos usando su mecanismo de **interrupt/resume con checkpointing** — funcionalidad real pero con complejidad adicional (serialización de estado, límites de ejecución) que no aporta valor todavía en esta iteración, donde la recomendación está fakeada y cierre/escalación quedan fuera de alcance.
> - **Swarm** no aplica: está pensado para colaboración autónoma/emergente entre pares (ej. researcher → architect → coder), no para un funnel con orden obligatorio y guardrails de cumplimiento — el hand-off lo deciden los agentes, no el desarrollador.
> - **Agents-as-tools** encaja mejor con el modelo turno-a-turno: el `Agent` orquestador mantiene la conversación real con el usuario de forma natural entre llamadas HTTP (es solo un objeto `Agent` cuyo historial persiste), y delega en `identification_assistant` / `qualification_assistant` como tools cuando necesita razonar sobre esa porción del problema (extraer nombre/email, clasificar motivación, verificar si la calificación está completa). Cada sub-agente sigue siendo genuinamente agéntico (su propio system prompt + razonamiento), solo que la orquestación es más simple de implementar y depurar que un grafo con checkpoints.
> - Camino de migración: si más adelante se necesita gating estrictamente determinista (ej. para cierre/escalación en unit-3, o si el orquestador empieza a saltarse pasos), migrar de agents-as-tools a `GraphBuilder` es incremental — la lógica de cada agente especializado no cambia, solo la capa de orquestación.
>
> **Corrección (2026-07-01)**: el usuario aclaró que el canal es **WebSocket persistente**, no HTTP request/response sin estado. Esto invalida mi argumento original contra Graph (que decía que necesitarías checkpointing/interrupt-resume porque el proceso no sobrevive entre turnos) — con una conexión WS de larga duración, el objeto `Graph` (o el `Agent` orquestador) puede vivir en memoria durante toda la conversación.
>
> Revisé la doc de Strands buscando específicamente "reinvocar un `Graph` ya construido una vez por mensaje entrante, retomando el nodo activo" y **no encontré ese patrón documentado como caso de primera clase** — los ejemplos de ciclos (`graph_loops_example`) son loops *internos* a una sola invocación (ej. write→review→improve), no turnos externos llegando uno a la vez desde el usuario. Es probable que funcione (por defecto `reset_on_revisit=False`, así que el estado del agente de un nodo se conserva al revisitarlo), pero lo trataría como algo a **prototipar/validar**, no como garantizado.
>
> **Recomendación se mantiene en C (agents-as-tools)**, pero ahora por otra razón: es el único de los tres patrones cuyo comportamiento turno-a-turno es el comportamiento *estándar* de cualquier `Agent` de Strands (llamar de nuevo al orquestador con el siguiente mensaje, su historial se acumula solo) — sin depender de un uso no documentado de Graph. Si en una iteración futura se valida que la reinvocación de Graph funciona como se espera y se quiere ese nivel de estructura explícita, migrar es incremental.

[Answer]: C

### Pregunta 2 — Alcance del tool de recomendación fake

El tool de recomendación siempre debe recomendar el mismo programa X. ¿Cómo debe comportarse?

A) Tool sin argumentos que retorna siempre el mismo `course_id` hardcodeado (ej. `diploma_data_analyst`), ignorando cualquier dato de calificación
B) Tool que **recibe** los datos de calificación (perfil, motivación, etc.) como argumentos — para preservar el contrato futuro con búsqueda real — pero internamente ignora esos argumentos y siempre retorna el mismo `course_id`
C) Tool que retorna un `course_id` fijo pero SÍ personaliza el texto del pitch según la motivación detectada (usando las plantillas de la sección 5.1 del PRD), aunque el programa recomendado no cambie
D) Other (please describe after [Answer]: tag below)

> **Nota**: confirmado por el usuario que esto es temporal — la evolución prevista es que el `RecommendationAgent`/tool haga búsqueda semántica real sobre el perfil del interesado (US-18, cuando unit-1/Vector DB estén conectados). El contrato de input (recibir `course_id` fijo, ignorando argumentos) debe diseñarse ya pensando en ese reemplazo futuro.

[Answer]: A

### Pregunta 3 — Estado de la conversación (memoria)

El diseño original usa AWS AgentCore Memory para persistir el hilo conversacional entre sesiones. Para esta iteración del backend:

A) Usar **AgentCore Memory real** desde ya (requiere `AGENTCORE_RUNTIME_ID` y acceso AWS configurado)
B) Usar **memoria en proceso** (in-memory, se pierde al reiniciar el servidor) como stub, dejando el `Protocol`/interfaz lista para enchufar AgentCore Memory después
C) No manejar múltiples turnos con estado persistido todavía — cada request incluye el historial completo de mensajes (como ya hace el stub actual en `services/api/main.py`, sin persistencia de servidor)
D) Other (please describe after [Answer]: tag below)

> **Nota (2026-07-01)**: Esto ya fue decidido en Inception y no debería re-abrirse como si estuviera libre — `application-design.md` dice explícitamente *"AgentCore Memory es la fuente de verdad"* del estado del funnel, y `services.md` indica que `session_id` se mapea al session ID de AgentCore Memory. La razón por la que esto importa técnicamente: no podemos depender de que el proceso/conexión WebSocket se mantenga vivo entre turnos (reconexiones, múltiples réplicas de AgentCore Runtime, cold starts) — la persistencia tiene que ser externa al proceso.
>
> Strands expone justo la abstracción para esto: `Agent` acepta un `SessionManager`/`SessionRepository` (interfaz + implementaciones nativas para File/S3) que carga y guarda el historial de conversación por `session_id` en cada invocación, sin importar si el proceso sobrevive o no.
>
> **Recomendación del AI para esta pregunta**: opción **B**, pero más específica — diseñar un `SessionRepository` (Protocol/interfaz, siguiendo el mismo patrón que `LLMProvider`/`VectorDBRepository` en `components.md`) desde ahora, con una implementación **in-memory** como stub para esta iteración (`InMemorySessionRepository`), dejando el punto de extensión listo para una implementación real respaldada por AgentCore Memory sin tocar la lógica del agente. Esto también refuerza la Pregunta 1: con **un solo agente orquestador** (C — agents-as-tools) hay un solo punto donde enchufar este repositorio, mapeado 1:1 a un hilo de conversación — con Graph, el historial quedaría repartido entre estado del grafo y agentes de nodo, más difícil de reconciliar con un único hilo de AgentCore Memory / `dmc-conversations`.

> **Decisión final del usuario**: AgentCore Memory real en producción; en dev/local, memoria en proceso. Esto es el mismo patrón `ENV` (LOCAL/PRODUCTION) que unit-1 ya usa para `LLMProvider`/embeddings (`BedrockLLMProvider` vs Ollama) — `SessionRepository` sigue esa misma convención: `AgentCoreMemorySessionRepository` (PRODUCTION) vs `InMemorySessionRepository` (LOCAL), seleccionado por `ENV` en `config.py`, igual que en `services/ingestion/src/config.py`.

[Answer]: A — AgentCore Memory real en PRODUCTION; in-process en memoria en LOCAL/dev (ruteo por ENV, mismo patrón que unit-1)

### Pregunta 4 — Dónde vive el código

`unit-of-work.md` especificaba `services/agent/` como directorio de esta unidad, pero ya existe un stub parcial en `services/api/` con un agente más simple.

A) Continuar y expandir `services/api/` (renombrar/reestructurar según haga falta), tratando esto como la implementación real de unit-2 y actualizando `unit-of-work.md` como divergencia (igual que DIV-01..DIV-09 de unit-1)
B) Crear `services/agent/` desde cero según el plan original de Inception, y dejar `services/api/` como el futuro `backend-api` (unit-3) que en algún punto invocará a este agente
C) Other (please describe after [Answer]: tag below)

> **Nota**: dado que la Pregunta 7 pide un endpoint WebSocket de streaming ya en esta iteración (ver abajo), y `unit-of-work.md` originalmente asignaba el WebSocket a `backend-api` (unit-3), voy a incluir un servidor WS mínimo de desarrollo **dentro de `services/agent/`** (no en `services/api/`) solo para poder conversar con el agente mientras se construye — sin `AuthMiddleware`, sin persistencia de leads ni Mercado Pago (eso sigue siendo trabajo de unit-3 más adelante). Lo marco explícitamente como código de desarrollo/demo, no como el WebSocketHandler final de producción.

[Answer]: B

### Pregunta 5 — Qué tan completa debe quedar la etapa de Calificación

El PRD define 5 dimensiones de calificación (perfil, motivación, objetivo, disponibilidad, urgencia).

A) El agente de calificación debe cubrir las 5 dimensiones antes de pasar a recomendación (fidelidad completa al PRD)
B) Para esta iteración basta con capturar **motivación** (obligatoria, porque determina el pitch) + al menos una dimensión adicional; el resto queda como mejora futura
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Pregunta 6 — Guardrails en esta iteración

¿Qué guardrails deben quedar activos ya en esta iteración (US-09 anti-alucinación, US-10 sin promesas, US-11 sin competidores, US-12 scope de ventas)?

A) Los 4 guardrails, vía system prompt (sin verificación automática/tests todavía más allá de lo que Functional Design defina como reglas)
B) Solo scope de ventas (US-12) y anti-alucinación (US-09); US-10 y US-11 se agregan en una iteración posterior
C) Other (please describe after [Answer]: tag below)

> **Decisión del usuario**: los guardrails (US-09, US-10, US-11, US-12) se difieren por completo de esta iteración. Se documentan como **pendiente/backlog** en `business-rules.md`, sin implementación (ni siquiera vía system prompt) todavía.

[Answer]: Ninguno por ahora — diferido a backlog (ver nota)

### Pregunta 7 — Interfaz de entrada/salida de esta unidad en esta iteración

¿Cómo se va a probar/exponer el flujo mientras se construye (antes de que exista unit-3/unit-4)?

A) Mantener el endpoint HTTP tipo `/ask` (streaming) que ya existe en `services/api/main.py`, adaptado al nuevo flujo multi-etapa
B) Un script/CLI de prueba local (sin servidor HTTP) que simula una conversación turno a turno contra el agente
C) Ambos: CLI para desarrollo rápido + endpoint HTTP para integración futura con el frontend
D) Other (please describe after [Answer]: tag below)

> **Decisión del usuario**: tiene que ser un **endpoint WebSocket de streaming**, no HTTP — siguiendo el patrón del ejemplo `poc-multi-agent-demo/backend` (`lambdas/ws_connect`, `ws_disconnect`, `ws_message` en producción; para desarrollo local, un servidor WS equivalente, ej. FastAPI `@app.websocket`). Token-a-token vía WS, no polling ni SSE sobre HTTP.

[Answer]: D — Endpoint WebSocket de streaming (FastAPI `@app.websocket` local, mismo patrón que el ejemplo de referencia)

### Pregunta 8 — Identificación: re-identificación por `window.storage`

El PRD indica que si el visitante ya tiene nombre/email guardados en el navegador, el agente no debe volver a pedirlos.

A) Diseñar el contrato del agente para **recibir** `name`/`email` conocidos como parte del estado inicial de la conversación (el frontend los inyecta); si vienen, el agente de Identificación los confirma y salta la captura
B) No modelar esto todavía — la Identificación siempre captura desde cero en esta iteración; se agrega cuando exista el frontend widget (unit-4)
C) Other (please describe after [Answer]: tag below)

> **Clarificado**: "Ignoremos el auth por ahora" se refería a esta pregunta (P8) — no a autenticación de la conexión WebSocket. La Identificación siempre captura desde cero en esta iteración.

[Answer]: B

---

**Cuando termines de responder, avísame y sigo con el análisis de las respuestas y la generación de los artefactos de Functional Design (`business-logic-model.md`, `business-rules.md`, `domain-entities.md`).**
