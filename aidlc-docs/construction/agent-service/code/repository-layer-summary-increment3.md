# Repository Layer — Code Generation Summary (agent-service, Incremento 3)

## Generado

- **Puertos extendidos**: `LeadRepository.list_leads`/`find_by_id` (`src/ports/lead_repository.py`), `CourseRepository.find_by_id` (`src/ports/course_repository.py`) — ambos internos, no expuestos vía API pública (ver nota en `business-logic-summary-increment3.md`).
- **Puerto nuevo**: `DraftRepository` (`src/ports/draft_repository.py`) — `save`, `find_active_by_lead_id`, `find_by_id`, `mark_sent` (atómico, PATTERN-28), `mark_discarded`.
- **Adaptadores extendidos**: `PostgresLeadRepository.list_leads`/`find_by_id`, `PostgresCourseRepository.find_by_id` (`src/adapters/postgres_{lead,course}_repository.py`).
- **Adaptador nuevo**: `PostgresDraftRepository` (`src/adapters/postgres_draft_repository.py`) — `mark_sent` usa `UPDATE ... WHERE status = 'pending' RETURNING *`, retorna `None` si la fila ya no estaba pending (no reenvía).
- **Migración** (`migrations/004_create_outreach_drafts.sql`): tabla `outreach_drafts` (`CHECK` constraints sobre `status`/`trigger`, `FOREIGN KEY` a `leads`) + un **índice único parcial** (`WHERE status = 'pending'`) que enforca BR-22 ("a lo sumo un draft pending por lead") también a nivel de base de datos — defensa en profundidad, no solo el dedupe de `OutreachAgentService.generate_draft`.
- **Config** (`src/config.py`, extendido): `acs_connection_string`, `acs_sender_address` (`ACS_CONNECTION_STRING`/`ACS_SENDER_ADDRESS`).

## Tests generados

- `tests/unit/test_postgres_lead_repository.py` (extendido, 4 tests nuevos) — `list_leads` (todos, vacío), `find_by_id` (encontrado, no encontrado). Contra Postgres real (`TEST_DATABASE_URL`).
- `tests/unit/test_postgres_repository.py` (extendido, 2 tests nuevos) — `find_by_id` para `Course`. Contra Postgres real.
- `tests/unit/test_postgres_draft_repository.py` (nuevo, 5 tests) — CRUD completo + **la propiedad central de PATTERN-28**: una segunda llamada a `mark_sent` sobre un draft ya `sent` retorna `None` y no modifica `sent_at`. Contra Postgres real, requiere la migración 004 aplicada.

Todos los tests contra Postgres real quedan `skipped` en este entorno (sin `TEST_DATABASE_URL` configurada) — mismo comportamiento que el resto de la suite desde incremento 1.

## Nota: `find_by_id` en dos repositorios, ninguno contradice Application Design

Tanto `LeadRepository.find_by_id` como `CourseRepository.find_by_id` son metodos de uso **interno** (`OutreachAgentService`/`GetCourseDetailsTool`), nunca expuestos como endpoint HTTP — la decisión de Application Design (Q5 = B: sin `GET /leads/{id}` público) era específicamente sobre la superficie de la API, no sobre qué métodos puede tener un repositorio para uso interno del propio servicio.
