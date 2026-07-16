variable "location" {
  description = "Azure region (East US — see infrastructure-design.md)"
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  type    = string
  default = "rg-dmc-agent-service"
}

variable "container_image" {
  description = "Full ACR image reference for agent-service (e.g. acrdmcsales.azurecr.io/agent-service:v1)"
  type        = string
}

variable "postgres_admin_password" {
  description = "Admin password for Postgres Flexible Server (prefer Azure AD auth where possible)"
  type        = string
  sensitive   = true
}

variable "azure_openai_embedding_deployment" {
  type    = string
  default = "text-embedding-3-small"
}

variable "foundry_agent_model_deployment" {
  type    = string
  default = "gpt-5.4-nano"
}

# --- Incremento 2 — Mercado Pago Checkout Pro ---

variable "mercadopago_access_token" {
  description = "Mercado Pago access token (sandbox/test para este incremento)"
  type        = string
  sensitive   = true
}

variable "mercadopago_webhook_secret" {
  description = "Secreto de verificación de firma del webhook de Mercado Pago"
  type        = string
  sensitive   = true
}

variable "acr_name" {
  description = "Azure Container Registry name (globally unique, lowercase alphanumeric only)"
  type        = string
  default     = "acrdmcagentservice"
}
