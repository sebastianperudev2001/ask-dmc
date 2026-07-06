# Frontend↔Backend Integration — Preguntas de Clarificación

**Contexto**: `apps/chat` (Next.js, Effect) y `services/agent-service` (Azure, incremento 1: catálogo + recomendación por perfil) existen ambos pero no se hablan entre sí. Hallazgos de la exploración:

- `apps/chat` hace **HTTP POST + streaming de texto plano** a `/api/ask` (proxy Next.js → `API_URL`), envía `{question: string}` libre, y espera un header `x-sources` con `Source{course, section, distance}` (forma de chunk RAG). Este contrato fue diseñado para el servicio legacy `services/api` (AWS Strands, ahora SUPERSEDED), no para `agent-service`.
- `services/agent-service` expone solo `WS /ws/recommendation`: el cliente debe enviar `recommendation_request` con **campos estructurados** (`budget`, `max_duration_weeks`, `professional_background`, `desired_stack`) — no una pregunta libre — y recibe `recommendation_delta`/`recommendation_done` con `CandidateSummary{course_id, name, similarity_score}` (forma de recomendación de catálogo, no de chunk RAG). El flujo es potencialmente multi-mensaje (puede ofrecer relajar filtros o avisar que no hay match exacto antes de la recomendación final).
- La visión original de Inception (`requirements.md` RF-01 a RF-11) describía un agente conversacional completo (identificación, calificación pregunta-por-pregunta, detección de motivación, recomendación, link de pago, escalación) vía WebSocket — pero el incremento 1 de `agent-service` (DIV-10) implementa **solo** catálogo + recomendación por perfil, no ese flujo conversacional completo.

Por favor responde cada pregunta con la letra de tu elección después de `[Answer]:`.

## Question 1
¿Cuál debe ser el enfoque de integración para conectar `apps/chat` con `services/agent-service` en este incremento?

A) **Adaptador/puente**: mantener la UI actual de `apps/chat` (caja de texto libre) y construir una capa puente (ej. ruta API de Next.js o pequeño servicio) que traduzca la pregunta libre a `recommendation_request` (con valores por defecto o extracción simple) y reformatee las respuestas del WS a texto plano + sources
B) **Reescritura del frontend**: cambiar `apps/chat` para hablar el protocolo WebSocket nativo del agent-service directamente, reemplazando la caja de texto libre por un formulario estructurado (presupuesto, duración, background profesional, stack deseado)
C) **Híbrido**: chat conversacional en el frontend que internamente recolecta los 4 campos estructurados turno por turno (simulando conversación) antes de enviar el `recommendation_request` — sin backend adicional de extracción de lenguaje natural
D) Other (please describe after [Answer]: tag below)

[Answer]: Debemos mantener la estructura de chat libre, al final lo que estamos haciendo es un agent de ventas. Es un chat libre, podemos agregar un tool al agente para que inicialice la recoleccion de los datos, y el frontend puede detectar ese tool call (ya que estamos en modo streaming) y mostrar un widget para que el usuario complete los datos faltantes. Pero, el diseno debe ser un chat libre no estructurado, pero claro al final parte del system prompt es cerrar la venta y obtener una recomendacion del curso.

## Question 2
El incremento 1 de `agent-service` **no** implementa el flujo conversacional completo (identificación, calificación, motivación) de la visión original — solo catálogo + recomendación. ¿Cuál es el alcance de este trabajo de integración?

A) Integrar únicamente lo que ya existe hoy en `agent-service` (catálogo + recomendación por perfil) — el resto del flujo conversacional queda para un incremento futuro del backend
B) Este trabajo de integración debe además extender `agent-service` para cubrir más del flujo conversacional original (identificación/calificación) antes de conectar el frontend
C) Other (please describe after [Answer]: tag below)

[Answer]: B. Lo que dice el B + integracion frontend streaming conversacional tipo chatbot

## Question 3
El backend puede responder con mensajes intermedios (`relax_filters_offer` cuando no hay match exacto con los filtros duros, `no_exact_match_showing_all`, `no_recommendation`) antes de la recomendación final. ¿Cómo debe manejar esto el frontend en este incremento?

A) Mostrar estos mensajes intermedios al usuario y permitirle responder (ej. aceptar relajar filtros) — soporte completo del flujo multi-turno
B) Mostrarlos solo como texto informativo de una sola vía (sin acción del usuario para relajar filtros en este incremento)
C) Ignorar estos casos por ahora — asumir siempre el camino feliz (`recommendation_done` con candidatos)
D) Other (please describe after [Answer]: tag below)

[Answer]: A 

## Question 4
La UI actual (`SourceChips`) muestra `Source{course, section, distance}` (chunks RAG). El agent-service devuelve `CandidateSummary{course_id, name, similarity_score}` (recomendaciones de catálogo). ¿Qué debe pasar con esa parte de la UI?

A) Rediseñar el componente para mostrar recomendaciones de curso (nombre, score) en vez de chunks RAG — cambia la semántica visual pero reutiliza el patrón de "chips"
B) Reemplazar completamente por una nueva UI de tarjetas de curso recomendado (más detalle: nombre, posiblemente precio/duración si se agregan al backend)
C) Eliminar esa parte de la UI por ahora — el incremento se enfoca solo en el texto de la respuesta del agente
D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5
Si se elige un adaptador/puente (Question 1 = A o C), ¿dónde debe vivir esa lógica?

A) Dentro de la ruta API existente de Next.js (`app/api/ask/route.ts`), como server-side bridge HTTP→WebSocket
B) Como una capa nueva dentro de `services/agent-service` (ej. un endpoint HTTP adicional junto al WS existente) que internamente reutiliza la misma lógica de recomendación
C) No aplica — elegí reescritura nativa (Question 1 = B)
D) Other (please describe after [Answer]: tag below)

[Answer]: no creo que aplica esa pregunta segun el enfoque seleccionado

## Question 6
¿Cuál es el alcance de despliegue para este trabajo de integración?

A) Solo desarrollo local (frontend en `localhost:3000`, backend en `localhost:8000`) — sin preocuparnos aún por CORS/topología de producción
B) Debe funcionar también en un entorno desplegado (ej. Container Apps + frontend hospedado aparte) — implica definir CORS y/o autenticación en `agent-service` en este mismo incremento
C) Other (please describe after [Answer]: tag below)

[Answer]: A
