# Unit of Work — BackOffice Lead Qualification View

**Date**: 2026-07-10
**Based on**: `backoffice-execution-plan.md`, `backoffice-application-design.md`, answered `backoffice-unit-of-work-plan.md`
**Supersedes for this scope**: the original `unit-of-work.md` (2026-04-28) is historical record only (AWS/DynamoDB/Cognito design, mostly deleted/superseded — see DIV-10, DIV-15 in `aidlc-state.md`). This file reflects the current, real architecture for this increment.

---

## Decomposition Model

Two units, built **sequentially** (Q2 = A): `agent-service` first, then `apps/backoffice`, which consumes its contract.

```
[agent-service, Incremento 3]
        |  (GET /leads + /ws/leads verified working)
        v
[apps/backoffice, new unit]
```

---

## Unit 1 — agent-service (extended), Incremento 3

*(Continues the existing sequential incremento numbering per Q1 = A — see prior incrementos in `aidlc-state.md`: Incremento 1 = catalog + recommendation, Incremento 2 = chat + payment.)*

| Field | Value |
|---|---|
| **Directory** | `services/agent-service/` (existing, extended) |
| **Runtime** | Python — FastAPI + Azure AI Foundry Agent (existing stack, unchanged) |
| **Deployment** | Azure Container Apps (existing; no new infra target for this increment — deployment itself remains out of scope per prior incrementos' pattern) |

### Responsibility
Gains, on top of its existing chat/recommendation/payment capabilities: a read path for listing leads, a real-time broadcast channel for lead/score events, and a standalone outreach-drafting agent with its own persisted draft lifecycle and human-gated send action.

### Components included (new/extended this increment)
- `LeadQueryService` — `list_leads()` read orchestration
- `LeadRepository` (extended) — `list_leads()` added
- `LeadEventPublisher` — in-process pub/sub for lead lifecycle events
- `LeadBroadcaster` — `/ws/leads` WebSocket connection manager
- `ChatAgentClient` (extended) — one new call to `LeadEventPublisher.publish(...)` after a score change
- `OutreachAgentService` — drafting + full lifecycle (dedupe, send, discard)
- `OutreachDraft` (domain model, new)
- `DraftRepository` — new port + Postgres adapter
- `EmailSender` — new port only (adapter deferred to NFR Requirements, NFR-5)

Full responsibilities/interfaces: `backoffice-components.md`, `backoffice-component-methods.md`.

### Entry Criteria
- Application Design approved (this increment) — done, 2026-07-10
- Existing `agent-service` Incremento 2 code in place (`Lead` model, `LeadRepository`, `ChatAgentClient`, BR-17/BR-17b) — already true
- Email provider decision made (NFR Requirements, this increment's Construction phase) before `EmailSender` can be implemented (not before `OutreachAgentService`'s other methods, which don't depend on it)

### Exit Criteria
- `GET /leads` returns all leads with fields required by FR-3/FR-4
- `/ws/leads` broadcasts lead-created and score-changed events, with reconnect snapshot reconciliation (Story 3 AC)
- Outreach draft auto-generates on score reaching `hot` with no duplicates (Story 4 AC)
- On-demand draft generation works for any score tier (Story 5 AC)
- Send/discard actions work, with no code path that sends without an explicit staff action (FR-12)
- Tests passing (unit + integration, consistent with this project's established practice of testing against real infrastructure — Postgres, WS — over mocks where feasible)

### Stories Covered (backend half)
FR-7, FR-8 backing capability for Stories 1, 2, 3; full ownership of FR-9–FR-13 (Stories 4, 5, 6); event stream backing Story 7. See `backoffice-unit-of-work-story-map.md` for the full per-story breakdown across both units.

---

## Unit 2 — apps/backoffice (new)

| Field | Value |
|---|---|
| **Directory** | `apps/backoffice/` (new, sibling to `apps/chat/`) |
| **Runtime** | TypeScript — Next.js |
| **Deployment** | Local (`next dev`) only for this increment — no deployment target decided, matching `apps/chat`'s current state (Infrastructure Design skipped per `backoffice-execution-plan.md`) |

### Responsibility
Internal-facing kanban board for DMC Sales Staff: real-time Hot/Warm/Cold board, read-only lead detail popup, outreach draft review/send/discard UI, in-app notifications. Visually distinct from `apps/chat` per NFR-2 (executed via the `frontend-design` skill during Code Generation).

### Code Organization (Q3 = A)
Standalone Next.js app, own `package.json`, no shared package or monorepo tooling — matches the existing `apps/chat` precedent exactly. The repo has no root `package.json`/`turbo.json` today. **Follow-up tracked**: [GitHub issue #20](https://github.com/sebastianperudev2001/ask-dmc/issues/20) — a spike to evaluate Turborepo if/when duplication between `apps/chat` and `apps/backoffice` (shared types, WS client pattern) starts to hurt; not adopted now.

### Components included
- `KanbanBoard`, `LeadCard`, `LeadDetailModal`, `DraftPanel`, `NotificationCenter`, `WsLeadsClient`

Full responsibilities/interfaces: `backoffice-components.md`, `backoffice-component-methods.md`.

### Entry Criteria
- Unit 1 (`agent-service`, Incremento 3) fully built and its endpoints (`GET /leads`, `/ws/leads`, draft generate/send/discard) verified working (Q2 = A — strictly sequential, not built against a mock)
- Application Design approved — done, 2026-07-10

### Exit Criteria
- Board renders all leads grouped Hot/Warm/Cold (Story 1 AC)
- Detail popup shows all required `Lead` fields, read-only, no transcript (Story 2 AC)
- Board updates live on score change / new lead, reconciles cleanly on reconnect (Story 3 AC)
- Draft review/generate/send/discard UI functions end-to-end against real `agent-service` (Stories 4–6 AC)
- In-app notification fires on a lead reaching hot, remains visible/dismissable after returning to the tab (Story 7 AC)
- Visual identity distinct from `apps/chat`, aligned to dmc.pe brand guidelines (NFR-2)

### Stories Covered (frontend half)
Full ownership of the UI surface for all 7 stories. See `backoffice-unit-of-work-story-map.md`.
