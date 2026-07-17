# CI/CD Setup for agent-service (One-Time Manual Steps)

`.github/workflows/deploy-agent-service.yml` authenticates to Azure via OIDC federated
credentials — no client secret is stored anywhere. This has to be set up once, manually,
before the workflow can run: Terraform can't provision this itself, since Terraform needs
Azure auth to already exist (same chicken-and-egg reasoning as
`provisioning-foundry-azd.md`).

At the very first `terraform apply`, the ACR is brand new and empty, so there is no real
`agent-service` image for it to pull yet — set `container_image` to a public placeholder
(e.g. `mcr.microsoft.com/k8se/quickstart:latest`) for that initial apply. It's expected
that the Container App's first revision will just be running this placeholder, not the
real app; don't treat that as a failure. It becomes the actual `agent-service` image
automatically once the first CI push (after completing this runbook's steps) builds and
deploys it.

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
