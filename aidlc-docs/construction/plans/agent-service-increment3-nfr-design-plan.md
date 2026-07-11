# NFR Design Plan — agent-service, Incremento 3

**Date**: 2026-07-11
**Based on**: `aidlc-docs/construction/agent-service/nfr-requirements/{nfr-requirements,tech-stack-decisions}.md` (Incremento 3 sections, approved)

---

## Mandatory Artifacts

- [ ] `aidlc-docs/construction/agent-service/nfr-design/nfr-design-patterns.md` — append "Incremento 3" section (continuing from PATTERN-20)
- [ ] `aidlc-docs/construction/agent-service/nfr-design/logical-components.md` — append "Incremento 3" section

---

## Categories Evaluated, Not Asked (with justification)

- **Scalability Patterns**: Fully decided in NFR Requirements Sección 17 — hard `min=max=1` replica constraint, no scale-out pattern to design. Documented directly as PATTERN-21, no open question.
- **Performance Patterns**: No SLA set (NFR Requirements Sección 18) — no caching/optimization pattern is being introduced for `list_leads` or draft generation at this scale (consistent with existing `PATTERN-06`'s "no in-memory cache" precedent).
- **Security Patterns**: The two new security-relevant behaviors — validating `Lead.email` before `EmailSender.send` (BR-28) and redacting draft content from logs (NFR Requirements Sección 19) — are already fully specified; documented directly as patterns (mirroring `PATTERN-03`'s fail-safe-defaults precedent), no open question.

---

## Questions

### Question 1 — Resilience Pattern: should `EmailSender.send` get automatic retry-with-backoff?
Two existing precedents point in different directions here. `PATTERN-01`/`PATTERN-14` wrap other external calls (LLM, Mercado Pago) in the existing `RetryPolicy` (retry-with-backoff) before surfacing failure. But in Functional Design, Question 6 explicitly chose **not** to add automatic retry for the outreach LLM call itself (propagate immediately instead) — a deliberate "no extra retry" stance for this new outreach flow.

A) **Consistent with `PATTERN-01`/`PATTERN-14`** — wrap `EmailSender.send` in the existing `RetryPolicy` (retry-with-backoff) before giving up; only after retries are exhausted does the draft stay `pending` and surface to staff (NFR Requirements Sección 16 still holds either way — retries happen first, then the same fallback)
B) **Consistent with Functional Design's stance on the LLM call** — no automatic retry; a single failed attempt immediately leaves the draft `pending` and surfaces the error to staff, who retries manually via the "Send" button
C) Other (please describe after [Answer]: tag below)

[Answer]: A

### Question 2 — Resilience / Logical Components: dead-connection detection for `/ws/leads`
Unlike `/ws/chat` (bidirectional — client sends messages, server streams tokens back), `/ws/leads` is push-only: the server broadcasts snapshots/events, and the client (`WsLeadsClient`) isn't expected to send application messages. How should `LeadBroadcaster` detect and clean up a dead/disconnected client?

A) **Lazy detection** — no active heartbeat; a dead connection is only discovered (and removed from the broadcast set) the next time `LeadBroadcaster.broadcast()` tries to send to it and the send fails. Simple, matches this project's minimal-infra bias — acceptable because reconnects are cheap (`WsLeadsClient` reconnects and gets a fresh snapshot, Story 3 AC) even if cleanup lags briefly.
B) **Active heartbeat/ping-pong** — `LeadBroadcaster` periodically pings connected clients and prunes ones that don't respond, so the connection set stays accurate even during quiet periods with no events to broadcast
C) Other (please describe after [Answer]: tag below)

[Answer]: A
---

*(After answers are provided, this plan will be reviewed for ambiguities/contradictions before generating the NFR design artifacts.)*
