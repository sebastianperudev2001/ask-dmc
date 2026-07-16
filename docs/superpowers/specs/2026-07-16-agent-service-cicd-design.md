# agent-service CI/CD Design — Build, Push, Deploy Container

**Date:** 2026-07-16
**Scope:** `infra/agent-service/`, new `.github/workflows/deploy-agent-service.yml`, new
`services/agent-service/docs/ci-cd-setup.md`
**Approach:** GitHub Actions builds and pushes the `agent-service` Docker image to a new Azure
Container Registry and updates the existing Container App's image via `az containerapp update`.
No `terraform apply` in CI, no frontend deploys.

---

## Context

Nothing is deployed today — `infra/agent-service/main.tf` has real Terraform (Container Apps,
Postgres Flexible Server + pgvector, Key Vault, Azure OpenAI, Azure Communication Services, Log
Analytics) but was "written but not applied." There is no `.github/workflows/` directory and no
Azure Container Registry resource. A broader design
(`docs/superpowers/specs/2026-07-12-azure-terraform-full-stack-deployment-design.md`) covers
deploying `apps/chat` and `apps/backoffice` too, via Static Web Apps — that stays out of scope
here. This design covers only `agent-service`: getting a container built, pushed, and deployed to
Azure on every relevant push to `main`.

The user will run `terraform apply` manually (not from CI) to provision/update infra, including
the changes below. CI is limited to building/pushing the image and pointing the existing Container
App at the new tag.

## Goals

- Add the missing Azure Container Registry to Terraform, with least-privilege pull access for the
  Container App (no admin credentials, no static passwords)
- Fix the `DATABASE_URL` bug in `infra/agent-service/main.tf` (currently missing the Postgres
  password, so the deployed container cannot connect to the database as written)
- A GitHub Actions workflow that builds the Docker image, pushes it to ACR, and updates the
  Container App's revision — triggered by pushes to `main` that touch `agent-service` or its infra
- Authenticate GitHub Actions to Azure via OIDC federated credentials — no long-lived secrets
- Document the one-time manual Azure AD setup as a runbook (mirrors the existing
  `provisioning-foundry-azd.md` pattern for out-of-Terraform setup)

## Out of scope

- `apps/chat` / `apps/backoffice` deploys (Static Web Apps) — covered by the separate 2026-07-12
  design, not touched here
- Running `terraform apply` from CI — the user applies manually; CI only builds/pushes/updates the
  image on infra that already exists
- Any change to `agent-service` application/business logic
- Azure AI Foundry project provisioning — stays on `azd`, unrelated to this container's CI/CD

---

## Architecture

```
GitHub push to main (paths: services/agent-service/**, infra/agent-service/**)
        │
        ▼
GitHub Actions: deploy-agent-service.yml
        │  azure/login@v2 (OIDC, federated credential — no client secret)
        ▼
az acr login  →  docker build  →  docker push
        │  tag: short git SHA
        ▼
ACR: acr-dmc-agent-service (Basic SKU, admin disabled)
        │  AcrPull (Container App's SystemAssigned identity — Terraform-managed)
        │  AcrPush (CI's federated identity — role assignment, one-time manual setup)
        ▼
az containerapp update --image <acr-login-server>/agent-service:<sha>
        │
        ▼
Container App: agent-service (existing, unchanged compute shape — min=max=1 replica)
```

The Container App itself, Postgres, Key Vault, Azure OpenAI, and ACS are unchanged except for the
two fixes below. No new compute layer beyond the registry.

---

## File changes

### Modified: `infra/agent-service/main.tf`

| Change | Reason |
|---|---|
| Add `azurerm_container_registry.main` (Basic SKU, `admin_enabled = false`) | CI needs somewhere to push images; admin credentials are avoided in favor of identity-based access, consistent with the rest of this file (`SystemAssigned` identities, Key Vault secret references via `identity = "System"`) |
| Add `registry { server = azurerm_container_registry.main.login_server, identity = "System" }` block on `azurerm_container_app.agent_service` | Lets the Container App pull from the private registry using its existing managed identity instead of a registry password |
| Add `azurerm_role_assignment.container_app_to_acr` (`AcrPull`, scoped to the registry, principal = Container App's identity) | Least-privilege pull access, same pattern as `container_app_to_openai`/`container_app_to_keyvault` |
| Add `azurerm_key_vault_secret.database_url` (value = full connection string, built in Terraform by interpolating `var.postgres_admin_password` into the existing FQDN/DB-name expression) | Fixes the real bug at the current `DATABASE_URL` env block (main.tf:218-219): the password is never interpolated today, so the deployed container cannot connect to Postgres |
| Change the `DATABASE_URL` `env` block from a plain `value` to `secret_name = "database-url"` | It's a real credential (contains the admin password) — should not be a plain env var, matching how `MERCADOPAGO_ACCESS_TOKEN`/`ACS_CONNECTION_STRING` are already handled |

### Modified: `infra/agent-service/variables.tf`

| Change | Reason |
|---|---|
| Add `variable "acr_name"` (default `"acrdmcagentservice"` — ACR names must be globally unique, lowercase alphanumeric only) | Lets the name be overridden if the default is taken, without editing `main.tf` |

### Modified: `infra/agent-service/outputs.tf`

| Change | Reason |
|---|---|
| Add `output "acr_login_server"` | The GitHub Actions workflow needs this to know where to push/pull |

### New: `.github/workflows/deploy-agent-service.yml`

Triggered on push to `main` with `paths: ['services/agent-service/**', 'infra/agent-service/**', '.github/workflows/deploy-agent-service.yml']`, plus `workflow_dispatch` for manual runs.

Steps:
1. `actions/checkout@v4`
2. `azure/login@v2` using OIDC — `client-id`/`tenant-id`/`subscription-id` come from repository
   **variables** (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` — not secrets, since
   they aren't sensitive under OIDC federation)
3. `az acr login --name <ACR_NAME>` (repository variable)
4. `docker build` the image from `services/agent-service/Dockerfile`, tagged with the short git SHA
   (`${{ github.sha }}` truncated to 7 chars) and `latest`
5. `docker push` both tags to ACR
6. `az containerapp update --name agent-service --resource-group <RESOURCE_GROUP> --image <acr-login-server>/agent-service:<sha>`

Repository variables needed (Settings → Actions → Variables, not Secrets, since none of these are
sensitive once OIDC is configured): `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`ACR_NAME`, `RESOURCE_GROUP` (`rg-dmc-agent-service`).

### New: `services/agent-service/docs/ci-cd-setup.md`

One-time manual runbook (not automated by Terraform — same chicken-and-egg reasoning already
documented for Foundry provisioning): create an Azure AD App Registration, add a federated
credential trusting GitHub's OIDC issuer for `repo:<owner>/<repo>:ref:refs/heads/main`, and grant
it exactly two roles, both scoped as narrowly as possible:
- `AcrPush` on the new Container Registry
- `Container Apps Contributor` (or the most specific built-in role that permits
  `az containerapp update`) scoped to the `agent-service` Container App only — not `Contributor` on
  the resource group

Includes the exact `az ad app create` / `az ad app federated-credential create` / `az role
assignment create` commands, plus which repository variables to set afterward.

### Unchanged

- `agent-service` application code, Postgres schema, everything under `src/`
- `apps/chat`, `apps/backoffice` — no workflow, no infra
- Existing Key Vault secrets (`mercadopago-*`, `acs-connection-string`) and their role assignments
- Container App compute shape (0.5 CPU / 1Gi, min=max=1 replica) — untouched, this design changes
  how the image gets there, not the runtime shape

---

## Testing / validation

- `terraform validate` + `terraform plan` for `infra/agent-service/` before the user applies
  manually (no real Azure credentials in this session, so `apply` is the user's action, not part of
  this work)
- Workflow YAML reviewed for correctness (no live GitHub Actions run possible until the one-time
  Azure AD setup exists and the user pushes to `main`)
- Manual smoke test after first successful workflow run: confirm the new revision is running the
  pushed tag (`az containerapp revision list`), confirm `GET /health` succeeds, confirm the app
  actually connects to Postgres (validates the `DATABASE_URL` fix, not just that Terraform accepted
  it)
- No changes to `agent-service` business logic — existing `pytest` suite is unaffected and not
  re-run as part of this work

---

## Open items for the implementation plan

- Exact built-in Azure role name for `az containerapp update` scoped to a single Container App
  (verify `Container Apps Contributor` is sufficient and doesn't require broader resource-group
  scope) — resolve during implementation, document whatever is chosen in the runbook
- Whether to also tag/push `latest` or only the SHA tag (currently designed to do both, for easy
  manual `docker pull` during debugging)
