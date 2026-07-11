# Business Logic — Code Generation Summary (agent-service, Incremento 3)

## Generado

- **Dominio** (`src/domain/models.py`, extendido): `DraftStatus` (`pending`/`sent`/`discarded`), `DraftTrigger` (`auto`/`on_demand`), `OutreachDraft` (mutable, igual que `Lead` — BR-22), `LeadEvent` (frozen, lleva el `Lead` completo — BR-29).
- **Pub/sub en memoria** (`src/domain/lead_event_publisher.py`): `LeadEventPublisher` — `publish`/`subscribe`, un subscriber que falla no bloquea a los demás (defensivo, no especificado explícitamente en NFR Design pero consistente con SECURITY-15/fail-safe).
- **Puertos extendidos**: `LeadRepository.list_leads`/`find_by_id` (`src/ports/lead_repository.py`), `CourseRepository.find_by_id` (`src/ports/course_repository.py`).
- **Puertos nuevos**: `DraftRepository` (`src/ports/draft_repository.py`, incluye el `mark_sent` atómico de PATTERN-28), `EmailSender` (`src/ports/email_sender.py`, sin adaptador wireado hasta el Step 7).

## Tests generados

- `tests/unit/test_lead_event_publisher.py` — fan-out a múltiples subscribers, subscriber que falla no bloquea a los demás. **3/3 passed** (verificado, sin dependencias externas).
- `tests/unit/test_postgres_lead_repository.py` (extendido) — `list_leads` (todos, vacío), `find_by_id` (encontrado, no encontrado). Requiere `TEST_DATABASE_URL` (mismo patrón `requires_postgres` ya establecido).
- `tests/unit/test_postgres_repository.py` (extendido) — `find_by_id` para `Course` (encontrado, no encontrado). Requiere `TEST_DATABASE_URL`.
- `tests/unit/test_postgres_draft_repository.py` (nuevo) — CRUD completo + la propiedad de `mark_sent` de PATTERN-28: una segunda llamada sobre un draft ya `sent` es un no-op (`None`, `sent_at` sin cambiar). Requiere `TEST_DATABASE_URL` **y** la migración `004_create_outreach_drafts.sql` aplicada (ver Step 17).

## Cobertura de Business Rules

| BR | Cubierta en |
|---|---|
| BR-22 (draft "activo" = solo `pending`) | `DraftRepository.find_active_by_lead_id` — filtra por `status = 'pending'` en la query SQL, no en Python |
| BR-23 (regeneración retorna el existente) | Implementado en `OutreachAgentService.generate_draft` (Step 8) — usa `find_active_by_lead_id` antes de generar |
| BR-24 (fire-and-forget) | `OutreachAgentService`'s subscriber a `LeadEventPublisher` (Step 8) — `LeadEventPublisher.publish` en sí es síncrono/secuencial; es el subscriber quien debe agendar su propio trabajo en background, no el publisher |
| BR-25 (skip si falta email, solo trigger automático) | `OutreachAgentService.generate_draft` (Step 8) |
| BR-26 (tool `get_course_details`) | `CourseRepository.find_by_id` (este documento) + `GetCourseDetailsTool` (Step 8) |
| BR-27 (manejo de error LLM) | `OutreachAgentService` (Step 8) |
| BR-28 (validación de email antes de enviar, sin status `failed`) | `OutreachAgentService.send_draft` (Step 8) |
| BR-29 (`LeadEvent` lleva el `Lead` completo) | `src/domain/models.py::LeadEvent` |
| BR-30 (snapshot sin estado de draft) | `LeadBroadcaster` (Step 10) — el snapshot usa `LeadQueryService.list_leads()`, que nunca toca `DraftRepository` |

## Nota de diseño: `find_by_id` en dos repositorios distintos, mismo propósito

Tanto `LeadRepository.find_by_id` como `CourseRepository.find_by_id` son métodos **internos** (no expuestos vía API pública) — el primero lo usa `OutreachAgentService` para resolver el `Lead` de un draft; el segundo lo usa `GetCourseDetailsTool` para resolver los `course_id` en `Lead.recommended_programs`. Ninguno contradice la decisión de Application Design de no tener `GET /leads/{id}` — esa decisión era sobre la superficie HTTP pública, no sobre métodos de repositorio de uso interno.
