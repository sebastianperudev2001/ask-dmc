# Unit of Work — Story Map

**Fecha**: 2026-04-28

---

## Mapa Stories → Unidades

| Story | Título | unit-1 | unit-2 | unit-3 | unit-4 | unit-5 |
|---|---|---|---|---|---|---|
| US-01 | Bienvenida e identificación del agente | | ✅ logic | | ✅ UI | |
| US-02 | Captura de datos personales | | ✅ logic | | ✅ localStorage | |
| US-03 | Calificación conversacional del lead | | ✅ QualifyLeadTool | | ✅ UI | |
| US-04 | Recomendación personalizada | | ✅ SearchCoursesTool + GetBrochureUrlTool | | ✅ UI | |
| US-05 | Cierre de venta con link de pago | | ✅ GeneratePaymentLinkTool | ✅ PaymentService + LeadService.finalize | ✅ UI | |
| US-06 | Escalación a contacto humano | | ✅ detect | ✅ LeadService.flag_escalation + NotificationService | ✅ UI | |
| US-09 | Guardrail: Anti-alucinación | | ✅ system prompt + RAG constraint | | | |
| US-10 | Guardrail: Sin promesas no fundamentadas | | ✅ system prompt | | | |
| US-11 | Guardrail: Sin menciones de competidores | | ✅ system prompt | | | |
| US-12 | Guardrail: Scope limitado a ventas | | ✅ system prompt | | | |
| US-13 | Autenticación con Cognito | | | ✅ AuthMiddleware JWT | | ✅ Amplify SDK |
| US-14 | Vista lista de leads | | | ✅ LeadsAPIHandler.list_leads | | ✅ LeadsTable |
| US-15 | Vista detalle del lead | | | ✅ LeadsAPIHandler.get_lead | | ✅ LeadDetail |
| US-16 | Vista de leads escalados | | | ✅ escalated_to_human flag | | ✅ EscalationBanner |
| US-17 | Ingestion de brochures PDF | ✅ pipeline completo | | | | |
| US-18 | Búsqueda semántica de programas | ✅ infrastructure | ✅ SearchCoursesTool runtime | | | |

**Cobertura**: 16/16 stories asignadas ✅

---

## Distribución por Unidad

| Unidad | Stories primarias | Stories de soporte |
|---|---|---|
| **unit-1** ingestion-pipeline | US-17 | US-18 (infra) |
| **unit-2** strands-agent | US-01, US-02, US-03, US-04, US-05, US-06, US-09, US-10, US-11, US-12 | US-18 (runtime) |
| **unit-3** backend-api | US-05 (persistencia), US-06 (SES), US-13 (JWT), US-14, US-15, US-16 | US-01–US-04 (infra de persistencia) |
| **unit-4** frontend-widget | US-01, US-02, US-03, US-04, US-05, US-06 (UI) | |
| **unit-5** frontend-backoffice | US-13, US-14, US-15, US-16 (UI) | |

---

## Stories Multi-Unidad (requieren coordinación)

| Story | Unidades involucradas | Punto de coordinación |
|---|---|---|
| **US-05** Cierre de venta | unit-2 (tool) + unit-3 (PaymentService + persistencia) + unit-4 (UI) | GeneratePaymentLinkTool llama endpoint HTTP de unit-3 |
| **US-06** Escalación | unit-2 (detección) + unit-3 (flag + SES) + unit-4 (UI) | Agente señaliza fin de sesión; backend ejecuta la lógica |
| **US-13** Auth Cognito | unit-3 (JWT validation) + unit-5 (Amplify login form) | JWT emitido por Cognito; validado server-side en unit-3 |
| **US-18** Búsqueda semántica | unit-1 (upsert) + unit-2 (search runtime) | Vector DB es el punto de integración |

---

## Épicas por Unidad

| Epic | Unidades principales |
|---|---|
| E1 — Flujo Conversacional | unit-2 (lógica) + unit-4 (UI) + unit-3 (persistencia/pagos) |
| E2 — Guardrails | unit-2 (system prompt + RAG) |
| E3 — Backoffice Portal | unit-3 (API) + unit-5 (UI) |
| E4 — Knowledge Base | unit-1 (ingestion) + unit-2 (search runtime) |
