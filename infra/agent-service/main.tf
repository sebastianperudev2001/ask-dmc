terraform {
  required_version = ">= 1.7"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
}

# --- Observability (SECURITY-14: retention >= 90 days) ---

resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-dmc-agent-service"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 90
}

# --- Secrets ---

resource "azurerm_key_vault" "main" {
  name                       = "kv-dmc-agent-svc"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false # demo/best-effort project, not production-grade
}

data "azurerm_client_config" "current" {}

# Incremento 2 — 2 secrets nuevos en el mismo Key Vault (sin recurso nuevo, ver
# infrastructure-design.md Incremento 2). El Container App ya tiene el rol
# "Key Vault Secrets User" (container_app_to_keyvault, abajo).
resource "azurerm_key_vault_secret" "mercadopago_access_token" {
  name         = "mercadopago-access-token"
  value        = var.mercadopago_access_token
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_key_vault_secret" "mercadopago_webhook_secret" {
  name         = "mercadopago-webhook-secret"
  value        = var.mercadopago_webhook_secret
  key_vault_id = azurerm_key_vault.main.id
}

# --- Database (SECURITY-01: encryption at rest/in-transit by default) ---

resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "psql-dmc-agent-service"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = "agentservice_admin"
  administrator_password = var.postgres_admin_password
  storage_mb             = 32768
  sku_name               = "B_Standard_B1ms" # Burstable B1ms — decisión NFR/Infra Design
  zone                   = "1"

  # SECURITY-01
  ssl_enforcement_enabled = true # TLS enforced by default on Flexible Server
}

resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "VECTOR"
}

resource "azurerm_postgresql_flexible_server_database" "agent_service" {
  name      = "agent_service"
  server_id = azurerm_postgresql_flexible_server.main.id
}

# SECURITY-07: firewall restricted to the Container App's outbound IP only — no 0.0.0.0/0.
resource "azurerm_postgresql_flexible_server_firewall_rule" "container_app_outbound" {
  name             = "allow-container-app-outbound"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = azurerm_container_app_environment.main.static_ip_address
  end_ip_address   = azurerm_container_app_environment.main.static_ip_address
}

# --- Azure OpenAI (embeddings) ---

resource "azurerm_cognitive_account" "openai" {
  name                = "aoai-dmc-agent-service"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  kind                = "OpenAI"
  sku_name            = "S0"
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = var.azure_openai_embedding_deployment
  cognitive_account_id = azurerm_cognitive_account.openai.id
  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }
  sku {
    name     = "Standard"
    capacity = 10
  }
}

# --- Compute ---

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-dmc-agent-service"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

resource "azurerm_container_app" "agent_service" {
  name                         = "agent-service"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"

  identity {
    type = "SystemAssigned" # SECURITY-06: least-privilege identity, no static credentials
  }

  # Incremento 2 — secrets resueltos desde Key Vault (PATTERN-11), referenciados por
  # nombre en los `env` con `secret_name` dentro del container, abajo.
  secret {
    name                = "mercadopago-access-token"
    key_vault_secret_id = azurerm_key_vault_secret.mercadopago_access_token.id
    identity            = "System"
  }

  secret {
    name                = "mercadopago-webhook-secret"
    key_vault_secret_id = azurerm_key_vault_secret.mercadopago_webhook_secret.id
    identity            = "System"
  }

  template {
    min_replicas = 1 # PATTERN-04 — protects the <=3s first-delta NFR against cold start
    max_replicas = 3

    container {
      name   = "agent-service"
      image  = var.container_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AGENT_SERVICE_ENV"
        value = "production"
      }
      env {
        name  = "DATABASE_URL"
        value = "postgresql://agentservice_admin@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.agent_service.name}?sslmode=require"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }
      env {
        name  = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        value = var.azure_openai_embedding_deployment
      }
      env {
        name  = "FOUNDRY_AGENT_MODEL_DEPLOYMENT"
        value = var.foundry_agent_model_deployment
      }
      # Incremento 2 — via Key Vault secret references (unlike the plain env vars
      # above, these are real credentials, PATTERN-11/SECURITY-06).
      env {
        name        = "MERCADOPAGO_ACCESS_TOKEN"
        secret_name = "mercadopago-access-token"
      }
      env {
        name        = "MERCADOPAGO_WEBHOOK_SECRET"
        secret_name = "mercadopago-webhook-secret"
      }
      # FOUNDRY_PROJECT_ENDPOINT: set once the AI Foundry project is provisioned.
      # Investigado (2026-07-05): azurerm_ai_foundry/azurerm_ai_foundry_project SÍ existen,
      # pero hoy mapean al modelo hub-based "classic" (ML workspace) — no al proyecto de
      # Foundry no-hub que usa Agent Service/Persistent Agents (que es lo que necesita
      # FoundryPersistentAgentClient). El soporte de azurerm para ese tipo de proyecto está
      # en migración activa (los nombres azurerm_ai_foundry/_project se van a reasignar al
      # tipo nuevo, y el hub-based actual pasará a azurerm_ai_hub/azurerm_ai_project — ver
      # https://github.com/hashicorp/terraform-provider-azurerm/issues/29956, todavía
      # abierto, que pide explícitamente soporte de "network injection" para Agent Service).
      # Hasta que ese trabajo se publique, provisionar el proyecto de Foundry vía `azd`
      # o el portal (ai.azure.com) y wirear el endpoint acá manualmente.
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport         = "auto" # supports WebSocket upgrade
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

# --- Least-privilege role assignments (SECURITY-06) ---

resource "azurerm_role_assignment" "container_app_to_openai" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_container_app.agent_service.identity[0].principal_id
}

resource "azurerm_role_assignment" "container_app_to_keyvault" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_container_app.agent_service.identity[0].principal_id
}
