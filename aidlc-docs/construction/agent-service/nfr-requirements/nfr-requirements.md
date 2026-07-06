# NFR Requirements — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

---

## 1. Performance
- Primer token/delta de respuesta del agente: ≤ 3 segundos (heredado de requirements.md §9.1, aplica igual sobre Azure) — medido desde que el backend recibe `recommendation_request` (o `relax_filters_response` confirmando) hasta el primer `recommendation_delta` emitido.
- El pipeline de filtro SQL + embedding de perfil + ranking pgvector (pasos 2-7) debe completarse en el presupuesto de tiempo que deja ese objetivo de 3s antes de invocar al agente — implica que el filtro/ranking debe ser rápido (índices en `price`, `duration_weeks`; índice HNSW/IVFFlat en `embedding`).
- Modelo de chat: `gpt-5.4-nano` — elegido explícitamente por latencia baja además de costo (ver tech-stack-decisions.md).

## 2. Disponibilidad
- Best-effort, sin SLA formal — proyecto de curso/demo (heredado de requirements.md §9.2). No se requiere Multi-AZ, réplicas de lectura, ni failover automático en este incremento.
- Azure Container Apps con auto-scaling (incluye scale-to-zero) para el backend WS — equivalente directo al AWS App Runner ya decidido en Inception para otros componentes.

## 3. Escalabilidad
- Volumen esperado: bajo (demo/curso, no tráfico de producción real) — no se dimensiona para concurrencia alta.
- Azure Container Apps escala horizontalmente por defecto si el volumen crece; no se requiere configuración especial en este incremento.
- Embeddings de catálogo pre-calculados (BR-06) mantienen el costo de Azure OpenAI acotado independientemente del volumen de recomendaciones.

## 4. Seguridad (extensión Security Baseline — full enforcement)

| Regla | Estado | Justificación |
|---|---|---|
| SECURITY-01 (encripción at-rest/in-transit) | Compliant | Azure Database for PostgreSQL Flexible Server: encripción at-rest habilitada por defecto (managed key); conexión forzada por TLS 1.2+. Azure OpenAI/Foundry: TLS en tránsito por defecto. |
| SECURITY-02 (logging de intermediarios de red) | Compliant | Azure Container Apps: logging de ingress habilitado hacia Log Analytics Workspace. |
| SECURITY-03 (logging de aplicación) | Compliant | Logging estructurado JSON (heredado de requirements.md §9.6) con request/connection ID, level, timestamp; sin PII (no se loguea `professional_background`/`desired_stack` en texto plano, solo un hash o longitud si se necesita debug). Enviado a Azure Monitor/Log Analytics. |
| SECURITY-04 (headers HTTP de seguridad) | N/A | `agent-service` no sirve HTML — es un backend WebSocket puro. Aplicable al frontend (fuera de alcance de esta unidad). |
| SECURITY-05 (validación de input) | Compliant | `RecommendationRequest` valida tipos y obligatoriedad (BR-09); `budget`/`max_duration_weeks` con bounds numéricos razonables; queries a Postgres parametrizadas (nunca concatenación de strings) para filtro y pgvector. |
| SECURITY-06 (least privilege) | Compliant (a implementar en Infra Design) | Managed Identity de Container Apps con permisos acotados: acceso de solo lectura/escritura a la base de datos específica, sin permisos amplios sobre la suscripción. Detalle concreto en Infrastructure Design. |
| SECURITY-07 (config de red restrictiva) | Compliant (a implementar en Infra Design) | Firewall de Azure Postgres restringido a las IPs salientes de Container Apps (o VNet integration/private endpoint); sin acceso público abierto a `0.0.0.0/0`. |
| SECURITY-08 (control de acceso a nivel de aplicación) | **Excepción documentada, no bloqueante** | Endpoint WS es explícitamente público, sin autenticación — decisión ya tomada para el chat widget de visitantes anónimos (no hay usuarios ni recursos "propios" que proteger por IDOR en este incremento: no hay login, no hay recursos por ID de usuario). Cumple el carve-out explícito de la regla ("unless explicitly marked as public"). |
| SECURITY-09 (hardening) | Compliant | Mensajes de error al cliente son genéricos (`no_recommendation` con `reason` codificado, no stack traces); sin credenciales default. |
| SECURITY-10 (supply chain) | Compliant (a verificar en Code Generation) | `requirements.txt`/`poetry.lock` con versiones fijadas; se agregará `pip-audit` (o Dependabot) al pipeline en Build and Test. |
| SECURITY-11 (diseño seguro / rate limiting) | **NO COMPLIANT — riesgo aceptado explícitamente por el usuario** | El endpoint WS es público y sin auth (SECURITY-08 exception); sin rate limiting en este incremento. El usuario decidió explícitamente no implementarlo ahora ("sin rate limiting por ahora"). Riesgo: abuso del endpoint (spam de `recommendation_request`, costo de Azure OpenAI por llamadas excesivas). **Queda como pendiente de backlog, no oculto.** |
| SECURITY-12 (auth y credenciales) | N/A | No hay autenticación de usuarios en este incremento (decisión ya tomada, consistente con SECURITY-08). |
| SECURITY-13 (integridad de software/datos) | N/A | Sin deserialización de datos complejos no confiables (solo JSON validado de `RecommendationRequest`); sin persistencia, por lo que no aplica auditoría de cambios de datos (BR-08). |
| SECURITY-14 (alerting/monitoring) | Compliant (a implementar en Infra Design) | Azure Monitor con alertas sobre fallas del servicio de embeddings/agente (ver manejo de errores del Functional Design); retención de logs ≥ 90 días en Log Analytics Workspace. |
| SECURITY-15 (manejo de excepciones) | Compliant | Manejo de errores explícito ya definido en Functional Design (Sección 4): fallas de embeddings/agente responden con mensajes seguros y genéricos, nunca fallan "abiertos" mostrando datos parciales o inventados. |

**Resumen**: 1 hallazgo de seguridad bloqueante por defecto (SECURITY-11) queda como **riesgo aceptado explícitamente por el usuario** para este incremento — no bloquea el avance a NFR Design, pero se mantiene visible en este documento y en audit.md, no se marca como resuelto.

## 5. Testing (extensión Property-Based Testing — full enforcement)

| Regla | Estado | Nota |
|---|---|---|
| PBT-01 (identificación de propiedades) | Compliant | Sección "Testable Properties" agregada retroactivamente a `business-logic-model.md` (P1-P8) — ver audit.md, corrección de cumplimiento. |
| PBT-09 (selección de framework) | Compliant | **Hypothesis** (Python) — ver tech-stack-decisions.md. Soporta generadores custom, shrinking automático, reproducibilidad por seed; se integra con `pytest`. |
| PBT-02 a PBT-08, PBT-10 | Diferido a Code Generation | Aplican durante la planeación/generación de código (ver enforcement table de la extensión) — no evaluables aún en esta etapa. |

## 6. Observabilidad
- Logging estructurado JSON (heredado de requirements.md §9.6), sin PII, enviado a Azure Monitor / Log Analytics Workspace.
- Retención de logs: 90 días mínimo (SECURITY-14).
- Dashboard/alertas mínimas para este incremento: tasa de error del servicio de embeddings, tasa de error del agente, latencia del primer delta (para verificar el objetivo ≤3s).

## 7. Mantenibilidad
- Backend en Python (consistente con el resto del proyecto — `unit-1` y el `strands-agent` superseded también eran Python), usando Microsoft Agent Framework Python SDK.
- Separación de responsabilidades: lógica de filtro/relajación/ranking en módulos de dominio puros (testeables con Hypothesis sin necesidad de levantar Postgres/Azure OpenAI reales — inyección de dependencias sobre `ports` similar al patrón ya usado en `unit-1`).

---

## Fuera de alcance de NFR en este incremento
- Autenticación/autorización de usuarios (SECURITY-08/12) — decisión ya tomada, no es una NFR pendiente, es un scope boundary.
- Alta disponibilidad / multi-región / DR — no aplica a un demo best-effort.
- Rate limiting (SECURITY-11) — pendiente, riesgo aceptado (ver Sección 4).

---

# Incremento 2 — Chat conversacional + tool-calling + pago (Mercado Pago) + persistencia

**Fecha**: 2026-07-06

## 8. Performance
- El objetivo de ≤3s para el primer delta (Sección 1) sigue aplicando específicamente al flujo de recomendación (paso 8 del business-logic-model). La conversación libre de chat (identificación, calificación conversacional) es best-effort, sin SLA de latencia — consistente con la disponibilidad general del proyecto (Sección 2).
- El patrón "humano en el loop" de `collect_profile_data` (el tool queda en `await` hasta que el usuario responde el widget) introduce una espera potencialmente larga (segundos a minutos) que es **esperada e intencional**, no una regresión de performance — no cuenta contra ningún objetivo de latencia del agente.
- `create_payment_link` agrega una llamada de red síncrona a la API de Mercado Pago dentro del tool — sin objetivo de latencia estricto (best-effort), pero debe tener un timeout razonable (ver Sección 9, manejo de errores heredado de BR-18) para no colgar la conversación indefinidamente si Mercado Pago no responde.

## 9. Seguridad — extensiones (Security Baseline, full enforcement)

| Regla | Estado | Justificación |
|---|---|---|
| SECURITY-01 (encripción at-rest/in-transit) | Compliant | Ya cubierto por Postgres Flexible Server (Sección 4 original); ahora aplica también a datos reales de PII (`Lead.name`, `Lead.email`) que antes no existían (BR-08 override). |
| SECURITY-03 (logging sin PII) | Compliant (reforzado) | A diferencia de incremento 1 (sin persistencia), ahora sí hay PII real en la base de datos — se refuerza: nunca loguear `name`/`email`/`professional_background` en texto plano en logs de aplicación, solo IDs (`lead_id`, `service_session_id`). |
| SECURITY-06 (least privilege) | Compliant (a implementar en Infra Design) | Extiende a los 2 nuevos secretos de Key Vault (access token de Mercado Pago, secreto de verificación de firma del webhook) — mismo principio de Managed Identity con acceso acotado ya decidido en incremento 1. |
| SECURITY-11 (rate limiting) | Riesgo ya aceptado (sin cambios) | El nuevo endpoint webhook hereda la misma decisión — sin rate limiting explícito en este incremento; mitigado parcialmente por la verificación de firma (Sección 10 del business-logic-model) que rechaza payloads no auténticos antes de procesar. |

## 10. Testing de Webhook — sin exposición pública en este incremento
Decisión explícita del usuario: el webhook **no** se expone públicamente en este incremento (sin túnel ni despliegue a Container Apps). Se verifica con un script de simulación manual (análogo a `scripts/manual_ws_check.py` de incremento 1) que envía un payload realista de Mercado Pago directamente a `localhost:8000/webhooks/mercadopago`, firmado con el mismo secreto configurado localmente — cubre la lógica de verificación de firma + re-consulta + actualización de estado, sin depender de que Mercado Pago realmente alcance el servidor. Queda como pendiente explícito de un incremento futuro: exponer el webhook (túnel o despliegue real) para una prueba end-to-end con Mercado Pago real.

## 11. Idempotencia del webhook
Confirmado (Question 2 = A): si el `Lead` ya tiene `payment_confirmed=true` para el `preference_id` recibido, un webhook repetido responde 200 sin reprocesar — necesario porque Mercado Pago reintenta notificaciones no confirmadas.

## 12. Testing (extensión Property-Based Testing)
Las nuevas reglas BR-16 a BR-21 (business-rules.md) son candidatas a PBT donde aplique determinismo verificable (ej. BR-17 lead scoring — ver P9/P10 en business-logic-model.md). BR-16 (decisión del LLM de invocar un tool) y BR-19 (persistencia de escalación) no son propiedades formalmente verificables por PBT — se cubren con tests de integración dirigidos.

## 13. Observabilidad — nuevas métricas
- Tasa de éxito/fracaso de `create_payment_link` (llamadas a Mercado Pago).
- Latencia del webhook (recepción → confirmación de pago en Postgres).
- Conteo de conversaciones con `payment_confirmed=true` vs. `payment_link_sent=true` sin confirmar (funnel de conversión).
- Conteo de `escalated_to_human=true` (para dimensionar la necesidad futura de notificación activa, DIV-12).

---

## Fuera de alcance de NFR — Incremento 2
- Exposición pública real del webhook (túnel/despliegue) — diferido, ver Sección 10.
- Notificación activa de escalación (Azure Communication Services/Slack/Teams) — diferido (DIV-12).
- Cualquier requisito de cumplimiento normativo formal sobre PII (ej. derecho al olvido) — proyecto de demo/curso, no se agrega en este incremento.
