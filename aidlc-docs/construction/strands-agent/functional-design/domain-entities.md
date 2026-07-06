# Domain Entities — unit-2: strands-agent

**Fecha**: 2026-07-01
**Alcance**: BIENVENIDA → IDENTIFICACIÓN → CALIFICACIÓN → RECOMENDACIÓN (fake). CIERRE, ESCALACIÓN y guardrails quedan fuera de esta iteración (ver `business-rules.md`).

---

## Enums

### `ConversationStage`
Etapa activa del funnel para una sesión dada. Controla determinísticamente a qué sub-agente/tool enruta el orquestador (ver `business-logic-model.md`).

```
BIENVENIDA
IDENTIFICACION
CALIFICACION
RECOMENDACION
FIN_ITERACION      # terminal para esta iteración — CIERRE/ESCALACIÓN quedan pendientes
```

### `MotivationType`
Mismas 4 categorías + `undefined` del PRD (sección 5.1).

```
GROWTH                  # crecimiento profesional
SALARY                  # aumento salarial
COMPANY_REQUIREMENT     # requerimiento de empresa
ACADEMIC                # actualización académica
UNDEFINED                # señales vagas — ver BR-05 (repregunta antes de aceptar)
```

---

## Entidades

### `ConversationTurn`
Un mensaje individual del transcript.

| Campo | Tipo | Notas |
|---|---|---|
| `role` | `"user" \| "assistant"` | |
| `content` | `str` | |
| `timestamp` | `datetime` (ISO-8601) | |

### `IdentificationState`
Resultado (parcial o completo) de la etapa IDENTIFICACIÓN.

| Campo | Tipo | Notas |
|---|---|---|
| `name` | `str \| None` | |
| `email` | `str \| None` | Validado por formato (BR-01) antes de aceptarse |
| `is_complete` | `bool` | `True` cuando `name` y `email` válidos están presentes (BR-01) |

### `QualificationState`
Resultado (parcial o completo) de la etapa CALIFICACIÓN. Las 5 dimensiones del PRD (sección 4.2) son obligatorias en esta iteración (BR-04, decisión P5=A).

| Campo | Tipo | Notas |
|---|---|---|
| `profile_summary` | `str \| None` | Ocupación / experiencia técnica previa |
| `motivation` | `MotivationType \| None` | |
| `motivation_detail` | `str \| None` | Cita textual o paráfrasis de lo que dijo el usuario (para backoffice futuro) |
| `objective` | `str \| None` | Qué quiere aprender / rol deseado |
| `availability` | `str \| None` | Tiempo semanal + presupuesto aproximado (texto libre en esta iteración) |
| `urgency` | `str \| None` | Cuándo quiere empezar |
| `clarification_attempts` | `int` | Contador de repreguntas sobre motivación vaga (BR-05), reseteado al clasificar |
| `is_complete` | `bool` | `True` cuando las 5 dimensiones tienen valor (BR-04) |

### `Recommendation`
Resultado del tool fake de recomendación (BR-06).

| Campo | Tipo | Notas |
|---|---|---|
| `course_id` | `str` | Fijo en esta iteración — ver BR-06 |
| `course_title` | `str` | Resuelto desde el catálogo existente (`metadata.json`) por `course_id` |
| `generated_at` | `datetime` | |

### `ConversationSession`
Entidad raíz — lo que persiste `SessionRepository` por `session_id` (ver `business-logic-model.md` sección Persistencia).

| Campo | Tipo | Notas |
|---|---|---|
| `session_id` | `str` | Identificador de sesión (mapea a AgentCore Memory session ID en PRODUCTION — decisión P3) |
| `stage` | `ConversationStage` | |
| `identification` | `IdentificationState` | |
| `qualification` | `QualificationState` | |
| `recommendation` | `Recommendation \| None` | Presente solo cuando `stage >= RECOMENDACION` |
| `messages` | `list[ConversationTurn]` | Transcript completo — necesario para reconstruir contexto del orquestador tras una reconexión WS |
| `created_at` | `datetime` | |
| `updated_at` | `datetime` | |

---

## Relaciones

```
ConversationSession 1───* ConversationTurn
ConversationSession 1───1 IdentificationState
ConversationSession 1───1 QualificationState
ConversationSession 1───0..1 Recommendation
```

No hay entidades de `Lead` ni `dmc-leads` en esta unidad — la persistencia de leads (DynamoDB) es responsabilidad de `unit-3: backend-api` (US-05, US-06). Esta unidad solo produce y persiste `ConversationSession`.
