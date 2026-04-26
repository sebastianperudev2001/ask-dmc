# Requirements Verification Questions — DMC Sales Agent

Por favor responde cada pregunta llenando la letra elegida después del tag `[Answer]:`.
Si ninguna opción se ajusta, elige la última opción (Other/X) y describe tu preferencia.

---

## Sección 1: Despliegue e Infraestructura

## Question 1
¿Cuál es el entorno objetivo para este demo?

A) Solo local (correr todo en máquina de desarrollo, sin deploy a AWS real)
B) AWS real con servicios productivos (DynamoDB, Cognito, S3 en cuenta real)
C) AWS con cuenta de sandbox/dev dedicada para el demo
X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 2
¿Dónde se desplegará el backend FastAPI?

A) Local únicamente (para el demo, corre en localhost)
B) AWS EC2
C) AWS App Runner
D) AWS Lambda (serverless)
X) Other (please describe after [Answer]: tag below)

[Answer]: X. Monolito de backend + AgentCore Runtime para el deploy de los agentes. 

---

## Question 3
¿Dónde se desplegará el frontend Next.js (widget + backoffice)?

A) Local únicamente (para el demo, corre en localhost)
B) Vercel
C) AWS Amplify Hosting
D) AWS EC2 / App Runner
X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Sección 2: Knowledge Base / RAG

## Question 4
¿Cómo se almacenarán los embeddings para el RAG de los brochures PDF?

A) In-memory (FAISS local) — más simple, suficiente para demo
B) Amazon OpenSearch Serverless (vector store gestionado en AWS)
C) Amazon Bedrock Knowledge Base (RAG gestionado por Bedrock)
D) pgvector en PostgreSQL (RDS o local)
X) Other (please describe after [Answer]: tag below)

[Answer]: X. Como son una serie de brochures con un formato fijo. Presentacion, Sobre este diploma, como impulsamos tu carrera, por que estudiar este diploma, objetivo del diploma,
a quien esta dirigido, requisitos, herramientas, malla curricular, propuesta de capacitacion, certificacion, docentes. Estoy pensando usar algun LLM para estructurar esos PDFs. No se si un RAG sea lo mas adecuado.

---

## Question 5
Los brochures PDF que se mencionan en el PRD (power-bi, diploma-data-analyst, etc.), ¿ya existen y los tienes disponibles para subir a S3?

A) Sí, los tengo todos listos para subir
B) Sí, tengo algunos — el sistema debe funcionar aunque falten algunos
C) No todavía — el sistema debe estar preparado para cuando los suba
D) Para el demo usaré PDFs de ejemplo o placeholder
X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Sección 3: AgentCore Memory

## Question 6
Para el estado de conversación con AWS AgentCore Memory, ¿cómo quieres manejarlo?

A) Usar AWS Bedrock AgentCore Memory real (requiere cuenta AWS con acceso a AgentCore)
B) Simular con DynamoDB como store de conversación (más simple, evita dependencia de AgentCore)
C) Usar memoria en proceso (in-memory dict en FastAPI) — suficiente para demo de una sesión
X) Other (please describe after [Answer]: tag below)

[Answer]: A con Strands SDK

---

## Sección 4: Mercado Pago

## Question 7
¿En qué modalidad se usará Mercado Pago?

A) Sandbox / testing (credenciales de prueba, no se procesa dinero real)
B) Producción (credenciales reales de cuenta DMC)
X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 8
¿Tienes credenciales de Mercado Pago disponibles (access token) para configurar en el proyecto?

A) Sí, tengo access token de sandbox listo
B) Sí, tengo access token de producción listo
C) No todavía — construir el código y dejar placeholder para configurar después
X) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Sección 5: Chat Widget — Embedding

## Question 9
¿Cómo se embebería el chat widget en dmc.pe para el demo?

A) El demo solo corre de forma standalone (no se embebe en dmc.pe real)
B) Se embebe como script en una página de prueba / staging de dmc.pe
C) Se embebe directamente en producción de dmc.pe
X) Other (please describe after [Answer]: tag below)

[Answer]: A. Vamos a tener que crear una pagina de prueba. 

---

## Sección 6: Testing

## Question 10
¿Qué nivel de cobertura de tests se espera para este demo de curso?

A) Mínimo — solo los tests más críticos (happy path del agente, persistencia de lead)
B) Estándar — unit tests para lógica de negocio principal + tests de integración básicos
C) Completo — cobertura amplia incluyendo edge cases, guardrails, RAG
X) Other (please describe after [Answer]: tag below)

[Answer]: X. el curso esta enfocado en AI, podemos omitir pruebas frontend. Para backend, unit tests para lógica de negocio principal, Evals, guardrails y RAG.

---

## Sección 7: Autenticación Backoffice

## Question 11
Para el usuario admin del backoffice (`admin@dmc.pe`), ¿cómo se manejará la configuración inicial?

A) Creación manual en consola AWS Cognito (como indica el PRD)
B) Script de setup que crea el usuario programáticamente via AWS CLI
C) Usar Cognito Hosted UI (login page de AWS, sin formulario custom)
X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Sección 8: Extensions

## Question 12 — Security Extension
¿Se deben aplicar reglas de seguridad como restricciones bloqueantes en este proyecto?

A) Sí — aplicar todas las reglas SECURITY como constraints bloqueantes (recomendado para apps que van a producción)
B) No — omitir reglas SECURITY (adecuado para PoC, prototipos, proyectos experimentales de curso)
X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 13 — Property-Based Testing Extension
¿Se deben aplicar reglas de Property-Based Testing (PBT) en este proyecto?

A) Sí — aplicar todas las reglas PBT como constraints bloqueantes (recomendado para proyectos con lógica de negocio compleja)
B) Parcial — aplicar PBT solo para funciones puras y transformaciones de datos
C) No — omitir reglas PBT (adecuado para demos, CRUDs simples, capas de integración)
X) Other (please describe after [Answer]: tag below)

[Answer]: A
