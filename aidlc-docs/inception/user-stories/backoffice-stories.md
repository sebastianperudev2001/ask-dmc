# User Stories — BackOffice Lead Qualification View

**Epic**: Lead Qualification View & Outreach
**Persona**: [DMC Sales Staff](backoffice-personas.md#persona-dmc-sales-staff) (single persona, all stories)
**Breakdown approach**: Feature-based (`backoffice-story-generation-plan.md`, Question 3 = A)
**Acceptance criteria format**: Given/When/Then (`backoffice-story-generation-plan.md`, Question 4 = A)
**Traceability**: Each story references the FR(s) it implements in `backoffice-requirements.md`

---

## Story 1 — View leads on the qualification board
**As** DMC Sales Staff, **I want** to see all leads grouped into Hot/Warm/Cold columns, **so that** I can tell at a glance who deserves attention without digging through conversations.

*Implements: FR-2, FR-3, FR-7*

**Acceptance Criteria:**
- **Given** leads exist with different scores, **when** I open the BackOffice board, **then** I see three columns labeled Hot, Warm, and Cold, each containing the leads with that score.
- **Given** a lead is in a column, **when** I look at its card, **then** I see at least the lead's name.
- **Given** there are no leads in a given tier, **when** I view that column, **then** it renders empty (not an error state).

**INVEST notes**: Independent of the other stories (a static board with no popup/live updates is still shippable and valuable on its own); Small — a single read endpoint + static render.

---

## Story 2 — View a lead's full detail
**As** DMC Sales Staff, **I want** to click a lead card and see its full profile, **so that** I understand who they are and why they're scored the way they are before I decide to act.

*Implements: FR-4, FR-5, FR-7*

**Acceptance Criteria:**
- **Given** the board is showing lead cards, **when** I click one, **then** a popup opens showing name, email, created date, profile summary, motivation (+ detail), recommended programs, score, score justification, and payment status.
- **Given** the popup is open, **when** I look for a way to edit any field, **then** there is none — the view is read-only for the `Lead` record itself (FR-5).
- **Given** the popup is open, **when** I look for the conversation transcript, **then** it is not shown (explicitly out of scope per FR-4).

**INVEST notes**: Depends on Story 1 (needs a card to click), otherwise independently testable and valuable.

---

## Story 3 — See the board update live
**As** DMC Sales Staff, **I want** the board to reflect score changes and new leads as they happen, **so that** I don't miss a lead going hot while I'm looking at the board.

*Implements: FR-6, FR-8*

**Acceptance Criteria:**
- **Given** I have the board open, **when** a new lead is created in `agent-service`, **then** a new card appears in the Cold column without me reloading the page.
- **Given** I have the board open, **when** an existing lead's score changes (e.g. BR-17b engagement floor pushes it from Cold to Warm, or to Hot), **then** the card moves to the correct column live.
- **Given** my WebSocket connection drops, **when** it reconnects, **then** the board reconciles to the current server state (no stale/duplicate cards).

**INVEST notes**: Builds on Story 1's board; independently valuable (the board is useful even before Stories 4-7 exist) but depends on it existing first.

---

## Story 4 — Get an automatic draft when a lead goes hot
**As** DMC Sales Staff, **I want** the system to draft a personalized outreach email the moment a lead becomes Hot, **so that** I don't have to write one from scratch under time pressure.

*Implements: FR-9, FR-10*

**Acceptance Criteria:**
- **Given** a lead's score transitions to Hot, **when** that happens, **then** the outreach agent generates a draft email using that lead's `profile_summary`, `motivation`, `motivation_detail`, and `recommended_programs`.
- **Given** a draft has been generated for a lead, **when** I open that lead's detail popup, **then** I see the draft available for review (not yet sent — see Story 6).
- **Given** a lead is already Hot and a draft already exists for it, **when** its score is re-evaluated and it stays Hot, **then** a duplicate draft is not generated (one active draft per lead at a time).

**INVEST notes**: Depends on Story 2 (draft surfaces in the detail popup) and the scoring pipeline already in production (BR-17/BR-17b) — no new domain logic there, only a new consumer of the existing score-change event.

---

## Story 5 — Request a draft for any lead, on demand
**As** DMC Sales Staff, **I want** to trigger a draft for a lead that isn't Hot yet, **so that** I can reach out proactively to a promising Warm or Cold lead if I choose to, without waiting for the automatic trigger.

*Implements: FR-11*

**Acceptance Criteria:**
- **Given** I have a lead's detail popup open, **when** I click a "Generate draft" action, **then** the outreach agent generates a personalized draft for that lead, regardless of its current score.
- **Given** a lead already has an active draft, **when** I trigger draft generation again for that lead, **then** I am shown the existing draft rather than silently overwriting it (exact behavior — replace vs. warn vs. keep both — deferred to Functional Design).

**INVEST notes**: Independent of Story 4 (different trigger, same underlying draft-generation capability) — could ship without Story 4 existing, though they'll likely share the same draft-generation service under the hood.

---

## Story 6 — Review and send a drafted message
**As** DMC Sales Staff, **I want** to review a drafted email before it goes out and be the one who actually sends it, **so that** nothing reaches a prospective student without my approval — these messages represent DMC.

*Implements: FR-12*

**Acceptance Criteria:**
- **Given** a draft exists for a lead (from Story 4 or Story 5), **when** I open that lead's detail popup, **then** I see the full draft text and a "Send" action.
- **Given** I am viewing a draft, **when** I click "Send", **then** the email is sent to the lead's `Lead.email` and the UI confirms it was sent.
- **Given** a draft exists, **when** I take no action, **then** nothing is sent — there is no automatic fallback send.
- **Given** I choose not to send a draft, **when** I look for a "Discard" or equivalent action, **then** one exists (exact UX deferred to Functional Design, but silently accumulating unusable drafts forever is out of scope for a good experience).

**INVEST notes**: Directly depends on Story 4 and/or Story 5 producing a draft to review — this is the capability that makes those stories valuable, not shippable on its own.

---

## Story 7 — Get notified when a lead needs attention
**As** DMC Sales Staff, **I want** an in-app alert when a lead becomes actionable, **so that** I notice it even if I'm not staring at the board at that exact moment.

*Implements: FR-14*

**Acceptance Criteria:**
- **Given** I have the BackOffice open in a browser tab, **when** a lead's score reaches Hot, **then** I see an in-app banner/toast notification.
- **Given** the notification appears, **when** I click it, **then** it takes me directly to that lead's detail popup.
- **Given** I am not actively looking at the tab, **when** I return to it, **then** any notifications that fired while I was away are still visible/dismissable (not lost).

**Assumption carried from `backoffice-requirements.md` FR-14** (pending your confirmation): "needs attention" = score reaches Hot, same trigger as Story 4's auto-draft — not every lead creation.

**INVEST notes**: Reuses Story 3's WebSocket channel — small, additive on top of already-planned real-time infrastructure.

---

## Story Map (dependency order, not sprint order)

```
Story 1 (board) ─┬─> Story 2 (detail popup) ─┬─> Story 4 (auto-draft on hot) ─┐
                 │                            ├─> Story 5 (on-demand draft) ──┼─> Story 6 (review & send)
                 └─> Story 3 (live updates) ──┴─────────────────────────────> Story 7 (notification)
```
