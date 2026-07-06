# NFR Design Plan — agent-service Incremento 2

**Basado en**: NFR Requirements aprobado (`aidlc-docs/construction/agent-service/nfr-requirements/*.md`, secciones "Incremento 2")

## Plan de Diseño (checkboxes)
- [ ] Patrones de resiliencia: retry para llamadas a Mercado Pago, manejo del `asyncio.Future` pendiente (patrón "humano en el loop")
- [ ] Patrones de seguridad: verificación de firma del webhook, idempotencia
- [ ] Componentes lógicos nuevos: `PendingToolCallRegistry`, `PaymentClient`/adaptador Mercado Pago, `WebhookHandler`, `LeadRepository`, `ConversationSessionStore`

## Preguntas de Clarificación

Sin preguntas bloqueantes — las decisiones necesarias ya quedaron resueltas en Functional Design y NFR Requirements (patrón de pausa vía `asyncio.Future`, verificación de firma + re-consulta, idempotencia confirmada, sin exposición pública del webhook en este incremento). Dado el feedback del usuario de no sobre-invertir en performance para esta demo, se reutilizan los patrones ya establecidos en incremento 1 (retry 3x backoff, `minReplicas:1`, sin cache, sin circuit breaker) sin abrir nuevas variantes. Se procede directo a generar los artefactos.
