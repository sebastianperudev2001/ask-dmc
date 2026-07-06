# Domain Entities — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05
**Alcance**: Catálogo de cursos + recomendación por perfil. No incluye identificación/calificación conversacional (incremento siguiente) ni persistencia de leads (fuera de alcance — ver BR-08).

---

## `Course`

Representa un programa/curso del catálogo de DMC Institute.

| Campo | Tipo | Descripción |
|---|---|---|
| `course_id` | `str` (UUID o slug) | Identificador único |
| `name` | `str` | Nombre del programa |
| `description` | `str` | Descripción rica del curso — insumo principal para el embedding semántico (temario, público objetivo, tecnologías cubiertas) |
| `category` | `str` | Área temática (ej. "Data Science", "Marketing Digital") — informativo, no es filtro duro en este incremento |
| `curriculum` | `list[str]` | Malla curricular: nombres de los módulos/temas cubiertos (ej. `["Python para Data Science", "SQL avanzado", "Machine Learning"]`) — señal semántica principal para matchear `desired_stack` (ver nota más abajo) |
| `price` | `Decimal` | Precio del programa, mismo moneda para todo el catálogo (asumido PEN — confirmar en revisión) |
| `duration_weeks` | `int` | Duración del programa en semanas |
| `embedding` | `vector(1536)` | Embedding de `description` + `name` + `category` + `curriculum`, generado una sola vez al cargar/actualizar el catálogo (Azure OpenAI `text-embedding-3-small`, 1536 dimensiones — ver business-logic-model.md) |

> **Nota**: `curriculum` es la señal más específica para matchear el stack/tema que el interesado quiere aprender (`RecommendationRequest.desired_stack`) — una descripción de marketing genérica no distingue bien entre cursos de la misma categoría. Modelado como lista simple de temas (no estructura por módulo con horas/descripción) para mantener el esfuerzo de carga de seed data acotado en este incremento.

> **Nota de fuente de datos**: el catálogo se carga como *seed data* manual en este incremento (decisión del usuario, P6=B) — no se reprocesan los brochures PDF ya ingeridos por `unit-1` (AWS/Bedrock).

---

## `RecommendationRequest`

Representa el mini-formulario estructurado que el frontend envía por WebSocket cuando el usuario lo completa dentro del chat.

| Campo | Tipo | Descripción |
|---|---|---|
| `budget` | `Decimal` | Presupuesto aproximado del interesado — **filtro duro** (BR-01) |
| `max_duration_weeks` | `int` | Disponibilidad/tiempo máximo que puede dedicar — **filtro duro** (BR-02) |
| `professional_background` | `str` | Texto libre: background profesional del interesado (ej. "Data Engineer en Yape, proyecto de recomendación de productos") — insumo semántico |
| `desired_stack` | `str` | Texto libre: stack/tema que le gustaría aprender (ej. "Data Science") — insumo semántico |

Todos los campos son obligatorios en este incremento (BR-09) — el mini-form no se envía al backend hasta estar completo (validación en frontend).

---

## `ProfileQuery` (interno, no persistido)

Representa el texto sintetizado a partir del perfil para generar el embedding de búsqueda. No es una entidad persistida — se construye por request y se descarta (BR-08).

| Campo | Tipo | Descripción |
|---|---|---|
| `query_text` | `str` | Concatenación de `professional_background` + `desired_stack` |
| `query_embedding` | `vector(1536)` | Embedding de `query_text`, generado por request vía Azure OpenAI |

---

## `RecommendationCandidate`

Resultado intermedio: un curso que pasó los filtros duros, con su score de similitud semántica frente al `ProfileQuery`.

| Campo | Tipo | Descripción |
|---|---|---|
| `course` | `Course` | Curso candidato |
| `similarity_score` | `float` | 1 − distancia coseno (`pgvector` `<=>`) entre `course.embedding` y `query_embedding`; mayor = más similar |
| `filters_relaxed` | `list[str]` | Filtros duros ampliados que este candidato solo cumple bajo el criterio relajado (ej. `["budget"]`), tras confirmación explícita del usuario (BR-03). Vacío en el caso normal. |
| `from_full_catalog` | `bool` | `True` cuando el candidato viene de la rama de catálogo completo sin filtrar (BR-11 — usuario declinó la relajación, o ni el criterio relajado encontró nada). Distinto de `filters_relaxed`: aquí no se sabe cuánto se pasa de presupuesto/duración, simplemente no se filtró. |

---

## `RecommendationResponse` (mensaje de salida por WebSocket)

| Campo | Tipo | Descripción |
|---|---|---|
| `candidates` | `list[RecommendationCandidate]` | Top-K (≤ 3, ver BR-05) candidatos entregados al LLM |
| `message_stream` | `str` (streaming, por deltas de `AgentRunResponseUpdate.text` — no tokens individuales garantizados, ver business-logic-model.md §3.1) | Texto compuesto por el agente presentando la recomendación al usuario, basado únicamente en `candidates` |

---

## Relaciones

```
RecommendationRequest ──(síntesis)──> ProfileQuery
Course ──(filtro duro: price, duration_weeks)──> [candidatos filtrados]
[candidatos filtrados] + ProfileQuery ──(ranking por embedding)──> RecommendationCandidate[] (top-K)
RecommendationCandidate[] ──(composición LLM)──> RecommendationResponse
```

Ninguna de estas entidades se persiste en este incremento — todo el flujo es efímero por request (BR-08).

---

# Incremento 2 — Nuevas entidades (chat conversacional + pago + persistencia)

**Fecha**: 2026-07-06
**Override**: BR-08 (sin persistencia) y BR-10 (sin identificación/calificación) quedan retomados — ver business-rules.md BR-21/BR-16.

## `ConversationSession`

Referencia local a una conversación gestionada del lado del servicio (Azure AI Foundry Agent Memory). No duplica el historial de mensajes — Foundry Memory ya es la fuente de verdad de la transcripción completa.

| Campo | Tipo | Descripción |
|---|---|---|
| `session_id` | `str` (UUID) | Identificador local (`AgentSession.session_id`) |
| `service_session_id` | `str` | Identificador gestionado por Foundry (`AgentSession.service_session_id`) — se persiste del lado del cliente (localStorage) para retomar la conversación tras un refresh |
| `lead_id` | `str \| None` | Referencia al `Lead` asociado, una vez creado (puede ser `None` al inicio de la conversación, antes de tener suficientes datos) |
| `created_at` | `datetime` | Timestamp de creación |

## `Lead`

Reemplaza el diseño original de DynamoDB `dmc-leads` (§6 requirements.md), adaptado a Postgres (ver DIV-13).

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `str` (UUID) | Identificador único |
| `created_at` | `datetime` | Timestamp de creación |
| `name` | `str \| None` | Nombre capturado conversacionalmente |
| `email` | `str \| None` | Email capturado conversacionalmente |
| `profile_summary` | `str` | Resumen del perfil (background, stack deseado) |
| `motivation` | `str` | `growth \| salary \| company_requirement \| academic \| undefined` (mismas 5 categorías de §5.2 RF-06 original) |
| `motivation_detail` | `str` | Cita textual o resumen de la señal de motivación |
| `recommended_programs` | `list[str]` | `course_id`s recomendados durante la conversación |
| `payment_link_sent` | `bool` | `True` si se invocó `create_payment_link` con éxito |
| `payment_checkout_url` | `str \| None` | Último `init_point`/`sandbox_init_point` generado |
| `payment_confirmed` | `bool` | `True` tras confirmación via webhook + `GET /v1/payments/{id}` (BR-20) |
| `payment_confirmed_at` | `datetime \| None` | Timestamp de confirmación de pago |
| `score` | `str` | `hot \| warm \| cold` (BR-17) |
| `score_justification` | `str` | Breve justificación del score |
| `escalated_to_human` | `bool` | `True` si el usuario pidió hablar con una persona (BR-19) |
| `service_session_id` | `str` | Referencia a `ConversationSession.service_session_id` — para recuperar la transcripción completa desde Foundry Memory si se necesita |

## `PaymentOrder` (interno, no necesariamente persistido como tabla propia — puede vivir embebido en `Lead`)

Representa el resultado de una invocación de `create_payment_link`.

| Campo | Tipo | Descripción |
|---|---|---|
| `preference_id` | `str` | ID de la preferencia creada en Mercado Pago |
| `checkout_url` | `str` | `init_point` (prod) o `sandbox_init_point` (test) |
| `amount` | `Decimal` | Monto de la orden |
| `description` | `str` | Descripción (ej. nombre del curso) |
| `status` | `str` | `pending \| approved \| rejected` — actualizado tras el webhook + re-consulta (BR-20) |

## Relaciones — Incremento 2

```
ConversationSession ──(1:0..1)──> Lead
Lead ──(0..1)──> PaymentOrder (vía payment_checkout_url / preference_id)
Lead.recommended_programs ──(referencia)──> Course.course_id (incremento 1)
```
