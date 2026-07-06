# Infrastructure Design Plan — agent-service Incremento 2

**Basado en**: NFR Design aprobado (`aidlc-docs/construction/agent-service/nfr-design/*.md`, secciones "Incremento 2")

## Plan de Diseño (checkboxes)
- [ ] Mapeo de componentes lógicos nuevos → recursos Azure existentes (sin recursos nuevos: mismo Container App, mismo Postgres, mismo Key Vault)
- [ ] Nueva migración Postgres (tablas `leads`, `conversation_sessions`)
- [ ] Nuevos secrets en el Key Vault ya existente (Mercado Pago access token, secreto de verificación de webhook)
- [ ] Nueva ruta HTTP (`/webhooks/mercadopago`) en el mismo Container App — sin exposición pública real en este incremento (consistente con NFR Requirements/Design)

## Preguntas de Clarificación

Sin preguntas — el alcance ya quedó acotado en Workflow Planning/NFR Requirements: sin nuevos recursos de cómputo, sin CORS/despliegue real, mismo resource group único `rg-dmc-agent-service` (Terraform existente, aún sin aplicar — igual que incremento 1). Se procede directo a generar los artefactos.
