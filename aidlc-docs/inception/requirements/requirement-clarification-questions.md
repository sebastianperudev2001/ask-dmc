# Requirements Clarification Questions — DMC Sales Agent

Detecté 2 ambigüedades en tus respuestas que necesito resolver para definir bien la arquitectura.

---

## Ambiguity 1: Arquitectura FastAPI + AgentCore Runtime (Q2 + Q6)

Indicaste "monolito de backend + AgentCore Runtime para el deploy de los agentes" y "AgentCore Memory con Strands SDK".

Esto puede significar dos arquitecturas muy diferentes:

**Arquitectura A — FastAPI como gateway, Strands Agent en AgentCore Runtime**
```
Next.js Widget
    |
    | POST /chat
    v
FastAPI (thin layer: auth, routing, lead persistence, Mercado Pago)
    |
    | invoke AgentCore Runtime
    v
Strands Agent (en AgentCore Runtime)
    ├── Tool: search_courses (busca en knowledge base estructurada)
    ├── Tool: save_lead (persiste en DynamoDB via FastAPI o directo)
    ├── Tool: generate_payment_link (llama Mercado Pago)
    └── AgentCore Memory (historial de conversación)
```

**Arquitectura B — Strands Agent corre EN FastAPI (no en AgentCore Runtime), usa AgentCore Memory**
```
Next.js Widget
    |
    | POST /chat
    v
FastAPI (backend principal)
    ├── Strands Agent (instanciado aquí, con herramientas Python)
    │       ├── Tool: search_courses
    │       ├── Tool: save_lead
    │       └── Tool: generate_payment_link
    └── AgentCore Memory SDK (para persistir hilo de conversación)
```
El "AgentCore Runtime" en este caso sería la plataforma de DEPLOY del contenedor FastAPI, no un runtime separado de agentes.

### Clarification Question 1
¿Cuál de estas arquitecturas describe mejor lo que tienes en mente?

A) Arquitectura A — Strands Agent desplegado independientemente en AgentCore Runtime; FastAPI es un thin layer de API
B) Arquitectura B — Strands Agent corre dentro de FastAPI; AgentCore Memory se usa solo para persistir el historial de conversación
C) Otra arquitectura (describir abajo)
X) Other (please describe after [Answer]: tag below)

[Answer]: A. Pero, recuerda que deberia ser un websocket para facilitar el streaming de las respuestas.

---

## Ambiguity 2: Knowledge Base — LLM-structured PDFs (Q4)

Indicaste que prefieres usar un LLM para estructurar los PDFs en lugar de RAG tradicional. Los brochures tienen formato fijo con secciones conocidas.

Hay varias formas de implementar esto:

**Opción A — Ingestion pipeline: PDF → LLM extractor → JSON estructurado en S3/DynamoDB**
- Script de ingestion que procesa cada PDF una vez con Claude
- Genera un JSON por curso con todas las secciones del brochure
- El agente accede a los JSONs como herramienta/tool (query por nombre de curso)
- No se necesita vector store ni embeddings

**Opción B — PDFs en S3 + Bedrock Knowledge Base (RAG gestionado por AWS)**
- Sube los PDFs a S3
- Bedrock Knowledge Base hace el chunking + embeddings automáticamente
- El agente hace semantic search via Bedrock KB tool
- AWS gestiona todo el pipeline de RAG

**Opción C — Brochures como context estático en el system prompt del agente**
- Estructuras los brochures en Markdown/JSON una vez
- Se incluyen directamente en el contexto del sistema del agente (si el volumen lo permite)
- Más simple, sin infra extra

### Clarification Question 2
¿Cómo prefieres implementar la knowledge base de los brochures?

A) Opción A — Script de ingestion: PDF → LLM (Claude) → JSON estructurado almacenado en DynamoDB o S3; el agente tiene un tool para consultar cursos por nombre/perfil
B) Opción B — Bedrock Knowledge Base (RAG gestionado, sube PDFs a S3 y AWS hace el resto)
C) Opción C — Brochures pre-procesados como contexto estático en el system prompt (sin infra adicional)
X) Other (please describe after [Answer]: tag below)

[Answer]:  Crear una DB vectorial con los brochures estructurados. Para ello, deberiamos crear un pipeline de ingestion que procese los PDFs con Claude y genere embeddings de las secciones relevantes y agregamos metadata estructurada para facilitar la búsqueda.
