# Unit of Work Plan — BackOffice Lead Qualification View

**Date**: 2026-07-10
**Based on**: `backoffice-requirements.md`, `backoffice-{stories,personas}.md`, `backoffice-execution-plan.md`, `backoffice-application-design.md`

---

## Mandatory Unit Artifacts

- [ ] Generate `aidlc-docs/inception/application-design/backoffice-unit-of-work.md` — unit definitions and responsibilities
- [ ] Generate `aidlc-docs/inception/application-design/backoffice-unit-of-work-dependency.md` — dependency matrix
- [ ] Generate `aidlc-docs/inception/application-design/backoffice-unit-of-work-story-map.md` — story-to-unit mapping
- [ ] Validate unit boundaries and dependencies
- [ ] Ensure all 7 stories (`backoffice-stories.md`) are assigned to a unit

**Naming note**: this project's original `unit-of-work.md` (2026-04-28) documents a fully superseded AWS/DynamoDB/Cognito design (3 of its 5 units — `ingestion-pipeline`, `strands-agent`, `backend-api` — are deleted, superseded, or never matched what was actually built; see DIV-10, DIV-15 in `aidlc-state.md`). Per this project's established convention (`backoffice-requirements.md`, `backoffice-components.md`, etc.), this stage produces **new `backoffice-`-prefixed files** reflecting the current, real architecture rather than editing that historical record.

---

## Two Units Already Established by the Execution Plan

`backoffice-execution-plan.md` already settled the unit boundary question: this work spans **two units**, not one — a genuinely new unit (`apps/backoffice`) and an extension of the existing `agent-service` unit. This is carried forward here, not re-decided.

1. **`agent-service` (extended)** — `services/agent-service/`, existing unit, now on its 3rd increment. Gains: `LeadQueryService`, `LeadEventPublisher`, `LeadBroadcaster`, `OutreachAgentService` + `OutreachDraft` + `DraftRepository`, `EmailSender` (port).
2. **`apps/backoffice` (new)** — new unit, standalone Next.js app. Gains: `KanbanBoard`, `LeadCard`, `LeadDetailModal`, `DraftPanel`, `NotificationCenter`, `WsLeadsClient`.

---

## Categories Evaluated, Not Asked (with justification)

- **Team Alignment**: N/A — single-developer demo/course project (per prior project guidance already in memory), no team ownership boundaries to negotiate.
- **Business Domain / bounded contexts**: Already settled in Application Design — outreach drafting and lead broadcasting both live inside the `agent-service` bounded context (not a new microservice); `backoffice-components.md`/`backoffice-services.md` already assign every capability to one of the two units unambiguously.
- **Technical Considerations (scalability/deployment)**: Already settled — `backoffice-execution-plan.md` skips NFR Requirements/Design/Infrastructure Design for `apps/backoffice` (local `next dev`, same as `apps/chat`); no new compute/scaling decision exists at this stage for either unit.

---

## Questions

Please answer by filling in the letter choice after each `[Answer]:` tag. Choose "Other" and describe your preference if none of the options fit.

### Question 1 — Story Grouping: increment tracking/labeling
`agent-service` already has 2 prior incrementos (catalog+recommendation; chat+payment). Should this unit's registry entry continue that numbering?

A) Label this as "Unit — agent-service, Incremento 3 (BackOffice read/broadcast/outreach)" — continues the existing sequential incremento numbering already used in `aidlc-state.md`
B) Don't track increment numbers inside the unit-of-work doc itself — describe only the unit's current cumulative capability set; increment history stays in `aidlc-state.md`/`audit.md`
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2 — Dependencies: build/integration sequencing between the two units
`apps/backoffice`'s initial board load depends on `GET /leads`; live updates depend on `/ws/leads` — both provided by `agent-service`. How should this dependency be recorded for Construction sequencing?

A) Strictly sequential — `agent-service` (extended) is fully built and its endpoints verified working before `apps/backoffice` Code Generation starts (matches `backoffice-execution-plan.md`'s stated build order: agent-service first, `apps/backoffice` "built second, consuming agent-service's contract")
B) Parallel — `apps/backoffice` is built against a mocked/documented contract (from `backoffice-component-methods.md`) and integrated afterward, without waiting for `agent-service`'s Code Generation to finish
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 3 — Code Organization: `apps/backoffice` project structure
The repo has no monorepo tooling today (no root `package.json`, no `turbo.json` — `apps/chat` is a fully standalone Next.js project). Should `apps/backoffice` follow that exact same precedent?

A) Yes — `apps/backoffice/` is a standalone Next.js app, sibling to `apps/chat/`, with its own `package.json`; no shared package or monorepo tooling introduced
B) Introduce a minimal shared package now (e.g. `packages/ui`) for anything the two frontends might share visually or logically
C) Other (please describe after [Answer]: tag below)

[Answer]: A (add a github ticke as a spike to consider using turborepo and why it would be useful)

---

*(After answers are provided, this plan will be reviewed for ambiguities/contradictions before generating the unit-of-work artifacts.)*
