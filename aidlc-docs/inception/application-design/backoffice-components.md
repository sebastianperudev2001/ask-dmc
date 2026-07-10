# Components — BackOffice Lead Qualification View

**Date**: 2026-07-10
**Scope**: `agent-service` (extended) + `apps/backoffice` (new). See `backoffice-application-design-plan.md` for the answered questions this design is built from.
**Note**: This is a new increment's components, additive to the existing `agent-service`/`apps/chat` components already documented in `components.md`. This file does not restate or replace those.

---

## Layer: agent-service — Read Path

### LeadQueryService
**Responsibility**: Orchestrates the lead listing capability (FR-7). Sits between the API layer and `LeadRepository`. No single-lead read method — the detail popup is served from the already-fetched list (Q5 = B), so this service intentionally exposes only the list operation.
**Type**: Service class
**Interfaces exposed**:
- `list_leads() -> list[Lead]`

### LeadRepository (extended)
**Responsibility**: Unchanged core responsibility (persistence of `Lead`); gains a `list_leads` capability to back `LeadQueryService`.
**Type**: Existing `Protocol` port + `PostgresLeadRepository` adapter, extended
**Interfaces added**:
- `list_leads() -> list[Lead]`

---

## Layer: agent-service — Real-Time Event Fan-Out

### LeadEventPublisher
**Responsibility**: In-process publish/subscribe bus for lead lifecycle events (created, score changed). Decouples the scoring code path (`ChatAgentClient`/BR-17b) from its two consumers — `LeadBroadcaster` (FR-6/FR-8) and `OutreachAgentService` (FR-10) — per Q2 = A. Single-process, in-memory; no cross-process/durable delivery needed at this scale.
**Type**: Concrete class (in-memory event bus)
**Interfaces exposed**:
- `publish(event: LeadEvent) -> None`
- `subscribe(handler: Callable[[LeadEvent], Awaitable[None]]) -> None`

### LeadBroadcaster
**Responsibility**: Manages WebSocket connections at `/ws/leads`. Subscribes to `LeadEventPublisher` and forwards every event to all connected BackOffice clients. On a fresh/reconnected client, sends a full snapshot (via `LeadQueryService.list_leads()`) before switching to live event forwarding, so reconnection reconciles to current server state without stale/duplicate cards (Story 3 AC).
**Type**: Concrete class (WS connection manager — same pattern already established for `/ws/chat`)
**Interfaces exposed**:
- `handle_connection(websocket) -> None`
- `broadcast(event: LeadEvent) -> None`

### ChatAgentClient (extended)
**Responsibility**: Unchanged core responsibility (chat/tool-calling flow). Gains exactly one new call: after BR-17b re-evaluates `Lead.score` inside `_apply_engagement_floor`, it publishes a `LeadEvent` via `LeadEventPublisher`. This is the only touch point into the existing incremento-2 component.
**Type**: Existing concrete class, extended
**Interfaces added**: none new; adds an internal call to `LeadEventPublisher.publish(...)`.

---

## Layer: agent-service — Outreach Agent

### OutreachAgentService
**Responsibility**: Standalone component (Q1 = A), decoupled from `ChatAgentClient` — shares only the `Lead` domain model. Owns the full outreach draft lifecycle end-to-end (Q4 = A): generating personalized drafts via LLM (FR-9), auto-triggering on `hot` (FR-10, by subscribing to `LeadEventPublisher`), on-demand generation for any score tier (FR-11), enforcing "one active draft per lead" (Story 4), and executing the human-gated send/discard actions (FR-12, Story 6).
**Type**: Service class
**Interfaces exposed**:
- `generate_draft(lead_id) -> OutreachDraft`
- `get_active_draft(lead_id) -> OutreachDraft | None`
- `send_draft(draft_id) -> OutreachDraft`
- `discard_draft(draft_id) -> OutreachDraft`

### OutreachDraft (domain model)
**Responsibility**: New persisted entity (Q3 = A) representing one drafted outreach message and its lifecycle state — independent of `Lead`. Exact field shape and the pending/sent/discarded state machine are detailed in Functional Design.
**Type**: Dataclass, analogous in shape to `Lead`
**Indicative fields**: `draft_id`, `lead_id`, `subject`, `body`, `status`, `trigger` (`auto` | `on_demand`), `created_at`, `sent_at`

### DraftRepository
**Responsibility**: New port + Postgres adapter (Q3 = A), persistence for `OutreachDraft`, parallel in shape to `LeadRepository`.
**Type**: `Protocol` port + `PostgresDraftRepository` adapter
**Interfaces exposed**:
- `save(draft: OutreachDraft) -> None`
- `find_active_by_lead_id(lead_id) -> OutreachDraft | None`
- `find_by_id(draft_id) -> OutreachDraft | None`

### EmailSender
**Responsibility**: New port, interface only (Q7 = A) — sends a drafted message to a lead's email address. No concrete adapter defined at this stage; provider selection is an explicit NFR Requirements decision (NFR-5).
**Type**: `Protocol` port (adapter deferred)
**Interfaces exposed**:
- `send(to_email: str, subject: str, body: str) -> None`

---

## Layer: apps/backoffice (new frontend app)

Modular componentization (Q6 = A) — each component has a single responsibility.

### KanbanBoard
**Responsibility**: Top-level board view (FR-2/FR-3). Fetches the initial lead list via `GET /leads`, groups leads into Hot/Warm/Cold columns, and stays in sync via live events delivered through `WsLeadsClient` (FR-6).
**Type**: React component (page-level)

### LeadCard
**Responsibility**: Renders one lead's summary (at minimum, name) inside its column. Click opens `LeadDetailModal` (FR-3/FR-4).
**Type**: React component

### LeadDetailModal
**Responsibility**: Read-only popup (FR-4/FR-5) showing all `Lead` fields required by FR-4. Does not render the conversation transcript. Hosts `DraftPanel`.
**Type**: React component

### DraftPanel
**Responsibility**: Rendered inside `LeadDetailModal`. Fetches/shows the lead's active draft if one exists; offers "Generate draft" when none exists (on-demand, FR-11, any score tier); offers "Send" and "Discard" actions once a draft exists (Story 6, FR-12).
**Type**: React component

### NotificationCenter
**Responsibility**: Subscribes to `WsLeadsClient` for score-change events; shows an in-app toast/banner the moment a lead's score reaches `hot` (FR-14). Keeps a dismissable list visible for the lifetime of the tab session — notifications that fired while the user was on another tab remain visible on return (Story 7 AC). Clicking a notification opens that lead's `LeadDetailModal`.
**Type**: React component

### WsLeadsClient
**Responsibility**: Shared WebSocket connection to `/ws/leads` — a single connection reused by `KanbanBoard` and `NotificationCenter`, same pattern already established by `apps/chat`'s `WsChatService`.
**Type**: Frontend service class / hook (`useLeadsSocket`)
