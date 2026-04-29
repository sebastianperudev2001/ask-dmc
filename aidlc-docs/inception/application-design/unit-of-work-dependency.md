# Unit of Work — Dependency Matrix

**Fecha**: 2026-04-28

---

## Matriz de Dependencias

| Unidad | Depende de | Tipo de dependencia |
|---|---|---|
| **unit-1** ingestion-pipeline | — (ninguna) | — |
| **unit-2** strands-agent | unit-1 (Vector DB poblado) | Runtime: necesita knowledge base para responder |
| **unit-3** backend-api | unit-2 (AgentCore Runtime disponible) | Runtime: invoca agente via SDK |
| **unit-4** frontend-widget | unit-3 (WebSocket API disponible) | Runtime: conecta al WebSocket endpoint |
| **unit-5** frontend-backoffice | unit-3 (REST API disponible) | Runtime: consume endpoints REST + Cognito |

---

## Orden de Construcción

```
Orden    Unidad                  Bloqueada por        Puede parallelizarse con
─────    ────────────────────    ─────────────────    ────────────────────────
  1      ingestion-pipeline      —                    —
  2      strands-agent           unit-1 (runtime)     —
  3      backend-api             unit-2 (runtime)     —
  4      frontend-widget         unit-3 (runtime)     unit-5
  5      frontend-backoffice     unit-3 (runtime)     unit-4
```

**unit-4 y unit-5 pueden construirse en paralelo** una vez unit-3 esté disponible (o con mock del API).

---

## Dependencias de Infraestructura AWS por Unidad

| Servicio AWS | unit-1 | unit-2 | unit-3 | unit-4 | unit-5 |
|---|---|---|---|---|---|
| Amazon Bedrock | ✅ LLM + Embeddings | ✅ LLM (via LLMProvider) | — | — | — |
| AgentCore Runtime | — | ✅ Deploy | ✅ Invoke | — | — |
| AgentCore Memory | — | ✅ | — | — | — |
| DynamoDB `dmc-leads` | — | — | ✅ | — | ✅ (read via API) |
| DynamoDB `dmc-conversations` | — | — | ✅ | — | ✅ (read via API) |
| Amazon S3 | ✅ Read PDFs | ✅ Presigned URLs | ✅ Presigned URLs | — | — |
| Vector DB (TBD) | ✅ Upsert | ✅ Search | — | — | — |
| API Gateway WebSocket | — | — | ✅ | ✅ Client | — |
| API Gateway REST | — | — | ✅ | — | ✅ Client |
| AWS Lambda | — | — | ✅ | — | — |
| Amazon SES | — | — | ✅ | — | — |
| AWS Cognito | — | — | ✅ JWT validate | — | ✅ Amplify |
| Vercel | — | — | — | ✅ Deploy | ✅ Deploy |
| Mercado Pago API | — | — | ✅ | — | — |

---

## Dependencias de Código Compartido

| Elemento compartido | unit-1 | unit-2 | unit-3 | unit-4 | unit-5 |
|---|---|---|---|---|---|
| `LLMProvider` Protocol | ✅ (own copy) | ✅ (own copy) | — | — | — |
| `VectorDBRepository` Protocol | ✅ (own copy) | ✅ (own copy) | — | — | — |
| `BedrockLLMProvider` impl | ✅ | ✅ | — | — | — |
| `S3Repository` impl | ✅ | ✅ | ✅ | — | — |
| `packages/ui` (Badge, tokens) | — | — | — | ✅ | ✅ |

> **Nota**: LLMProvider y VectorDBRepository se duplican entre unit-1 y unit-2 por simplicidad de deployment. Cada servicio Python es un package independiente. Si en el futuro se quiere compartir, se extrae a `packages/shared-python/`.

---

## Riesgos de Dependencia

| Riesgo | Unidades afectadas | Mitigación |
|---|---|---|
| Vector DB technology TBD | unit-1, unit-2 | Decidir en NFR Design de unit-1; usar VectorDBRepository Protocol para aislar |
| AgentCore Runtime setup tiempo | unit-2 | Testear tools con mocks de AgentCore en tests unitarios |
| Mercado Pago sandbox credentials | unit-3 | Usar placeholder token; el link generado es mock en demo |
| WebSocket timeout 29s en Lambda | unit-3 | Target ≤3s primer token; monitorear en integration tests |
