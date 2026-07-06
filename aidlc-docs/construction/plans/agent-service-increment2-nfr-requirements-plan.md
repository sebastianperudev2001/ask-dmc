# NFR Requirements Plan — agent-service Incremento 2

**Basado en**: Functional Design aprobado (`aidlc-docs/construction/agent-service/functional-design/*.md`, secciones "Incremento 2")

## Contexto heredado de incremento 1 (no se repite, sigue vigente salvo lo indicado)
Azure Container Apps + Postgres Flexible Server/pgvector + Foundry Persistent Agent, East US, best-effort sin SLA, SECURITY-11 (rate limiting) como riesgo ya aceptado, SECURITY-08 (WS público sin auth) como excepción ya aceptada.

## Plan de Evaluación (checkboxes)

- [ ] Performance: impacto de la conversación multi-turno + tool-calling en el objetivo de latencia existente (≤3s primer delta)
- [ ] Seguridad: extender Key Vault a los nuevos secretos (Mercado Pago access token + secreto de verificación de webhook); PII real ahora persistida (nombre/email del lead)
- [ ] **Conflicto detectado — exposición del webhook vs. alcance "solo local"**: ver Pregunta 1 abajo, es bloqueante para Infrastructure Design
- [ ] Idempotencia del webhook (Mercado Pago puede reintentar notificaciones)
- [ ] Testing: extender Hypothesis/PBT a las nuevas reglas de negocio (BR-16 a BR-21)
- [ ] Observabilidad: nuevas métricas (tasa de éxito de tool-calls, latencia del webhook, conversaciones con pago confirmado)

## Preguntas de Clarificación

### Question 1 (BLOQUEANTE): Cómo exponer el webhook de Mercado Pago dado el alcance "solo local"
Requirements Analysis decidió que este incremento se verifica **solo en desarrollo local** (`localhost:8000`, sin CORS/despliegue). Pero un webhook, por definición, necesita ser alcanzable **desde internet** — los servidores de Mercado Pago no pueden hacer POST a `localhost`. Esto es un conflicto real que necesita resolverse antes de Infrastructure Design:

A) Usar un túnel temporal (ej. `ngrok`, ntfy, Cloudflare Tunnel) apuntando a `localhost:8000` solo durante las sesiones de prueba manual — sin cambiar el alcance de despliegue decidido, el webhook real de Mercado Pago sandbox sí llega
B) Desplegar únicamente esta pieza (el endpoint webhook) a Azure Container Apps para tener una URL pública estable, mientras el resto del flujo se sigue probando en local
C) No probar el webhook contra Mercado Pago real en este incremento — simular la llamada del webhook manualmente (ej. con `curl`/script) contra `localhost`, verificando la lógica de verificación de firma y actualización de estado, sin depender de que Mercado Pago realmente lo alcance
D) Other (please describe after [Answer]: tag below)

[Answer]: O sea como estamos probando en local, podemos llamar al webhook de sandbox de mercado pago normal 

### Question 2: Idempotencia del webhook
Mercado Pago puede reintentar la entrega de una notificación (ej. si tu servidor no responde 200 a tiempo). Propongo que el webhook sea idempotente: si el `Lead` ya tiene `payment_confirmed=true` para ese `preference_id`, un webhook repetido simplemente responde 200 sin volver a procesar. ¿De acuerdo?

A) Sí, proceder con ese comportamiento idempotente
B) Other (please describe after [Answer]: tag below)

[Answer]: A
