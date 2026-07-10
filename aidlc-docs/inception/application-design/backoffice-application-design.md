# Application Design — BackOffice Lead Qualification View (Consolidated)

**Date**: 2026-07-10
**Based on**: `backoffice-requirements.md`, `backoffice-{stories,personas}.md`, `backoffice-execution-plan.md`, answered `backoffice-application-design-plan.md`
**Detail docs**: `backoffice-components.md`, `backoffice-component-methods.md`, `backoffice-services.md`, `backoffice-component-dependency.md`

---

## Design Decisions (from the answered plan)

| # | Decision | Answer |
|---|---|---|
| 1 | Outreach agent is a standalone component (`OutreachAgentService`), decoupled from `ChatAgentClient` | A |
| 2 | Score-change events fan out via a single in-process publisher (`LeadEventPublisher`), consumed independently by `LeadBroadcaster` and `OutreachAgentService` | A |
| 3 | Outreach drafts are a new persisted entity (`OutreachDraft`) with their own repository (`DraftRepository`), not fields bolted onto `Lead` | A |
| 4 | `OutreachAgentService` owns both drafting and lifecycle rules (dedupe, status transitions) — no separate `DraftLifecycleService` | A |
| 5 | No dedicated `GET /leads/{id}` — the detail popup is served from the already-fetched `GET /leads` list | B |
| 6 | `apps/backoffice` is modular: `KanbanBoard`, `LeadCard`, `LeadDetailModal`, `DraftPanel`, `NotificationCenter` | A |
| 7 | `EmailSender` port is defined now (interface only); concrete adapter/provider chosen in NFR Requirements (NFR-5) | A |

---

## New Components Summary

**`agent-service` (extended)** — 7 new/extended components:
- `LeadQueryService` + `LeadRepository.list_leads` (read path)
- `LeadEventPublisher` (in-process pub/sub)
- `LeadBroadcaster` (`/ws/leads` WebSocket delivery)
- `ChatAgentClient` (extended with one new publish call)
- `OutreachAgentService` + `OutreachDraft` + `DraftRepository` (outreach draft lifecycle)
- `EmailSender` (port only)

**`apps/backoffice` (new)** — 6 components:
- `KanbanBoard`, `LeadCard`, `LeadDetailModal`, `DraftPanel`, `NotificationCenter`, `WsLeadsClient`

Full responsibilities and interfaces: `backoffice-components.md`. Method signatures: `backoffice-component-methods.md`.

---

## Service Orchestration Summary

Four orchestration flows, detailed in `backoffice-services.md`:
1. **Lead Listing** (FR-2/3/7) — thin read-through `LeadQueryService` → `LeadRepository`.
2. **Real-Time Board Sync** (FR-6/8) — `ChatAgentClient` publishes once; `LeadEventPublisher` fans out to `LeadBroadcaster` and `OutreachAgentService` independently, neither aware of the other.
3. **Outreach Draft Lifecycle** (FR-9–13, Stories 4-6) — auto-trigger (score → hot) and on-demand trigger (staff action) converge on the same `OutreachAgentService.generate_draft` method; review/send/discard is entirely staff-initiated, no automatic send path exists anywhere in the design.
4. **Staff Notifications** (FR-14, Story 7) — no new backend service; the frontend derives "actionable" client-side from the same event stream Service 2 already broadcasts.

---

## Architectural Consistency Check

- **NFR-3** (reuse existing patterns): confirmed — `DraftRepository`/`LeadEventPublisher`/`LeadBroadcaster` all follow the existing port/adapter and WS-handler shapes already established by `LeadRepository`/`CourseRepository` and `/ws/chat`.
- **NFR-4** (demo-scale performance): confirmed — no message broker, no pagination, no caching layer introduced; in-process pub/sub is sufficient at this scale.
- **NFR-5** (email provider deferred): confirmed — `EmailSender` exists only as an unimplemented `Protocol` port in this design; no vendor SDK, credential, or adapter is introduced here.
- **`apps/chat` isolation**: confirmed — no component in this design imports from or depends on `apps/chat`; the only shared surface is `agent-service` itself.
- **Human-in-the-loop gate (FR-12)**: confirmed structurally — `EmailSender.send` is only ever reachable through `OutreachAgentService.send_draft`, which is only ever reachable from an explicit staff-initiated `DraftPanel` action. No code path calls `send_draft` automatically.

---

## What's Deferred to Functional Design (Construction phase, per-unit)

- Exact `OutreachDraft` status state machine and transition rules.
- Exact dedupe/conflict behavior for re-triggering an on-demand draft when one is already active (Story 5 — replace vs. warn vs. return existing).
- Exact API route shapes (`POST` paths for generate/send/discard, `/ws/leads` message schema).
- `LeadEvent` payload shape (fields carried on lead-created vs. score-changed).
- Postgres schema for the new `outreach_drafts` table (or equivalent).
- Frontend visual design execution (NFR-2, via the `frontend-design` skill) — this document defines component boundaries, not visual treatment.

---

## Traceability

| Requirement | Covered By |
|---|---|
| FR-2, FR-3, FR-7 | `LeadQueryService`, `KanbanBoard`, `LeadCard` |
| FR-4, FR-5 | `LeadDetailModal` |
| FR-6, FR-8 | `LeadEventPublisher`, `LeadBroadcaster`, `WsLeadsClient` |
| FR-9, FR-10 | `OutreachAgentService` (auto trigger via `LeadEventPublisher` subscription) |
| FR-11 | `OutreachAgentService.generate_draft` (on-demand path), `DraftPanel` |
| FR-12, FR-13 | `OutreachAgentService.send_draft`/`discard_draft`, `EmailSender` (port), `DraftPanel` |
| FR-14 | `NotificationCenter` (client-side derivation from Service 2's event stream) |
| NFR-2 | Deferred to Code Generation (`frontend-design` skill) |
| NFR-3 | `DraftRepository`/`LeadRepository` port-adapter pattern, WS handler pattern reuse |
| NFR-4 | No broker/pagination/cache added |
| NFR-5 | `EmailSender` port defined, adapter deferred |
