# User Stories — DMC Sales Agent

**Versión**: 1.0  
**Fecha**: 2026-04-28  
**Idioma**: Español  
**Criterios de aceptación**: Híbrido (BDD para flujos y guardrails; bullets para UI simple)

---

## Epic E1 — Flujo Conversacional Completo

**Descripción**: Como visitante de dmc.pe, quiero interactuar con un agente de IA que me oriente sobre qué programa estudiar, califique mi perfil de forma conversacional, y me permita completar la compra o solicitar contacto humano, sin tener que llenar formularios ni esperar llamadas.

**Personas**: P1 (Visitante), P3 (Agente IA)  
**Requisitos cubiertos**: RF-01 a RF-11, RF-14, RF-15, S4

---

### US-01 — Bienvenida e identificación del agente

**Como** visitante que abre el chat,  
**quiero** saber desde el inicio que estoy hablando con un agente de IA de DMC Institute,  
**para** tener claridad sobre con quién interactúo antes de compartir mis datos.

**Criterios de aceptación**:

*Escenario 1 — Primera visita*
- **Dado** que el visitante abre el chat por primera vez
- **Cuando** el agente inicia la conversación
- **Entonces** el agente se presenta por nombre, indica explícitamente que es un asistente de IA, y da la bienvenida en nombre de DMC Institute

*Escenario 2 — Visita recurrente con datos en localStorage*
- **Dado** que el visitante tiene nombre y email guardados en localStorage
- **Cuando** el agente inicia la conversación
- **Entonces** el agente saluda al visitante por su nombre, confirma sus datos brevemente, y NO vuelve a solicitar nombre ni email

*Escenario 3 — Primera visita sin datos*
- **Dado** que no hay datos en localStorage
- **Cuando** el agente completa la bienvenida
- **Entonces** el agente solicita el nombre completo (primera pregunta, sin hacer múltiples preguntas en el mismo turno)

---

### US-02 — Captura de datos personales

**Como** visitante nuevo,  
**quiero** que el agente capture mi nombre y correo de forma conversacional,  
**para** no tener que llenar un formulario y que mis datos queden guardados para futuras visitas.

**Criterios de aceptación**:

*Escenario 1 — Captura secuencial*
- **Dado** que el agente solicitó el nombre
- **Cuando** el visitante lo proporciona
- **Entonces** el agente lo confirma y solicita únicamente el correo electrónico en el siguiente turno (una pregunta a la vez)

*Escenario 2 — Validación de email*
- **Dado** que el visitante ingresa un email con formato inválido
- **Cuando** el agente lo recibe
- **Entonces** el agente solicita amablemente que lo corrija, sin avanzar al siguiente estado

*Escenario 3 — Persistencia en localStorage*
- **Dado** que nombre y email han sido capturados y validados
- **Cuando** el agente los registra
- **Entonces** se persisten en `localStorage` para que en la próxima sesión no sean solicitados nuevamente

---

### US-03 — Calificación conversacional del lead

**Como** visitante,  
**quiero** que el agente entienda mi perfil, motivación y objetivos mediante una conversación natural,  
**para** recibir una recomendación genuinamente personalizada sin sentir que me están interrogando.

**Criterios de aceptación**:

*Escenario 1 — Flujo de calificación secuencial*
- **Dado** que el visitante ha sido identificado
- **Cuando** el agente inicia la calificación
- **Entonces** el agente hace una sola pregunta por turno, cubriendo: perfil actual (ocupación/experiencia técnica), motivación, objetivo de aprendizaje/rol deseado, disponibilidad semanal, presupuesto aproximado, urgencia/fecha de inicio

*Escenario 2 — Detección de motivación*
- **Dado** que el visitante responde preguntas de calificación
- **Cuando** sus respuestas contienen señales de motivación
- **Entonces** el agente clasifica la motivación en una de las categorías: `growth`, `salary`, `company_requirement`, `academic`; si las señales son vagas, el agente profundiza antes de clasificar como `undefined`

*Escenario 3 — Guardrail referenciado: scope de ventas* (ver también US-12)
- **Dado** que el visitante hace una pregunta fuera del scope durante la calificación (ej. pide un ejercicio de código)
- **Cuando** el agente la recibe
- **Entonces** el agente responde educadamente que su rol es ayudar a encontrar el programa ideal, y retoma la calificación

---

### US-04 — Recomendación personalizada de programas

**Como** visitante calificado,  
**quiero** recibir una recomendación de 1 a 3 programas adaptada a mi perfil y motivación,  
**para** entender claramente por qué esos programas son los indicados para mí.

**Criterios de aceptación**:

*Escenario 1 — Recomendación personalizada*
- **Dado** que el agente ha completado la calificación
- **Cuando** genera la recomendación
- **Entonces** recomienda entre 1 y 3 programas del catálogo, personalizando el pitch según la motivación detectada (ej. para `salary`: destaca el impacto salarial; para `company_requirement`: enfatiza la certificación)

*Escenario 2 — Fuente de verdad exclusiva*
- **Dado** que el agente recomienda un programa
- **Cuando** el visitante pregunta sobre precio, fechas de inicio o requisitos
- **Entonces** el agente solo responde con información presente en la knowledge base (brochures); si no tiene el dato, activa el guardrail anti-alucinación (ver US-09)

*Escenario 3 — Envío de brochure (S4)*
- **Dado** que el agente ha recomendado un programa
- **Cuando** el visitante muestra interés en el detalle del programa
- **Entonces** el agente ofrece y envía una presigned URL de S3 con el brochure oficial del programa recomendado, válida por un tiempo limitado

*Escenario 4 — Comparación entre opciones*
- **Dado** que el agente recomendó más de un programa
- **Cuando** el visitante solicita comparar opciones
- **Entonces** el agente compara únicamente los programas del catálogo DMC, sin mencionar programas de otras instituciones (ver también US-11)

---

### US-05 — Cierre de venta con link de pago

**Como** visitante interesado en comprar,  
**quiero** recibir un link de pago directo en el chat,  
**para** completar mi inscripción sin salir de la conversación ni hacer trámites adicionales.

**Criterios de aceptación**:

*Escenario 1 — Generación del link*
- **Dado** que el visitante muestra intención de compra (ej. "quiero inscribirme", "¿cómo pago?")
- **Cuando** el agente detecta la intención
- **Entonces** genera un link de pago via Mercado Pago Checkout API (sandbox) y lo envía en el chat

*Escenario 2 — Persistencia del lead al cierre*
- **Dado** que el agente envió el link de pago
- **Cuando** se finaliza la sesión
- **Entonces** el lead se persiste en DynamoDB con `payment_link_sent: true`, `mercado_pago_url` con el link generado, y `score: hot`

*Escenario 3 — Streaming de respuesta*
- **Dado** que el agente genera cualquier respuesta
- **Cuando** la envía al widget
- **Entonces** la respuesta se transmite token a token via WebSocket (no se espera la respuesta completa para mostrarla)

---

### US-06 — Escalación a contacto humano

**Como** visitante que prefiere hablar con una persona,  
**quiero** poder solicitar contacto con el equipo de DMC,  
**para** que alguien me llame o escriba sin tener que buscar el número yo mismo.

**Criterios de aceptación**:

*Escenario 1 — Respuesta del agente*
- **Dado** que el visitante solicita hablar con una persona
- **Cuando** el agente lo detecta
- **Entonces** el agente responde que alguien del equipo se pondrá en contacto con él/ella, sin proporcionar número de teléfono ni WhatsApp directamente

*Escenario 2 — Flag en DynamoDB*
- **Dado** que el agente detectó la solicitud de contacto humano
- **Cuando** persiste el lead
- **Entonces** el campo `escalated_to_human` se registra como `true` en la tabla `dmc-leads`

*Escenario 3 — Notificación por email*
- **Dado** que el lead fue marcado con `escalated_to_human: true`
- **Cuando** Lambda finaliza la sesión
- **Entonces** se envía un email de notificación via Amazon SES al equipo comercial con: nombre del lead, email, resumen de la conversación y motivación detectada

*Escenario 4 — Cierre de sesión*
- **Dado** que el agente notificó al visitante y al equipo
- **Cuando** se completa el proceso de escalación
- **Entonces** la sesión conversacional se cierra y el lead queda en DynamoDB con `score` calculado

---

## Epic E2 — Guardrails del Agente

**Descripción**: Como DMC Institute, necesito que el agente IA opere dentro de límites estrictos de veracidad, alcance y competencia, para proteger la reputación de la institución y garantizar una experiencia confiable al visitante.

**Personas**: P3 (Agente IA), P1 (Visitante)  
**Requisitos cubiertos**: RF-12, RF-13, RF-17, RF-18

---

### US-09 — Guardrail: Anti-alucinación

**Como** DMC Institute,  
**quiero** que el agente nunca invente información sobre precios, fechas ni condiciones especiales,  
**para** proteger la confianza del visitante y evitar compromisos falsos.

**Criterios de aceptación**:

*Escenario 1 — Información no disponible*
- **Dado** que el visitante pregunta por un dato (ej. precio exacto, fecha de inicio) que no está en la knowledge base
- **Cuando** el agente busca en su contexto
- **Entonces** el agente responde: *"No tengo esa información disponible. Si tienes más preguntas, alguien de nuestro equipo puede ayudarte."* — nunca inventa un valor

*Escenario 2 — Solo información de brochures*
- **Dado** que el agente emite cualquier afirmación sobre un programa
- **Cuando** esa afirmación puede verificarse
- **Entonces** la información está presente textualmente en alguno de los brochures de la knowledge base

---

### US-10 — Guardrail: Sin promesas no fundamentadas

**Como** DMC Institute,  
**quiero** que el agente no ofrezca becas, descuentos ni condiciones especiales no documentadas,  
**para** evitar expectativas falsas que el equipo comercial no pueda cumplir.

**Criterios de aceptación**:

- El agente no menciona ni ofrece ningún descuento, beca o condición especial a menos que figure explícitamente en el brochure del programa
- Si el visitante pregunta por descuentos no documentados, el agente responde que no tiene esa información y sugiere consultar al equipo

---

### US-11 — Guardrail: Sin menciones de competidores

**Como** DMC Institute,  
**quiero** que el agente no mencione ninguna otra institución educativa ni plataforma de cursos,  
**para** mantener la conversación centrada en la oferta de DMC y evitar comparaciones que puedan desviar al visitante.

**Criterios de aceptación**:

*Escenario 1 — Pregunta directa sobre competidor*
- **Dado** que el visitante pregunta cómo se compara DMC con otra institución (ej. Crehana, Udemy, Coursera, UTEC)
- **Cuando** el agente recibe la pregunta
- **Entonces** el agente no menciona el competidor por nombre, no realiza la comparación, y redirige la conversación hacia los diferenciadores de DMC basados en los brochures

*Escenario 2 — Mención espontánea*
- El agente nunca introduce por iniciativa propia el nombre de otra institución o plataforma

---

### US-12 — Guardrail: Scope limitado a ventas

**Como** DMC Institute,  
**quiero** que el agente solo ejecute tareas de orientación, recomendación y cierre de ventas,  
**para** que el visitante no lo use como tutor, asistente de código o herramienta de propósito general.

**Criterios de aceptación**:

*Escenario 1 — Solicitud fuera de scope*
- **Dado** que el visitante solicita algo fuera del scope (ej. "resuelve este ejercicio de Python", "explícame qué es machine learning", "redacta mi CV")
- **Cuando** el agente recibe la solicitud
- **Entonces** el agente responde educadamente que su función es ayudar a encontrar el programa ideal para el visitante, y ofrece retomar la orientación

*Escenario 2 — No rompe el flujo*
- **Dado** que el agente activó el guardrail de scope
- **Cuando** el visitante acepta continuar
- **Entonces** el agente retoma el flujo conversacional en el estado donde estaba antes de la solicitud fuera de scope

---

## Epic E3 — Backoffice Portal

**Descripción**: Como miembro del equipo comercial de DMC, necesito un portal seguro donde pueda revisar, filtrar y gestionar los leads capturados por el agente IA, para priorizar mi gestión comercial y dar seguimiento oportuno a los prospectos más calientes.

**Personas**: P2 (Equipo Comercial)  
**Requisitos cubiertos**: RF-14, RF-15, RF-16, S2, S3

---

### US-13 — Autenticación con Cognito

**Como** miembro del equipo comercial,  
**quiero** acceder al backoffice con mis credenciales corporativas,  
**para** que la información de leads esté protegida y solo accesible al equipo autorizado.

**Criterios de aceptación**:

- El portal `/admin/*` está protegido; un usuario no autenticado es redirigido a `/admin/login`
- El formulario de login usa Amplify SDK con AWS Cognito User Pool
- Tras autenticación exitosa, se emite un JWT que se valida server-side en cada request a la API
- El botón de logout invalida el token y redirige a `/admin/login`
- Credenciales incorrectas muestran mensaje de error sin revelar detalles de seguridad

---

### US-14 — Vista lista de leads

**Como** miembro del equipo comercial,  
**quiero** ver todos los leads en una tabla con información clave visible de un vistazo,  
**para** identificar rápidamente cuáles requieren atención prioritaria.

**Criterios de aceptación**:

- La tabla muestra las columnas: Fecha · Nombre · Email · Motivación (badge con color) · Score (badge: hot=rojo, warm=amarillo, cold=azul) · Programa recomendado · Link enviado (sí/no)
- Los leads se muestran ordenados por fecha descendente por defecto
- Filtros disponibles: score (hot/warm/cold), motivación (las 5 categorías), rango de fechas
- Al hacer clic en una fila, navega al detalle del lead
- Los leads con `escalated_to_human: true` se destacan visualmente (ej. ícono o badge "Solicita contacto")

---

### US-15 — Vista detalle del lead

**Como** miembro del equipo comercial,  
**quiero** ver todos los datos de un lead en una pantalla de detalle,  
**para** prepararme para el contacto comercial sin tener que leer la conversación completa.

**Criterios de aceptación**:

- Muestra: datos personales (nombre, email, perfil resumido), badge de score con justificación breve, badge de motivación con cita textual del usuario, programa(s) recomendado(s), link de Mercado Pago (si fue generado), resumen ejecutivo de la conversación
- La transcripción completa de la conversación está disponible en una sección colapsable
- Si el lead tiene `escalated_to_human: true`, se muestra un banner destacado indicando que el visitante solicitó contacto humano

---

### US-16 — Vista de leads escalados

**Como** miembro del equipo comercial,  
**quiero** identificar de inmediato los leads que solicitaron ser contactados por una persona,  
**para** priorizar esas conversaciones y responder antes de que el prospecto pierda interés.

**Criterios de aceptación**:

- En la lista de leads, los registros con `escalated_to_human: true` son visualmente distinguibles del resto
- Existe un filtro rápido o sección dedicada "Solicitan contacto" que muestra solo esos leads
- El equipo recibe adicionalmente un email de notificación via SES al momento de la escalación (no solo en el backoffice)

---

## Epic E4 — Pipeline de Ingestion de Knowledge Base

**Descripción**: Como sistema DMC, necesito procesar los brochures PDF del catálogo de programas y cargarlos en la knowledge base vectorial, para que el agente pueda responder con información precisa y actualizada sobre cada programa.

**Personas**: P3 (Agente IA / Sistema)  
**Requisitos cubiertos**: RF-07, M7

---

### US-17 — Ingestion de brochures PDF

**Como** sistema DMC,  
**quiero** procesar automáticamente los PDFs del catálogo cargados en S3,  
**para** que el agente siempre tenga acceso a la información más reciente de cada programa.

**Criterios de aceptación**:

- El pipeline lee PDFs desde `s3://dmc-knowledge-base/brochures/`
- Cada PDF es procesado por Claude via Amazon Bedrock (capa LLMProvider), extrayendo las secciones definidas en el schema: `presentacion`, `sobre_este_diploma`, `como_impulsamos`, `por_que_estudiar`, `objetivo`, `a_quien_dirigido`, `requisitos`, `herramientas`, `malla_curricular`, `propuesta_capacitacion`, `certificacion`, `docentes`
- Se generan embeddings por sección con metadata: `course_name`, `section_type`, `keywords`
- Los embeddings y metadata se almacenan en el vector DB
- El pipeline puede ejecutarse manualmente y, opcionalmente, ser disparado por un evento S3

---

### US-18 — Búsqueda semántica de programas

**Como** agente IA,  
**quiero** consultar la knowledge base con el perfil y motivación del visitante,  
**para** recuperar los chunks más relevantes de los brochures y fundamentar mi recomendación.

**Criterios de aceptación**:

- La tool `search_courses(query, perfil_usuario)` consulta el vector DB con búsqueda semántica
- Retorna los chunks más relevantes con metadata (`course_name`, `section_type`)
- El agente utiliza exclusivamente los chunks retornados como contexto; no inventa información adicional
- El mapeo perfil → brochures prioritarios orienta el ranking (ej. Data Scientist → `machine-learning`, `diploma-data-scientist`)

---

## Mapa Personas — Stories

| Persona | Stories |
|---|---|
| P1 — Visitante | US-01, US-02, US-03, US-04, US-05, US-06, US-09, US-10, US-11, US-12 |
| P2 — Equipo Comercial | US-13, US-14, US-15, US-16 |
| P3 — Agente IA (Sistema) | US-01, US-03, US-04, US-05, US-06, US-09, US-10, US-11, US-12, US-17, US-18 |

---

## Verificación INVEST

| Story | I | N | V | E | S | T |
|---|---|---|---|---|---|---|
| US-01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-03 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-04 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-05 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-06 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-09 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-11 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-12 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-13 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-14 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-15 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-16 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-17 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| US-18 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
