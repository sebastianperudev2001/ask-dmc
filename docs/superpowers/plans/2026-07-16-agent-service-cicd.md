# agent-service CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get `agent-service` building, pushing to an Azure Container Registry, and deploying to
its existing Container App automatically on every relevant push to `main`, via GitHub Actions with
OIDC auth — no long-lived secrets, no `terraform apply` in CI.

**Architecture:** Terraform (`infra/agent-service/main.tf`) gains an Azure Container Registry, a
managed-identity-based pull path for the Container App, and a fix for a real bug (`DATABASE_URL`
never interpolates the Postgres password). A new GitHub Actions workflow builds the Docker image,
pushes it to that registry, and runs `az containerapp update` to roll out the new tag. A one-time
manual runbook documents the Azure AD App Registration + federated credential + role assignments
CI needs — this is a chicken-and-egg step Terraform can't self-provision (Terraform needs auth to
already exist).

**Tech Stack:** Terraform (`azurerm` ~> 3.110), GitHub Actions (`azure/login@v2`, OIDC), Docker,
Azure CLI (`az acr`, `az containerapp`, `az ad`, `az role`).

## Global Constraints

- Scope is `agent-service` only — no changes to `apps/chat`, `apps/backoffice`, or any Static Web
  App infra (per `docs/superpowers/specs/2026-07-16-agent-service-cicd-design.md`, "Out of scope")
- CI never runs `terraform apply` — the user applies Terraform manually; CI only builds/pushes the
  image and updates the Container App's image reference
- Auth to Azure from CI is OIDC federated credentials only — no client secrets, no ACR admin
  credentials (`admin_enabled = false`)
- Container App compute shape stays exactly as-is: 0.5 CPU / 1Gi memory, `min_replicas = 1`,
  `max_replicas = 1` — do not touch `template` sizing
- Workflow triggers only on pushes touching `services/agent-service/**`,
  `infra/agent-service/**`, or the workflow file itself, plus manual `workflow_dispatch`
- Every new/changed secret-bearing value goes through Key Vault + `secret_name`, never a plain
  `env { value = ... }` block (matches the existing `MERCADOPAGO_ACCESS_TOKEN`/
  `ACS_CONNECTION_STRING` pattern already in `main.tf`)

---

### Task 1: Add Azure Container Registry to Terraform

**Files:**
- Modify: `infra/agent-service/main.tf` (new resources, plus edit `azurerm_container_app.agent_service` around line 169-271)
- Modify: `infra/agent-service/variables.tf`
- Modify: `infra/agent-service/outputs.tf`

**Interfaces:**
- Produces: `azurerm_container_registry.main` (used by Task 2's `registry` block is not needed —
  Task 2 is unrelated; used by the GitHub Actions workflow in Task 3 via the `acr_login_server`
  output and the `var.acr_name` value)
- Produces: `output "acr_login_server"` — exact login server hostname (e.g.
  `acrdmcagentservice.azurecr.io`) that Task 3's workflow pushes to

- [ ] **Step 1: Add the `acr_name` variable**

In `infra/agent-service/variables.tf`, append:

```hcl
variable "acr_name" {
  description = "Azure Container Registry name (globally unique, lowercase alphanumeric only)"
  type        = string
  default     = "acrdmcagentservice"
}
```

- [ ] **Step 2: Add the `azurerm_container_registry` resource**

In `infra/agent-service/main.tf`, add a new section right after the `# --- Compute ---` comment
(before `azurerm_container_app_environment.main`, around line 160):

```hcl
# --- Container Registry (CI pushes here; Container App pulls via managed identity) ---

resource "azurerm_container_registry" "main" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false # SECURITY-06: pull via managed identity, no static credentials
}
```

- [ ] **Step 3: Add a `registry` block to the Container App**

In `infra/agent-service/main.tf`, inside `resource "azurerm_container_app" "agent_service"`, add a
`registry` block as a sibling of the existing `identity`/`secret`/`template`/`ingress` blocks.
Place it right after the `identity { ... }` block (currently lines 175-177):

```hcl
  identity {
    type = "SystemAssigned" # SECURITY-06: least-privilege identity, no static credentials
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = "System"
  }
```

- [ ] **Step 4: Add the `AcrPull` role assignment**

In `infra/agent-service/main.tf`, in the `# --- Least-privilege role assignments (SECURITY-06) ---`
section (currently lines 273-286), add:

```hcl
resource "azurerm_role_assignment" "container_app_to_acr" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.agent_service.identity[0].principal_id
}
```

- [ ] **Step 5: Add the `acr_login_server` output**

In `infra/agent-service/outputs.tf`, append:

```hcl
output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}
```

- [ ] **Step 6: Validate the Terraform**

Run:
```bash
cd infra/agent-service
terraform fmt -check
terraform init -backend=false
terraform validate
```
Expected: `terraform fmt -check` prints nothing (already formatted — if it lists a file, run
`terraform fmt` and re-check); `terraform validate` prints `Success! The configuration is valid.`

- [ ] **Step 7: Commit**

```bash
git add infra/agent-service/main.tf infra/agent-service/variables.tf infra/agent-service/outputs.tf
git commit -m "feat(infra): add Azure Container Registry for agent-service CI/CD"
```

---

### Task 2: Fix the `DATABASE_URL` password bug

**Files:**
- Modify: `infra/agent-service/main.tf` (new Key Vault secret near lines 47-67; edit the
  `secret`/`env` blocks inside `azurerm_container_app.agent_service` around lines 179-220)

**Interfaces:**
- Consumes: `azurerm_key_vault.main` (already exists, line 32), `var.postgres_admin_password`
  (already exists, `variables.tf`), `azurerm_postgresql_flexible_server.main.fqdn` and
  `azurerm_postgresql_flexible_server_database.agent_service.name` (already exist)
- Produces: `azurerm_key_vault_secret.database_url` — consumed only within this task (the
  container's `secret`/`env` blocks)

- [ ] **Step 1: Add the `database_url` Key Vault secret**

In `infra/agent-service/main.tf`, right after `azurerm_key_vault_secret.acs_connection_string`
(currently ends at line 67), add:

```hcl
# Incremento 4 — fix: DATABASE_URL previously never interpolated the admin password
# (see main.tf history), so the container could not connect to Postgres. Built here from
# the same FQDN/DB-name expressions the plain env var used, plus the password, and stored
# as a Key Vault secret since it's a real credential (PATTERN-11, same as the two secrets
# above).
resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  value        = "postgresql://agentservice_admin:${var.postgres_admin_password}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.agent_service.name}?sslmode=require"
  key_vault_id = azurerm_key_vault.main.id
}
```

- [ ] **Step 2: Reference it as a container secret**

In `infra/agent-service/main.tf`, inside `azurerm_container_app.agent_service`, add a `secret`
block alongside the existing three (`mercadopago-access-token`, `mercadopago-webhook-secret`,
`acs-connection-string`, currently lines 181-198). Add after the `acs-connection-string` block:

```hcl
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.id
    identity            = "System"
  }
```

- [ ] **Step 3: Change the `DATABASE_URL` env block from a plain value to the secret reference**

In `infra/agent-service/main.tf`, replace the existing block (currently lines 217-220):

```hcl
      env {
        name  = "DATABASE_URL"
        value = "postgresql://agentservice_admin@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.agent_service.name}?sslmode=require"
      }
```

with:

```hcl
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
```

- [ ] **Step 4: Validate the Terraform**

Run:
```bash
cd infra/agent-service
terraform fmt -check
terraform validate
```
Expected: `Success! The configuration is valid.` (no `fmt` diffs)

- [ ] **Step 5: Commit**

```bash
git add infra/agent-service/main.tf
git commit -m "fix(infra): interpolate Postgres password into DATABASE_URL via Key Vault secret"
```

---

### Task 3: GitHub Actions workflow — build, push, deploy

**Files:**
- Create: `.github/workflows/deploy-agent-service.yml`

**Interfaces:**
- Consumes: repository variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
  `ACR_NAME`, `RESOURCE_GROUP` (all set up in Task 4's runbook — the workflow will fail at
  `azure/login` until those exist, which is expected until Task 4 is followed)
- Consumes: `services/agent-service/Dockerfile` (existing, unchanged)

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/deploy-agent-service.yml`:

```yaml
name: Deploy agent-service

on:
  push:
    branches: [main]
    paths:
      - 'services/agent-service/**'
      - 'infra/agent-service/**'
      - '.github/workflows/deploy-agent-service.yml'
  workflow_dispatch: {}

permissions:
  id-token: write
  contents: read

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Azure login (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}

      - name: Log in to ACR
        run: az acr login --name ${{ vars.ACR_NAME }}

      - name: Set image tag
        id: image
        run: echo "tag=$(git rev-parse --short=7 HEAD)" >> "$GITHUB_OUTPUT"

      - name: Build image
        run: |
          docker build \
            -t ${{ vars.ACR_NAME }}.azurecr.io/agent-service:${{ steps.image.outputs.tag }} \
            -t ${{ vars.ACR_NAME }}.azurecr.io/agent-service:latest \
            services/agent-service

      - name: Push image
        run: |
          docker push ${{ vars.ACR_NAME }}.azurecr.io/agent-service:${{ steps.image.outputs.tag }}
          docker push ${{ vars.ACR_NAME }}.azurecr.io/agent-service:latest

      - name: Deploy to Container App
        run: |
          az containerapp update \
            --name agent-service \
            --resource-group ${{ vars.RESOURCE_GROUP }} \
            --image ${{ vars.ACR_NAME }}.azurecr.io/agent-service:${{ steps.image.outputs.tag }}
```

- [ ] **Step 2: Validate YAML syntax**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-agent-service.yml'))" && echo OK
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy-agent-service.yml
git commit -m "feat(ci): add GitHub Actions workflow to build/push/deploy agent-service"
```

---

### Task 4: One-time Azure AD setup runbook

**Files:**
- Create: `services/agent-service/docs/ci-cd-setup.md`

**Interfaces:**
- Produces: documented values for the 5 repository variables Task 3's workflow consumes
  (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `ACR_NAME`, `RESOURCE_GROUP`)

- [ ] **Step 1: Write the runbook**

Create `services/agent-service/docs/ci-cd-setup.md`:

````markdown
# CI/CD Setup for agent-service (One-Time Manual Steps)

`.github/workflows/deploy-agent-service.yml` authenticates to Azure via OIDC federated
credentials — no client secret is stored anywhere. This has to be set up once, manually,
before the workflow can run: Terraform can't provision this itself, since Terraform needs
Azure auth to already exist (same chicken-and-egg reasoning as
`provisioning-foundry-azd.md`).

Run these after `terraform apply` has created the resource group and Container Registry
(so `az acr show` / `az containerapp show` below can resolve).

Replace `<GITHUB_OWNER>/<GITHUB_REPO>` with this repo's `owner/name` (e.g. `you/ask-dmc`).
`<ACR_NAME>` and `<RESOURCE_GROUP>` should match `var.acr_name` (default
`acrdmcagentservice`) and `var.resource_group_name` (default `rg-dmc-agent-service`) from
`infra/agent-service/variables.tf`.

## 1. Create the App Registration

```bash
AZURE_CLIENT_ID=$(az ad app create --display-name "gh-actions-agent-service-deploy" --query appId -o tsv)
echo "$AZURE_CLIENT_ID"
az ad sp create --id "$AZURE_CLIENT_ID"
```

## 2. Add the federated credential (trusts GitHub Actions OIDC for pushes to main)

```bash
az ad app federated-credential create \
  --id "$AZURE_CLIENT_ID" \
  --parameters '{
    "name": "github-actions-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<GITHUB_OWNER>/<GITHUB_REPO>:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

## 3. Grant least-privilege roles

`AcrPush`, scoped only to the registry:

```bash
az role assignment create \
  --assignee "$AZURE_CLIENT_ID" \
  --role AcrPush \
  --scope "$(az acr show --name <ACR_NAME> --query id -o tsv)"
```

`Container Apps Contributor`, scoped only to the `agent-service` Container App (not the
resource group):

```bash
az role assignment create \
  --assignee "$AZURE_CLIENT_ID" \
  --role "Container Apps Contributor" \
  --scope "$(az containerapp show --name agent-service --resource-group <RESOURCE_GROUP> --query id -o tsv)"
```

If `az role assignment create` rejects `"Container Apps Contributor"` as an unknown role
name, run `az role definition list --name "*Container Apps*" -o table` to find the exact
built-in role name for your `az` CLI version and use that instead.

## 4. Set the GitHub repository variables

```bash
gh variable set AZURE_CLIENT_ID --body "$AZURE_CLIENT_ID"
gh variable set AZURE_TENANT_ID --body "$(az account show --query tenantId -o tsv)"
gh variable set AZURE_SUBSCRIPTION_ID --body "$(az account show --query id -o tsv)"
gh variable set ACR_NAME --body "<ACR_NAME>"
gh variable set RESOURCE_GROUP --body "<RESOURCE_GROUP>"
```

## 5. Verify

Push a commit touching `services/agent-service/**` to `main` (or run the workflow manually
via `gh workflow run deploy-agent-service.yml`), then check
`az containerapp revision list --name agent-service --resource-group <RESOURCE_GROUP> -o table`
for a new revision running the pushed image tag.
````

- [ ] **Step 2: Read the doc back and confirm every placeholder is explained**

Confirm `<GITHUB_OWNER>/<GITHUB_REPO>`, `<ACR_NAME>`, and `<RESOURCE_GROUP>` are each defined
in the paragraph above the first code block that uses them (they are, per Step 1) — this
is a documentation runbook, so these are user-supplied values, not implementation gaps.

- [ ] **Step 3: Commit**

```bash
git add services/agent-service/docs/ci-cd-setup.md
git commit -m "docs(agent-service): add one-time Azure AD CI/CD setup runbook"
```

---

## After this plan

The user runs `terraform apply` manually in `infra/agent-service/` to create the ACR and apply
the `DATABASE_URL` fix, then follows Task 4's runbook once to wire up OIDC, then pushes to `main`
(or runs the workflow manually) to confirm the first deploy.
