# Infrastructure Design Plan — agent-service, Incremento 3

**Date**: 2026-07-11
**Based on**: `aidlc-docs/construction/agent-service/nfr-design/{nfr-design-patterns,logical-components}.md` (Incremento 3, approved)

---

## Mandatory Artifacts

- [ ] `aidlc-docs/construction/agent-service/infrastructure-design/infrastructure-design.md` — append "Incremento 3" section
- [ ] `aidlc-docs/construction/agent-service/infrastructure-design/deployment-architecture.md` — append "Incremento 3" section (or "sin cambios de topología" if nothing shifts, matching Incremento 2's precedent)
- [ ] No `shared-infrastructure.md` needed — single unit, single resource group, no new shared infra

---

## Categories Evaluated, Not Asked (with justification)

- **Deployment Environment**: Same Azure subscription/resource group (`rg-dmc-agent-service`) as Incremento 1/2 — no new environment.
- **Messaging Infrastructure**: `LeadEventPublisher` is in-process (NFR Design, PATTERN-25 forces single-instance) — no Azure messaging resource (Service Bus/Event Grid) is being introduced.
- **Networking Infrastructure**: `/ws/leads` is a new route on the same existing Container App — no new ingress/load-balancer/API Gateway resource. `apps/backoffice` has no deployment target yet (local `next dev` only, per `backoffice-execution-plan.md`), so no CORS/networking decision is needed for it here.
- **Monitoring Infrastructure**: New metrics (NFR Requirements Sección 21) flow through the same Azure Monitor/Log Analytics Workspace already provisioned — no new observability tooling.
- **Shared Infrastructure**: N/A — single unit, no multi-tenancy concern.

---

## Questions

### Question 1 — Compute Infrastructure: apply the 1-replica constraint to Terraform now?
`infra/agent-service/main.tf` currently has `min_replicas = 1, max_replicas = 3`. PATTERN-25 (NFR Design) requires exactly 1 replica. Should this Terraform file be updated now?

A) Yes — update `main.tf` now (`max_replicas` 3 → 1), written but not applied, same precedent as Incremento 2 (which added 2 new Key Vault secret resources to `main.tf` without running `terraform apply`)
B) No — only document the requirement in `infrastructure-design.md`; leave `main.tf` untouched until the user is ready to actually deploy
C) Other (please describe after [Answer]: tag below)

[Answer]: A (AI default, user asked to skip ahead)

### Question 2 — Storage/Deployment: how should Azure Communication Services (Email) be provisioned?
ACS Email needs both a Communication Services resource and a verified sender domain.

A) **Azure Managed Domain** — Terraform provisions the ACS resource with the Azure-managed domain (auto-verified, no DNS work required, but the sender address looks like `donotreply@<random>.azurecomm.net`) — fastest path to something testable
B) **Custom domain** (e.g. a subdomain of dmc.pe) — Terraform can provision the ACS resource itself, but domain verification (SPF/DKIM/DMARC DNS records) is a manual follow-up step outside Terraform before it's actually usable
C) **Defer entirely** — write the Terraform resource definitions now (per Q1's "written but not applied" precedent), but treat actual creation/domain setup as a manual step for whenever the user is ready to test real sends
D) Other (please describe after [Answer]: tag below)

[Answer]: C (AI default, user asked to skip ahead)

### Question 3 — Storage: when should the `outreach_drafts` migration SQL be written?
A) **Code Generation** — Infrastructure Design only notes that a new migration will be needed (same convention already used for Incremento 1/2's tables); the actual SQL file is written in `services/agent-service/migrations/` during Code Generation
B) Write the migration SQL now, during Infrastructure Design
C) Other (please describe after [Answer]: tag below)

[Answer]: A (AI default, user asked to skip ahead)

---

*(After answers are provided, this plan will be reviewed for ambiguities/contradictions before generating the infrastructure design artifacts.)*
