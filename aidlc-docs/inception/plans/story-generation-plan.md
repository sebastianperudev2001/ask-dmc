# Story Generation Plan — DMC Sales Agent

## Approach Selected
**Epic-Based with Persona mapping** — stories organized as hierarchical epics aligned to system surfaces and the conversational funnel states. Each epic maps clearly to one or more personas.

---

## Personas to Generate
- **P1 — Visitante (Prospective Student)**: arrives on dmc.pe, unsure which program fits them
- **P2 — Equipo Comercial (Sales Admin)**: DMC sales rep who reviews leads in the backoffice
- **P3 — Agente IA (System)**: internal persona representing the agent's own behavioral constraints (guardrails stories)

---

## Questions for the User

Please fill in each `[Answer]:` tag below before approving this plan.

---

### Q1 — Story language
[Answer]: Spanish

### Q2 — Acceptance criteria format
[Answer]: C — Hybrid (BDD Given/When/Then para flujos de funnel y guardrails; bullets para UI simple)

### Q3 — Story granularity for the conversational funnel
[Answer]: C — Un único epic "Flujo Conversacional Completo" con todos los estados del funnel como criterios de aceptación

### Q4 — Backoffice scope for stories
[Answer]: C — Vistas + auth flow + vista de notificación de escalación (leads con `escalated_to_human: true`)

### Q5 — Guardrail stories
[Answer]: C — Ambas: stories standalone bajo un epic "Guardrails" Y referenciadas como criterios de aceptación en las stories del funnel donde aplique

### Q6 — Brochure presigned URL story
[Answer]: A — Story dentro del epic RECOMENDACIÓN: el agente ofrece proactivamente la URL del brochure tras recomendar un programa

---

## Execution Checklist (Part 2 — Generation)

- [x] Step 1: Generate `personas.md` — P1 Visitante, P2 Equipo Comercial, P3 Agente IA
- [x] Step 2: Generate Epic E1 — Chat Widget / Conversational Funnel stories
  - [x] US-01 BIENVENIDA story
  - [x] US-02 IDENTIFICACIÓN story (+ re-identification from localStorage)
  - [x] US-03 CALIFICACIÓN story
  - [x] US-04 RECOMENDACIÓN story (+ brochure URL)
  - [x] US-05 CIERRE story (payment link generation)
  - [x] US-06 ESCALACIÓN story (human handoff + DB flag + SES email)
- [x] Step 3: Generate Epic E2 — Guardrails stories (US-09, US-10, US-11, US-12)
- [x] Step 4: Generate Epic E3 — Backoffice Portal stories (US-13, US-14, US-15, US-16)
- [x] Step 5: Generate Epic E4 — Knowledge Base / Ingestion Pipeline (US-17, US-18)
- [x] Step 6: Verify INVEST criteria for all stories
- [x] Step 7: Map personas to stories
- [x] Step 8: Save `stories.md` and `personas.md` to `aidlc-docs/inception/user-stories/`
- [x] Step 9: Update checkboxes in this plan and `aidlc-state.md`
