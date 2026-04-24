# PRD: DMC Sales Agent
## AI Sales Agent para DMC Institute

**Versión:** 1.1  
**Autor:** Sebastian (Curso AI Engineering — DMC Institute)  
**Estado:** Draft  
**Alcance:** Demo / Proyecto de curso  

---

## 1. One-Liner

Un agente conversacional embebido como popup en dmc.pe que orienta al visitante entre el catálogo de cursos, califica el lead según perfil, motivación e intención, y cierra la venta generando un link de pago via Mercado Pago — con un portal de backoffice protegido con Cognito para que el equipo comercial de DMC visualice y gestione los leads persistidos en DynamoDB.

---

## 2. Problema

El equipo comercial de DMC atiende consultas repetitivas vía WhatsApp y formulario de contacto sobre qué curso tomar, cuánto cuesta y qué perfil se necesita. El visitante que llega al sitio no tiene orientación inmediata personalizada y cae en un funnel pasivo (formulario → esperar llamada). Un agente conversacional elimina esa fricción y captura el lead de forma estructurada 24/7.

---

## 3. Alcance del Demo

Dos superficies:

| Superficie | Descripción |
|---|---|
| **A — Chat Widget** | Popup flotante en el sitio de DMC. El agente conversa, recomienda cursos, califica y cierra con link de Mercado Pago. |
| **B — Backoffice Portal** | SPA Next.js protegida con Cognito. Lista de leads con calificación, datos personales y resumen de conversación almacenados en DynamoDB. |

---

## 4. Flujo del Agente (Superficie A)

### 4.1 Estados de la conversación

```
BIENVENIDA → IDENTIFICACIÓN → CALIFICACIÓN → RECOMENDACIÓN → CIERRE → FIN
                                                    ↓
                                              ESCALACIÓN (usuario pide hablar con persona)
```

### 4.2 Pasos detallados

**BIENVENIDA**  
El agente se presenta como asistente de DMC Institute (se identifica como IA) y pregunta cómo puede ayudar.

**IDENTIFICACIÓN** — recuperación o captura de datos personales  
Antes de calificar, el agente verifica si el usuario ya completó sus datos en una sesión anterior (via `window.storage`). Si existen, los confirma brevemente y no los vuelve a pedir. Si no existen, los recolecta conversacionalmente:
- Nombre completo *(obligatorio)*
- Correo electrónico *(obligatorio)*

> Una vez capturados, estos datos se persisten en `window.storage` para no volver a solicitarlos en conversaciones futuras del mismo navegador.

**CALIFICACIÓN** — el agente recolecta conversacionalmente:

| Dimensión | Pregunta orientativa |
|---|---|
| **Perfil actual** | ¿A qué se dedica? ¿Tiene experiencia técnica previa? |
| **Motivación** | ¿Qué lo lleva a buscar esta capacitación? *(ver sección 5.1)* |
| **Objetivo** | ¿Qué quiere aprender / en qué rol quiere trabajar? |
| **Disponibilidad** | ¿Cuánto tiempo semanal tiene? ¿Cuál es su presupuesto aproximado? |
| **Urgencia** | ¿Cuándo quiere empezar? |

> El agente **no** hace un formulario. Extrae estos datos de forma conversacional, haciendo una pregunta a la vez.

**RECOMENDACIÓN**  
Con base en las respuestas, recomienda 1–3 programas del catálogo. Personaliza el pitch según la motivación detectada (ver sección 5.1). Puede comparar opciones si el usuario pregunta. El conocimiento del agente proviene de brochures en PDF almacenados en S3 (ver sección 8).

**CIERRE**  
Cuando el usuario muestra intención de compra ("me interesa", "¿cómo pago?"), el agente genera y envía un link de pago de Mercado Pago para el producto recomendado. Confirma que puede completar la compra ahí y que recibirá más información por correo.

**ESCALACIÓN**  
Si el usuario pide hablar con una persona, el agente da el número de WhatsApp de ventas (`+51 912 322 976`) y cierra la sesión.

**FIN**  
El agente persiste el lead en DynamoDB con todos los datos recolectados, el score y el resumen de conversación.

### 4.3 Guardrails

- El agente **no** inventa precios ni fechas de inicio que no estén en los brochures cargados en S3.
- Si no sabe algo, responde: *"No tengo esa información disponible. Te recomiendo contactar directamente al equipo en +51 912 322 976."*
- No hace promesas de becas, descuentos ni condiciones especiales.

---

## 5. Calificación del Lead (Lead Score)

### 5.1 Dimensión de Motivación

La motivación es una señal de calificación de primer orden: determina el pitch correcto y el nivel de urgencia real del lead.

| Motivación | Señal conversacional | Implicación para el pitch |
|---|---|---|
| 🚀 **Crecimiento profesional** | "Quiero avanzar", "cambiar de carrera", "especializarme" | Énfasis en certificación, empleabilidad, comunidad |
| 💰 **Aumento salarial** | "Quiero ganar más", "mejorar mi sueldo", "negociar" | Énfasis en ROI, salarios del mercado, tiempo al resultado |
| 🏢 **Requerimiento de empresa** | "Mi jefe me pidió", "la empresa lo exige", "es obligatorio" | Énfasis en modalidad flexible, velocidad de completación, facturación corporativa |
| 🎓 **Actualización académica** | "Quiero aprender", "curiosidad", "complementar mis estudios" | Énfasis en calidad del contenido, docentes, metodología |
| ❓ **No definida** | Respuestas vagas o evasivas | Agente profundiza con repregunta antes de recomendar |

### 5.2 Score General

| Dimensión | Señal | Peso |
|---|---|---|
| **Intención de compra** | Preguntó por precio / pidió link de pago | Alto |
| **Motivación definida** | Motivación clara identificada (cualquiera de las 4) | Alto |
| **Fit de perfil** | Perfil alineado al programa recomendado | Medio |
| **Urgencia** | Quiere empezar pronto (este mes / próxima semana) | Medio |
| **Datos completos** | Nombre + correo capturados | Obligatorio |

**Categorías de output:**

| Badge | Categoría | Criterio |
|---|---|---|
| 🔥 **Hot** | Alta intención | Pidió link de pago o expresó decisión de compra |
| 🟡 **Warm** | Interesado | Motivación clara + interés, pero sin decisión de compra todavía |
| 🔵 **Cold** | Exploración | Motivación vaga o solo curiosidad, sin intención clara |

---

## 6. Estructura del Lead

```json
{
  "id": "uuid",
  "created_at": "ISO-8601 timestamp",
  "name": "string",
  "email": "string",
  "profile_summary": "string",
  "motivation": "growth | salary | company_requirement | academic | undefined",
  "motivation_detail": "string (cita textual o paráfrasis de lo que dijo el usuario)",
  "recommended_programs": ["string"],
  "payment_link_sent": "boolean",
  "mercado_pago_url": "string | null",
  "score": "hot | warm | cold",
  "score_justification": "string",
  "conversation_summary": "string",
  "full_transcript": [
    { "role": "agent | user", "content": "string", "timestamp": "ISO-8601" }
  ]
}
```

---

## 7. Backoffice Portal (Superficie B)

### 7.1 Auth — AWS Cognito

El backoffice usa **AWS Cognito User Pool** para autenticación. Para la demo se crea un único usuario `admin@dmc.pe` manualmente en la consola.

- Login via formulario custom con Amplify/Cognito SDK
- JWT token para mantener sesión
- Rutas protegidas en Next.js con middleware de verificación de token
- Logout limpia el token y redirige al login

### 7.2 Persistencia — DynamoDB

Los leads se almacenan en una tabla DynamoDB con el siguiente esquema:

| Atributo | Tipo | Descripción |
|---|---|---|
| `id` | String (PK) | UUID del lead |
| `created_at` | String (SK) | ISO-8601, permite ordenar por fecha |
| `email` | String | Email del candidato (GSI para búsqueda) |
| `score` | String | `hot`, `warm`, `cold` |
| `motivation` | String | Tipo de motivación detectada |
| `name` | String | Nombre del lead |
| `recommended_programs` | List | Programas recomendados |
| `payment_link_sent` | Boolean | Si se generó link de Mercado Pago |
| `conversation_summary` | String | Resumen generado por el agente |
| `full_transcript` | String (JSON serializado) | Historial completo |

### 7.3 Vistas

**Vista 1 — Lista de Leads**  
Tabla con columnas: Fecha · Nombre · Email · Motivación (badge) · Score (badge de color) · Programa recomendado · Link enviado. Filtros por score, motivación y rango de fechas. Clic en una fila abre el detalle.

**Vista 2 — Detalle del Lead**
- Datos personales completos (nombre, email, perfil)
- Badge de score con justificación breve
- Badge de motivación con cita textual del usuario
- Resumen ejecutivo de la conversación (generado por el agente)
- Transcripción completa colapsable
- Programa(s) recomendados con link al producto en dmc.pe
- Link de Mercado Pago generado (si aplica)

---

## 8. Knowledge Base del Agente

El agente responde preguntas sobre cursos usando **brochures en PDF** almacenados en **Amazon S3**. El flujo de RAG es:

```
Pregunta del usuario
      ↓
FastAPI (backend)
      ↓
Recupera chunks relevantes del PDF via embeddings (S3 + vector store)
      ↓
Construye contexto para el LLM
      ↓
Claude genera respuesta fundamentada en el brochure
```

**Organización de los PDFs en S3:**
```
s3://dmc-knowledge-base/
  brochures/
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

> Los brochures son la **única fuente de verdad** para el agente. Si la información no está en los PDFs, el agente escala a humano.

**Mapeo de perfiles a brochures prioritarios:**

| Perfil objetivo | PDFs prioritarios |
|---|---|
| Analista de datos / BI | power-bi, excel-ia, diploma-data-analyst |
| Data Scientist | machine-learning, adv-machine-learning, diploma-data-scientist |
| Data Engineer | azure-data-engineering, big-data, diploma-data-engineer |
| Desarrollador / App | full-stack-angular, front-end-angular-ia |
| IA & Automatización | n8n-chatbots, diseno-chatbots-python |
| Ejecutivo / No técnico | ia-ejecutivos, people-analytics, power-bi-financiero |
| Sin definir / explorador | membresia-datapro, membresia-ia-developer |

---

## 9. Stack Técnico

| Capa | Tecnología | Notas |
|---|---|---|
| **LLM** | Claude API (`claude-sonnet-4-6`) | Via Anthropic API desde FastAPI |
| **Backend** | FastAPI (Python) | API REST: chat, leads, RAG, Mercado Pago |
| **Frontend widget** | Next.js (React) | Popup flotante embebible en dmc.pe |
| **Backoffice** | Next.js (React) | Rutas `/admin/*` del mismo proyecto Next.js |
| **Auth** | AWS Cognito User Pool | JWT, Amplify SDK en el frontend |
| **Estado de conversación** | AWS AgentCore Memory | Persiste el hilo de conversación entre sesiones del mismo usuario |
| **Persistencia de leads** | Amazon DynamoDB | Tabla `dmc-leads` vía boto3 desde FastAPI |
| **Datos personales (browser)** | `window.storage` | Evita re-preguntar nombre/email en visitas repetidas del mismo navegador |
| **Knowledge Base** | Amazon S3 + RAG | PDFs de brochures; embeddings para retrieval semántico |
| **Link de pago** | Mercado Pago Checkout API | Genera preference + checkout URL desde FastAPI |
| **Infra cloud** | AWS | Cognito, DynamoDB, S3, AgentCore |

### 9.1 Diagrama de Arquitectura

```
[Usuario en dmc.pe]
        │
        │ (1) abre chat, envía mensaje
        ▼
[Next.js Widget]
        │
        │ (2) POST /api/chat
        ▼
[FastAPI Backend]
    ├── (3) AgentCore Memory → recupera/guarda hilo de conversación
    ├── (4) S3 + RAG → recupera chunks de brochures relevantes
    ├── (5) Claude API → genera respuesta con contexto
    ├── (6) DynamoDB → persiste lead al finalizar conversación
    └── (7) Mercado Pago API → genera link de pago si hay intención de compra
        │
        │ (8) respuesta al usuario
        ▼
[Next.js Widget → muestra respuesta]

[Equipo DMC — Backoffice]
        │
        │ (1) login
        ▼
[Next.js /admin]
        │
        │ (2) verifica JWT
        ▼
[AWS Cognito]  ✓ token válido
        │
        │ (3) GET /api/leads
        ▼
[FastAPI → DynamoDB → lista/detalle de leads]
```

---

## 10. Scope MoSCoW

### Must Have — v1 Demo

| # | Feature |
|---|---|
| M1 | Chat widget funcional con flujo completo (identificación → calificación → recomendación → cierre) |
| M2 | Skip de identificación si nombre/email ya están en `window.storage` |
| M3 | Calificación conversacional con captura de motivación (growth, salary, company, academic) |
| M4 | Recomendación de programas personalizada según perfil + motivación |
| M5 | Generación de link de pago Mercado Pago y envío en el chat |
| M6 | Knowledge Base RAG sobre brochures PDF en S3 |
| M7 | Estado de conversación persistido en AgentCore Memory |
| M8 | Persistencia del lead en DynamoDB al finalizar conversación |
| M9 | Backoffice Next.js con lista y detalle de leads |
| M10 | Auth con AWS Cognito en el backoffice |
| M11 | Guardrail de escalación a humano |
| M12 | Guardrail anti-alucinación (solo responde con info de los brochures) |

### Should Have

| # | Feature |
|---|---|
| S1 | Resumen ejecutivo generado por el agente al cerrar la conversación |
| S2 | Filtros por score y motivación en el backoffice |
| S3 | Badge de motivación en el detalle del lead con cita textual del usuario |

### Could Have

| # | Feature |
|---|---|
| C1 | Dashboard con métricas agregadas (total leads, % hot, % warm, motivaciones más frecuentes) |
| C2 | Notificación por email al equipo comercial cuando llega un lead Hot |
| C3 | Comparador de programas side-by-side dentro del chat |

### Won't Have (para este demo)

| # | Feature | Razón |
|---|---|---|
| W1 | Integración con CRM real | Complejidad fuera de scope |
| W2 | Pago procesado end-to-end | Solo se genera el link; el pago ocurre en Mercado Pago |
| W3 | Multi-tenancy | Innecesario para el proyecto |
| W4 | Análisis de video o voz | Fuera de scope |

---

## 11. Métricas de Éxito del Demo

| Métrica | Meta |
|---|---|
| Happy path completo | El agente llega al cierre sin romperse |
| Captura de datos | Nombre + email extraídos conversacionalmente en ≥80% de los casos |
| Re-identificación | Datos personales NO se vuelven a pedir si ya están en `window.storage` |
| Motivación detectada | Clasificada correctamente en ≥85% de las conversaciones de prueba |
| Score correcto | Hot cuando el usuario pidió link; Cold cuando solo exploró |
| Link de Mercado Pago | Se genera y envía correctamente para el programa recomendado |
| Lead en DynamoDB | Aparece con todos los campos correctos tras la conversación |
| Backoffice funcional | Lista y detalle de lead visibles tras login con Cognito |
| Guardrail activo | El agente no inventa precios al ser preguntado por info no cargada en S3 |

---

## 12. User Journeys

### Happy Path A — Motivación: Aumento salarial

**Contexto:** Andrea, 27 años, analista en una empresa de retail. Ya visitó el sitio la semana pasada y dejó su nombre y correo.

1. Andrea abre el chat. El agente la saluda por nombre y **no** le vuelve a pedir el correo (datos en `window.storage`).
2. El agente pregunta en qué puede ayudarla hoy.
3. Andrea dice: *"Quiero aprender Power BI, mi jefe me dijo que si lo manejo bien me suben el sueldo."*
4. El agente detecta motivación **💰 Aumento salarial** y pregunta por su experiencia actual con datos.
5. El agente recomienda la **Esp. Power BI potenciado con IA**, enfatizando el tiempo al resultado y el salario de mercado para perfiles BI (datos del brochure en S3).
6. Andrea pregunta cuánto cuesta. El agente responde con el precio del brochure y ofrece el link de Mercado Pago.
7. Andrea acepta. El agente genera el link y lo envía en el chat.
8. **Lead guardado en DynamoDB:** Score 🔥 Hot · Motivación 💰 Salary.

### Happy Path B — Motivación: Requerimiento de empresa

**Contexto:** Carlos, 34 años, contador. Primera visita. Su empresa le exige certificarse en Excel con IA.

1. Carlos abre el chat. El agente le pide nombre y correo (primera visita).
2. Carlos dice: *"Mi empresa me pidió que me certifique en Excel con IA, es obligatorio para el área."*
3. El agente detecta motivación **🏢 Requerimiento de empresa**, pregunta el área y el plazo que tiene.
4. El agente recomienda la **Esp. Excel potenciado con IA**, enfatizando la modalidad flexible y la posibilidad de facturación corporativa.
5. Carlos pregunta si la empresa puede pagar directamente. El agente escala: *"Para facturación corporativa, el equipo de ventas puede ayudarte: +51 912 322 976."*
6. **Lead guardado en DynamoDB:** Score 🟡 Warm · Motivación 🏢 Company.

---

## Apéndice: Recursos y Links

| Recurso | URL |
|---|---|
| Sitio DMC Institute | https://dmc.pe |
| Catálogo de cursos | https://dmc.pe/cursos |
| Membresías DATAPRO | https://dmc.pe/membresias-datapro |
| Membresías IA Developer | https://dmc.pe/membresias-ia-developer |
| WhatsApp ventas | https://wa.me/51912322976 |
| Mercado Pago Checkout Docs | https://www.mercadopago.com.pe/developers/es/docs/checkout-pro/landing |
| AWS Cognito Docs | https://docs.aws.amazon.com/cognito |
| AWS AgentCore Docs | https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html |