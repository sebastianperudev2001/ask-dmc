# Provisionar el proyecto de Azure AI Foundry con `azd`

**Por qué este documento existe**: Terraform (`infra/agent-service/*.tf`) no cubre el proyecto/agente de
Azure AI Foundry todavía — el soporte de `azurerm` para el tipo de proyecto no-hub que usa Agent
Service/Persistent Agents sigue en desarrollo activo (ver
[hashicorp/terraform-provider-azurerm#29956](https://github.com/hashicorp/terraform-provider-azurerm/issues/29956),
abierto al momento de escribir esto). Este documento cubre **solo** esa pieza — todo lo demás
(Container Apps, Postgres, Azure OpenAI para embeddings, Key Vault) se sigue provisionando con
Terraform.

**Actualizado tras inspeccionar el template real** (`Azure-Samples/azd-ai-starter-basic`, ya clonado
en `/tmp/dmc-foundry-provision/azd-ai-starter-basic/infra/`) — los valores de abajo salen de leer
`infra/main.bicep`, `infra/main.parameters.json` y `infra/core/ai/ai-project.bicep` directamente,
no de documentación genérica.

---

## 0. Prerequisitos

```bash
az login
azd auth login
```

## 1. Configurar el entorno azd (ya inicializado en `/tmp/dmc-foundry-provision/azd-ai-starter-basic`)

`azd init` ya creó y seleccionó el entorno como `defaultEnvironment` (ver `.azure/config.json`) —
**no** correr `azd env new` de nuevo, falla con "environment already exists". Ir directo a:

```bash
cd /tmp/dmc-foundry-provision/azd-ai-starter-basic
azd env set AZURE_LOCATION eastus       # consistente con infra/agent-service/variables.tf
```

## 2. Configurar los flags específicos para nuestra arquitectura

El template (`infra/main.parameters.json`) soporta estos overrides vía variables de entorno azd —
estos son los que nos importan dado que **ya decidimos no usar Foundry Hosted Agents** (NFR
Requirements: preview, región fija North Central US, WS topado a ~10 min):

```bash
# Ya es el default (false), pero explícito para que quede claro en el historial de azd env:
azd env set ENABLE_HOSTED_AGENTS false

# NO default (default es false = SÍ crea ACR) — nosotros no necesitamos Container Registry
# de Foundry porque nuestro Container App se construye/despliega vía nuestro propio
# pipeline + Terraform, no vía azd:
azd env set AZD_AGENT_SKIP_ACR true
```

## 3. Definir el model deployment (gpt-5.4-nano) directamente en el provisioning

A diferencia de lo que asumí antes de leer el bicep, **no hace falta un paso separado con
`az cognitiveservices account deployment create`** — el template acepta la lista de deployments
como JSON vía `AI_PROJECT_DEPLOYMENTS` (ver `infra/core/ai/ai-project.bicep`, tipo `deploymentsType`):

**Importante — dos errores reales encontrados en esta sesión al armar este valor**:

1. Debe ir en **una sola línea** — `azd` lo sustituye como texto dentro de
   `infra/main.parameters.json` (que es JSON), y un salto de línea literal dentro del valor rompe
   el parseo (`invalid character '\n' in string literal`).
2. Las comillas internas del JSON deben ir **pre-escapadas con `\"`** — `main.parameters.json`
   tiene `"value": "${AI_PROJECT_DEPLOYMENTS=[]}"`; `azd` sustituye el token con el valor crudo
   de la variable de entorno **sin re-escaparlo** para el contexto JSON en el que cae. Si le pasas
   comillas normales (`"name"`), el resultado sustituido es JSON inválido (`invalid character 'n'
   after object key:value pair` — la comilla sin escapar cierra el string antes de tiempo).
   Verificado localmente (`azd env set` + `azd env get-value`, sin tocar la suscripción real):
   con `\"` pre-escapadas, el valor se guarda y se recupera intacto, y la sustitución resultante
   sí es JSON válido (un string que contiene JSON escapado — exactamente lo que espera
   `aiProjectDeploymentsJson`, que Bicep decodifica internamente con `json(...)`).

```bash
azd env set AI_PROJECT_DEPLOYMENTS '[{\"name\":\"gpt-5.4-nano-dmc-bicep\",\"model\":{\"name\":\"gpt-5.4-nano\",\"format\":\"OpenAI\",\"version\":\"2026-03-17\"},\"sku\":{\"name\":\"GlobalStandard\",\"capacity\":10}}]'
```

> **Historial de intentos fallidos (2026-07-05) — por qué terminamos en `gpt-5.4-nano`**:
> 1. `gpt-4o-mini` (`2024-07-18`) → `ServiceModelDeprecating: ... cannot be used for new deployments`.
>    Confirmado con `az cognitiveservices model list --location eastus` (consulta real, solo
>    lectura) que Azure ya cerró esa versión a deployments nuevos aunque siga sirviendo existentes.
> 2. `gpt-4.1-mini` (`2025-04-14`, el reemplazo oficial señalado por `replacementConfig` de
>    `gpt-4o-mini`) → **el mismo error**. La causa real: el catálogo devuelve **dos entradas
>    `GlobalStandard` duplicadas** para ese modelo/versión, con `deprecationDate` distintos
>    (`2026-10-14` y `2027-10-14`) — sin poder distinguir cuál tranche de capacidad elige ARM, a
>    veces resuelve a la que ya está cerrada a deployments nuevos. Mismo problema confirmado
>    también en `gpt-4.1-nano`, así que no era específico de `gpt-4.1-mini`.
> 3. `gpt-5.4-nano` (`2026-03-17`) → **funciona**: verificado que este modelo/versión tiene una
>    **única** entrada `GlobalStandard` (sin duplicados), deprecación hasta `2027-03-18`, sin
>    ambigüedad de SKU.
>
> Si este mismo error vuelve a aparecer con otro modelo, el comando para inspeccionar duplicados de
> SKU (no requiere cuenta ya creada, solo región) es:
> ```bash
> az cognitiveservices model list --location eastus -o json > /tmp/eastus-models.json
> python3 -c "
> import json
> data = json.load(open('/tmp/eastus-models.json'))
> seen = set()
> for m in data:
>     model = m.get('model', {})
>     if model.get('name') == '<nombre-del-modelo>':
>         for s in (model.get('skus') or []):
>             key = (s.get('name'), s.get('deprecationDate'))
>             if key in seen: continue
>             seen.add(key)
>             print(s.get('name'), s.get('deprecationDate'))
> "
> # Si aparece el mismo sku.name dos veces con deprecationDate distintos, hay ambigüedad —
> # mejor buscar un modelo/versión sin duplicados, o desplegar manualmente desde ai.azure.com
> # (el portal sí resuelve la tranche correcta).
> ```

## 4. Provisionar

```bash
azd provision
```

Esto crea (leyendo `infra/main.bicep`): resource group `rg-dmc-agent-service-foundry`, la cuenta de
AI Services + proyecto de Foundry (`ai-project.bicep`), el model deployment de `gpt-5.4-nano` definido
arriba, y monitoreo (App Insights + Log Analytics, `ENABLE_MONITORING` default `true`) — **sin ACR**
gracias al flag del paso 2.

## 5. Obtener los endpoints reales

```bash
azd env get-value FOUNDRY_PROJECT_ENDPOINT
azd env get-value AZURE_OPENAI_ENDPOINT
```

> **Hallazgo al leer `main.bicep`**: la misma cuenta de Foundry expone también un
> `AZURE_OPENAI_ENDPOINT` (AI Services es compatible con la API de Azure OpenAI). Esto significa
> que, en teoría, **podríamos deployar `text-embedding-3-small` en esta MISMA cuenta** en vez de la
> `azurerm_cognitive_account "openai"` separada que ya tenemos en `infra/agent-service/main.tf` —
> simplificaría a un solo recurso de IA. No lo estoy cambiando ahora (implicaría tocar el Terraform
> ya aprobado en Infrastructure Design); lo dejo anotado como posible simplificación futura.

## 6. Configurar `agent-service` con los valores reales

```bash
cd /Users/sebastianchavarry/Documents/ask-dmc/services/agent-service
cp .env.example .env   # si no lo habías creado ya
```

Editar `.env`:
```bash
FOUNDRY_PROJECT_ENDPOINT=<valor de azd env get-value FOUNDRY_PROJECT_ENDPOINT>
FOUNDRY_AGENT_MODEL_DEPLOYMENT=<el "name" que usaste en AI_PROJECT_DEPLOYMENTS, NO model.name>
```

> **Bug real encontrado en esta sesión**: `AI_PROJECT_DEPLOYMENTS` distingue `"name"` (el
> **deployment name**, el identificador que usa la API) de `"model": {"name": ...}` (el
> **modelo subyacente**, solo metadata). Si `FOUNDRY_AGENT_MODEL_DEPLOYMENT` en `.env` usa
> el nombre del modelo (`gpt-5.4-nano`) en vez del deployment name real (en nuestro caso
> `gpt-5.4-nano-dmc-bicep`), la API responde `404 DeploymentNotFound` — **aunque el
> deployment exista y esté `Running`/`Succeeded`** (confundible con la demora normal de
> propagación de un deployment recién creado, pero no es lo mismo). Verificar el nombre
> real con:
> ```bash
> az cognitiveservices account deployment list --name <cuenta> --resource-group <rg> \
>   --query "[].name" -o tsv
> ```

## 7. Verificar la conexión (aislado, sin Postgres)

```bash
cd /Users/sebastianchavarry/Documents/ask-dmc/services/agent-service
uv sync --all-extras   # o: pip install -e ".[dev]" (requiere el [build-system] ya corregido en pyproject.toml)
uv run python -m scripts.manual_agent_check
```

**Verificado end-to-end en esta sesión** (contra la suscripción real del usuario): el agente
respondió correctamente, recomendando un curso basándose únicamente en los datos de
`candidates` de prueba, sin inventar información fuera de esa lista (BR-07).

---

## Limpieza (cuando ya no lo necesites)

```bash
cd /tmp/dmc-foundry-provision/azd-ai-starter-basic
azd down --purge
```

---

## Fuentes

- Lectura directa de `infra/main.bicep`, `infra/main.parameters.json`,
  `infra/core/ai/ai-project.bicep` en `/tmp/dmc-foundry-provision/azd-ai-starter-basic/` (clonado
  por el usuario de [Azure-Samples/azd-ai-starter-basic](https://github.com/Azure-Samples/azd-ai-starter-basic))
- [Quickstart: Deploy your first hosted agent — Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)
- [Use the Microsoft Foundry azd agent extension — Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/extensions/azure-ai-foundry-extension)
