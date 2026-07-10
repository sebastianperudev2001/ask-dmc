# Application Design Plan — BackOffice Lead Qualification View

**Date**: 2026-07-10
**Based on**: `aidlc-docs/inception/requirements/backoffice-requirements.md`, `aidlc-docs/inception/user-stories/backoffice-{stories,personas}.md`, `aidlc-docs/inception/plans/backoffice-execution-plan.md`

---

## Scope of This Design

High-level component identification and service layer design for:
1. **`agent-service` (extended)** — new read path (`list_leads`), new real-time broadcast (lead/score events), new outreach agent capability, new draft lifecycle/persistence, new email-sending adapter.
2. **`apps/backoffice` (new)** — kanban board, lead detail popup, draft review/send UI, notifications.

Detailed business logic (state machines, exact validation rules) is deferred to Functional Design (Construction phase, per-unit).

---

## Mandatory Design Artifacts

- [ ] `aidlc-docs/inception/application-design/components.md` — component definitions and high-level responsibilities
- [ ] `aidlc-docs/inception/application-design/component-methods.md` — method signatures (business rules detailed later in Functional Design)
- [ ] `aidlc-docs/inception/application-design/services.md` — service definitions and orchestration patterns
- [ ] `aidlc-docs/inception/application-design/component-dependency.md` — dependency relationships and communication patterns
- [ ] `aidlc-docs/inception/application-design/application-design.md` — consolidated summary of the above
- [ ] Validate design completeness and consistency

---

## Context Already Established (not re-litigated below)

- `Lead` domain model, `LeadRepository` port, and BR-17/BR-17b scoring already exist in `services/agent-service/src/domain/models.py` and `src/adapters/chat_agent_client.py`.
- Existing port/adapter pattern: `LeadRepository`, `CourseRepository`, `ConversationMessageRepository`, `ConversationSessionStore` — new components should follow this same shape.
- `apps/chat` is unaffected — `apps/backoffice` is a fully separate Next.js app/deploy.
- Email provider selection itself (which vendor) is explicitly deferred to NFR Requirements (NFR-5) — the question below is only about whether to define the *port* now, not which adapter implements it.
- "Replace vs. warn vs. keep both" for re-triggering an on-demand draft (Story 5) is explicitly deferred to Functional Design — not asked here.

---

## Questions

Please answer by filling in the letter choice after each `[Answer]:` tag. Choose "Other" and describe your preference if none of the options fit.

### Question 1 — Component Identification: Outreach agent boundary
Should the outreach agent (drafts personalized emails, FR-9) be a new standalone component, or an extension of the existing chat agent?

A) New standalone component (`OutreachAgentService`), separate from `ChatAgentClient` — shares only the `Lead` domain model, no coupling to the chat/tool-calling flow
B) Extend `ChatAgentClient` itself to also handle outreach drafting
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2 — Component Identification: Score-change event wiring
FR-6/FR-8 (live board updates) and FR-10 (auto-draft on `hot`) both need to react when a lead's score changes (computed today inside `ChatAgentClient._apply_engagement_floor`/BR-17b). How should this be wired?

A) A single internal `LeadEventPublisher` component that the scoring code calls once; the WS broadcaster and the outreach agent both subscribe to it (in-process pub/sub) — one trigger point, decoupled consumers
B) Two independent hooks: the scoring code directly calls the WS broadcaster AND directly calls the outreach agent's "generate draft" method — no shared publisher
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 3 — Component Methods: Draft persistence model
Should the outreach draft be a new persisted domain entity with its own repository (analogous to how `Lead` has `LeadRepository`)?

A) Yes — new entity (e.g. `OutreachDraft`) + new repository (`DraftRepository`) — the draft has its own lifecycle/state (pending/sent/discarded) independent of `Lead`
B) No — store draft fields directly on the `Lead` record (e.g. `draft_text`, `draft_status` columns on the `leads` table)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 4 — Service Layer Design: Where do dedupe/lifecycle rules live?
Story 4 requires "no duplicate active draft per lead." Should this rule live inside the same component that generates the draft, or in a separate component?

A) Single `OutreachAgentService` owns both drafting (LLM call) and lifecycle rules (dedupe check, status transitions)
B) Split: `OutreachAgentService` only drafts; a separate `DraftLifecycleService` (backed by `DraftRepository`) owns dedupe + status transitions and is the one `OutreachAgentService` consults before generating
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 5 — Component Methods: Lead detail endpoint shape
FR-7 explicitly defers the exact endpoint shape to Functional Design, but Application Design still needs to name the service boundary. Should there be a dedicated read method for a single lead, or does detail come only from the already-fetched list?

A) Dedicated method/endpoint for a single lead (`LeadQueryService.get_lead(id)` → `GET /leads/{id}`), even if Functional Design later decides not to call it from the frontend
B) No dedicated single-lead method at this level — `LeadQueryService` only exposes `list_leads()`; detail is a frontend-side lookup into the already-fetched list
C) Other (please describe after [Answer]: tag below)

[Answer]: B

### Question 6 — Component Dependencies: `apps/backoffice` componentization
How granular should the frontend component breakdown be?

A) Modular — separate components with single responsibilities: `KanbanBoard`, `LeadCard`, `LeadDetailModal`, `DraftPanel` (draft review/send, used inside the modal), `NotificationCenter` (toast/banner)
B) Fewer, larger components — `KanbanBoard` (cards rendered inline, no separate `LeadCard`) + `LeadDetailModal` (draft UI and notification handling folded in)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 7 — Design Patterns: Email port now or later?
Should an `EmailSender` port (interface only, no concrete adapter) be defined now in Application Design, consistent with the existing port/adapter pattern (`LeadRepository`, `CourseRepository`), with the concrete adapter/provider chosen later in NFR Requirements (NFR-5)?

A) Yes — define the `EmailSender` port now (method signature only); concrete adapter chosen and implemented in NFR Requirements/Design
B) No — defer even the port definition to NFR Design/Functional Design; Application Design should not lock in any interface yet
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

*(After answers are provided, this plan will be reviewed for ambiguities/contradictions per `common/question-format-guide.md` before generating the design artifacts.)*
