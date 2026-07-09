# BackOffice — Lead Qualification View: Clarification Questions

Please answer each question by filling in the letter after `[Answer]:`. Choose "Other" and describe your answer if none of the options fit.

## Question 1 — Where does this view live?
`apps/chat` is today's only frontend app, and it's built for end users (leads chatting with the sales agent). This new view is for internal DMC staff.

A) New standalone app, `apps/backoffice` (separate Next.js project, own deploy)
B) New route/section inside the existing `apps/chat` app (e.g. `/backoffice`), sharing its build
C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Who can access it, and how is that enforced?
`Lead` records contain PII (name, email, motivation, payment info) — access needs some form of gating.

A) Simple shared password/token gate (no per-user accounts) — good enough for a demo/small team
B) Real authentication with individual staff accounts (login form, sessions)
C) No access control for now — trust network/deployment boundary (e.g. only reachable internally)
D) Other (please describe after [Answer]: tag below)

[Answer]: C. For this iteration no auth, create a GitHub ticket for managing the control acccess after this so that only internal users can login into this view.

## Question 3 — Core capability: what does "qualify a lead" mean in this view?
`Lead.score` (hot/warm/cold) is already computed automatically by the agent (BR-17/BR-17b). This view's job could be to just *surface* that, or to let staff *override* it.

A) Read-only: list/filter/inspect leads and their auto-computed score + justification — no edits
B) Read + manual override: staff can change `score` and/or add a qualification note/status themselves
C) Read + full lead management: override score, add notes, mark as contacted/converted/discarded, escalate
D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — List view: what does staff need to see and filter/sort by?

A) Simple table: name, email, score, motivation, created date — filter by score, sort by date
B) Table plus quick stats/summary (counts per score tier, conversion funnel) at the top
C) Table plus search by name/email and filter by score, motivation, and payment status
D) Other (please describe after [Answer]: tag below)

[Answer]: Simple table 3 columns that show name. 1 column for hot, 1 column for warm, 1 column for cold. When i click I should get a popup with specific details of the selected lead.

## Question 5 — Lead detail view: what should staff see when they open one lead?

A) Just the `Lead` record fields (profile summary, motivation, recommended programs, score, payment status)
B) The `Lead` record plus the full conversation transcript (already persisted via `conversation_messages`, incremento 2 Ronda 3)
C) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 6 — Backend support: does an endpoint to list/filter leads already exist?
Checked `services/agent-service/src/ports/lead_repository.py` — today it only has `save`, `find_by_service_session_id`, and `mark_payment_confirmed`. There is no "list all leads" capability yet.

A) Confirmed gap — build a new `list_leads` repository method + a new `GET /leads` (and `GET /leads/{id}`) endpoint in `agent-service` as part of this work
B) There's a different existing service/endpoint I should use instead (please describe after [Answer]: tag below)
C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Data freshness: does the list need to update live, or is manual refresh fine?

A) Manual refresh only (staff reloads the page / clicks a refresh button) — simplest
B) Polling (auto-refresh every N seconds)
C) Real-time via WebSocket (reuses the existing WS infrastructure pattern from `apps/chat`)
D) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 8 — Visual direction: any constraints for the "frontend design" pass?
You asked for this to use frontend design deliberately (distinctive, intentional visual choices) rather than defaults.

A) Should feel consistent with `apps/chat`'s existing visual identity (same design language, staff-facing counterpart)
B) Fully separate identity — a distinct "internal tool" look (denser, more utilitarian, unrelated to the chat app's branding)
C) No strong preference — use good judgment

D) Other (please describe after [Answer]: tag below)

[Answer]: B (let's use frontend design to get an aligned design system according to DMC institute brand guidelines https://dmc.pe/)
