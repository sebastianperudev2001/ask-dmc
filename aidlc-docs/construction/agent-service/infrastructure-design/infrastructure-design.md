# Infrastructure Design — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05
**IaC**: Terraform
**Región**: East US
**Ambiente**: Uno solo (prod/demo), resource group único

---

## 1. Mapeo de componentes lógicos → servicios Azure

| Componente lógico (NFR Design) | Servicio Azure | Notas |
|---|---|---|
| `WebSocketConnectionHandler` + `RecommendationOrchestrator` (runtime) | Azure Container Apps | Contenedor Python (FastAPI), `minReplicas: 1`, `maxReplicas: 3` |
| `CourseRepository` / `ConnectionPool` | Azure Database for PostgreSQL Flexible Server | Tier Burstable B1ms, extensión `pgvector` habilitada |
| `EmbeddingService` | Azure OpenAI (`text-embedding-3-small`) | Deployment tipo Standard (pay-per-token) |
| `RecommendationAgentClient` | Azure AI Foundry — Persistent Agent (`gpt-5.4-nano`) | Creado vía `agent_framework.foundry.FoundryChatClient` + `agent_framework.Agent` (corregido en Build and Test — ver `code/repository-layer-summary.md`), invocado desde Container Apps vía Agent Framework SDK |
| `SecretsProvider` | Azure Key Vault | Referenciado desde Container Apps secrets |
| `StructuredLogger` | Azure Monitor + Log Analytics Workspace | Retención 90 días (SECURITY-14) |
| Identidad de servicio | Managed Identity (system-assigned) en el Container App | Roles least-privilege sobre Azure OpenAI/Foundry y Key Vault (SECURITY-06) |

## 2. Recursos Terraform (resource group único)

```
rg-dmc-agent-service (East US)
├── azurerm_container_app_environment
│   └── azurerm_container_app (agent-service)
│       ├── system-assigned identity
│       ├── min_replicas = 1, max_replicas = 3
│       └── secrets (referencian Key Vault)
├── azurerm_postgresql_flexible_server (Burstable B1ms)
│   ├── azurerm_postgresql_flexible_server_database (courses db)
│   ├── azurerm_postgresql_flexible_server_firewall_rule (IP saliente del Container App)
│   └── extensión pgvector habilitada vía configuration
├── azurerm_cognitive_account (Azure OpenAI) + azurerm_cognitive_deployment (text-embedding-3-small)
├── Azure AI Foundry project/hub + Persistent Agent (gpt-5.4-nano) — recurso Foundry
├── azurerm_key_vault
│   └── secrets: connection string Postgres (si no se usa Azure AD auth), claves si aplica
├── azurerm_log_analytics_workspace (retención 90 días)
└── azurerm_role_assignment (least privilege: Container App identity → Azure OpenAI/Foundry, Key Vault)
```

## 3. Red (SECURITY-07)

- **Postgres Flexible Server**: acceso público habilitado, pero con `azurerm_postgresql_flexible_server_firewall_rule` restringido **únicamente** a la IP saliente estática de Container Apps (obtenida vía NAT Gateway asociado al Container Apps Environment, o vía el rango de IP saliente publicado por el entorno). Ninguna regla `0.0.0.0/0`.
- **Container Apps**: ingress público habilitado solo para el endpoint WebSocket (puerto 443, TLS terminado por Container Apps). Sin necesidad de un Load Balancer/API Gateway adicional — Container Apps Environment ya provee el ingress gestionado.
- **Azure OpenAI/Foundry**: acceso vía llamada saliente autenticada con Managed Identity — no requiere reglas de firewall entrantes adicionales.
- Se descarta VNet + Private Endpoint para Postgres en este incremento (decisión del usuario) — reevaluar si el proyecto pasa de demo a producción con datos sensibles reales.

## 4. Seguridad — mapeo a recursos concretos (cierra los "a implementar en Infra Design" de NFR Requirements)

| Regla | Implementación concreta |
|---|---|
| SECURITY-01 | `azurerm_postgresql_flexible_server`: `storage_mb`/`sku_name` con encryption at-rest por defecto (managed key); `ssl_enforcement_enabled = true`, `minimum_tls_version = "TLS1_2"` |
| SECURITY-06 | `azurerm_role_assignment` scoped al recurso Azure OpenAI/Foundry específico (no a nivel de resource group ni suscripción) para la Managed Identity del Container App |
| SECURITY-07 | Firewall rule de Postgres restringido a la IP saliente de Container Apps (ver Sección 3) |
| SECURITY-14 | `azurerm_log_analytics_workspace` con `retention_in_days = 90` |

## 5. Costos (orden de magnitud, referencial — no es cotización formal)
- Container Apps (1 réplica mínima, tamaño pequeño): costo base bajo, facturación por vCPU-segundo/GiB-segundo.
- Postgres Flexible Server Burstable B1ms: el tier más económico de Flexible Server.
- Azure OpenAI: pay-per-token (`text-embedding-3-small` + `gpt-5.4-nano`), ambos entre los modelos más económicos del catálogo — costo dominado por volumen de uso, bajo en fase demo.
- Sin costos de VNet/Private Endpoint/NAT Gateway dedicado (se usa el NAT compartido del Container Apps Environment para la IP saliente).

---

# Incremento 2 — Chat conversacional + tool-calling + pago (Mercado Pago)

**Fecha**: 2026-07-06
**Nota**: sin recursos de cómputo/red nuevos — se reutiliza el mismo Container App, Postgres y Key Vault ya diseñados en incremento 1. Terraform sigue sin aplicarse (mismo estado que incremento 1 — despliegue real fuera de alcance).

## 6. Mapeo de componentes lógicos nuevos → recursos Azure (sin recursos nuevos)

| Componente lógico (NFR Design, Incremento 2) | Servicio Azure | Notas |
|---|---|---|
| `ChatWebSocketHandler` / `ChatOrchestrator` | Azure Container Apps (mismo Container App) | Nueva ruta `/ws/chat` reemplaza `/ws/recommendation` en el mismo proceso FastAPI |
| `WebhookHandler` | Azure Container Apps (misma app) | Nueva ruta HTTP `POST /webhooks/mercadopago` — **sin exposición pública real en este incremento** (NFR Requirements/Design); alcanzable solo dentro del mismo entorno local para el script de simulación |
| `ConversationSessionStore` | Azure AI Foundry — Agent Memory (mismo recurso Persistent Agent) | Usa `Agent.create_session`/`get_session` del SDK ya integrado — sin recurso de infraestructura adicional, es una capacidad del mismo Foundry Persistent Agent |
| `LeadRepository` | Azure Database for PostgreSQL Flexible Server (mismo servidor, misma base) | Nueva migración: tablas `leads`, `conversation_sessions` — no requiere un servidor Postgres nuevo |
| `MercadoPagoPaymentClient` | N/A (SaaS externo) | Llamadas HTTPS salientes a la API de Mercado Pago — no requiere recurso Azure propio; sale por el mismo NAT del Container Apps Environment |
| `SignatureVerifier` / secretos de Mercado Pago | Azure Key Vault (mismo Key Vault) | 2 secrets nuevos: access token de Mercado Pago (sandbox) y secreto de verificación de firma del webhook — agregados al Key Vault ya existente, sin nuevo recurso |

## 7. Migración Postgres — Incremento 2
Nueva migración (ej. `migrations/002_create_leads_and_sessions.sql`) que agrega `leads` y `conversation_sessions` (domain-entities.md) al mismo servidor/base ya usado para `courses` — sin nuevo servidor Flexible Server.

## 8. Red — sin cambios respecto a incremento 1
- La nueva ruta `/webhooks/mercadopago` vive en el mismo Container App, mismo ingress ya configurado — no se abre ningún puerto o regla de firewall adicional, y **no se expone públicamente** en este incremento (decisión ya tomada en NFR Requirements: se prueba con simulación local, no con tráfico real de Mercado Pago).
- Llamadas salientes a la API de Mercado Pago (crear preferencia, `GET /v1/payments/{id}`) usan el mismo NAT saliente del Container Apps Environment ya existente — sin regla de firewall adicional (es tráfico saliente HTTPS estándar).

## 9. Seguridad — mapeo a recursos concretos (Incremento 2)

| Regla / Patrón | Implementación concreta |
|---|---|
| PATTERN-17 (firma HMAC) | Secreto de verificación almacenado en el `azurerm_key_vault` ya existente, referenciado como Container Apps secret (mismo mecanismo que la connection string de Postgres en incremento 1) |
| PATTERN-14 (retry Mercado Pago) | Mismo `RetryPolicy` component (código, no infraestructura) — sin cambios de infraestructura |
| SECURITY-06 (least privilege) | El acceso a los 2 secrets nuevos de Key Vault se otorga a la misma Managed Identity del Container App ya existente, sin ampliar su alcance más allá de Key Vault (ya tenía ese rol) |

## 10. Costos — incremental (Incremento 2)
- Sin costo de infraestructura nuevo (mismo Container App/Postgres/Key Vault). Costo adicional: llamadas a la API de Mercado Pago (sandbox, sin costo real) y el volumen extra de tokens del LLM por la conversación más larga (tool-calling) — mismo modelo económico (`gpt-5.4-nano`) ya elegido.
