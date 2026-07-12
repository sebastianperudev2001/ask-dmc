# Azure Full-Stack Deployment Design — Terraform

**Date:** 2026-07-12
**Scope:** `infra/agent-service/`, new `infra/frontends/`, `.github/workflows/`, `apps/chat/next.config.ts`, `apps/backoffice/next.config.ts`, `services/agent-service/main.py` (CORS config)
**Approach:** Static Web Apps for both frontends + existing Container App for `agent-service` (unchanged compute shape), no new compute layer

---

## Context

Nothing is deployed today — `infra/agent-service/` already contains real Terraform (Container Apps, Postgres Flexible Server + pgvector, Key Vault, Azure OpenAI, Azure Communication Services, Log Analytics) but a comment in `main.tf` notes it was "written but not applied." `apps/chat` and `apps/backoffice` have no infra, Dockerfile, or CI/CD at all. This design covers deploying the whole stack to Azure for the first time.

## Goals

- Deploy `apps/chat`, `apps/backoffice`, and `agent-service` to Azure using Terraform
- Keep it cheap and simple — this is a demo/course project, not a production system
- Fix two defects in the existing `agent-service` Terraform discovered during this design pass (see below) rather than deferring them
- Repeatable deploys via CI, not one-off manual applies

## Out of scope

- Splitting `agent-service`'s CRUD endpoints into Azure Functions — `LeadBroadcaster`/`LeadEventPublisher` are in-memory, single-process singletons shared between the `/ws/leads` WebSocket and the leads CRUD routes; moving CRUD to Functions would break real-time push unless replaced with Azure SignalR Service or similar, which is a backend architecture change, not an infra one. Revisit only if a real scaling need shows up.
- Provisioning the Azure AI Foundry project/agents — stays on `azd`, per `services/agent-service/docs/provisioning-foundry-azd.md`. Not something `azurerm` supports cleanly yet (see the existing comment in `main.tf` above `FOUNDRY_PROJECT_ENDPOINT`).
- Custom domains — both Static Web Apps and the Container App use their default Azure-issued hostnames.
- Any change to `apps/chat`/`apps/backoffice` UI or `agent-service` business logic beyond what's needed to deploy (CORS config, `next.config.ts` export mode).

---

## Architecture

```
                        ┌─────────────────────────────┐
                        │   Azure Static Web Apps       │
  Browser ─────────────▶│   swa-dmc-chat (eastus2)      │──┐
                        │   swa-dmc-backoffice (eastus2) │  │
                        └─────────────────────────────┘  │
                                                           │  fetch + wss
                                                           │  (CORS)
                        ┌─────────────────────────────┐  │
                        │ Container App: agent-service │◀─┘
                        │ (existing Terraform, mostly   │
                        │  unchanged — 1 environment,   │
                        │  min=max=1 replica)            │
                        └───────┬─────────────┬─────────┘
                                │             │
                    ┌───────────▼──┐   ┌───────▼──────────┐
                    │ Postgres      │   │ Azure OpenAI /    │
                    │ Flexible Srv  │   │ Key Vault / ACS   │
                    │ (+pgvector)   │   │ (existing)        │
                    └───────────────┘   └───────────────────┘
```

`agent-service` keeps doing everything it does today (WebSocket chat, WebSocket leads push, leads/drafts CRUD, Mercado Pago webhook, agent tool-calling) as a single Container App. The only new compute is two Static Web Apps serving statically-exported Next.js builds.

---

## File changes

### New: `infra/frontends/`

Separate Terraform root/state from `infra/agent-service/`, per the existing per-component convention. A Terraform mistake in one never risks the other.

| File | Purpose |
|---|---|
| `main.tf` | `azurerm_resource_group`, `azurerm_static_web_app.chat`, `azurerm_static_web_app.backoffice` (Free tier) |
| `variables.tf` | `location` (default `eastus2` — Static Web Apps Free tier isn't available in `eastus`, where `agent-service` lives), `resource_group_name`, `agent_service_fqdn` (passed in from the agent-service state/output) |
| `outputs.tf` | `chat_default_hostname`, `backoffice_default_hostname`, deployment tokens (sensitive, for the CI workflow to push builds) |

### Modified: `infra/agent-service/`

| File | Change |
|---|---|
| `main.tf` | Add `azurerm_container_registry` (Basic SKU). Fix `DATABASE_URL` env var to actually interpolate the admin password — currently constructed without it (`main.tf:218-220`), which would fail to connect at runtime. Add a Terraform-supplied `ALLOWED_ORIGINS` env var (comma-separated) instead of leaving CORS hardcoded. |
| `variables.tf` | Add `allowed_origins` (list of strings — the two Static Web Apps' hostnames, passed in once `infra/frontends/` exists) |
| `outputs.tf` | Already exposes `container_app_fqdn` — reused by `infra/frontends/` and CI |

### Modified: `services/agent-service/main.py`

| Change | Reason |
|---|---|
| CORS middleware reads `allowed_origins` from an env var (`ALLOWED_ORIGINS`, comma-split) instead of the hardcoded `localhost:3000`/`3001` list | So Terraform can wire in the real Static Web App origins without an app code change per environment. Local dev keeps working via a default of `http://localhost:3000,http://localhost:3001` when the env var is unset. |

### Modified: `apps/chat/next.config.ts`, `apps/backoffice/next.config.ts`

| Change | Reason |
|---|---|
| Add `output: 'export'` | Both apps are pure client-side (no API routes, no SSR data needs — confirmed by reading `package.json`/`app/` — everything happens over WebSocket/fetch to `agent-service` from the browser). Static export is all Static Web Apps needs. |

### New: `.github/workflows/deploy.yml`

Single workflow, triggered on push to `main`:
1. Authenticate to Azure via OIDC federated credentials (`azure/login@v2`, no long-lived service principal secret — matches the least-privilege pattern already used in the existing Terraform, e.g. `SystemAssigned` identities and scoped role assignments)
2. Build + push `agent-service`'s Docker image to the new ACR
3. `terraform apply` in `infra/agent-service/` (image tag as a variable)
4. Build `apps/chat` and `apps/backoffice` (static export) with `NEXT_PUBLIC_WS_URL`/`NEXT_PUBLIC_API_URL` pointing at the Container App's FQDN (available from `infra/agent-service`'s output — this is a real ordering dependency: agent-service must exist/have a stable FQDN before the frontend build)
5. `terraform apply` in `infra/frontends/`, then deploy the static builds using the Static Web Apps deployment token output

Requires a one-time manual setup: an Azure AD App Registration with a federated credential trusting this repo's GitHub Actions OIDC issuer, granted `Contributor` on the resource group(s). Documented as a setup step, not automated by Terraform (chicken-and-egg — Terraform needs auth to exist first).

### Unchanged

- `agent-service`'s domain/ports/adapters code, Postgres schema/migrations, `RecommendationOrchestrator`, tool-calling logic
- `apps/chat` and `apps/backoffice` components, hooks, `ChatService`/`LeadsService` interfaces
- Azure AI Foundry project provisioning (`azd`)
- Key Vault, Azure OpenAI, ACS resources in `infra/agent-service/` (unchanged besides the two fixes above)

---

## Known issues fixed as part of this work

1. **`DATABASE_URL` missing password** (`infra/agent-service/main.tf:218-220`) — the connection string interpolates the FQDN and username but never `var.postgres_admin_password`. As written, `agent-service` cannot connect to Postgres. Fix: reference it via a Key Vault secret (consistent with how `MERCADOPAGO_ACCESS_TOKEN`/`ACS_CONNECTION_STRING` are already wired), not a plain env var, since it's a real credential.
2. **CORS hardcoded to localhost** (`services/agent-service/main.py`) — blocks the Static Web Apps' origins once deployed. Fix: read from `ALLOWED_ORIGINS` env var, Terraform-supplied.

---

## Testing / validation

- `terraform validate` + `terraform plan` for both `infra/agent-service/` and `infra/frontends/` before merging
- Manual smoke test after first apply: load both Static Web App URLs, confirm chat WebSocket connects (`wss://<container-app-fqdn>/ws/chat`) and leads WebSocket connects (`wss://<container-app-fqdn>/ws/leads`), confirm a `GET /health` succeeds from the browser (validates CORS is actually wired, not just present in Terraform)
- No new automated tests — this is infra/deploy plumbing, not application logic. Existing `pytest`/`vitest` suites are unaffected.

---

## Open items for the implementation plan

- Whether `infra/agent-service/` and `infra/frontends/` should be applied via one combined CI job (as drafted above) or two independent jobs with a manual promotion step between them
- Exact Key Vault secret wiring for the Postgres password (new `azurerm_key_vault_secret`, referenced the same way `container_app_to_keyvault` already grants access)
- Whether the GitHub OIDC App Registration setup gets documented as a manual runbook step or scripted with `az cli` in a setup script
