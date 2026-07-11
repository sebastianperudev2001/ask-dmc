# Deployment Architecture — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

---

## Diagrama de despliegue

```
                              Internet (visitante anónimo del chat widget)
                                        │
                                        │  WSS (TLS, sin auth — SECURITY-08 excepción documentada)
                                        ▼
                    ┌───────────────────────────────────────────┐
                    │  Azure Container Apps Environment (East US)│
                    │  ┌───────────────────────────────────────┐ │
                    │  │ agent-service (Container App)         │ │
                    │  │  - min_replicas=1, max_replicas=3     │ │
                    │  │  - Managed Identity (system-assigned) │ │
                    │  │  - WebSocketConnectionHandler          │ │
                    │  │  - RecommendationOrchestrator          │ │
                    │  └───────────────────────────────────────┘ │
                    │         │ IP saliente estática (NAT)        │
                    └─────────┼───────────────────────────────────┘
                              │
              ┌───────────────┼────────────────────────┬─────────────────────┐
              ▼               ▼                        ▼                     ▼
   ┌─────────────────┐ ┌──────────────────┐  ┌──────────────────────┐ ┌──────────────┐
   │ Postgres Flexible│ │ Azure OpenAI      │  │ Azure AI Foundry      │ │ Key Vault    │
   │ Server (B1ms)    │ │ text-embedding-3- │  │ Persistent Agent      │ │ (secrets)    │
   │ + pgvector        │ │ small (Standard)  │  │ gpt-5.4-nano           │ │              │
   │ Firewall: solo IP │ │ Managed Identity  │  │ Managed Identity      │ │ Managed      │
   │ saliente del App  │ │ auth              │  │ auth                  │ │ Identity auth│
   └─────────────────┘ └──────────────────┘  └──────────────────────┘ └──────────────┘
                              │
                              ▼
                    ┌─────────────────────────────┐
                    │ Log Analytics Workspace       │
                    │ (Azure Monitor, retención 90d)│
                    └─────────────────────────────┘
```

## Flujo de despliegue (Terraform)

1. `terraform init` / `terraform plan` / `terraform apply` sobre el resource group único `rg-dmc-agent-service`.
2. Orden de creación (dependencias): Log Analytics Workspace → Container Apps Environment → Key Vault → Postgres Flexible Server (+ firewall rule, requiere conocer la IP saliente del Container Apps Environment ya creado) → Azure OpenAI (Cognitive Account + deployment) → Azure AI Foundry project/Persistent Agent → Container App (con Managed Identity y las `role_assignment` hacia los recursos anteriores) → firewall rule final de Postgres apuntando a la IP saliente real del Container App.
3. Imagen del contenedor (`agent-service`): build vía CI (fuera de alcance de este documento — se detalla en Build and Test) y push a Azure Container Registry (ACR) — el Container App referencia la imagen desde ACR con Managed Identity con permiso `AcrPull`.
4. Variables/secrets inyectados vía Container Apps secrets (referenciando Key Vault): connection string de Postgres (si no se usa Azure AD auth nativo de Flexible Server), endpoint de Azure OpenAI/Foundry (no son secretos per se, pero se centralizan igual para consistencia).

## Ambiente

Un solo ambiente (prod/demo), un solo resource group — decisión explícita del usuario, consistente con el alcance best-effort de este incremento. No hay pipeline de promoción dev→staging→prod en este incremento; se detalla en Build and Test cómo se ejecuta el despliegue (manual vía `terraform apply` o CI simple).

## Fuera de alcance de este documento
- Pipeline de CI/CD completo (build de imagen, tests, apply automático) — se cubre en la fase Build and Test.
- Definición exacta de los archivos `.tf` (se generan en Code Generation, no en este documento de diseño).

---

# Incremento 2 — Sin cambios de topología de despliegue

**Fecha**: 2026-07-06

El diagrama de despliegue de incremento 1 sigue siendo válido sin cambios estructurales. Únicamente se agregan, dentro del mismo `agent-service` (Container App):
- Ruta `/ws/chat` (reemplaza `/ws/recommendation`)
- Ruta `POST /webhooks/mercadopago` (nueva, HTTP — **no expuesta públicamente en este incremento**, se prueba con un script de simulación local contra el mismo proceso corriendo en `localhost`)
- Llamadas salientes nuevas hacia `api.mercadopago.com` (Orders/Preferences, `GET /v1/payments/{id}`) — mismo patrón saliente que ya existe hacia Azure OpenAI/Foundry

Ningún recurso Terraform nuevo se agrega al resource group `rg-dmc-agent-service` más allá de: 2 secrets nuevos en el Key Vault ya existente y la migración de Postgres (tablas, no servidor). El estado de "Terraform sin aplicar" (`infra/agent-service/*.tf`) se mantiene igual que en incremento 1 — este incremento tampoco se despliega a Azure real, se verifica en local (decisión ya tomada en Requirements Analysis).

---

# Incremento 3 — Un recurso nuevo (Azure Communication Services), resto sin cambios de topología

**Fecha**: 2026-07-11

A diferencia de incremento 2, este sí agrega un recurso Azure genuinamente nuevo al resource group `rg-dmc-agent-service`: Azure Communication Services (Email), con dominio administrado por Azure (ver `infrastructure-design.md` Sección 12). Dentro del mismo `agent-service` (Container App):
- Rutas `GET /leads` y `/ws/leads` (nuevas, mismo proceso FastAPI, mismo ingress)
- Llamadas salientes nuevas hacia Azure Communication Services (envío de email)
- `max_replicas` baja de 3 a 1 — restricción dura, no solo económica (Sección 13 de `infrastructure-design.md`)

El estado de "Terraform sin aplicar" se mantiene: los recursos de ACS están definidos en `main.tf` pero no creados en Azure real — este incremento tampoco se despliega, se verifica en local (mismo alcance que incrementos 1 y 2, decisión ya tomada en Requirements Analysis y reafirmada aquí).
