# Requirements Document — DMC Sales Agent

**Versión**: 1.1
**Fecha**: 2026-04-28
**Origen**: PRD v1.1 + sesión de clarificación de requerimientos + amendment round 1
**Estado**: Aprobado pendiente

---

## 1. Intent Analysis

| Campo | Valor |
|---|---|
| **Solicitud** | Initializar proyecto: AI Sales Agent para DMC Institute |
| **Tipo** | New Project (Greenfield) |
| **Scope** | Cross-system — widget chat + backoffice + AWS cloud services + agente IA |
| **Complejidad** | Complex — múltiples superficies, agente IA con Strands SDK en AgentCore Runtime, vector DB, pagos |
| **Profundidad** | Comprehensive |

---

## 2. Contexto del Negocio

El equipo comercial de DMC Institute atiende consultas repetitivas via WhatsApp sobre qué curso tomar, costos y requisitos de ingreso. El visitante en dmc.pe cae en un funnel pasivo (formulario → esperar llamada), generando fricción y pérdida de leads calificados.

**Objetivo**: Un agente conversacional que:
- Oriente al visitante 24/7 con información fundamentada en los brochures oficiales
- Califique el lead de forma conversacional (no mediante formulario)
- Cierre la venta generando un link de pago via Mercado Pago
- Persista el lead estructurado en DynamoDB para gestión comercial via backoffice

---

## 3. Superficies del Sistema

| Superficie | Descripción |
|---|---|
| **A — Chat Widget** | Popup flotante embebible. Para el demo, corre como página standalone. Agente conversa, recomienda, califica y genera link de pago. |
| **B — Backoffice Portal** | SPA `/admin/*` del mismo proyecto Next.js. Lista y detalle de leads. Protegida con AWS Cognito. |

---

## 4. Arquitectura Técnica (Decisiones de Alto Nivel)

### 4.1 Stack Confirmado

| Capa | Tecnología | Decisión |
|---|---|---|
| **LLM** | Amazon Bedrock (Claude `claude-sonnet-4-6` via Bedrock) | Acceso via **capa de infraestructura agnóstica** (ver §4.3) |
| **Agente** | Strands SDK | Desplegado en AWS AgentCore Runtime (runtime independiente) |
| **Memoria conversacional** | AWS AgentCore Memory | Via Strands SDK; persiste hilo entre sesiones |
| **Backend** | FastAPI (Python) — monolito thin layer | AWS Lambda + API Gateway WebSocket |
| **Frontend** | Next.js (React) | Vercel |
| **Auth** | AWS Cognito User Pool | Admin creado manualmente en consola; Amplify SDK en frontend |
| **Persistencia de leads** | Amazon DynamoDB | Tabla `dmc-leads`; boto3 desde Lambda |
| **Persistencia de conversaciones** | Amazon DynamoDB | Tabla `dmc-conversations`; separada de leads |
| **Knowledge Base** | Vector DB (ver §4.2) | Pipeline de ingestion PDF → Bedrock Claude → embeddings + metadata |
| **Pagos** | Mercado Pago Checkout API | Modo **sandbox** — access token configurado via env var (placeholder) |
| **Storage PDFs** | Amazon S3 | Bucket `dmc-knowledge-base`; presigned URLs generadas por el agente |
| **Notificaciones** | Amazon SES | Email al equipo comercial cuando lead solicita contacto humano |
| **Sesión browser** | `localStorage` (`window.storage`) | Nombre + email del visitante para re-identificación |

### 4.2 Capa de Infraestructura LLM (Agnóstica)

El acceso al modelo de lenguaje se abstrae detrás de una interfaz de repositorio/infraestructura de modo que el proveedor puede cambiarse sin modificar la lógica de negocio del agente.

```
[Strands Agent / pipeline de ingestion]
        |
        | usa interfaz LLMProvider
        v
[LLMProvider — capa de infraestructura]
    |-- BedrockLLMProvider (implementación activa)
    |      └── boto3 → Amazon Bedrock → Claude claude-sonnet-4-6
    |-- (futuro: AnthropicLLMProvider, OpenAILLMProvider, etc.)
```

**Regla**: ningún módulo fuera de la capa de infraestructura importa directamente `boto3.client("bedrock-runtime")` ni la API de Anthropic. Toda invocación al LLM pasa por la interfaz `LLMProvider`.

---

### 4.3 Knowledge Base — Pipeline de Ingestion

**Decisión**: No RAG tradicional (embeddings de chunks crudos de PDF). En su lugar:

```
PDF en S3
    |
    | Script de ingestion
    v
Claude (extractor LLM)
    |
    | Estructura cada sección del brochure según schema fijo:
    | Presentación, Sobre este diploma, Cómo impulsamos tu carrera,
    | Por qué estudiar, Objetivo, A quién está dirigido, Requisitos,
    | Herramientas, Malla curricular, Propuesta de capacitación,
    | Certificación, Docentes
    v
JSON estructurado por sección
    |
    | Embeddings por sección (texto enriquecido)
    v
Vector DB (con metadata: course_name, section_type, keywords)
    |
    | Strands Tool: search_courses(query, perfil_usuario)
    v
Chunks relevantes → contexto del agente
```

**Vector DB**: tecnología específica a definir en NFR Design (candidatos: Amazon OpenSearch Serverless, pgvector en RDS, o Bedrock Knowledge Base con metadata filtering).

### 4.4 Arquitectura del Sistema

```
[Visitante — Demo Page]
        |
        | (1) abre chat, WebSocket $connect
        v
[API Gateway — WebSocket API]
        |
        | (2) routeKey: $default → Lambda handler
        v
[FastAPI en AWS Lambda]  <-- thin layer
    |-- (3) Valida/enruta mensaje
    |-- (4) Invoca Strands Agent en AgentCore Runtime
    |-- (7) DynamoDB: persiste lead al cierre
    |-- (8) Mercado Pago API: genera link de pago (sandbox)
    |-- (9) SES: email al equipo si lead solicita humano
        |
        | (4) invoke
        v
[Strands Agent — AgentCore Runtime]
    |-- Tool: search_courses() → consulta Vector DB
    |-- Tool: qualify_lead() → calcula score y motivación
    |-- Tool: generate_payment_link() → llama Lambda → Mercado Pago
    |-- Tool: get_brochure_url(course) → presigned URL de S3
    |-- LLMProvider (Bedrock) → Claude claude-sonnet-4-6
    |-- AgentCore Memory → historial de conversación
        |
        | (5) respuesta en streaming
        v
[Lambda → API Gateway WebSocket → Next.js Widget → Usuario]

[Equipo DMC — Backoffice]
        |
        | (1) login → AWS Cognito JWT
        v
[Next.js /admin — Vercel]
        |
        | (2) GET /api/leads (REST)
        v
[Lambda → DynamoDB → lista/detalle leads]
```

---

## 5. Requerimientos Funcionales

### 5.1 Chat Widget (Superficie A)

#### RF-01: Flujo conversacional completo
El agente debe ejecutar el flujo completo:
```
BIENVENIDA → IDENTIFICACIÓN → CALIFICACIÓN → RECOMENDACIÓN → CIERRE → FIN
                                                    ↓
                                              ESCALACIÓN (humano)
```

#### RF-02: Bienvenida e identificación del agente como IA
El agente se presenta como asistente de DMC Institute, identifica explícitamente que es IA.

#### RF-03: Re-identificación desde localStorage
Si `localStorage` tiene nombre y email del visitante (de sesión anterior), el agente los confirma brevemente y no los vuelve a solicitar.

#### RF-04: Captura conversacional de datos personales
Si no hay datos en `localStorage`:
- Nombre completo (obligatorio)
- Correo electrónico (obligatorio, formato validado)

Una vez capturados, se persisten en `localStorage`.

#### RF-05: Calificación conversacional (una pregunta a la vez)
El agente recolecta de forma conversacional:
- Perfil actual (ocupación, experiencia técnica)
- Motivación (ver §5.2)
- Objetivo de aprendizaje / rol deseado
- Disponibilidad semanal y presupuesto aproximado
- Urgencia / fecha de inicio deseada

**Restricción**: el agente NO presenta formularios ni hace múltiples preguntas en un mismo turno.

#### RF-06: Detección de motivación
El agente clasifica la motivación del lead en una de 5 categorías:

| Categoría | Señal |
|---|---|
| `growth` | "Quiero avanzar", "cambiar de carrera", "especializarme" |
| `salary` | "Quiero ganar más", "negociar mi sueldo" |
| `company_requirement` | "Mi jefe me pidió", "es obligatorio para mi área" |
| `academic` | "Quiero aprender", "complementar mis estudios" |
| `undefined` | Respuestas vagas → agente profundiza antes de recomendar |

#### RF-07: Recomendación personalizada de programas
Basada en perfil + motivación, recomienda 1–3 programas del catálogo. Personaliza el pitch según la motivación detectada. Puede comparar opciones si el usuario lo solicita.

**Fuente de verdad**: únicamente los brochures cargados en el pipeline de ingestion. El agente no inventa datos.

#### RF-08: Generación de link de Mercado Pago
Cuando el usuario muestra intención de compra, el agente genera un link de pago via Mercado Pago Checkout API (sandbox) y lo envía en el chat.

#### RF-09: Escalación a humano
Si el usuario pide hablar con una persona:
- El agente responde que alguien del equipo se pondrá en contacto con ellos
- El agente NO provee número de teléfono ni WhatsApp directamente
- Se registra el flag `escalated_to_human: true` en el registro del lead en DynamoDB
- Lambda envía un email de notificación al equipo comercial via Amazon SES con: nombre, email y resumen del lead
- La sesión conversacional se cierra

#### RF-10: Persistencia del lead en DynamoDB
Al finalizar la conversación (FIN o ESCALACIÓN), el agente persiste el lead con la estructura definida en §6.

#### RF-11: Streaming de respuestas via WebSocket
Las respuestas del agente se transmiten al widget via WebSocket para habilitar streaming token a token.

### 5.2 Guardrails del Agente

#### RF-12: Anti-alucinación
El agente NO inventa precios, fechas de inicio, descuentos ni condiciones especiales. Si no tiene la información en la knowledge base, responde:
> *"No tengo esa información disponible. Si tienes más preguntas, alguien de nuestro equipo puede ayudarte."*

#### RF-13: Sin promesas no fundamentadas
El agente no ofrece becas, descuentos ni condiciones especiales que no estén en los brochures.

#### RF-17: Sin menciones de competidores
El agente NO menciona ninguna otra empresa, instituto educativo ni plataforma de cursos. NO realiza comparaciones con competidores bajo ninguna circunstancia.

#### RF-18: Scope limitado a ventas
El agente solo ejecuta tareas de recomendación y cierre de ventas. Si el usuario solicita algo fuera de ese scope (ej. ejercicios de código, soporte técnico, tutoría), el agente responde educadamente que su rol es ayudar a encontrar el programa ideal, y ofrece continuar con esa orientación.

### 5.3 Backoffice Portal (Superficie B)

#### RF-14: Autenticación con Cognito
- Login con formulario custom usando Amplify SDK
- JWT token para mantener sesión
- Rutas `/admin/*` protegidas con middleware de verificación de token server-side
- Logout invalida token y redirige a login

#### RF-15: Vista Lista de Leads
Tabla con columnas: Fecha · Nombre · Email · Motivación (badge) · Score (badge de color) · Programa recomendado · Link enviado.
Filtros: score (hot/warm/cold), motivación, rango de fechas.
Clic en fila → detalle.

#### RF-16: Vista Detalle del Lead
- Datos personales (nombre, email, perfil)
- Badge de score con justificación breve
- Badge de motivación con cita textual del usuario
- Resumen ejecutivo de conversación
- Transcripción completa colapsable
- Programa(s) recomendado(s)
- Link de Mercado Pago (si generado)

---

## 6. Estructura de Datos (DynamoDB)

### 6.1 Tabla `dmc-leads`

```json
{
  "id": "uuid",
  "created_at": 1714089600000,
  "name": "string",
  "email": "string",
  "profile_summary": "string",
  "motivation": "growth | salary | company_requirement | academic | undefined",
  "motivation_detail": "string",
  "recommended_programs": ["string"],
  "payment_link_sent": "boolean",
  "mercado_pago_url": "string | null",
  "score": "hot | warm | cold",
  "score_justification": "string",
  "conversation_summary": "string",
  "escalated_to_human": "boolean"
}
```

**Schema DynamoDB — `dmc-leads`:**
- PK: `id` (UUID, String)
- SK: `created_at` (Number — timestamp en milisegundos)
- GSI: `email-index` sobre `email`

### 6.2 Tabla `dmc-conversations`

Almacena los mensajes individuales de cada conversación, separados del lead.

```json
{
  "lead_id": "uuid",
  "timestamp": 1714089600000,
  "role": "agent | user",
  "content": "string"
}
```

**Schema DynamoDB — `dmc-conversations`:**
- PK: `lead_id` (UUID, String)
- SK: `timestamp` (Number — timestamp en milisegundos)
- Permite recuperar la transcripción completa de un lead con `Query` por `lead_id`

---

## 7. Lead Scoring

| Score | Criterio |
|---|---|
| 🔥 **hot** | Pidió link de pago o expresó decisión de compra |
| 🟡 **warm** | Motivación clara + interés, sin decisión de compra |
| 🔵 **cold** | Motivación vaga o solo curiosidad |

**Pesos de señales**:
- Intención de compra: Alto
- Motivación definida (cualquiera de las 4): Alto
- Fit de perfil con programa recomendado: Medio
- Urgencia (quiere empezar pronto): Medio
- Datos completos (nombre + email): Obligatorio

---

## 8. Knowledge Base

### 8.1 Catálogo de Brochures
```
s3://dmc-knowledge-base/brochures/
  power-bi-especializacion.pdf
  diploma-data-analyst.pdf
  machine-learning-especializacion.pdf
  diploma-data-scientist.pdf
  azure-data-engineering.pdf
  diploma-data-engineer.pdf
  n8n-chatbots-especializacion.pdf
  diseno-chatbots-python.pdf
  ia-ejecutivos.pdf
  people-analytics.pdf
  membresia-datapro.pdf
  membresia-ia-developer.pdf
```

**Estado de PDFs**: todos disponibles y listos para subir a S3.

### 8.2 Schema de Secciones por Brochure
Cada brochure se procesa extrayendo estas secciones:
```
presentacion | sobre_este_diploma | como_impulsamos | por_que_estudiar |
objetivo | a_quien_dirigido | requisitos | herramientas | malla_curricular |
propuesta_capacitacion | certificacion | docentes
```

### 8.3 Mapeo Perfil → Brochures Prioritarios

| Perfil | PDFs prioritarios |
|---|---|
| Analista de datos / BI | power-bi, diploma-data-analyst |
| Data Scientist | machine-learning, diploma-data-scientist |
| Data Engineer | azure-data-engineering, diploma-data-engineer |
| IA & Automatización | n8n-chatbots, diseno-chatbots-python |
| Ejecutivo / No técnico | ia-ejecutivos, people-analytics |
| Sin definir / explorador | membresia-datapro, membresia-ia-developer |

---

## 9. Requerimientos No Funcionales (NFR)

### 9.1 Performance
- Primer token de respuesta del agente: ≤ 3 segundos (via streaming WebSocket)
- WebSocket: reconexión automática en caso de desconexión

### 9.2 Disponibilidad
- Demo (proyecto de curso): best-effort; no SLA formal
- AWS App Runner: auto-scaling habilitado

### 9.3 Escalabilidad
- AgentCore Runtime maneja concurrencia del agente
- DynamoDB: on-demand capacity

### 9.4 Seguridad (ver extensión SECURITY — todos los rules son bloqueantes)
- Cognito JWT validado server-side en cada request al backoffice
- CORS restringido a orígenes explícitos (no wildcard en endpoints autenticados)
- Secrets via AWS Secrets Manager o variables de entorno (nunca hardcoded)
- TLS en tránsito para todos los servicios AWS
- S3 bucket `dmc-knowledge-base`: acceso público bloqueado

### 9.5 Testing (ver extensión PBT — full enforcement)
- **Backend** (Python): Pytest + Hypothesis (PBT framework)
- **Cobertura**: unit tests para lógica de negocio (scoring, detección de motivación, herramientas del agente)
- **Evals**: evaluaciones del agente con escenarios de prueba definidos (happy paths A y B del PRD)
- **Guardrails tests**: verificar que el agente no alucina precios ni información fuera de los brochures
- **RAG quality tests**: verificar relevancia de los chunks recuperados por el vector DB
- **Frontend**: sin tests (curso enfocado en IA)

### 9.6 Observabilidad
- FastAPI: structured logging (JSON) con request ID, level, timestamp
- Logs → AWS CloudWatch (via App Runner)
- No PII en logs

---

## 10. Scope MoSCoW

### Must Have — v1 Demo
| # | Feature |
|---|---|
| M1 | Chat widget con flujo completo (identificación → calificación → recomendación → cierre) |
| M2 | Skip de identificación si datos en localStorage |
| M3 | Calificación conversacional, una pregunta a la vez |
| M4 | Detección de motivación (4 categorías + undefined) |
| M5 | Recomendación personalizada según perfil + motivación |
| M6 | Generación de link de pago Mercado Pago (sandbox) |
| M7 | Pipeline de ingestion PDF → Claude → embeddings → vector DB |
| M8 | Strands Agent en AgentCore Runtime con tools: search_courses, qualify_lead, generate_payment_link; acceso al LLM via capa LLMProvider (Bedrock) |
| M9 | AgentCore Memory para historial de conversación |
| M10 | Streaming de respuestas via WebSocket |
| M11 | Persistencia del lead en DynamoDB al finalizar |
| M12 | Backoffice Next.js: lista y detalle de leads |
| M13 | Auth con AWS Cognito (admin@dmc.pe creado manualmente) |
| M14 | Guardrail anti-alucinación (solo responde con info de brochures) |
| M15 | Guardrail de escalación a humano (flag en DB + email SES al equipo) |
| M16 | Guardrail: el agente no menciona competidores ni realiza comparaciones |
| M17 | Guardrail: scope limitado a recomendación y cierre de ventas |

### Should Have
| # | Feature |
|---|---|
| S1 | Resumen ejecutivo generado por el agente al cerrar conversación |
| S2 | Filtros por score y motivación en el backoffice |
| S3 | Badge de motivación con cita textual del usuario |
| S4 | Tool `get_brochure_url(course)`: el agente envía presigned URL de S3 del brochure del programa recomendado |

### Could Have
| # | Feature |
|---|---|
| C1 | Dashboard con métricas agregadas |
| C2 | Notificación al equipo cuando llega un lead Hot |
| C3 | Comparador side-by-side de programas |

### Won't Have
| # | Feature | Razón |
|---|---|---|
| W1 | Integración con CRM real | Fuera de scope |
| W2 | Pago end-to-end | Solo se genera el link |
| W3 | Multi-tenancy | Innecesario |
| W4 | Tests de frontend | Curso enfocado en IA |

---

## 11. User Journeys (Métricas de Éxito)

| Escenario | Criterio |
|---|---|
| Happy path completo | El agente llega al cierre sin romperse |
| Re-identificación | Datos NO se vuelven a pedir si están en localStorage |
| Motivación detectada | Clasificada correctamente en ≥85% de conversaciones de prueba |
| Score correcto | Hot cuando pidió link; Cold cuando solo exploró |
| Link de Mercado Pago | Se genera y envía correctamente |
| Lead en DynamoDB | Todos los campos correctos tras conversación |
| Backoffice | Lista y detalle visibles tras login con Cognito |
| Guardrail activo | El agente no inventa precios al preguntarse por info no cargada |

---

## 12. Configuración y Entorno

### 12.1 AWS Services (cuenta real)
- Amazon DynamoDB (tabla `dmc-leads`)
- Amazon DynamoDB (tabla `dmc-conversations`)
- AWS Cognito User Pool
- Amazon S3 (bucket `dmc-knowledge-base`)
- AWS AgentCore Runtime
- AWS Lambda + API Gateway WebSocket (FastAPI via Mangum adapter)
- Amazon SES (notificaciones al equipo comercial)
- Amazon Bedrock (Claude `claude-sonnet-4-6`)
- Vector DB (TBD en NFR Design)

### 12.2 Variables de Entorno / Secrets
```env
# AWS
AWS_REGION=us-east-1
DYNAMODB_TABLE_LEADS=dmc-leads
DYNAMODB_TABLE_CONVERSATIONS=dmc-conversations
S3_BUCKET_NAME=dmc-knowledge-base
COGNITO_USER_POOL_ID=<valor>
COGNITO_CLIENT_ID=<valor>
AGENTCORE_RUNTIME_ID=<valor>

# Bedrock
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-6-20251001-v1:0

# SES
SES_SALES_EMAIL=ventas@dmc.pe
SES_FROM_EMAIL=noreply@dmc.pe

# Mercado Pago (sandbox — placeholder)
MERCADO_PAGO_ACCESS_TOKEN=<placeholder>

# CORS
ALLOWED_ORIGINS=http://localhost:3000,https://<vercel-domain>
```

### 12.3 Demo Page
- Página standalone de prueba del widget (no se embebe en dmc.pe producción)
- Puede ser una ruta de Next.js (e.g., `/demo`)

---

## 13. Decisiones Diferidas (para NFR Design)

| Decisión | Candidatos | Criterio de selección |
|---|---|---|
| Vector DB | Amazon OpenSearch Serverless, pgvector (RDS), Bedrock KB | Costo, facilidad de setup en AWS, soporte de metadata filtering |
| Ingestion pipeline trigger | Script manual, Lambda S3 trigger | Frecuencia de actualización de brochures |
| Lambda packaging | Docker image vs ZIP + layer | Tamaño de dependencias (Strands SDK, Mangum) |

---

## 14. Extensiones Habilitadas

| Extensión | Estado | Enforcement |
|---|---|---|
| Security Baseline (SECURITY-01 a SECURITY-15) | **ENABLED** | Todas las rules son blocking |
| Property-Based Testing (PBT-01 a PBT-10) | **ENABLED** | Full enforcement — Hypothesis (Python) |
