# Frontend Components — apps/backoffice

**Date**: 2026-07-11
**Unit**: `apps/backoffice` (new)
**Based on**: `aidlc-docs/inception/application-design/backoffice-{components,component-methods,services}.md` (approved), `agent-service` Incremento 3's actual generated contract (`GET /leads`, `/ws/leads`, `POST /leads/{id}/drafts`, `GET /leads/{id}/drafts/active`, `POST /drafts/{id}/send`, `POST /drafts/{id}/discard`), answered `apps-backoffice-functional-design-plan.md`.

---

## 1. Architecture — mirrors `apps/chat` exactly (Q1 = A)

Same `effect` library shape as `apps/chat`'s WS/chat layer — nothing app-wide, confined to the data layer:

- `lib/LeadsService.ts` — `Context.Tag` exposing `events: Stream.Stream<LeadWireEvent, LeadsError>` (raw `snapshot`/`lead_event` messages off `/ws/leads`)
- `lib/WsLeadsService.ts` — `Live` implementation: opens the `WebSocket`, waits for `open` via `Effect.async`, exposes `events` as `Stream.asyncPush` wired to the socket's message/close/error listeners — same shape as `WsChatService.ts`
- `lib/leadsRuntime.ts` — `export const LeadsAppRuntime = ManagedRuntime.make(WsLeadsServiceLive)`, a module-level singleton (built once)
- `lib/LeadsRuntimeProvider.tsx` — puts `LeadsAppRuntime` into React Context, mirrors `RuntimeProvider.tsx`
- `hooks/useLeadsSocket.ts` — the **sole** subscriber: calls `runtime.runFork` once (cleaned up via `Fiber.interrupt`), reduces incoming events into board/notification state via pure functions (Section 5)

**Single data source, no separate `GET /leads` call**: `LeadBroadcaster` (agent-service, generated in Code Generation) already sends a full `snapshot` message on every new `/ws/leads` connection before switching to live events — this supersedes Application Design's original mention of `KanbanBoard` calling `GET /leads` on mount (written before Functional Design settled the exact snapshot behavior). Using the WS snapshot as the only initial-state source avoids a race between an HTTP response and the WS snapshot arriving in a different order, and avoids fetching the same data twice. `GET /leads` still exists on the backend (harmless, unused by this frontend) — not a contradiction, just an unused capability.

## 2. Component hierarchy

```
BackofficeApp (app/page.tsx, new — sole call site of useLeadsSocket(), same role ChatApp plays in apps/chat)
 ├─ KanbanBoard
 │   └─ LeadCard[]  (one per lead, grouped into Hot/Warm/Cold columns)
 ├─ LeadDetailModal  (conditionally rendered — null when no lead selected)
 │   └─ DraftPanel
 └─ NotificationCenter
```

## 3. `useLeadsSocket` (hook)

```ts
type LeadsState = Record<string, LeadOut>  // keyed by lead.id

type Notification = {
  id: string          // `${lead.id}-${Date.now()}`, synthetic — no server-issued id
  leadId: string
  leadName: string | null
  createdAt: number
}

type UseLeadsSocketResult = {
  leads: LeadOut[]
  notifications: Notification[]
  dismissNotification: (id: string) => void
  connectionStatus: "connecting" | "open" | "closed"
}
```

**Pure, directly-testable reducer functions** (mirrors `apps/chat`'s `applyDelta`/`messagesFromHistory` — tested as plain functions, no WS mock needed):

- `applyLeadWireEvent(state: LeadsState, event: LeadWireEvent) -> LeadsState` — `snapshot` replaces the whole state; `lead_event` upserts one entry by `lead.id`.
- `deriveNotification(event: LeadWireEvent) -> Notification | null` — returns a `Notification` only for `{ type: "lead_event", event_type: "score_changed", lead: { score: "hot" } }`; every other event/type returns `null`. This is where FR-14's "actionable = reaches hot" assumption lives in code, not just in a comment.

**Reconnect behavior** (Story 3 AC — reconciles to current server state): on reconnect, the new connection's `snapshot` message fully replaces `leads` state (via `applyLeadWireEvent`'s `snapshot` branch) — no merge/diff logic needed, no stale/duplicate cards possible by construction.

**Notification lifecycle** (Q2 = A — in-memory only): `notifications` is plain hook state (`useState`), reset on a full page reload. `dismissNotification(id)` filters it out of the array — no persistence layer.

## 4. `BackofficeApp` (`app/page.tsx`)

**State**: `selectedLeadId: string | null` (drives `LeadDetailModal`'s visibility).
**Wiring**: calls `useLeadsSocket()` once; passes `leads`/`onSelectLead={setSelectedLeadId}` to `KanbanBoard`; passes the lead matching `selectedLeadId` (or `null`) + `onClose={() => setSelectedLeadId(null)}` to `LeadDetailModal`; passes `notifications`/`dismissNotification`/`onNotificationClick={setSelectedLeadId}` to `NotificationCenter`.

## 5. `KanbanBoard`

**Props**: `{ leads: LeadOut[]; onSelectLead: (leadId: string) => void }`
**State**: none — columns derived via a pure function `groupLeadsByScore(leads: LeadOut[]) -> { hot: LeadOut[]; warm: LeadOut[]; cold: LeadOut[] }` (directly testable, same "extract the pure part" convention).
**Rendering**: three columns (Hot/Warm/Cold), each rendering `LeadCard` for its leads; an empty column renders an empty state, not an error (Story 1 AC).
**Automation**: `data-testid="kanban-column-{hot|warm|cold}"` on each column (per this project's automation-friendly code convention — CLAUDE.md/code-generation.md — relevant here since Build and Test will drive this board through a real browser, same as `apps/chat`'s Playwright rounds).

## 6. `LeadCard`

**Props**: `{ lead: LeadOut; onClick: () => void }`
**State**: none — presentational.
**Shows**: at minimum `lead.name` (FR-3); score is already implied by its column, no redundant badge needed.
**Automation**: `data-testid="lead-card"` (clickable — per the automation-friendly convention, interactive elements get stable testids).

## 7. `LeadDetailModal`

**Props**: `{ lead: LeadOut | null; onClose: () => void }` — `null` means closed; parent controls visibility, this component has no open/closed state of its own.
**Renders** (FR-4, read-only, FR-5): name, email, `created_at`, `profile_summary`, `motivation` + `motivation_detail`, `recommended_programs`, `score` + `score_justification`, payment status (`payment_link_sent`, `payment_confirmed`, `payment_confirmed_at`). **Does not** render a conversation transcript (explicitly out of scope, FR-4) — `LeadOut` doesn't even carry transcript data, so this isn't reachable by construction.
**No edit affordances anywhere** — FR-5's read-only constraint is structural (no input fields bound to `Lead` fields), not just a UI convention.
**Hosts**: `<DraftPanel leadId={lead.id} leadEmail={lead.email} />` when `lead` is non-null.

## 8. `DraftPanel`

**Props**: `{ leadId: string; leadEmail: string | null }`
**State**: `draft: OutreachDraftOut | null`, `loading: boolean`, `sending: boolean`, `error: string | null`.
**On mount / `leadId` change**: `GET /leads/{leadId}/drafts/active` → sets `draft` (`null` if none exists yet).
**"Generate draft" action** (shown when `draft` is `null` — FR-11, on-demand, any score tier): `POST /leads/{leadId}/drafts` → sets `draft`.
**"Send" action** (shown when `draft?.status === "pending"`): sets `sending = true` (disables the button — this **is** the frontend half of PATTERN-28's two-layer send guard, NFR Requirements Sección 16), `POST /drafts/{draft.draft_id}/send` → updates `draft`, `sending = false`. Disabled entirely (not just on-click) when `!leadEmail` — mirrors the backend's PATTERN-26 validation client-side, giving immediate feedback instead of a round-trip that's guaranteed to fail.
**"Discard" action** (shown when `draft?.status === "pending"`): `POST /drafts/{draft.draft_id}/discard` → updates `draft`.
**Sent/discarded state**: shows the draft read-only (subject/body), no actions — matches the backend's terminal `sent`/`discarded` statuses.

## 9. `NotificationCenter`

**Props**: `{ notifications: Notification[]; onDismiss: (id: string) => void; onNotificationClick: (leadId: string) => void }`
**State**: none — presentational, list driven entirely by props.
**Renders**: a toast/banner per notification, each with a dismiss control (`onDismiss(notification.id)`) and a click target (`onNotificationClick(notification.leadId)`, which `BackofficeApp` wires to open `LeadDetailModal` for that lead — Story 7 AC: "click takes me directly to that lead's detail popup").

---

## Out of Scope for This Document

- Visual design execution (NFR-2, brand alignment) — deferred to Code Generation, executed via the `frontend-design` skill.
- Exact toast/banner animation or positioning — implementation detail, not a functional design concern.
- `apps/chat` — untouched, no shared code between the two apps (confirmed independently in both Application Design and here).
