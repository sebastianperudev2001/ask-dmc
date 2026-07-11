# Functional Design Plan (light) — apps/backoffice

**Date**: 2026-07-11
**Unit**: `apps/backoffice` (new) — see `aidlc-docs/inception/application-design/backoffice-unit-of-work.md`
**Treatment**: light, same as `apps/chat` got in Incremento 2 — component/state structure only, no new backend-style business logic (this app is a pure consumer of `agent-service`'s now-verified contract).
**Stories assigned**: full frontend ownership of Stories 1–7 (`backoffice-unit-of-work-story-map.md`).

---

## Context Already Established (grounded in `apps/chat`'s actual code, explored directly — not assumed)

- **Tooling to mirror exactly** (no open question — low-stakes, no reason to diverge): Next.js 15, App Router, React 19, TypeScript strict, Tailwind v4 with CSS custom-property tokens (`@theme`, `var(--color-*)`), Vitest with colocated `*.test.ts(x)` files, standalone `package.json`/`node_modules` (no monorepo tooling, per Units Generation Q3 = A / issue #20).
- **Shared WS connection pattern to mirror** (no open question): a single hook call at one shared ancestor component, not independent subscriptions per component — `apps/chat`'s `ChatApp` is the sole call site of `useChat()`, passing state down as props to `Sidebar`/`MessageList`. `apps/backoffice` will follow the same shape: one top-level component owns `useLeadsSocket()`, passes board state down to `KanbanBoard` and notification state down to `NotificationCenter`, neither of which subscribes independently.
- **Testing style to mirror** (no open question): pure logic extracted into plain, directly-testable functions (e.g. `apps/chat`'s `applyDelta`/`messagesFromHistory` inside `useChat.ts`), WS mocked with a hand-rolled fake class (`vitest.config.ts` uses `environment: 'node'`, no jsdom).
- **Component list already fixed by Application Design** (`backoffice-components.md`, approved): `KanbanBoard`, `LeadCard`, `LeadDetailModal`, `DraftPanel`, `NotificationCenter`, `WsLeadsClient`.

---

## Mandatory Design Artifact

- [ ] `aidlc-docs/construction/apps-backoffice/functional-design/frontend-components.md` — component hierarchy, props/state per component, user interaction flows, API integration points (mirrors the shape of `apps-chat/functional-design/frontend-components.md`)

---

## Questions

### Question 1 — Architecture: Effect (`Context.Tag`/`ManagedRuntime`) or plain hooks for `WsLeadsClient`?
`apps/chat` uses the `effect` library for its WS/chat data layer specifically (not app-wide — components themselves are plain React). `apps/backoffice`'s needs are simpler: a snapshot-then-event-stream over `/ws/leads`, no request/response RPC-style protocol (no `collect_profile_data`-style pause/resume). Should `apps/backoffice` still adopt Effect for consistency with `apps/chat`, or use plain native `WebSocket` + hooks?

A) **Mirror `apps/chat`'s Effect pattern exactly** — same `Context.Tag`/`ManagedRuntime`/`Stream` shape, consistent architecture across both frontends for anyone maintaining both
B) **Plain hooks, no `effect` dependency** — native `WebSocket`, `useState`/`useEffect`/`useCallback`, one fewer library dependency for a simpler protocol (snapshot + fire-and-forget events, no pause/resume RPC)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2 — Notification persistence across a page reload
Story 7 AC requires notifications to remain visible/dismissable when the staff member returns to the tab. Should that survive a full page reload, or only last for the current in-memory session (tab stays open, not reloaded)?

A) **In-memory only** — notifications reset on a full page reload; matches the AC's literal scenario (staff steps away from the tab, doesn't close/reload it) and keeps this simple (no new persistence layer)
B) **Persist across reloads too** (`localStorage`) — a reload shouldn't lose a pending "lead went hot" notification either
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

*(After answers are provided, this plan will be reviewed for ambiguities/contradictions before generating `frontend-components.md`.)*
