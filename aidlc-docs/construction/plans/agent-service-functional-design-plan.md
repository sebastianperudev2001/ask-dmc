# Functional Design Plan — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05
**Unidad**: `agent-service` (redefinición de `unit-2`, plataforma Azure — ver DIV-10 en `aidlc-state.md`)
**Incremento**: 1 de N — Catálogo de cursos + recomendación por perfil (identificación/calificación conversacional queda para un incremento siguiente)

---

## Contexto

`unit-2: strands-agent` (AWS Strands SDK + AgentCore) tenía su Functional Design COMPLETADO y pendiente de aprobación cuando el usuario decidió pivotar la plataforma a **Azure AI Foundry + Microsoft Agent Framework**. Ese diseño queda SUPERSEDED (DIV-10). Este plan cubre el primer incremento del `agent-service` redefinido: estructurar el catálogo de cursos y construir la lógica de recomendación por perfil.

## Checklist del Plan

- [x] Analizar contexto de la unidad (unit-of-work.md unit-2, requirements.md RF-07)
- [x] Generar preguntas de alcance (plataforma, foco de MVP, motor de DB)
- [x] Generar preguntas de diseño funcional (filtros duros, fuente de datos, captura de perfil)
- [x] Recolectar y analizar respuestas — sin ambigüedades pendientes
- [ ] Generar artefactos de Functional Design (domain-entities.md, business-rules.md, business-logic-model.md)
- [ ] Presentar para aprobación

---

## Preguntas y Respuestas

### P1 — Alcance del pivote de plataforma
**Pregunta**: El diseño actual (Inception + unit-2 Functional Design pendiente) está construido 100% sobre AWS. ¿Cuál es el alcance de este pivote a Azure?
- A) Reemplazo total — Azure reemplaza AWS en todo el proyecto; se descarta el Functional Design de unit-2 (Strands) pendiente
- B) Paralelo / nuevo track — dejar AWS/Strands como está, explorar Azure aparte
- C) Solo la capa de datos/recomendación — el resto del agente se decide después

**[Answer]: A**

### P2 — Foco del MVP inmediato
**Pregunta**: Para el MVP inmediato (DB + estructura de cursos + recomendación por perfil), ¿qué construir ahora?
- A) Solo capa de datos y lógica (sin orquestación de agente)
- B) Datos + agente mínimo en Azure AI Foundry
- C) Re-scope completo de unit-2 (identificación + calificación + recomendación) sobre Azure Agent Framework

**[Answer]: C** — con la precisión (ver P-perfil más abajo) de que este incremento 1 solo cubre catálogo + recomendación; identificación/calificación queda para el incremento 2 de la misma unidad redefinida.

### P3 — Motor de base de datos (ronda 1)
**Pregunta inicial**: ¿Postgres+pgvector, Cosmos DB, o Azure SQL+AI Search?
**Respuesta usuario**: Cuestionó por qué Postgres sería mejor que Cosmos (vector search nativo) o AI Search (servicio dedicado).
**Análisis AI**: Comparación completa presentada — Cosmos gana en integración nativa con Agent Framework samples y para guardar thread/state del agente; AI Search gana en madurez de hybrid search pero añade un segundo servicio a sincronizar; Postgres gana en integridad transaccional (relevante para pagos futuros con Mercado Pago/Culqi) y por ser un solo motor.

### P4 — ¿Se necesita vector DB en absoluto?
**Pregunta usuario**: "Realmente necesitamos un vector DB? Si tomamos un perfil, cómo se realizaría la búsqueda vectorial? Sobre el contenido o cómo?"
**Análisis AI**: Distinción entre atributos estructurados (no necesitan vector search — un scoring por reglas basta) y texto libre (sí necesita embeddings). Se preguntó cuál aplica al perfil real.

**[Answer]: Híbrido** — "Habrían primero reglas fijas, como presupuesto, duración. Pero, algunas frases sí son semánticas como cuál es tu perfil (background profesional) y qué stack te gustaría aprender. Ejemplo: 'soy Data Engineer y trabajo en Yape para un proyecto de recomendación de productos, me gustaría profundizar en Data Science'."

**Decisión derivada**: Filtros duros (SQL) sobre presupuesto/duración + ranking semántico (pgvector) sobre background profesional + stack deseado. Motor de DB confirmado: **Azure Database for PostgreSQL Flexible Server + pgvector**.

### P5 — Filtros duros exactos
**Pregunta**: ¿Cuáles son los filtros duros del MVP además de presupuesto y duración?
- A) Solo presupuesto y duración
- B) + Modalidad y nivel
- C) Otro conjunto

**[Answer]: A** — Solo presupuesto y duración. Modalidad/nivel no son filtros duros en este incremento (pueden influir en el ranking semántico si aparecen en el texto libre del perfil, pero no excluyen candidatos).

### P6 — Fuente de datos del catálogo de cursos
**Pregunta**: ¿Reprocesar los brochures ya ingeridos por unit-1 (AWS/Bedrock), o un catálogo manual nuevo?
- A) Reprocesar los mismos brochures con Azure OpenAI embeddings
- B) Catálogo manual nuevo (seed data)
- C) Otra fuente

**[Answer]: B** — Catálogo manual nuevo. No se reprocesan los brochures de unit-1 en este incremento; se carga un set estructurado (seed) de cursos con sus campos (nombre, descripción, presupuesto/precio, duración, etc.).

### P7 — Captura del perfil del interesado
**Pregunta**: ¿Cómo se captura el perfil (background profesional + stack deseado) en este incremento?
- A) Input estructurado directo (objeto/request ya armado, sin agente conversacional todavía)
- B) Ya integrar con Azure Agent Framework (agente conversacional completo)

**[Answer]**: Precisión del usuario — "La idea es que el frontend envíe un form estructurado. O sea durante el chat se envíe un mini form estructurado, el cual el user tenga que llenar y eso vaya directamente al LLM. Asume que todo lo que hagamos es con streaming, o sea un websocket en tiempo real."

**Decisión derivada**: Es un híbrido de A y B — el perfil llega como un mini-form estructurado (no conversación libre turno a turno para identificación/calificación todavía), pero se envía sobre un canal WebSocket en tiempo real y el resultado de la recomendación sí lo compone un LLM/agente (streaming token a token). No hay persistencia de leads en este incremento (out of scope, consistente con BR-10 del diseño anterior).

---

## Sin ambigüedades pendientes

Todas las respuestas fueron específicas y accionables. Se procede a generar los artefactos de Functional Design.
