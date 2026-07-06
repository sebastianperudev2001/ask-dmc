# Infrastructure Design Plan — agent-service (Azure) — Incremento 1

**Fecha**: 2026-07-05

## Checklist

- [x] Analizar Functional Design + NFR Design
- [x] Generar preguntas (IaC tool, red de Postgres, tier de DB, ambientes)
- [x] Recolectar respuestas
- [ ] Generar artefactos (infrastructure-design.md, deployment-architecture.md)

## Preguntas y Respuestas

### P1 — Herramienta de IaC
**[Answer]: Terraform** — el usuario prefirió Terraform sobre Bicep (recomendado por simplicidad nativa de Azure), posiblemente pensando en tooling consistente si en el futuro se gestiona infra multi-cloud (unit-1 en AWS + agent-service en Azure).

### P2 — Red de Postgres
**[Answer]: Acceso público + firewall restringido** a las IPs salientes de Container Apps (vía NAT/IP estática) — cumple SECURITY-07 sin el costo/complejidad de una VNet + Private Endpoint completa.

### P3 — Tier de Postgres Flexible Server
**[Answer]: Burstable B1ms** — el tier más barato, adecuado para el volumen bajo esperado (demo/curso).

### P4 — Ambientes
**[Answer]: Uno solo (prod/demo)** — un único resource group, consistente con el alcance best-effort del proyecto.

## Sin ambigüedades pendientes

Procediendo a generar los artefactos de Infrastructure Design.
