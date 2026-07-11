# Functional Design Plan — agent-service, Incremento 3 (BackOffice: read path + real-time broadcast + outreach agent)

**Date**: 2026-07-10
**Unit**: `agent-service` (extended) — see `aidlc-docs/inception/application-design/backoffice-unit-of-work.md`
**Stories assigned**: 1, 2, 3 (backend half), 4, 5, 6 (full ownership), 7 (event stream only) — see `backoffice-unit-of-work-story-map.md`
**Scope note**: this unit only. `apps/backoffice`'s own (light) Functional Design happens later, after this unit's Code Generation is verified working (per the strictly-sequential build order agreed in Units Generation).

---

## Mandatory Design Artifacts

- [ ] Append "Incremento 3" section to `aidlc-docs/construction/agent-service/functional-design/business-logic-model.md` (continuing from Sección 18)
- [ ] Append "Incremento 3" section to `aidlc-docs/construction/agent-service/functional-design/business-rules.md` (continuing from BR-21)
- [ ] Append "Incremento 3" section to `aidlc-docs/construction/agent-service/functional-design/domain-entities.md`
- [ ] No `frontend-components.md` needed for this unit (backend-only)

Following this unit's own established convention (Incremento 2 appended sections to these same 3 files rather than creating new ones — unlike the INCEPTION-phase docs, which used `backoffice-`-prefixed new files because they described a different, superseded system).

---

## Context Already Established (not re-litigated below)

- Components/services/method signatures: `backoffice-{components,component-methods,services}.md` (Application Design, approved).
- `OutreachAgentService` owns both drafting and lifecycle (Q4 = A, Application Design); `LeadEventPublisher` is a single in-process pub/sub point (Q2 = A); `EmailSender` is a port only, no adapter yet (Q7 = A, Application Design — provider decided in this unit's own NFR Requirements stage, next).
- BR-17b (`services/agent-service/src/domain/lead_scoring.py`) is monotonic — once a lead reaches `hot` in a conversation, its score never decreases. This means "score transitions to hot" is a one-time event per lead's lifetime, not something that can flicker.

---

## Questions

Please answer by filling in the letter choice after each `[Answer]:` tag. Choose "Other" and describe your preference if none of the options fit.

### Question 1 — Business Rules: what counts as an "active" draft for dedupe?
Story 4 requires "no duplicate draft" while a lead is hot. What should "active" mean for that check?

A) Only `status = pending` counts as active — once a draft is sent or discarded, generating a new draft (auto or on-demand) is allowed again
B) Any draft ever generated for a lead blocks new generation forever — one draft per lead, period, regardless of status
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2 — Business Scenarios: on-demand regeneration when a pending draft already exists
Story 5's AC explicitly deferred this to Functional Design: when staff clicks "Generate draft" for a lead that already has a `pending` draft, what happens?

A) Return the existing pending draft unchanged (no new LLM call, no error) — "show, don't regenerate"
B) Regenerate and replace the existing pending draft with a fresh one (discarding the old text)
C) Reject the request with an error telling staff to review/send/discard the existing draft first
D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 3 — Integration Points: synchronous or fire-and-forget auto-draft generation?
The auto-draft trigger (FR-10) fires from inside `ChatAgentClient`'s scoring update path, which runs during a live chat turn in `apps/chat`. Drafting is an LLM call (seconds). Should it block that turn?

A) Fire-and-forget — `LeadEventPublisher.publish()` does not await the outreach subscriber's LLM call; it runs as a background task so chat turn latency in `apps/chat` is unaffected
B) Synchronous — the chat turn genuinely waits for the draft to finish generating before the user's message turn completes
C) Other (please describe after [Answer]: tag below)
 
[Answer]: A

### Question 4 — Business Rules: auto-draft trigger when `Lead.email` is missing
BR-17b's message-count floor can push a lead to `hot` (10+ user messages) without ever completing the profile form — the only place `Lead.email` is captured. What should happen when the auto-draft trigger fires for a `hot` lead with no email on file?

A) Skip draft generation for now (log it); nothing else changes — the lead has no further automatic retry since BR-17b is monotonic and won't re-fire the same transition. Staff can still trigger an on-demand draft later if email gets filled in.
B) Generate the draft text anyway (personalization doesn't strictly need email), but block only the "Send" action in the UI until `Lead.email` is present
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 5 — Data Flow: resolving course names for personalization
`Lead.recommended_programs` stores `course_id`s, not names/descriptions. Should `OutreachAgentService` depend on the existing `CourseRepository` to resolve course details for the drafted email's content?

A) Yes — `OutreachAgentService` takes a `CourseRepository` dependency to resolve `course_id → name/description/curriculum` for use in the LLM prompt
B) No — pass only the raw `course_id`s into the prompt; personalization works with IDs alone
C) Other (please describe after [Answer]: tag below)

[Answer]: A (this should be a tool)

### Question 6 — Error Handling: draft generation (LLM call) failure
If the LLM call inside `generate_draft` fails (timeout, provider error), what should happen?

A) Propagate the error — an on-demand caller (staff-initiated) gets an error response to show in the UI; the auto-trigger subscriber logs it and swallows the error (must never crash the scoring/broadcast path it's attached to)
B) Retry with backoff first (reuse the existing `RetryPolicy` pattern already used by other adapters), then fall back to (A) if retries are exhausted
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 7 — Error Handling: send (email) failure
If `EmailSender.send` fails inside `send_draft`, what should happen to the draft's status?

A) Stays `pending` — the error is surfaced to staff so they can retry the Send action; no new status needed
B) Moves to a distinct `failed` status, so staff can tell "never attempted" apart from "attempted and failed"
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 8 — Domain Model: `LeadEvent` payload shape
What should the event object published by `LeadEventPublisher` carry?

A) Minimal — `event_type` (created / score_changed) + `lead_id` + the new `score` only; any consumer needing more (e.g. the board rendering a new card) re-fetches full detail via the already-available lead list
B) Full — the entire `Lead` record embedded in every event, so `LeadBroadcaster` can forward it directly with no additional lookup, and `KanbanBoard` never needs a second round-trip for a newly created lead
C) Other (please describe after [Answer]: tag below)

[Answer]: B

### Question 9 — Business Rules: does the reconnect snapshot need draft-state awareness?
`LeadBroadcaster` sends a full `list_leads()` snapshot on (re)connect. Should that snapshot (or the live event stream) also indicate which leads currently have an active draft, so the board could show a "draft ready" indicator on the card itself — or is draft state entirely a detail-popup concern?

A) Snapshot/events are Lead-only, no draft indicator on cards — draft state is only checked when a specific lead's detail popup opens (matches Application Design's decision not to push separate draft-ready events)
B) Snapshot/events should also carry a `has_active_draft` boolean per lead so the board can show an indicator without opening each popup
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Follow-up Questions (2026-07-11)

Two items need clarification before generation:

### Follow-up 1 — Question 4 was left unanswered
Please pick A, B, or Other for: what should happen when the auto-draft trigger fires for a `hot` lead with no `Lead.email` on file?

A) Skip draft generation for now (log it); no automatic retry (BR-17b's `hot` transition is monotonic/one-time). Staff can still trigger an on-demand draft later if email gets filled in.
B) Generate the draft text anyway, but block only the "Send" action in the UI until `Lead.email` is present
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Follow-up 2 — Question 5: what does "this should be a tool" mean architecturally?
You answered A (resolve course details via `CourseRepository`) but added "this should be a tool." That could mean two different designs:

A) **`OutreachAgentService` becomes agentic (tool-calling)**, mirroring `ChatAgentClient`'s existing architecture — the LLM itself decides to invoke a `get_course_details(course_id)` tool mid-generation to look up name/description/curriculum, rather than the orchestration code pre-fetching that data and stuffing it into a single-shot prompt. This means `generate_draft` runs a full agent loop (system prompt + tool + LLM), not one `LLMProvider.complete()` call.
B) **Simpler internal-code meaning** — no agentic tool-calling loop; `OutreachAgentService.generate_draft` deterministically calls `CourseRepository` in plain Python to resolve `course_id → name/description` *before* building the prompt, and "tool" just meant "give it a way to look this up" (organizationally, not architecturally agentic)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

*(After answers are provided, this plan will be reviewed for ambiguities/contradictions before generating the functional design artifacts.)*
