# BackOffice — Outreach Agent & Notifications: Follow-Up Clarification

You chose to include the outreach agent (personalized WhatsApp/email drafting + sending) and staff notifications in **this** increment (Clarification Q1 = C). Before I fold this into `requirements.md`, a few things need to be pinned down — this is a meaningfully bigger piece of work than the read-only board, and it touches things the codebase doesn't have yet.

## What I checked in the codebase first
- `Lead` (`services/agent-service/src/domain/models.py`) has **no phone number field**, and `collect_profile_data` (the tool that captures lead info during chat) doesn't collect one either — only `name` and `email`. WhatsApp delivery needs a phone number, so this is a real gap, not just a design detail.
- There's project precedent for exactly this kind of open question: **DIV-12** already deferred "notify a human on escalation" in `agent-service` incremento 2, specifically because no notification channel was decided for Azure. The same unresolved question applies here.
- Mercado Pago (payments) is integrated but has never been tested against real sandbox credentials — a similar "integration exists in code, but untested without real credentials" situation may apply to WhatsApp Business API.

## Question 1 — Human-in-the-loop: how much control does staff have before a message goes out?
Your answer mentioned both "reduce manual work" and "human in the loop" — these pull in different directions, so I want the exact mechanism.

A) Agent drafts the message; staff must review and click "Send" in the BackOffice UI (nothing goes out without a human action)
B) Agent drafts and sends automatically; staff is only notified after the fact (can follow up manually if needed, but doesn't gate the send)
C) Agent drafts and sends automatically for lower-stakes cases, but requires staff approval for something specific (please describe the distinction after [Answer]: below)
D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Trigger: when does the outreach agent act?

A) When a lead's score reaches `hot` (the strongest, most actionable signal already computed by BR-17/BR-17b)
B) As soon as any lead is created (first message from a new lead)
C) On-demand — staff clicks a button on a lead's detail popup to generate/send a message, rather than it happening automatically
D) Other (please describe after [Answer]: tag below)

[Answer]: 1) When it's hot it´s automatic, 2) On demand

## Question 3 — Channel scope, given the phone-number gap
WhatsApp requires a phone number, which nothing currently collects.

A) Email only for this increment (already have `Lead.email`); add phone number collection + WhatsApp as a fast-follow once this ships
B) Both channels now — also extend `collect_profile_data` (and the `Lead` model/migration) to capture a phone number as part of this increment
C) Other (please describe after [Answer]: tag below)

[Answer]: A (create a ticket for whatsapp)

## Question 4 — WhatsApp Business API access
Do you already have WhatsApp Business API credentials/access (similar to what Mercado Pago needed), or is this the same situation as payments — build it, but it goes untested without real credentials?

A) I have (or can get) real WhatsApp Business API credentials to test with
B) No credentials yet — build the integration, but expect it to go untested like Mercado Pago (DIV-11/build-and-test-summary.md precedent)
C) Other (please describe after [Answer]: tag below)

[Answer]: B (ticket for this)

## Question 5 — Staff notification channel
Given DIV-12's unresolved "no channel decided" problem, and that BackOffice is a new browser-based surface with real-time WebSocket already planned (FR-6/FR-8):

A) In-app only — a banner/toast on the BackOffice board itself when a new lead needs attention (reuses the WebSocket channel already being built for FR-6, no new external integration)
B) Email notification to staff (needs an email-sending provider — same open question as DIV-12)
C) Both — in-app now, email as a fast-follow
D) Other (please describe after [Answer]: tag below)

[Answer]: A 
