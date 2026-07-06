# Requirements Document — Agent-Service Incremento 2: Chat Conversacional + Integración Frontend

**Versión**: 1.0
**Fecha**: 2026-07-06
**Origen**: Continuación de `requirements.md` (v1.1, aprobado 2026-04-28) tras el pivote de plataforma DIV-10 + 3 rondas de clarificación con el usuario
**Estado**: Aprobado pendiente

---

## 1. Intent Analysis

| Campo | Valor |
|---|---|
| **Solicitud** | "Necesitamos integrar el frontend con el backend de services/agent-service/ apps/chat/" |
| **Tipo** | Enhancement — extiende `agent-service` (unit-2 redefinida, Azure) más allá de su incremento 1 (catálogo + recomendación) e integra `apps/chat` con él |
| **Scope** | Cross-system — frontend (Next.js/Effect) + backend (Azure AI Foundry + Agent Framework) + nuevo proveedor de pagos (Culqi) |
| **Complejidad** | Complex — tool-calling conversacional, widget dinámico en frontend, checkout de pago externo con webhook asíncrono, persistencia de sesión vía Foundry Memory, lead scoring |
| **Profundidad** | Comprehensive (elevada desde Standard tras 2 rondas de clarificación que revelaron alcance real) |

**Relación con Inception original**: La visión de `requirements.md` §5.1 (RF-01 a RF-11) describía el flujo conversacional completo del Chat Widget bajo AWS/Strands. DIV-10 pivoteó la plataforma a Azure y limitó el incremento 1 de `agent-service` a solo catálogo + recomendación por perfil. **Este documento cubre el incremento 2**, que retoma la visión conversacional completa (identificación, calificación, recomendación, pago, escalación) re-plataformada en Azure, con cambios de diseño respecto al original (ver §7 Divergencias).

**User Stories**: Se **omite** re-ejecutar la etapa de User Stories para este incremento — el comportamiento orientado al usuario (flujo de venta conversacional, escalación, pago) ya está descrito desde la perspectiva de usuario en `aidlc-docs/inception/user-stories/stories.md` (aprobado 2026-04-28) para la visión original. Este incremento es una reimplementación técnica de esa visión ya storyficada, no una funcionalidad nueva de cara al usuario.

---

## 2. Resumen del Flujo

```
Usuario escribe libremente en apps/chat
        │
        ▼
Agente (system prompt: asesor de ventas) responde en streaming
        │
        ├─ Detecta que necesita datos de perfil → invoca tool "collect_profile_data"
        │       └─ Frontend detecta el tool-call en el stream → muestra widget
        │              └─ Usuario completa (presupuesto, duración, background, stack)
        │                     └─ Frontend envía profile_data_submitted → agente continúa
        │
        ├─ Recomienda curso(s) del catálogo (reusa lógica de incremento 1: filtros duros + ranking semántico)
        │       └─ Si no hay match exacto → agente ofrece conversacionalmente relajar filtros (texto plano, sin widget)
        │
        ├─ Detecta intención de compra → invoca tool "create_payment_link"
        │       └─ Backend crea preferencia en Mercado Pago (Checkout Pro) → responde con init_point (URL de pago ya hospedada)
        │              └─ Webhook de Mercado Pago (type=payment, firma x-signature verificada) confirma pago → actualiza lead en Postgres
        │
        └─ Usuario pide hablar con humano → agente responde conversacionalmente (RF-09 style) → persiste
                escalated_to_human=true (sin notificación activa en este incremento)

Toda la conversación persiste vía Azure AI Foundry Agent Memory (thread), recuperable entre refreshes/sesiones.
Al cierre de la conversación, se persiste el lead (perfil, motivación, score, resumen) en Postgres.
```

---

## 3. Requerimientos Funcionales

### 3.1 Transporte y Protocolo

**RF-I01: Endpoint unificado de chat**
El endpoint WebSocket existente `/ws/recommendation` se renombra a `/ws/chat` y se extiende para aceptar mensajes de chat libre además del flujo estructurado de incremento 1. El agente decide internamente cuándo responder libremente (asesor conversacional) y cuándo invocar tools.

**RF-I02: Mensajes de usuario libres**
El cliente envía mensajes de tipo `user_message` con texto libre (sin estructura obligatoria), en cualquier punto de la conversación.

**RF-I03: Tool-calling detectable en streaming**
Cuando el agente invoca un tool (`collect_profile_data`, `create_payment_link`), el evento de tool-call debe ser distinguible en el stream WS de los tokens de texto normal, para que el frontend pueda reaccionar (mostrar widget) sin esperar a que termine el mensaje.

**RF-I04: Respuesta estructurada del widget**
El frontend envía un mensaje `profile_data_submitted` con los campos `budget`, `max_duration_weeks`, `professional_background`, `desired_stack` (mismo shape que `RecommendationRequest` de incremento 1) como resultado del tool call. El backend continúa la conversación usando esos datos.

**RF-I05: Persistencia de sesión (Foundry Memory)**
La conversación se asocia a un thread de Azure AI Foundry Agent Memory. El cliente guarda el identificador de thread (ej. `localStorage`) para recuperar la conversación completa tras un refresh o cierre de pestaña, análogo al patrón de re-identificación de RF-03 original.

### 3.2 Conversación y Ventas (retoma RF-01 a RF-07, RF-09 originales)

**RF-I06: Rol de asesor de ventas conversacional**
El system prompt del agente debe identificarlo como IA, guiarlo a identificar al usuario, calificarlo (perfil, motivación, presupuesto, duración) de forma conversacional (una pregunta a la vez, sin formularios de texto — el único formulario es el widget de RF-I03/04), detectar motivación (mismas 5 categorías de §5.2 RF-06 original: growth/salary/company_requirement/academic/undefined), recomendar curso(s), e intentar cerrar la venta.

**RF-I07: Recomendación reutiliza lógica de incremento 1**
La recomendación de cursos reutiliza el filtro duro (presupuesto/duración) + ranking semántico (background/stack) ya implementado en incremento 1. Cuando no hay match exacto, el agente ofrece conversacionalmente relajar los filtros (texto plano); el usuario responde escribiendo, sin UI especial.

**RF-I08: Escalación a humano (alcance reducido respecto al original)**
Si el usuario pide hablar con una persona, el agente responde que alguien del equipo se pondrá en contacto (sin dar teléfono/WhatsApp) y persiste `escalated_to_human=true` en el lead. **A diferencia del RF-09 original, este incremento NO envía notificación activa al equipo comercial** (no hay equivalente de Amazon SES decidido aún) — queda como pendiente explícito para un incremento futuro.

**RF-I09: Guardrails heredados**
Se mantienen sin cambios los guardrails RF-12, RF-13, RF-17, RF-18 del documento original (anti-alucinación, sin promesas no fundamentadas, sin mención de competidores, scope limitado a ventas).

### 3.3 Pago (RF-08 original, restaurado — ver DIV-11)

**RF-I10: Tool de generación de link de pago (Mercado Pago Checkout Pro)**
Cuando el usuario expresa intención de compra, el agente invoca el tool `create_payment_link(amount, description, client_details)`, que:
1. Crea una preferencia de pago vía la API de Preferencias de Mercado Pago (Checkout Pro)
2. Recibe de vuelta `init_point` (sandbox: `sandbox_init_point`) — una URL de checkout **ya hospedada por Mercado Pago**, sin necesidad de página de checkout propia
3. Retorna esa URL al agente, quien la comparte con el usuario en el chat

**RF-I11: Sin página de checkout propia**
A diferencia del enfoque descartado con Culqi, Mercado Pago Checkout Pro no requiere una página propia — `init_point`/`sandbox_init_point` es directamente el link de pago funcional a compartir con el usuario.

**RF-I12: Webhook de confirmación de pago**
`agent-service` expone un endpoint webhook que recibe la notificación de Mercado Pago (`type=payment`) en la `notification_url` configurada al crear la preferencia. El webhook:
1. Verifica la firma HMAC (`x-signature` + `x-request-id`) contra el secreto de la aplicación — mecanismo documentado oficialmente por Mercado Pago
2. Usa el `data.id` (payment id) recibido para consultar `GET /v1/payments/{id}` y obtener el estado autoritativo del pago
3. Actualiza el registro del lead (`payment_link_sent`, estado de pago) en Postgres

El comportamiento de notificar al usuario en un chat ya cerrado/inactivo se define en Functional Design (no bloqueante para este documento).

**RF-I13: Secretos de Mercado Pago**
El access token de Mercado Pago (sandbox/test) y el secreto de verificación de firma del webhook se almacenan en Azure Key Vault, nunca en el system prompt ni en el schema del tool.

### 3.4 Persistencia y Scoring (reemplaza RF-10 original, retoma §7)

**RF-I14: Persistencia de leads en Postgres**
Se reemplaza el diseño original de DynamoDB (`dmc-leads`, `dmc-conversations`, §6) por tablas equivalentes en el Postgres ya existente de `agent-service`. Estructura conceptual equivalente: lead (id, nombre, email, perfil, motivación, programas recomendados, score, `escalated_to_human`, estado de pago) + conversación (mensajes con rol y contenido, o referencia al thread de Foundry Memory).

**RF-I15: Lead scoring**
Se implementa el scoring hot/warm/cold definido en §7 del documento original, sin cambios en los criterios (intención de compra, motivación definida, fit de perfil, urgencia, datos completos).

### 3.5 Frontend

**RF-I16: UI de recomendación de curso**
El componente `SourceChips` (actualmente muestra `Source{course, section, distance}`, forma de chunk RAG) se reemplaza por una nueva UI de tarjetas de recomendación de curso, mostrando al menos nombre del curso y score de similitud; se evalúa en Functional Design si se agregan precio/duración.

**RF-I17: Widget de recolección de datos**
Nuevo componente en `apps/chat` que se renderiza al detectar el tool-call `collect_profile_data` en el stream, permite al usuario ingresar presupuesto, duración máxima, background profesional y stack deseado, y al enviarlo dispara el mensaje `profile_data_submitted` (RF-I04).

**RF-I18: Fuera de alcance — Backoffice Portal**
El Backoffice Portal (Superficie B, RF-14/RF-15/RF-16 original) queda **explícitamente fuera de alcance** de este incremento. No se construye ninguna UI de revisión de leads. Anotado como pendiente para un incremento futuro.

---

## 4. Requerimientos No Funcionales

### 4.1 Despliegue
Este incremento se alcanza y verifica **solo en entorno de desarrollo local** (frontend `localhost:3000`, backend `localhost:8000`). No se implementa CORS ni autenticación adicional para producción en este incremento — ambos quedan pendientes cuando se decida desplegar.

### 4.2 Seguridad
- Access token y secreto de verificación de Mercado Pago en Azure Key Vault (RF-I13), nunca en código ni prompts.
- Verificación de autenticidad del webhook de Mercado Pago antes de procesar (RF-I12) — firma HMAC (`x-signature`/`x-request-id`), mecanismo documentado oficialmente por Mercado Pago; se re-consulta además `GET /v1/payments/{id}` para confirmar el estado autoritativo antes de marcar el pago como confirmado.
- El resto de guardrails de seguridad del proyecto (SECURITY-01 a SECURITY-15, extensión ya habilitada) aplican también a este incremento; SECURITY-08 (excepción de no-autenticación en el WS, ya aceptada para incremento 1) se mantiene para `/ws/chat` dado que el alcance de despliegue sigue siendo local.

### 4.3 Testing
Property-Based Testing (extensión ya habilitada, full enforcement) aplica al nuevo código de este incremento, igual que en incremento 1.

---

## 5. Fuera de Alcance (explícito)

- Backoffice Portal completo (RF-14/RF-15/RF-16) — diferido.
- Notificación activa de escalación a humano (reemplazo de RF-09/SES) — diferido, solo se persiste el flag.
- CORS / topología de despliegue en la nube para este flujo — diferido.
- Autenticación de usuarios finales en el chat — no solicitada, no se agrega.

---

## 6. Resumen de Decisiones Clave (de las 3 rondas de clarificación)

| Decisión | Elegida |
|---|---|
| Enfoque de integración | Chat libre + tool-calling + widget detectado en streaming (no formulario estructurado, no HTTP adapter) |
| Endpoint | Unificar en `/ws/chat` (renombrado desde `/ws/recommendation`), mismo entry point |
| Respuesta del widget | Mensaje WS estructurado `profile_data_submitted` |
| Persistencia de sesión | Azure AI Foundry Agent Memory (thread persistente entre refreshes) |
| Relajar filtros | Conversacional (texto plano), sin widget |
| Alcance del incremento | Identificación + calificación + recomendación + pago + escalación (persistencia de flag, sin notificación) |
| Proveedor de pago | Mercado Pago Checkout Pro (API de Preferencias → `init_point`, sin checkout propio) + webhook con verificación de firma HMAC — se descartó Culqi (requería negocio formal) tras evaluarlo en Functional Design |
| Notificación de escalación | Diferida — solo se persiste el flag |
| Lead scoring | Sí, implementar completo (hot/warm/cold, §7 original) |
| Visibilidad de leads | Diferida completamente (sin backoffice ni vista mínima) |
| Almacenamiento de leads | Postgres (reemplaza DynamoDB original) |
| Alcance de despliegue | Solo local, sin CORS/producción |

---

## 7. Divergencias respecto a Inception Original (nuevas, a registrar en aidlc-state.md)

| # | Decisión original | Divergencia de este incremento | Rationale |
|---|---|---|---|
| DIV-11 | RF-08: Mercado Pago Checkout API (sandbox) | **REVERTIDO** — se evaluó Culqi (Orders API v2 + checkout propio) durante Requirements Analysis, pero se descartó en Functional Design (2026-07-06: "necesito un negocio oficial") y se confirmó Mercado Pago, ahora vía Checkout Pro (API de Preferencias → `init_point`, sin checkout propio) + webhook con verificación de firma HMAC oficial (`x-signature`) | Culqi exige una cuenta de negocio formal que el usuario no tiene; Mercado Pago es accesible sin ese requisito y su Checkout Pro simplifica la arquitectura (no requiere página de checkout propia, sí tiene firma de webhook documentada oficialmente) |
| DIV-12 | RF-09: notificación de escalación via Lambda + Amazon SES | Sin notificación activa en este incremento — solo se persiste `escalated_to_human=true` | No hay equivalente decidido aún en Azure (Azure Communication Services, Slack/Teams, etc.); usuario eligió diferir explícitamente en vez de asumir un reemplazo |
| DIV-13 | §6: persistencia de leads/conversaciones en DynamoDB (`dmc-leads`, `dmc-conversations`) | Persistencia en Postgres (mismo motor ya usado por `agent-service` para el catálogo) | Consistente con el pivote de plataforma a Azure (DIV-10); evita introducir DynamoDB en una arquitectura Azure |
| DIV-14 | RF-11: streaming vía WebSocket con protocolo implícito de un solo turno (visión original) / incremento 1: `recommendation_request` estructurado de un solo turno | Protocolo conversacional multi-turno con tool-calling (`collect_profile_data`, `create_payment_link`) sobre el mismo endpoint renombrado `/ws/chat` | Decisión explícita del usuario: mantener chat libre como experiencia principal, usando tools para recolectar datos estructurados solo cuando el agente lo determina necesario |

---

## 8. Próximos Pasos Sugeridos

Dada la complejidad (nuevos tools, nuevo proveedor de pago externo con webhook asíncrono, nueva persistencia de sesión, cambios de componentes en frontend), se recomienda que **Workflow Planning** determine re-ejecutar, para este incremento:
- **Functional Design** (unit-2 agent-service): definir tools, schemas de mensajes WS, lógica de scoring, modelo de datos Postgres para leads/conversaciones, mecánica del webhook de Culqi
- **NFR Requirements / NFR Design**: revisar si Culqi + Key Vault + Foundry Memory introducen nuevos NFRs o patrones
- **Infrastructure Design**: Key Vault, posible endpoint HTTP adicional (webhook) junto al WS existente
- **Code Generation**: para agent-service (incremento 2) y para apps/chat (widget, tarjetas de recomendación, página de checkout)
- **Application Design**: probablemente NO necesario — no se agregan nuevas unidades/servicios, solo componentes dentro de las 2 unidades existentes
