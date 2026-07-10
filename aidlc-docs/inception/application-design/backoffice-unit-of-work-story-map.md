# Unit of Work Story Map — BackOffice Lead Qualification View

**Date**: 2026-07-10

Every story in `backoffice-stories.md` spans both units, as expected for a full-stack feature — the table below breaks each one into its backend (`agent-service`) and frontend (`apps/backoffice`) half so both units' Functional Design stages know exactly what they own.

| Story | FRs | `agent-service` (Incremento 3) | `apps/backoffice` |
|---|---|---|---|
| **1** — View leads on the board | FR-2, FR-3, FR-7 | `LeadQueryService.list_leads()`, `GET /leads` | `KanbanBoard`, `LeadCard` |
| **2** — View a lead's full detail | FR-4, FR-5, FR-7 | (same `GET /leads` payload — no dedicated endpoint, Q5 = B from Application Design) | `LeadDetailModal` |
| **3** — Board updates live | FR-6, FR-8 | `LeadEventPublisher`, `LeadBroadcaster`, `/ws/leads`, `ChatAgentClient` publish hook | `WsLeadsClient`, `KanbanBoard` (live patch + reconnect reconciliation) |
| **4** — Automatic draft on `hot` | FR-9, FR-10 | `OutreachAgentService.generate_draft` (auto trigger via `LeadEventPublisher` subscription), `OutreachDraft`, `DraftRepository` | `DraftPanel` (surfaces the draft once generated) |
| **5** — On-demand draft, any score | FR-11 | `OutreachAgentService.generate_draft` (on-demand path, same method as Story 4) | `DraftPanel` ("Generate draft" action) |
| **6** — Review and send | FR-12, FR-13 | `OutreachAgentService.send_draft` / `discard_draft`, `EmailSender` (port; adapter pending NFR-5) | `DraftPanel` (Send/Discard actions, draft text display) |
| **7** — Notification on actionable lead | FR-14 | No new backend work — reuses Story 3's event stream | `NotificationCenter` |

---

## Coverage Check

- All 7 stories assigned: yes.
- All 14 FRs (FR-1–FR-14) traced to at least one unit: `backoffice-application-design.md`'s traceability table already confirms this at the component level; this table confirms it at the story level.
- No story is orphaned (assigned to neither unit) or unowned within a unit (every row has a concrete component on both sides, except Story 7's backend half, which is *intentionally* "no new work" per the Application Design decision to derive notifications client-side from the existing event stream — not a gap).
