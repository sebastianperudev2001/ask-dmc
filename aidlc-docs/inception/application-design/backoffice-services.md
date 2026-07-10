# Services — BackOffice Lead Qualification View

**Date**: 2026-07-10

This file describes the service-layer orchestration for this increment — how the new components coordinate with each other and with existing `agent-service` components. Component-level responsibilities are in `backoffice-components.md`; method signatures are in `backoffice-component-methods.md`.

---

## Service 1 — Lead Listing (FR-2, FR-3, FR-7)

**Owner**: `LeadQueryService`

**Orchestration**:
1. `apps/backoffice`'s `KanbanBoard` calls `GET /leads` on mount.
2. `LeadQueryService.list_leads()` delegates to `LeadRepository.list_leads()`.
3. Response is grouped client-side into Hot/Warm/Cold by `Lead.score`.

**No new business logic** — this service is a thin orchestration layer over an existing repository capability, matching NFR-3 (reuse existing patterns).

---

## Service 2 — Real-Time Board Sync (FR-6, FR-8)

**Owners**: `LeadEventPublisher` (trigger), `LeadBroadcaster` (delivery)

**Orchestration**:
1. `ChatAgentClient._apply_engagement_floor` (existing, BR-17b) persists a `Lead.score` change, then calls `LeadEventPublisher.publish(event)`.
2. `LeadEventPublisher` invokes every subscribed handler in-process — `LeadBroadcaster.broadcast` and `OutreachAgentService`'s auto-draft handler both receive the same event (Q2 = A: single publish point, decoupled subscribers — neither knows about the other).
3. `LeadBroadcaster` forwards the event to every WebSocket client connected at `/ws/leads`.
4. On (re)connection, `LeadBroadcaster` first sends a full snapshot (`LeadQueryService.list_leads()`) before switching to live event delivery — this is what lets `apps/backoffice` reconcile to current server state after a dropped connection (Story 3 AC), instead of requiring per-event replay/backfill.

**Design rationale**: An in-process pub/sub, not an external broker (Redis/SQS/etc.) — consistent with this project's demo scale (NFR-4) and with keeping `agent-service` a single deployable (NFR-3). If a future increment needs multi-instance fan-out, this is the seam where that would be introduced without touching `ChatAgentClient`.

---

## Service 3 — Outreach Draft Lifecycle (FR-9 – FR-13, Stories 4–6)

**Owner**: `OutreachAgentService` (single owner of drafting + lifecycle rules, Q4 = A)

**Orchestration — auto trigger (FR-10, Story 4)**:
1. `OutreachAgentService` subscribes to `LeadEventPublisher` at startup (same subscription mechanism as `LeadBroadcaster`).
2. On a score-changed event where the new score is `hot`, it calls `find_active_by_lead_id` against `DraftRepository` to check for an existing active draft.
3. If none exists, it generates one (LLM call, using `Lead.profile_summary`/`motivation`/`motivation_detail`/`recommended_programs`) and persists it via `DraftRepository.save`.
4. If one already exists, no new draft is generated (Story 4 AC — "no duplicate draft").

**Orchestration — on-demand trigger (FR-11, Story 5)**:
1. Staff clicks "Generate draft" in `DraftPanel` → `POST` to a draft-generation endpoint (exact route deferred to Functional Design) with `lead_id`.
2. Same `OutreachAgentService.generate_draft(lead_id)` method is called — no separate code path from the auto trigger, only a different caller. This is why Q4 = A (single service, not split) reads naturally: both triggers converge on one method that already knows how to check-then-generate.
3. If an active draft already exists, the existing draft is returned instead of silently overwritten (per Story 5 AC — exact UX for "show vs. replace" deferred to Functional Design).

**Orchestration — review/send/discard (FR-12, Story 6)**:
1. `DraftPanel` fetches the active draft via `get_active_draft` when the modal opens.
2. Staff reviews the draft text in the UI. No automatic send exists anywhere in this design — `send_draft` is only ever invoked by an explicit staff action (FR-12's human gate).
3. `send_draft(draft_id)` calls `EmailSender.send(...)` (port only at this stage — concrete provider chosen in NFR Requirements, NFR-5) to `Lead.email`, then updates the draft's status to `sent`.
4. `discard_draft(draft_id)` updates status to `discarded` without ever calling `EmailSender`.

---

## Service 4 — Staff Notifications (FR-14, Story 7)

**Owner**: no new backend service — this is a frontend-only consumer of Service 2's existing event stream.

**Orchestration**:
1. `NotificationCenter` (via `WsLeadsClient`) filters the same `/ws/leads` event stream `KanbanBoard` already consumes, watching for score-changed events where the new score is `hot`.
2. No new backend event type or endpoint is introduced for notifications — "actionable" (per FR-14's assumption, confirmed in Requirements Analysis) is derived client-side from the score-changed event already being broadcast for Service 2. This keeps the WS channel single-purpose at the transport level (one event stream, multiple client-side interpretations) rather than adding a second notification-specific channel.

---

## Frontend Service Layer — `apps/backoffice`

**`WsLeadsClient`** is the single service-layer component on the frontend: it owns the `/ws/leads` connection lifecycle (connect, reconnect, snapshot-then-stream) and exposes a subscribe API consumed by both `KanbanBoard` (board state) and `NotificationCenter` (notification state) — mirroring the existing `WsChatService` pattern in `apps/chat`, per NFR-3's instruction to reuse established patterns rather than invent new ones.
