# Requirements — BackOffice: Lead Qualification View

## Intent Analysis Summary

- **User Request**: "Using frontend design I need to create the view for DMC backOffice to qualify leads"
- **Request Type**: New Feature
- **Scope Estimate**: Multiple Components — new frontend app (`apps/backoffice`) + new backend read/broadcast capability on `agent-service` (`list_leads`, `GET /leads`, a leads WebSocket channel)
- **Complexity Estimate**: Moderate — no auth, read-only, reuses existing `Lead`/scoring domain model; the real-time (WebSocket) requirement is the main source of complexity, since it means propagating live score changes computed deep in the agent's conversation flow (`ChatAgentClient._apply_engagement_floor`) out to a separate, unrelated frontend surface.

## Background / Existing System Context

`agent-service` already computes and persists everything this view needs to *read*:
- `Lead` (`services/agent-service/src/domain/models.py`): `id`, `created_at`, `name`, `email`, `profile_summary`, `motivation`, `motivation_detail`, `recommended_programs`, `score` (`LeadScore`: `hot`/`warm`/`cold`), `score_justification`, payment fields (`payment_link_sent`, `payment_checkout_url`, `payment_preference_id`, `payment_confirmed`, `payment_confirmed_at`, `mercadopago_payment_id`), `escalated_to_human`, `service_session_id`.
- `score_lead()` (BR-17) and `engagement_floor()`/`apply_score_floor()` (BR-17b) — the scoring logic behind `Lead.score`.

What does **not** exist yet:
- Any way to list leads. `LeadRepository` only supports `save`, `find_by_service_session_id`, `mark_payment_confirmed` — no `list_leads`.
- Any staff-facing frontend. `apps/chat` is the only frontend app, and it's built for end users (leads), not internal staff.
- Any WebSocket channel for lead/score events — the existing `/ws/chat` channel is scoped to a single conversation, not a broadcast of all leads.

## Functional Requirements

- **FR-1**: A new frontend application, `apps/backoffice`, shall be created for internal DMC staff to view and qualify leads. It is a separate Next.js project/deploy from `apps/chat` (not a route within it).
- **FR-2**: The main BackOffice view shall present all leads as a **kanban-style board with three columns**: Hot, Warm, Cold — one column per `LeadScore` value.
- **FR-3**: Each lead shall appear as a card in its score column, showing at minimum the lead's name.
- **FR-4**: Clicking a lead card shall open a detail popup showing the `Lead` record's fields: name, email, `created_at`, `profile_summary`, `motivation`, `motivation_detail`, `recommended_programs`, `score` + `score_justification`, and payment status (`payment_link_sent`, `payment_confirmed`, `payment_confirmed_at`). The popup does **not** show the conversation transcript.
- **FR-5**: This view is **read-only** in this iteration — no manual score override, no notes/status fields, no escalation actions from the BackOffice UI. It only surfaces what the agent already computed.
- **FR-6**: The board shall update **in real time**: when a lead is created or its `score` changes server-side (e.g. via BR-17b engagement floor during an active chat), the corresponding card shall appear/move to the correct column live, without a manual page refresh.
- **FR-7**: `agent-service` shall gain a `list_leads` capability (`LeadRepository.list_leads()` + backing `GET /leads` endpoint) returning all leads with the fields needed for FR-3/FR-4. Whether the detail popup (FR-4) is served by a dedicated `GET /leads/{id}` or read directly from the already-fetched list payload is an implementation decision deferred to Functional Design.
- **FR-8**: `agent-service` shall gain a way to push lead create/score-change events to connected BackOffice clients (a new WebSocket channel, e.g. `/ws/leads`) to satisfy FR-6. Exact broadcast mechanism (fan-out to all connected clients, in-process pub/sub, etc.) is deferred to Functional/NFR Design.

## Non-Functional Requirements

- **NFR-1 (Access Control — explicitly descoped this iteration)**: No authentication or access control is implemented for `apps/backoffice` or its backend endpoints in this iteration. This is an accepted, explicit risk for the current local/demo scope (`Lead` records contain PII — name, email, motivation, payment status). Tracked as follow-up work: **[GitHub issue #18](https://github.com/sebastianperudev2001/ask-dmc/issues/18)** ("Add access control to BackOffice lead qualification view"). This must be revisited under the project's Security Baseline extension (already enabled, see `aidlc-state.md` Extension Configuration) before any real/shared deployment.
- **NFR-2 (Visual Design)**: The BackOffice shall have its own distinct visual identity — an "internal tool" look, **not** matching `apps/chat`'s branding — aligned with DMC institute's brand guidelines as published at dmc.pe. This shall be executed deliberately using the `frontend-design` skill during Code Generation, not left to framework defaults.
- **NFR-3 (Consistency with existing architecture)**: New backend work shall reuse `agent-service`'s existing patterns (Postgres persistence via a new adapter alongside `PostgresLeadRepository`, FastAPI routing, WebSocket handling patterns already established for `/ws/chat`) rather than introducing new infrastructure or a separate service.
- **NFR-4 (Read path performance)**: `GET /leads` should perform acceptably for the current demo-scale catalog/lead volume; no specific latency target is set given the project's demo/course scope (per prior project guidance — performance/scaling work is intentionally de-prioritized for this project).

## Summary

New internal-facing feature: a read-only, real-time kanban board (`apps/backoffice`) showing leads grouped Hot/Warm/Cold, backed by a new `list_leads` read path and a new leads WebSocket channel on `agent-service`. No auth in this iteration (tracked as issue #18). Visual design is deliberately distinct from `apps/chat`, aligned to DMC's brand (dmc.pe), executed via the `frontend-design` skill during Code Generation.
