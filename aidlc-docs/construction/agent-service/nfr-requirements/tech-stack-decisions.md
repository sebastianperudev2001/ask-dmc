# Tech Stack Decisions — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

---

## Resumen de arquitectura de hosting

```
Frontend (chat widget, fuera de alcance de esta unidad)
        │  WebSocket (recommendation_request / relax_filters_response)
        ▼
┌───────────────────────────────────────────────────────────┐
│ Azure Container Apps (East US)                            │
│  — Backend Python (FastAPI + WebSocket)                    │
│  — Filtro SQL, relajación con confirmación, embedding      │
│    de perfil, ranking pgvector                              │
│  — Invoca al Persistent Agent de Foundry vía Agent          │
│    Framework SDK (agent.run(..., stream=True))              │
└───────────────────────────────────────────────────────────┘
        │                                   │
        ▼                                   ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│ Azure Database for           │   │ Azure AI Foundry (East US)   │
│ PostgreSQL Flexible Server   │   │  — Persistent Agent           │
│  + pgvector                  │   │    (modelo: gpt-5.4-nano)      │
│  — tabla courses             │   │  — solo compone el texto      │
│  — Azure OpenAI               │   │    final (paso 8)             │
│    text-embedding-3-small    │   └─────────────────────────────┘
└─────────────────────────────┘
```

## Decisiones y alternativas descartadas

### Hosting del backend WS: Azure Container Apps
- **Alternativa descartada — Azure App Service**: sin scale-to-zero, mayor costo base para un proyecto demo.
- **Alternativa descartada — AKS**: sobre-ingeniería operativa para el volumen esperado.
- **Alternativa descartada — Foundry "Hosted Agents" (todo-en-uno)**: investigado y descartado — depende de `invocations_ws`, en **preview**, restringido a la región **North Central US**, con conexiones WS topadas a ~10 minutos. Riesgo de preview y de bloqueo de región no justificado para este incremento. Revisar de nuevo cuando la feature alcance GA.

### Hosting del agente: Azure AI Foundry — Persistent Agent
- Creado vía `agent_framework.foundry.FoundryChatClient` + `agent_framework.Agent` (integración real de Foundry en Agent Framework, verificada en Build and Test — ver `code/repository-layer-summary.md`), invocado desde el backend en Container Apps vía SDK (`agent.run(message, stream=True)`, llamada síncrona que retorna un stream).
- Es el equivalente directo al patrón anterior (`AgentCore Runtime` hosteando el `StrandsAgent`, invocado por `backend-api`).
- Modelo: **gpt-5.4-nano** — costo y latencia bajos; suficiente para redactar un pitch corto basado en `candidates` ya estructurados (no requiere razonamiento complejo ni tool-calling en este incremento).
  - **Alternativa descartada — gpt-4o**: mejor calidad de redacción, pero mayor costo/latencia sin beneficio claro dado que el contenido ya viene estructurado (no hay necesidad de razonamiento profundo).
  - **Actualización (2026-07-05, durante aprovisionamiento real vía azd)**: el modelo originalmente elegido en esta sección (`gpt-4o-mini`) resultó estar cerrado a deployments nuevos en Azure (`ServiceModelDeprecating`, verificado en vivo contra la suscripción real con `az cognitiveservices model list`). Se intentó el reemplazo oficial `gpt-4.1-mini` con el mismo resultado — causa real: el catálogo tenía dos tranches `GlobalStandard` duplicadas con `deprecationDate` distintos para ese modelo/versión, sin forma de elegir la vigente desde el JSON de `azd`. `gpt-5.4-nano` (versión `2026-03-17`) se confirmó sin esa ambigüedad (una sola tranche `GlobalStandard`, deprecación 2027-03-18) y es el que quedó desplegado. Ver `services/agent-service/docs/provisioning-foundry-azd.md` para el detalle completo. No cambia el criterio original (modelo pequeño/económico para composición de texto simple) — solo la versión concreta disponible.

### Base de datos: Azure Database for PostgreSQL Flexible Server + pgvector
- Confirmado en Functional Design tras comparación con Cosmos DB y Azure SQL+AI Search — un solo motor relacional con soporte de vector search suficiente a la escala del catálogo MVP, y con integridad transaccional real para cuando se integren pagos (Mercado Pago/Culqi).
- Extensión `pgvector` habilitada desde el aprovisionamiento inicial (no se difiere, dado que el ranking semántico es requisito del incremento 1, no una mejora futura).
- Índice recomendado sobre `Course.embedding`: HNSW (mejor balance recall/latencia que IVFFlat a la escala esperada).

### Embeddings: Azure OpenAI `text-embedding-3-small`
- 1536 dimensiones — balance costo/calidad estándar para este caso de uso (matching de background profesional + stack deseado contra descripción/malla curricular de cursos).
- Mismo modelo usado tanto para el catálogo (offline, BR-06) como para el `ProfileQuery` (online, por request) — evita desalineación de espacios vectoriales.

### Región: East US
- Elegida sobre Brazil South por mayor disponibilidad de modelos Azure OpenAI y mejor precio; la latencia de red adicional hacia Perú es aceptable dado el objetivo best-effort de ≤3s (requirements.md §9.1) y que este es un proyecto de curso/demo, no un SLA comercial.
- Todos los recursos (Container Apps, Postgres, Foundry) co-localizados en East US para minimizar latencia inter-servicio.

### Backend: Python + FastAPI + Microsoft Agent Framework (Python SDK)
- Consistente con el resto del proyecto (unit-1 y el diseño superseded de unit-2 también eran Python).
- FastAPI provee el servidor WebSocket (ya usado en `poc-multi-agent-demo` como referencia de patrón, según sesión previa).

### Testing: Hypothesis (PBT-09)
- Framework de property-based testing para Python — shrinking automático, generadores custom para `Course`/`RecommendationRequest`, reproducibilidad por seed. Se integra con `pytest`, consistente con `unit-1`.

### Observabilidad: Azure Monitor + Log Analytics Workspace
- Equivalente directo a AWS CloudWatch (ya usado en el resto del proyecto). Retención de logs: 90 días (SECURITY-14).

### Secrets: Azure Key Vault (referenciado desde Container Apps secrets)
- Ninguna credencial (connection string de Postgres, API key de Azure OpenAI/Foundry) hardcodeada — inyectadas como secrets de Container Apps respaldados por Key Vault.

---

## Pendiente conocido (no resuelto en este incremento)
- **Rate limiting (SECURITY-11)**: sin implementar — riesgo aceptado explícitamente por el usuario para este incremento MVP/demo. Candidato natural para una futura vuelta: throttling por IP a nivel de Container Apps o un middleware simple en FastAPI.

---

# Incremento 2 — Chat conversacional + tool-calling + pago

**Fecha**: 2026-07-06

## Proveedor de pago: Mercado Pago Checkout Pro (reemplaza la exploración de Culqi)
- API de Preferencias (`POST /checkout/preferences`) invocada desde el tool `create_payment_link` — retorna `init_point`/`sandbox_init_point` ya hospedado, sin necesidad de página de checkout propia (a diferencia de lo que hubiera requerido Culqi).
- **Alternativa descartada — Culqi**: evaluado en profundidad durante Requirements Analysis/Functional Design (Orders API v2 + checkout propio + webhook), descartado porque requiere una cuenta de negocio formal que el usuario no tiene (ver DIV-11, revertido).
- Webhook (`type=payment`) verificado con firma HMAC (`x-signature`/`x-request-id`) — mecanismo documentado oficialmente por Mercado Pago (a diferencia de Culqi, donde no se encontró documentación pública de firma verificable).

## Secretos nuevos en Key Vault
- Access token de Mercado Pago (sandbox/test para este incremento).
- Secreto de verificación de firma de webhook (provisto por Mercado Pago al configurar la integración).
- Inyectados como secrets de Container Apps respaldados por Key Vault, mismo patrón ya establecido en incremento 1 (`keyvault_secrets.py` adapter ya existe en el código).

## Persistencia: nuevas tablas en el mismo Postgres ya provisionado
- No se agrega ningún motor de base de datos nuevo — `leads` y `conversation_sessions` (domain-entities.md, Incremento 2) viven en la misma instancia Azure Database for PostgreSQL Flexible Server ya usada para `courses` (incremento 1). Requiere una nueva migración (extensión de `migrations/`), no un aprovisionamiento nuevo.

## Testing del webhook: simulación local, sin exposición pública (esta vuelta)
- Decisión explícita del usuario (NFR Requirements): no se usa túnel (`ngrok`) ni se despliega el webhook a Container Apps en este incremento. Se agrega un script de simulación manual (patrón ya establecido con `scripts/manual_ws_check.py`) que firma y envía un payload realista directamente a `localhost`.
- **Alternativas descartadas para este incremento**: túnel temporal (ngrok) y despliegue parcial a Container Apps — ambas viables pero se prefirió no tocar el alcance de despliegue "solo local" ya decidido; quedan como candidatas naturales para cuando se decida una prueba end-to-end real contra Mercado Pago.
