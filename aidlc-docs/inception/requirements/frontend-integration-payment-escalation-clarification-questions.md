# Frontend↔Backend Integration — Clarificación: Pago, Escalación y Persistencia de Leads

Al confirmar el alcance (Clarification 5 = C), este incremento pasa a cubrir identificación, calificación, recomendación, **generación de link de pago** y **escalación a humano** — no solo la integración de chat. Dos de esas piezas (RF-08, RF-09 en `requirements.md`) fueron diseñadas originalmente para AWS (Mercado Pago + notificación via Amazon SES), que ya no aplica tras el pivote a Azure (DIV-10). Necesito 4 confirmaciones más antes de pasar a Functional Design.

## Question 1: Mecanismo de notificación de escalación a humano
RF-09 original: al escalar, "Lambda envía un email de notificación al equipo comercial via Amazon SES". Ya no hay AWS. ¿Cómo se notifica al equipo comercial en este incremento?

A) Azure Communication Services (email) — equivalente directo de SES pero en Azure
B) Webhook a Slack o Microsoft Teams (canal del equipo comercial)
C) Solo persistir el flag `escalated_to_human=true` en la base de datos por ahora, sin notificación activa (se revisa manualmente); el envío proactivo queda para un incremento futuro
D) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 2: Integración de pago
RF-08 original: "genera un link de pago via Mercado Pago Checkout API (sandbox)". ¿Se mantiene igual?

A) Sí, mantener Mercado Pago Checkout API (sandbox) tal como en la visión original — es independiente de la nube que hospeda el backend
B) Reconsiderar el proveedor de pago (especifica cuál en "Other")
C) Other (please describe after [Answer]: tag below)

[Answer]: Usar Culqi. Lo importante primero: Culqi no te da automáticamente una "URL pública" para cada pago
Culqi tiene dos caminos distintos, y elegir el correcto cambia toda la arquitectura:
1. CulqiLink — Es un producto ya hecho para esto: generas links de cobro reutilizables desde el CulqiPanel (dashboard), sin código. Es un servicio simple y seguro que te permite realizar cobros desde tus redes sociales sin necesidad de tener una tienda virtual, y puedes crear links de cobro para enviarlos a tus clientes. El problema: son links semi-estáticos configurados manualmente en el panel (usos, medios de pago, vigencia), no se generan dinámicamente vía API por cada conversación con montos/clientes distintos. Culqi
2. API de Órdenes — Esto sí es programático (lo que tu Agent necesita), pero una orden se crea a partir de la información de una posible compra, con datos como amount, currency_code, description, order_number, client_details y expiration_date. La API te devuelve un objeto order con un id único (ord_live_xxxx) — pero ese id no es un link navegable por sí solo. Necesitas una página propia (tu Checkout hospedado) que reciba ese order.id y abra el Culqi Checkout con él. Dado la naturaleza asincrónica de las órdenes, es obligatorio el uso de Webhooks para recibir la confirmación de pago del sistema. Culqi + 2
Arquitectura recomendada para tu Agent
Como Function/Tool que el Agent invoca (patrón estándar de tool-calling, igual que ya haces con Strands/Bedrock):
Usuario → Agent → Tool: create_payment_link(amount, description, client)
                     ↓
              POST /orders/v2 (Culqi API, con tu sk_live/sk_test)
                     ↓
              order.id devuelto (ord_live_xxxx)
                     ↓
              Construyes: https://tu-checkout.tudominio.com/pagar?order={order.id}
                     ↓
Agent responde al usuario con ese link
Piezas que necesitas:

Llave secreta de Culqi (sk_test/sk_live desde CulqiPanel → Desarrollo → API Keys) guardada en Key Vault, nunca en el prompt/tool schema.
Una función/tool en tu Agent (definida igual que tus tools de Strands o como Function en Azure AI Foundry Agent Service / Semantic Kernel) que haga el POST a /orders/v2 con amount, currency_code, description, client_details.
Una página de checkout propia (aunque sea mínima, estática) que cargue Culqi Checkout v4 (checkout.culqi.com/js/v4) pasándole el order.id como parámetro — esa página es la que realmente sirve como "el link".
Un Webhook (order.status.changed) apuntando a tu backend para saber si se pagó, ya que la confirmación no llega en el momento sino después.

## Question 3: Lead scoring (hot/warm/cold)
La visión original incluye scoring de leads (§7 de `requirements.md`) ligado a intención de compra/motivación, usado para priorización comercial. ¿Se implementa en este incremento?

A) Sí, implementar el scoring completo (hot/warm/cold) tal como está definido en §7
B) No por ahora — solo persistir la conversación/lead sin scoring; se agrega en un incremento futuro
C) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4: Visibilidad de los leads persistidos
No mencionaste el Backoffice Portal (Superficie B, RF-14/RF-15/RF-16) en esta conversación. Dado que ahora sí se van a persistir leads/conversaciones (Clarification 5), ¿necesitas alguna forma de visualizarlos en este incremento?

A) Diferir completamente — este incremento es solo el agente conversacional + persistencia; sin UI de revisión todavía
B) Se necesita una vista mínima (ej. un endpoint simple de consulta) solo para confirmar que los leads se están guardando correctamente — no el portal completo
C) Se necesita el Backoffice Portal completo (RF-14/RF-15/RF-16) en este mismo incremento
D) Other (please describe after [Answer]: tag below)

[Answer]: A (dejalo anotado como pendiente)
