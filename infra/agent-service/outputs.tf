output "container_app_fqdn" {
  value = azurerm_container_app.agent_service.ingress[0].fqdn
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "azure_openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}
