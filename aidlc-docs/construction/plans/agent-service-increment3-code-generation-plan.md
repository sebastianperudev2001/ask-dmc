# Code Generation Plan — agent-service, Incremento 3

**Date**: 2026-07-11
**Based on**: Functional Design, NFR Requirements, NFR Design, Infrastructure Design (all approved, Incremento 3 sections)
**Unit**: `agent-service` (brownfield — modify existing files where noted, create new ones elsewhere)
**Workspace root for code**: `services/agent-service/` (never `aidlc-docs/`)
**Stories**: 1, 2, 3 (backend half), 4, 5, 6 (full), 7 (event stream only) — `backoffice-unit-of-work-story-map.md`

---

## Step 1 — Domain models [x]
**File**: `services/agent-service/src/domain/models.py` (modify)
- Add `DraftStatus` (`pending`/`sent`/`discarded`) and `DraftTrigger` (`auto`/`on_demand`) enums
- Add `OutreachDraft` dataclass (mutable, like `Lead`): `draft_id, lead_id, subject, body, status, trigger, created_at, sent_at`
- Add `LeadEvent` frozen dataclass: `event_type: Literal["created", "score_changed"], lead: Lead`

## Step 2 — In-process event publisher (domain) [x]
**File**: `services/agent-service/src/domain/lead_event_publisher.py` (create)
- `LeadEventPublisher` — `publish(event: LeadEvent) -> None`, `subscribe(handler) -> None`. Synchronous fan-out to subscribers, except handlers that need to be non-blocking schedule their own `asyncio.create_task` internally (PATTERN-23) — the publisher itself stays simple/dumb.

## Step 3 — Ports [x]
- `services/agent-service/src/ports/lead_repository.py` (modify): add `list_leads() -> list[Lead]`, `find_by_id(lead_id) -> Lead | None`
- `services/agent-service/src/ports/course_repository.py` (modify): add `find_by_id(course_id) -> Course | None`
- `services/agent-service/src/ports/draft_repository.py` (create): `save`, `find_active_by_lead_id`, `find_by_id`, and an atomic `mark_sent(draft_id) -> OutreachDraft | None` (returns `None` if the row wasn't `pending` — backs PATTERN-28)
- `services/agent-service/src/ports/email_sender.py` (create): `send(to_email, subject, body) -> None`

## Step 4 — Repository adapters [x]
- `services/agent-service/src/adapters/postgres_lead_repository.py` (modify): implement `list_leads`, `find_by_id`
- `services/agent-service/src/adapters/postgres_course_repository.py` (modify): implement `find_by_id`
- `services/agent-service/src/adapters/postgres_draft_repository.py` (create): implement the port against a new `outreach_drafts` table; `mark_sent` uses `UPDATE ... WHERE status = 'pending' RETURNING *`

## Step 5 — Business logic unit tests [x]
- `tests/unit/test_lead_event_publisher.py` (create): publish fans out to all subscribers; a subscriber exception doesn't break delivery to others
- `tests/unit/test_postgres_lead_repository.py` (modify): `list_leads`, `find_by_id`
- `tests/unit/test_postgres_course_repository.py` (modify, or `test_postgres_repository.py` if that's where course tests live — verify at execution time): `find_by_id`
- `tests/unit/test_postgres_draft_repository.py` (create): CRUD + `mark_sent`'s atomic no-op-on-non-pending behavior (BR-22, PATTERN-28)

## Step 6 — Business logic summary [x]
**File**: `aidlc-docs/construction/agent-service/code/business-logic-summary-increment3.md` (create) — models, event publisher, repository extensions

## Step 7 — Email adapter [x]
**File**: `services/agent-service/src/adapters/acs_email_sender.py` (create)
- `AzureCommunicationServicesEmailSender` implementing `EmailSender`, wrapped in the existing `RetryPolicy` (PATTERN-21), reading `ACS_CONNECTION_STRING` from config

## Step 8 — Outreach agent service
**File**: `services/agent-service/src/adapters/outreach_agent_service.py` (create)
- `OutreachAgentService`, mirrors `ChatAgentClient`'s agent/tool-calling shape exactly (`FoundryChatClient` + `Agent` + `tool(...)`)
- `_get_course_details` tool method → `CourseRepository.find_by_id`
- `generate_draft(lead_id, trigger)`: dedupe via `DraftRepository.find_active_by_lead_id` (BR-23); skip-and-log if `trigger == "auto"` and `lead.email` empty (BR-25); run agent; persist via `DraftRepository.save`
- `get_active_draft`, `send_draft` (email-presence validation, PATTERN-26; atomic guard via `DraftRepository.mark_sent`, PATTERN-28; `RetryPolicy`-wrapped `EmailSender.send`, PATTERN-21), `discard_draft`
- Subscribes to `LeadEventPublisher` at construction; on `score_changed` → `hot`, schedules `asyncio.create_task(self.generate_draft(lead.id, "auto"))` (PATTERN-23) with a top-level try/except that logs (BR-27)

## Step 9 — Extend `ChatAgentClient`
**File**: `services/agent-service/src/adapters/chat_agent_client.py` (modify)
- Add `lead_event_publisher: LeadEventPublisher` param to `__init__`
- In `_upsert_lead` (after `await self._lead_repository.save(lead)`), publish a `LeadEvent` — `event_type="created"` the first time a lead is persisted for this conversation, `event_type="score_changed"` otherwise (single insertion point covers both BR-24's trigger and Story 3's board updates)

## Step 10 — Broadcaster (API layer)
**File**: `services/agent-service/src/api/lead_broadcaster.py` (create)
- `LeadBroadcaster`: maintains the `/ws/leads` connection set; `handle_connection(websocket)` sends a `snapshot` (via `LeadQueryService`) then streams `lead_event` messages; `broadcast(event)` iterates connections, drops ones whose send fails (PATTERN-24, lazy detection, no heartbeat)

## Step 11 — Lead query service (domain/orchestration)
**File**: `services/agent-service/src/domain/lead_query_service.py` (create)
- `LeadQueryService.list_leads()` → thin pass-through to `LeadRepository.list_leads()`

## Step 12 — API layer unit tests
- `tests/unit/test_outreach_agent_service.py` (create): mirrors `test_chat_agent_client_scoring.py`'s approach (patch `Agent`/`FoundryChatClient`, fake `DraftRepository`/`LeadRepository`/`CourseRepository`/`EmailSender`) — covers dedupe (BR-23), missing-email skip (BR-25), send validation (PATTERN-26), atomic guard (PATTERN-28)
- `tests/unit/test_lead_broadcaster.py` (create): snapshot-then-stream, dead connection dropped on failed send
- `tests/unit/test_acs_email_sender.py` (create): retry-with-backoff behavior via `RetryPolicy`
- `tests/unit/test_schemas.py` (modify): new response/request models (Step 13)

## Step 13 — API schemas + routes
**File**: `services/agent-service/src/api/schemas.py` (modify): add `LeadResponse`, `LeadListResponse`, `OutreachDraftResponse`
**File**: `services/agent-service/main.py` (modify):
- `lead_event_publisher = LeadEventPublisher()` and `lead_broadcaster = LeadBroadcaster(...)` as module-level singletons (like `connection_pool`) — must be shared across all `/ws/leads` connections and wired into `build_chat_websocket_handler`'s `agent_client_factory` so `ChatAgentClient` gets the same publisher instance
- `outreach_agent_service = OutreachAgentService(...)` module-level singleton, constructed with the same `lead_event_publisher` so its auto-trigger subscription is live at startup
- `GET /leads` → `LeadQueryService.list_leads()`
- `@app.websocket("/ws/leads")` → `lead_broadcaster.handle_connection(websocket)`
- `POST /leads/{lead_id}/drafts` (generate on-demand), `GET /leads/{lead_id}/drafts/active`, `POST /drafts/{draft_id}/send`, `POST /drafts/{draft_id}/discard`

## Step 14 — Integration tests
- `tests/integration/test_leads_websocket_flow.py` (create): connect → snapshot; publish event → broadcast reaches client; disconnect doesn't break broadcast to remaining clients
- `tests/integration/test_outreach_draft_flow.py` (create): score reaches hot → auto-draft generated exactly once even with repeated hot events (BR-22/BR-23); on-demand generate/send/discard via HTTP
- `tests/integration/fakes.py` (modify): add fakes for `DraftRepository`, `EmailSender`, extend existing `FakeLeadRepository`/`FakeCourseRepository` with the new methods
- `tests/unit/fakes.py` (modify): same additions for unit-level fakes

## Step 15 — API layer summary
**File**: `aidlc-docs/construction/agent-service/code/api-layer-summary-increment3.md` (create)

## Step 16 — Repository layer summary
**File**: `aidlc-docs/construction/agent-service/code/repository-layer-summary-increment3.md` (create)

## Step 17 — Database migration
**File**: `services/agent-service/migrations/004_create_outreach_drafts.sql` (create)
- `outreach_drafts` table: `draft_id UUID PK, lead_id UUID FK -> leads, subject TEXT, body TEXT, status TEXT, trigger TEXT, created_at TIMESTAMPTZ, sent_at TIMESTAMPTZ NULL`; partial unique index enforcing at most one `pending` row per `lead_id` (belt-and-suspenders alongside the application-level dedupe check, BR-22)

## Step 18 — Config
**File**: `services/agent-service/src/config.py` (modify): add `acs_connection_string` (from `ACS_CONNECTION_STRING` env var, matches `main.tf`'s Step 13 wiring from Infrastructure Design)

---

## Explicitly Out of Scope for This Plan (per prior stage decisions)
- Recipient safelist — not implemented (NFR Requirements, Q2 = B)
- `terraform apply` / real Azure deployment — infra written, not applied
- `apps/backoffice` — separate unit, starts after this one's Code Generation is verified working (strictly sequential build order)
- Manual E2E verification scripts / browser testing — Build and Test stage, not Code Generation
