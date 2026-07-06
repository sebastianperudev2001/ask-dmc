# Repository Layer — Code Generation Summary (agent-service, Incremento 2)

## Generado

- **Puerto** (`src/ports/lead_repository.py`): `LeadRepository` (`Protocol`) — `save`, `find_by_service_session_id`, `mark_payment_confirmed`.
- **Adaptador** (`src/adapters/postgres_lead_repository.py`): `PostgresLeadRepository` — upsert de `Lead` (todas las queries parametrizadas, SECURITY-05), sobre el mismo `ConnectionPool` ya usado por `PostgresCourseRepository` (sin servidor Postgres nuevo, DIV-13).
- **Migración** (`migrations/002_create_leads_and_sessions.sql`): tablas `leads` (con `CHECK` constraints sobre `motivation`/`score` para reflejar los enums de dominio en la BD) y `conversation_sessions`; índices sobre `service_session_id` y `email`.
- **Config** (`src/config.py`, extendido): `mercadopago_access_token`, `mercadopago_webhook_secret`, `mercadopago_base_url`.
- **`src/adapters/keyvault_secrets.py`**: sin cambios de código — sigue siendo el adaptador genérico (`get_secret(name)`) ya generado en incremento 1; no se invoca en runtime local (mismo patrón que incremento 1 — los secrets vienen de `.env` en desarrollo local, de Key Vault en el despliegue real que no ocurre en este incremento).

## Tests generados

- `tests/unit/test_postgres_lead_repository.py` — contra Postgres real (`TEST_DATABASE_URL`, skip si no está configurada, mismo patrón que `test_postgres_repository.py`): guardar y encontrar por `service_session_id`, `find` retorna `None` si no existe, `mark_payment_confirmed` actualiza los 3 campos correctos, `save` hace upsert (actualiza un lead existente en vez de duplicar).

## Nota
No se agregó ninguna tabla ni columna para `conversation_sessions.state` o transcripción de mensajes — Foundry Agent Memory es la única fuente de verdad de la conversación (PATTERN-20); `conversation_sessions` es solo la referencia local `session_id ↔ service_session_id ↔ lead_id`.
