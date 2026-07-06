# NFR Design Plan — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

## Checklist

- [x] Analizar NFR Requirements (`nfr-requirements.md`, `tech-stack-decisions.md`)
- [x] Generar preguntas sobre patrones (resiliencia, escalabilidad, performance, seguridad)
- [x] Recolectar respuestas
- [ ] Generar artefactos (nfr-design-patterns.md, logical-components.md)

## Preguntas y Respuestas

### P1 — Timeout de confirmación de relajación (BR-03, pendiente explícito del Functional Design)
**[Answer]: 5 minutos** — suficiente para que un usuario real responda sin apuro, sin dejar conexiones colgadas indefinidamente.

### P2 — Scale-to-zero vs mínimo 1 réplica (Container Apps)
**[Answer]: Mínimo 1 réplica siempre activa** — evita cold start que rompería el objetivo de ≤3s de primer delta en la primera request tras un período idle. Costo base bajo (1 réplica pequeña).

### P3 — Patrón de ranking semántico
**[Answer]: Consulta pgvector por request** — más simple, sin cache que invalidar cuando el catálogo cambia; a la escala esperada (decenas de cursos) la latencia es igualmente baja.

### P4 — Política de reintentos para llamadas externas (Azure OpenAI, Foundry Agent)
**[Answer]: Retry simple con backoff exponencial** — máx. 3 intentos (0.5s, 1s, 2s + jitter) antes de responder los errores ya definidos en Functional Design (`embedding_service_unavailable`, `agent_unavailable`). Sin circuit breaker — sobre-ingeniería para el volumen esperado.

## Sin ambigüedades pendientes

Procediendo a generar los artefactos de NFR Design.
