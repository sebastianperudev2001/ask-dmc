# User Stories — BackOffice: Scope Clarification

## Why this file exists
Question 2 of the story plan asked what the BackOffice view is *for* (business goal), but your answer described two new capabilities that go well beyond the approved `backoffice-requirements.md` (FR-1..FR-8, explicitly **read-only**, no outbound messaging, no notifications):

1. **An automated outreach agent** — drafts and sends personalized WhatsApp/email messages using data collected during the lead's conversation.
2. **Staff notifications** when a new lead is created and needs attention.

Both are real, valuable features — but they're a different size of work than the kanban board (new external integrations: WhatsApp Business API and/or an email-sending service, a new drafting agent, a notification/alerting mechanism). This project has a precedent for deliberately deferring exactly this kind of thing: DIV-12 already deferred human-escalation notifications in `agent-service` incremento 2 for the same reason (no channel decided yet). I don't want to silently fold a scope this size into the current "read-only board" stories without your explicit call.

### Clarification Question 1 — Scope for THIS increment
Should the outreach agent (drafting/sending WhatsApp/email) and lead-creation notifications be built as part of **this** BackOffice increment, or split off as a **separate, future increment** (documented now as a roadmap item, same pattern as GitHub issue #18 for auth)?

A) Split off — keep this increment exactly as scoped in `backoffice-requirements.md` (read-only board + detail popup, no messaging/notifications). Track the outreach agent + notifications as a new GitHub issue for a future increment.
B) Include lead-creation **notifications** now (staff gets alerted when a hot/new lead appears), but split off the outreach/messaging agent (WhatsApp/email drafting) as future work — notifications are much smaller in scope than a full messaging agent.
C) Include everything now — expand this increment's requirements to cover both notifications and the outreach agent.
D) Other (please describe after [Answer]: tag below)

[Answer]: C

### Clarification Question 2 — If anything is deferred, how should it be tracked?
(Skip this if you answered C above.)

A) Same as the auth follow-up — create a GitHub issue now describing the deferred scope, like issue #18
B) Just note it in `requirements.md` as a documented future increment (no GitHub issue yet)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Original Question 2, still needs a real answer
Independent of the scope decision above, I still need to know what motivates the persona for the stories **in this increment** (the read-only board). Please pick one:

A) Speed — staff can quickly see which leads are hot and need immediate follow-up, without digging through conversations
B) Prioritization — staff triage their work queue across many leads (which to call first, which to deprioritize)
C) Visibility/oversight — mainly a dashboard for tracking lead volume and quality over time, not a daily action tool
D) Other (please describe after [Answer]: tag below)

[Answer]: B (which at the end of the day is related to speed to reduce manual work and also serve as human in the loop)
