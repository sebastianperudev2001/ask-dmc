# Unit of Work Plan — DMC Sales Agent

## Decisiones de Diseño (resueltas en Application Design)
- 5 unidades independientes, desplegables separadamente
- Orden de construcción secuencial por dependencias técnicas
- Cada unidad tiene su propio directorio en `services/` (backend/agent/ingestion) o `apps/` (frontend)
- Código compartido: cada servicio Python tiene sus propios `ports/` (sin paquete Python compartido — simplicidad de deployment)
- Story mapping: derivado de stories.md y component-dependency.md

---

## Execution Checklist (Part 2 — Generation)

- [x] Generar `unit-of-work.md` — definición de las 5 unidades con responsabilidades y criterios de entrada/salida
- [x] Generar `unit-of-work-dependency.md` — matriz de dependencias y orden de construcción
- [x] Generar `unit-of-work-story-map.md` — mapeo stories → unidades
- [x] Validar que todas las stories están asignadas a una unidad (16/16 ✅)
- [x] Actualizar checkboxes y `aidlc-state.md`
