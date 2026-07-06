# Frontend↔Backend Integration — Clarificación de Ambigüedades

Tus respuestas definen una dirección clara (chat libre + tool-calling + widget + extensión conversacional de `agent-service`), pero introducen mecánica nueva que necesita precisión antes de pasar a Functional Design. Por favor responde estas 5 preguntas.

## Clarification 1: Mecanismo de respuesta al widget
Cuando el agente invoca el tool que dispara el widget de recolección de datos y el usuario lo completa, ¿cómo se envía esa respuesta de vuelta a la conversación?

A) Nuevo tipo de mensaje WS estructurado (ej. `profile_data_submitted` con los 4 campos) que el backend interpreta como el resultado del tool call y continúa la conversación desde ahí
B) El frontend convierte los datos del widget en un mensaje de chat en lenguaje natural (ej. "Mi presupuesto es X, mi duración máxima es Y, vengo de background Z, busco stack W") y lo envía como si fuera un mensaje normal del usuario
C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Clarification 2: Endpoint/transporte de la conversación
El endpoint actual `/ws/recommendation` fue diseñado para un único `recommendation_request` estructurado (no para chat libre de ida y vuelta). ¿Se extiende ese mismo endpoint para soportar chat libre, o se crea uno nuevo dedicado?

A) Extender `/ws/recommendation` para aceptar también mensajes de chat libre (mismo endpoint, protocolo ampliado)
B) Crear un endpoint nuevo dedicado (ej. `/ws/chat`) para el flujo conversacional; el endpoint estructurado actual se mantiene tal cual (sin uso desde el frontend, o para uso interno/futuro)
C) Other (please describe after [Answer]: tag below)

[Answer]: A. Y que se llame chat. Es en realidad el mismo entry point, el agente deberia tener la capacidad de determinar cuando recomendar y cuando respodner libremente como asesor de ventas.

## Clarification 3: Persistencia de sesión
¿La conversación debe sobrevivir a un refresh de página o cierre de pestaña (requiere guardar un identificador de thread/conversación en el cliente), o basta con que la sesión viva solo mientras la conexión WebSocket esté abierta?

A) Debe persistir entre sesiones/refreshes (se guarda un identificador de thread/conversación, ej. en localStorage, para retomarla)
B) Basta con que viva solo durante la conexión activa — se reinicia al recargar la página (suficiente para este incremento)
C) Other (please describe after [Answer]: tag below)

[Answer]: Me parece que Foundry permite guardar en Memory las conversaciones?. Deberia persistir entre sesiones/refreshes.

## Clarification 4: Manejo conversacional de "relajar filtros" / "sin match exacto"
Confirmaste soporte completo del flujo multi-turno (Question 3 = A) para cuando no hay match exacto. Dado que el frontend ahora es chat libre (no un formulario), ¿cómo se presenta la oferta de relajar filtros?

A) Como texto conversacional normal del agente (ej. "No encontré cursos exactos dentro de tu presupuesto, ¿quieres que amplíe la búsqueda?") — el usuario responde escribiendo libremente en el chat, sin widget especial
B) Con un widget/botón específico (similar al de recolección de datos) para aceptar/rechazar la opción
C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Clarification 5: Límite de alcance ("Definition of Done") de este incremento
La visión original de Inception incluía persistencia de leads (DynamoDB), generación de link de Mercado Pago, y escalación a humano (RF-08, RF-09, RF-10 en `requirements.md`). Dado que este incremento extiende `agent-service` para cubrir identificación/calificación conversacional + recomendación, ¿dónde termina exactamente el alcance de ESTE incremento?

A) Solo: chat libre + tool de recolección de datos + widget + recomendación final de curso (streaming). Sin persistencia de leads, sin pago, sin escalación — quedan para incrementos futuros
B) Incluye también persistencia de la conversación/lead (reutilizando la base de datos Postgres ya existente del proyecto) para no perder el historial, pero sin pago ni escalación todavía
C) Incluye todo lo anterior más generación de link de pago y/o escalación a humano en este mismo incremento
D) Other (please describe after [Answer]: tag below)

[Answer]: C
