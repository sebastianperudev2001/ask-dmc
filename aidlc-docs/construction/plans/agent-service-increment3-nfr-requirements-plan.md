# NFR Requirements Plan — agent-service, Incremento 3

**Date**: 2026-07-11
**Based on**: `aidlc-docs/construction/agent-service/functional-design/{business-logic-model,business-rules,domain-entities}.md` (Incremento 3 sections)

---

## Mandatory Artifacts

- [ ] `aidlc-docs/construction/agent-service/nfr-requirements/nfr-requirements.md` — append "Incremento 3" section (continuing from Sección 13 / Incremento 2)
- [ ] `aidlc-docs/construction/agent-service/nfr-requirements/tech-stack-decisions.md` — append "Incremento 3" section

---

## Categories Evaluated, Not Asked (with justification)

- **Availability**: No new disaster-recovery/failover concern beyond what Incremento 1/2 already accepted (demo-scale, no HA requirement).
- **Usability**: This unit is backend-only (`apps/backoffice`'s UX is its own unit's concern, deferred).
- **Maintainability**: NFR-3 already mandates reusing existing patterns (port/adapter, FastAPI routing, WS handling) — confirmed in Application Design and Functional Design, not newly ambiguous here.

---

## Questions

### Question 1 — Tech Stack Selection: email provider (NFR-5, deferred from Requirements Analysis)
Which provider should `EmailSender` be implemented against?

A) **Azure Communication Services (Email)** — same cloud as the rest of `agent-service`, no new vendor account, fits NFR-3's preference for reusing the existing Azure-centric stack
B) **SendGrid (Twilio)** — widely used, generous free tier, but a new vendor/account outside Azure
C) **SMTP via an existing personal/Gmail-style account** — fastest to wire up for a demo, but not production-grade and easy to hit sending limits
D) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2 — Security: should real outbound email be restricted to a safelist for this increment?
The outreach agent will send **real** emails to whatever address is in `Lead.email`. Unlike Mercado Pago (sandbox mode, no real charges possible), a real email provider sends a real email to a real inbox the moment credentials exist.

A) Restrict sending to an env-configured safelist of allowed recipient addresses for this increment — prevents accidentally emailing a real prospect's inbox before this is production-ready, while still letting the user test with their own address(es)
B) Fully open — send to whatever `Lead.email` contains, no restriction; rely on not having real provider credentials wired up yet as the actual safety net (same posture as Mercado Pago's "built but possibly untested without credentials" precedent)
C) Other (please describe after [Answer]: tag below)

[Answer]: B

### Question 3 — Reliability: should `send_draft` guard against a duplicate/double-click send?
A) Yes — `send_draft` only proceeds if `status == "pending"` at the moment of an atomic DB check-and-set; a second concurrent/duplicate call is a no-op (returns the already-sent draft) instead of sending a second email
B) No extra guard — rely on staff not double-clicking; acceptable risk at this demo scale
C) Other (please describe after [Answer]: tag below)

[Answer]: A (this is a UI design thing while is pending show a loading state in the UI like a loder so that they cannot press the same button again)

### Question 4 — Scalability: single-instance constraint for in-process pub/sub
`LeadEventPublisher`/`LeadBroadcaster` (Application Design, confirmed in Functional Design) are in-process — this only works correctly if `agent-service` runs as a single instance. An event published on one Container Apps replica never reaches a WebSocket client connected to a different replica.

A) Document this as an explicit hard constraint: `agent-service` must stay at min=max=1 replica for `/ws/leads` to behave correctly — consistent with the "min 1 réplica" decision already made in Incremento 1's NFR Design. Scaling out is explicitly out of scope until an external pub/sub is introduced.
B) Not worth calling out as a hard constraint at this stage
C) Other (please describe after [Answer]: tag below)

[Answer]:  A

### Question 5 — Performance: latency target for on-demand draft generation
The auto-trigger is fire-and-forget (BR-24, no user-facing latency concern), but the on-demand trigger (FR-11) is synchronous from the staff's point of view — they click "Generate draft" and wait for the agentic tool-calling call to finish.

A) No explicit SLA — best-effort, consistent with the rest of the conversational flow (Incremento 2's stance on the chat turn itself)
B) Yes — set an explicit target (e.g. ≤10s) since staff are actively waiting on this one, unlike the auto-trigger path
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Follow-up Question (2026-07-11)

### Follow-up 1 — Question 3: does the backend still need an atomic guard, or is this UI-only?
You picked A but reframed the mechanism as a UI loading state (button disabled while pending) rather than a backend atomic check-and-set. Those aren't mutually exclusive — a network retry or a second browser tab could still fire a duplicate `send_draft` call even with the button disabled client-side. Which should this design actually implement?

A) **Both** — frontend shows a loading state (disables the button) *and* the backend still guards with an atomic `UPDATE ... WHERE status = 'pending'` check (near-zero extra cost, same defense-in-depth spirit as BR-20's payment re-verification) — the UI loading state is the primary UX mechanism, the backend check is the correctness backstop
B) **UI-only** — no backend atomic check; `send_draft` doesn't verify `status` before acting, entirely relies on the frontend disabling the button
C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

*(After answers are provided, this plan will be reviewed for ambiguities/contradictions before generating the NFR requirements artifacts.)*
