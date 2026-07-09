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

### Board & Lead Data (read-only)
- **FR-1**: A new frontend application, `apps/backoffice`, shall be created for internal DMC staff to view and qualify leads. It is a separate Next.js project/deploy from `apps/chat` (not a route within it).
- **FR-2**: The main BackOffice view shall present all leads as a **kanban-style board with three columns**: Hot, Warm, Cold — one column per `LeadScore` value.
- **FR-3**: Each lead shall appear as a card in its score column, showing at minimum the lead's name.
- **FR-4**: Clicking a lead card shall open a detail popup showing the `Lead` record's fields: name, email, `created_at`, `profile_summary`, `motivation`, `motivation_detail`, `recommended_programs`, `score` + `score_justification`, and payment status (`payment_link_sent`, `payment_confirmed`, `payment_confirmed_at`). The popup does **not** show the conversation transcript.
- **FR-5**: The lead data itself is **read-only** — no manual score override, no notes/status fields editable from the BackOffice UI. Staff cannot directly edit a `Lead` record. (This does not preclude the outreach actions in FR-9..FR-13 below, which are a distinct capability, not edits to the `Lead` record.)
- **FR-6**: The board shall update **in real time**: when a lead is created or its `score` changes server-side (e.g. via BR-17b engagement floor during an active chat), the corresponding card shall appear/move to the correct column live, without a manual page refresh.
- **FR-7**: `agent-service` shall gain a `list_leads` capability (`LeadRepository.list_leads()` + backing `GET /leads` endpoint) returning all leads with the fields needed for FR-3/FR-4. Whether the detail popup (FR-4) is served by a dedicated `GET /leads/{id}` or read directly from the already-fetched list payload is an implementation decision deferred to Functional Design.
- **FR-8**: `agent-service` shall gain a way to push lead create/score-change events to connected BackOffice clients (a new WebSocket channel, e.g. `/ws/leads`) to satisfy FR-6. Exact broadcast mechanism (fan-out to all connected clients, in-process pub/sub, etc.) is deferred to Functional/NFR Design.

### Outreach Agent (added during User Stories — scope expansion, see audit.md 2026-07-09)
- **FR-9**: The system shall include an outreach agent capable of drafting a **personalized, contextual message** to a lead, using data already collected during that lead's conversation (`profile_summary`, `motivation`, `motivation_detail`, `recommended_programs`, etc.).
- **FR-10**: The outreach agent shall **automatically generate a draft** the moment a lead's score reaches `hot` (same trigger as BR-17/BR-17b reaching `LeadScore.HOT`).
- **FR-11**: Staff shall also be able to trigger draft generation **on-demand** for any lead (any score tier), from that lead's detail popup (FR-4).
- **FR-12**: A drafted message shall **never be sent automatically**. Staff must review the draft in the BackOffice UI and take an explicit "Send" action — this is a hard human-in-the-loop gate, not a notify-after-the-fact pattern.
- **FR-13**: **Channel scope for this increment: email only.** `Lead.email` already exists and is sufficient. **WhatsApp is explicitly out of scope for this increment** — no phone number is captured anywhere in the system today (`Lead`, `collect_profile_data`) and no WhatsApp Business API credentials exist. Tracked as follow-up: **[GitHub issue #19](https://github.com/sebastianperudev2001/ask-dmc/issues/19)** ("Add WhatsApp outreach channel to BackOffice lead qualification view").

### Staff Notifications
- **FR-14**: Staff shall be notified **in-app** (banner/toast on the BackOffice board itself) when a lead becomes actionable. This reuses the WebSocket channel already required for FR-6/FR-8 — no new external integration (email/SMS/Slack) is introduced for notifications in this increment. **Assumption, pending your confirmation at requirements approval**: "actionable" = the same moment FR-10's auto-draft fires (score reaches `hot`), not every lead creation — this avoids noisy notifications for `cold` leads created by default. Flag if you intended notification-on-creation regardless of score instead.

## Non-Functional Requirements

- **NFR-1 (Access Control — explicitly descoped this iteration)**: No authentication or access control is implemented for `apps/backoffice` or its backend endpoints in this iteration. This is an accepted, explicit risk for the current local/demo scope (`Lead` records contain PII — name, email, motivation, payment status). Tracked as follow-up work: **[GitHub issue #18](https://github.com/sebastianperudev2001/ask-dmc/issues/18)** ("Add access control to BackOffice lead qualification view"). This must be revisited under the project's Security Baseline extension (already enabled, see `aidlc-state.md` Extension Configuration) before any real/shared deployment.
- **NFR-2 (Visual Design)**: The BackOffice shall have its own distinct visual identity — an "internal tool" look, **not** matching `apps/chat`'s branding — aligned with DMC institute's brand guidelines as published at dmc.pe. This shall be executed deliberately using the `frontend-design` skill during Code Generation, not left to framework defaults.
- **NFR-3 (Consistency with existing architecture)**: New backend work shall reuse `agent-service`'s existing patterns (Postgres persistence via a new adapter alongside `PostgresLeadRepository`, FastAPI routing, WebSocket handling patterns already established for `/ws/chat`) rather than introducing new infrastructure or a separate service.
- **NFR-4 (Read path performance)**: `GET /leads` should perform acceptably for the current demo-scale catalog/lead volume; no specific latency target is set given the project's demo/course scope (per prior project guidance — performance/scaling work is intentionally de-prioritized for this project).
- **NFR-5 (Email provider — deferred to NFR Requirements)**: This increment needs a way to actually send email (FR-12's "Send" action). No email-sending provider is chosen yet — this project has an open, unresolved precedent for exactly this kind of decision (DIV-12: human-escalation notification channel deferred in `agent-service` incremento 2 for the same reason, no Azure SES equivalent decided). Provider selection is deferred to this unit's **NFR Requirements** stage in Construction, consistent with how prior tech-stack decisions (Container Apps, Postgres tier, Azure OpenAI model) were made at that stage, not at Requirements Analysis.
- **NFR-6 (WhatsApp — explicitly out of scope, tracked separately)**: See FR-13. Tracked as [GitHub issue #19](https://github.com/sebastianperudev2001/ask-dmc/issues/19).

## Summary

New internal-facing feature: a real-time kanban board (`apps/backoffice`) showing leads grouped Hot/Warm/Cold (read-only for the `Lead` record itself), backed by a new `list_leads` read path and a new leads WebSocket channel on `agent-service`. Expanded during User Stories (2026-07-09) to include an **outreach agent**: auto-drafts a personalized email when a lead reaches `hot`, or on-demand for any lead, with a hard human-in-the-loop gate before sending (email only this increment — WhatsApp deferred, issue #19) — plus **in-app staff notifications** reusing the same real-time channel. No auth in this iteration (tracked as issue #18). Visual design is deliberately distinct from `apps/chat`, aligned to DMC's brand (dmc.pe), executed via the `frontend-design` skill during Code Generation.
