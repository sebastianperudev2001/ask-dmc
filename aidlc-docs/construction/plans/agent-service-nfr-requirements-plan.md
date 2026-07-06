# NFR Requirements Plan — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

## Checklist

- [x] Analizar Functional Design aprobado (incl. corrección PBT-01)
- [x] Identificar qué ya está decidido (Azure AI Foundry + Agent Framework, Postgres+pgvector, Azure OpenAI embeddings, WebSocket) vs. qué falta
- [x] Cargar contexto de NFR ya fijado en Inception (`requirements.md` §9): primer token ≤3s, best-effort/no SLA formal (proyecto de curso), PBT full enforcement, Security Baseline habilitado
- [ ] Generar preguntas sobre lo que aún no está decidido (hosting, modelo de chat, región, rate limiting)
- [ ] Recolectar respuestas
- [ ] Generar artefactos (nfr-requirements.md, tech-stack-decisions.md) con compliance de Security Baseline y PBT

## Contexto ya fijado (no se vuelve a preguntar)

| Aspecto | Decisión | Fuente |
|---|---|---|
| Performance | Primer token de respuesta ≤ 3s vía streaming WS | requirements.md §9.1 (Inception, no específico de plataforma) |
| Disponibilidad | Best-effort, sin SLA formal — proyecto de curso/demo | requirements.md §9.2 |
| Escalabilidad | Bajo volumen esperado (demo), auto-scaling deseable pero no crítico | requirements.md §9.3 (adaptado de AWS App Runner a equivalente Azure) |
| Testing | PBT full enforcement (Hypothesis) + Security Baseline full enforcement | aidlc-state.md Extension Configuration |
| Observabilidad | Logging estructurado JSON, sin PII en logs | requirements.md §9.6 |
| Agente/orquestación | Azure AI Foundry + Microsoft Agent Framework | Functional Design (Q&A previa) |
| Base de datos | Azure Database for PostgreSQL Flexible Server + pgvector | Functional Design (Q&A previa) |
| Embeddings | Azure OpenAI `text-embedding-3-small`, 1536 dims | Functional Design |
| Interfaz | WebSocket, streaming por `AgentRunResponseUpdate.text` (delta, no token) | Functional Design + investigación Agent Framework |
| Auth | Ninguna en este incremento — endpoint público (chat widget para visitantes anónimos) | Decisión previa unit-2 ("ignoremos el auth por ahora") |

## Preguntas y Respuestas

### P1 — Hosting del backend WebSocket
**Pregunta inicial**: ¿Dónde corre el servicio Python que mantiene la conexión WS y orquesta el flujo (filtro → embedding → ranking → agente)?
**Respuesta usuario**: "Y foundry?" — cuestionó si Foundry mismo podía hostear todo.
**Investigación**: Confirmado (Context7 + Microsoft Learn) que existen 2 patrones: (1) Persistent Agent en Foundry invocado vía SDK desde una app separada, (2) Hosted Agents — contenedor custom completo desplegado directo a Foundry con WebSocket nativo (`invocations_ws`), pero **en preview**, solo región North Central US, conexiones WS topadas a ~10 min.

**[Answer]: Container Apps + Foundry Persistent Agent** — el backend WS propio (filtro/embedding/ranking/relajación) corre en Azure Container Apps (GA, sin límite de tiempo de conexión, cualquier región); solo la composición final del texto (paso 8) se delega a un Persistent Agent en Foundry vía SDK. Se descarta la opción "todo en Foundry Hosted Agents" por depender de una feature en preview con restricciones de región y duración de conexión.

### P2 — Modelo de chat para el agente
**[Answer]: gpt-4o-mini** — costo y latencia bajos, calidad suficiente para redactar un pitch corto sobre datos ya estructurados (no requiere razonamiento complejo), ayuda a cumplir el objetivo de primer token ≤3s (requirements.md §9.1).

### P3 — Región de Azure
**[Answer]: East US** — mayor disponibilidad de modelos Azure OpenAI y mejor precio, a cambio de más latencia de red vs. Brazil South (aceptable dado el target ≤3s best-effort). Aplica a Container Apps, Azure Database for PostgreSQL, y el recurso Azure OpenAI/Foundry — todo co-localizado para minimizar latencia entre servicios.

### P4 — Rate limiting (SECURITY-11)
**[Answer]: Sin rate limiting por ahora** — riesgo aceptado explícitamente por el usuario para este incremento MVP/demo. Documentado como hallazgo de seguridad no resuelto (SECURITY-11) en nfr-requirements.md, con la aceptación de riesgo registrada en audit.md — no es un N/A, es un gap conocido y aceptado, no oculto.

## Sin ambigüedades pendientes

Todas las respuestas son específicas y accionables. Procediendo a generar los artefactos de NFR Requirements.
