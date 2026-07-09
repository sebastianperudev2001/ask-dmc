# Story Generation Plan — BackOffice Lead Qualification View

Role: Product Owner, translating `aidlc-docs/inception/requirements/backoffice-requirements.md` (FR-1 through FR-8) into user-centered stories.

## Story Breakdown Approach Options

- **User Journey-Based**: One story per step of a staff member's actual workflow (open board → scan tiers → open a lead → decide next action). Best when the sequence of steps matters more than the individual feature.
- **Feature-Based**: One story per FR (board view, detail popup, real-time updates). Best for small, well-bounded scope like this one — maps cleanly to what's already itemized in `requirements.md`.
- **Persona-Based**: Stories grouped by staff role, if there turn out to be multiple distinct roles (see Question 1).
- **Domain-Based / Epic-Based**: Overkill for this scope — a single epic ("Lead Qualification View") with a handful of stories underneath covers it; not treated as separate top-level structures here.

**Recommendation**: Feature-based stories under a single "Lead Qualification View" epic, since scope is already itemized (FR-1..FR-8) and there's currently one known persona. This can be revisited based on your answer to Question 1.

## Clarifying Questions

### Question 1 — Staff persona(s)
`requirements.md` refers generically to "DMC staff." Is this one role, or should stories distinguish between roles with different needs (e.g. a sales rep who acts on leads day-to-day vs. a manager who wants an overview)?

A) One persona — all staff who use this view have the same needs (a generic "DMC Sales Staff" persona)
B) Two or more distinct roles with different needs (please name the roles after [Answer]: below)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2 — Business goal / success metric
What is this view actually *for*, from the business's perspective? This shapes the persona's motivation and the stories' "so that..." clauses.

A) Speed — staff can quickly see which leads are hot and need immediate follow-up, without digging through conversations
B) Prioritization — staff triage their work queue across many leads (which to call first, which to deprioritize)
C) Visibility/oversight — mainly a dashboard for tracking lead volume and quality over time, not a daily action tool
D) Other (please describe after [Answer]: tag below)

[Answer]: The idea is to implement another agent that allows them to draft messages and send them over WhatsApp or send email automatically with the information recollected. Everything should be personalized and contextual based on the data collected in the conversation. Also, staff should get notified when a lead is created and needs attention.

### Question 3 — Story breakdown approach
Given the recommendation above (Feature-based, single epic), do you want to proceed with that, or a different approach?

A) Feature-based (as recommended) — one story per FR/capability (view board, view lead detail, see live updates)
B) User Journey-based — stories follow the sequence of an actual staff workflow session
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 4 — Acceptance criteria format
A) Given/When/Then (Gherkin-style) — precise, testable, more verbose
B) Plain bullet checklist per story — faster to read, less rigorous
C) Other (please describe after [Answer]: tag below)

[Answer]:  A

## Resolved Answers (final, after two follow-up rounds — see `backoffice-story-generation-clarification-questions.md` and `backoffice-outreach-clarification-questions.md`)

- **Persona**: One — generic "DMC Sales Staff" persona.
- **Business goal**: Prioritization/triage across many leads, which the user tied back to speed ("reduce manual work") and to staff staying "in the loop" as the human checkpoint on outreach.
- **Breakdown approach**: Feature-based, single "Lead Qualification View" epic.
- **Acceptance criteria format**: Given/When/Then (Gherkin-style).
- **Scope**: Expanded to include the outreach agent (email-only, auto-draft on `hot`, on-demand for any lead, hard human-in-the-loop send gate) and in-app staff notifications — see `backoffice-requirements.md` FR-9..FR-14. WhatsApp explicitly deferred (issue #19).

## Mandatory Story Artifacts (Plan Checklist)

- [ ] Generate `aidlc-docs/inception/user-stories/backoffice-personas.md` with the "DMC Sales Staff" persona, motivation = prioritizing/triaging leads quickly while staying the human checkpoint on outreach
- [ ] Generate `aidlc-docs/inception/user-stories/backoffice-stories.md`, feature-based, one story per: FR-2 (board view), FR-3 (lead cards), FR-4 (detail popup), FR-6 (real-time board updates), FR-9/FR-10 (auto-draft on hot), FR-11 (on-demand draft), FR-12 (review-and-send gate), FR-14 (in-app notification). FR-5 (read-only boundary) and FR-13 (email-only/WhatsApp deferred) captured as explicit scope notes within the relevant stories rather than as standalone stories.
- [ ] Each story follows INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- [ ] Each story includes Given/When/Then acceptance criteria
- [ ] Map the persona to each story explicitly
