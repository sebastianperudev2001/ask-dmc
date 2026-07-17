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

# Incremento 3 — secreto para el connection string de Azure Communication Services
# (EmailSender/AzureCommunicationServicesEmailSender, NFR Design PATTERN-21). A
# diferencia de los secretos de Mercado Pago (credenciales externas, vía variable),
# este connection string lo genera el propio recurso ACS provisionado abajo.
resource "azurerm_key_vault_secret" "acs_connection_string" {
  name         = "acs-connection-string"
  value        = azurerm_communication_service.main.primary_connection_string
  key_vault_id = azurerm_key_vault.main.id
}

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

  # SECURITY-01: no configurable `ssl_enforcement_enabled` argument exists on this resource
  # (that attribute belongs to the older, non-Flexible `azurerm_postgresql_server`) — Flexible
  # Server enforces TLS in transit unconditionally, so there is nothing to set here.
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
  scale {
    type     = "Standard"
    capacity = 10
  }
}

# --- Email (Incremento 3 — EmailSender port, NFR Requirements Sección 14) ---
#
# Dominio Azure Managed (auto-verificado, sin trabajo de DNS) — decisión del AI en vez
# del usuario (ver audit.md, Infrastructure Design, Incremento 3: usuario pidió avanzar
# rápido y delegó las 3 preguntas restantes de esta etapa). Un dominio personalizado
# (subdominio de dmc.pe, remitente con marca DMC) queda como mejora manual futura —
# requeriría verificación DNS (SPF/DKIM/DMARC) fuera del alcance de este Terraform.
# Escrito pero no aplicado, mismo criterio que el resto de este archivo.
resource "azurerm_email_communication_service" "main" {
  name                = "ecs-dmc-agent-service"
  resource_group_name = azurerm_resource_group.main.name
  data_location       = "United States"
}

resource "azurerm_email_communication_service_domain" "managed" {
  name              = "AzureManagedDomain"
  email_service_id  = azurerm_email_communication_service.main.id
  domain_management = "AzureManaged"
}

resource "azurerm_communication_service" "main" {
  name                = "acs-dmc-agent-service"
  resource_group_name = azurerm_resource_group.main.name
  data_location       = "United States"

  # Vincula el dominio de email administrado — sintaxis exacta a verificar contra la
  # versión del provider azurerm al momento de aplicar (mismo tipo de nota ya dejada
  # para FOUNDRY_PROJECT_ENDPOINT más abajo: soporte de recursos nuevos de Azure a
  # veces va por delante o por detrás del provider de Terraform).
}

# --- Compute ---

# --- Container Registry (CI pushes here; Container App pulls via managed identity) ---

resource "azurerm_container_registry" "main" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false # SECURITY-06: pull via managed identity, no static credentials
}

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

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = "System"
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

  # Incremento 3
  secret {
    name                = "acs-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.acs_connection_string.id
    identity            = "System"
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.id
    identity            = "System"
  }

  template {
    min_replicas = 1 # PATTERN-04 — protects the <=3s first-delta NFR against cold start
    max_replicas = 1 # Incremento 3, PATTERN-25 — restricción DURA de correctitud, no solo
    # de costo: LeadEventPublisher/LeadBroadcaster son en memoria y de un solo proceso;
    # escalar a >1 réplica rompe /ws/leads (un evento publicado en una réplica nunca
    # llega a un cliente conectado a otra). No cambiar sin introducir un pub/sub externo.

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
        name        = "DATABASE_URL"
        secret_name = "database-url"
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
      # Incremento 3
      env {
        name        = "ACS_CONNECTION_STRING"
        secret_name = "acs-connection-string"
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
    transport        = "auto" # supports WebSocket upgrade
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image] # CI (GitHub Actions) updates the running
    # image via `az containerapp update`; Terraform must not revert it to var.container_image
    # on every apply — the deployed image tag is CI's responsibility, not Terraform's.
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

resource "azurerm_role_assignment" "container_app_to_acr" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.agent_service.identity[0].principal_id
}
