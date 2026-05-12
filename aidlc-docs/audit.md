# AI-DLC Audit Log

## New Request — nomic-embed-text Asymmetric Prefix Fix
**Timestamp**: 2026-05-03T00:00:00Z
**User Input**: "Okay, using AI-SDLC fix the prefix issue. I understand it's basically adding the prefix and document it"
**AI Response**: Added `search_document:` prefix to `EmbeddingGenerator.generate()` in `src/pipeline/embedding_generator.py` and `search_query:` prefix to the question embedding call in `scripts/test_rag.py`. Documented change in aidlc-state.md as DIV-09.
**Context**: RAG quality assessment identified that `nomic-embed-text` requires asymmetric prefixes (`search_document:` for indexed content, `search_query:` for queries) to produce well-aligned cosine similarities. Both files were missing these prefixes. After this fix, re-ingestion is required to recompute all stored embeddings with the correct prefix.

---

## New Request — INGESTION_WORKERS Single Source of Truth
**Timestamp**: 2026-05-02T00:00:00Z
**User Input**: "I noticed there are many potential point of errors due to several files where INGESTION_WORKERS are defined. The only source of truth should be the .env"
**AI Response**: Identified root bug: config.py hardcodes `4` for ENV.LOCAL, ignoring the .env variable entirely. Plan: remove env-conditional branching, always read INGESTION_WORKERS from os.environ.
**Context**: New change request on completed project. Minimal workflow: Workspace Detection → Requirements Analysis → Code Generation → Build and Test.

---

## Workflow Plan Approval — INGESTION_WORKERS Fix
**Timestamp**: 2026-05-02T00:01:00Z
**User Input**: "Yes"
**AI Response**: Proceeding with code generation — modifying src/config.py only.
**Context**: User approved minimal workflow plan.

---

## Commit Plan Approval — Separar cambios en commits atómicos + documentar divergencias
**Timestamp**: 2026-05-02T00:10:00Z
**User Input**: "Yes and update the audit as well to document the Divergence decisions from the original plan"
**AI Response**: Approved 8-commit plan. Updating audit.md and aidlc-state.md with DIV-02 through DIV-08 before committing. Adding reports/ to .gitignore.
**Context**: User approved commit grouping and requested divergence documentation.

---

## Divergence Decision — DIV-02: Keywords de por-sección a nivel de documento
**Timestamp**: 2026-05-02T00:11:00Z
**Decision**: KeywordsExtractor cambia de extracción per-sección a extracción de keywords a nivel de documento completo.
**Original Design** (functional-design/business-logic-model.md): `extract_keywords(sections) → list[BrochureSection]` — una llamada LLM por sección, keywords se almacenan en `BrochureSection.keywords`.
**Actual Implementation**: `extract_keywords(sections) → list[str]` — una única llamada LLM combinando 5 secciones clave (PRESENTACION, SOBRE_ESTE_DIPLOMA, OBJETIVO, A_QUIEN_DIRIGIDO, MALLA_CURRICULAR), retorna una lista de keywords compartida por todos los chunks del brochure.
**Rationale**: Keywords a nivel de documento son más representativas para búsqueda semántica; keywords por sección eran redundantes (el mismo curso repetido N veces). Reduce de N llamadas LLM a 1 por PDF. Salida estructurada con Pydantic elimina el parsing manual de JSON.
**Affected Design Files**: business-logic-model.md, domain-entities.md (BrochureSection.keywords removed)

---

## Divergence Decision — DIV-03: EmbeddedChunk pierde section_type; BrochureSection pierde keywords
**Timestamp**: 2026-05-02T00:11:00Z
**Decision**: Eliminados dos campos de entidades del dominio: `EmbeddedChunk.section_type` y `BrochureSection.keywords`.
**Original Design** (functional-design/domain-entities.md): `EmbeddedChunk` tenía `section_type: SectionType`; `BrochureSection` tenía `keywords: list[str] = field(default_factory=list)`.
**Actual Implementation**: Ambos campos eliminados. Keywords son ahora externas (list[str] pasada explícitamente), y section_type no se persiste en la DB.
**Rationale**: Consecuencia directa de DIV-02. Keywords son ahora documento-nivel (no por sección). section_type no aporta valor en el vector DB para recuperación — el contenido textual es suficiente para búsqueda semántica.
**Affected Design Files**: domain-entities.md, pgvector_repository (schema upsert SQL)

---

## Divergence Decision — DIV-04: EmbeddingGenerator — text-splitting + keywords externos
**Timestamp**: 2026-05-02T00:11:00Z
**Decision**: EmbeddingGenerator cambia firma y lógica interna: acepta keywords externos, divide textos largos, cambia formato de enriquecimiento.
**Original Design** (functional-design/business-logic-model.md): `generate(sections: list[BrochureSection]) → list[EmbeddedChunk]` — un chunk por sección, texto enriquecido con `Programa: / Sección:` header, keywords leídos de `section.keywords`.
**Actual Implementation**: `generate(sections: list[BrochureSection], keywords: list[str]) → list[EmbeddedChunk]` — texto dividido en chunks de 2000 chars con overlap de 200 (produce múltiples chunks por sección si el contenido es largo), formato `[section_type]\ncontent`, keywords documento-nivel aplicados a todos los chunks.
**Rationale**: Secciones largas (ej. MALLA_CURRICULAR) excedían el límite de tokens del modelo de embeddings. Text-splitting garantiza que ningún contenido sea truncado. Keywords externos vienen de DIV-02.
**Affected Design Files**: business-logic-model.md (EmbeddingGenerator algoritmo), domain-entities.md (EmbeddedChunk.id now includes part index for multi-chunk sections)

---

## Divergence Decision — DIV-05: Schema — eliminado section_type, embedding dim 1536→768
**Timestamp**: 2026-05-02T00:11:00Z
**Decision**: Tabla `brochure_chunks` pierde columna `section_type`, embedding dimension cambia de 1536 a 768.
**Original Design** (migrations/001): `section_type TEXT NOT NULL`, `embedding vector(1536)`.
**Actual Implementation**: Columna `section_type` eliminada. `embedding vector(768)`. Nueva migración 002 trunca la tabla para aplicar el cambio de esquema.
**Rationale**: section_type eliminado por DIV-03. Dimensión 1536 era para Bedrock Titan (`amazon.titan-embed-text-v2:0`); el modelo local `nomic-embed-text` de Ollama produce vectores de 768 dimensiones. Corrección necesaria para que los inserts no fallen.
**Affected Design Files**: migrations/001_create_brochure_chunks.sql, pgvector_repository.py

---

## Divergence Decision — DIV-06: PATTERN-03 Retry eliminado de OllamaEmbeddingsProvider
**Timestamp**: 2026-05-02T00:11:00Z
**Decision**: Retry con exponential backoff eliminado de `OllamaEmbeddingsProvider.embed()`. Reemplazado por `keep_alive=10m`.
**Original Design** (nfr-design/nfr-design-patterns.md PATTERN-03): Retry de 3 intentos con backoff 1s→2s→4s en `OllamaEmbeddingsProvider.embed()`. Fue añadido como post-build fix el 2026-04-30 para cubrir HTTP 500 de Ollama bajo carga concurrente.
**Actual Implementation**: Sin retry. Parámetro `keep_alive=10m` en el payload de la llamada a Ollama. Mejor reporte de errores (verifica `error` y `embedding` en la respuesta JSON).
**Rationale**: La causa raíz de los errores HTTP 500 era que Ollama descargaba el modelo entre llamadas concurrentes (model swap entre gemma3 y nomic-embed-text). `keep_alive` previene la descarga, eliminando la condición que causaba el error — el retry trataba el síntoma, no la causa.
**Affected Design Files**: nfr-design/nfr-design-patterns.md (PATTERN-03)

---

## Divergence Decision — DIV-07: LLMProvider port — parámetro format para structured output
**Timestamp**: 2026-05-02T00:11:00Z
**Decision**: Interfaz `LLMProvider.complete()` agrega parámetro opcional `format: dict | None`.
**Original Design** (ports/llm_provider.py): `complete(prompt: str) → str`.
**Actual Implementation**: `complete(prompt: str, format: dict | None = None) → str`. OllamaLLMProvider pasa `format` al payload de Ollama si no es None. BedrockLLMProvider acepta el parámetro pero lo ignora (Bedrock no soporta structured output de la misma forma).
**Rationale**: Consecuencia de DIV-02. La extracción de keywords usa el JSON schema de Pydantic (`KeywordsResponse.model_json_schema()`) pasado como `format` a Ollama para forzar salida estructurada válida. Elimina el parsing manual de JSON y los fallos por markdown fences en la respuesta.
**Affected Design Files**: ports/llm_provider.py, infrastructure/llm/ollama_llm.py, infrastructure/llm/bedrock_llm.py

---

## Divergence Decision — DIV-08: INGESTION_WORKERS — siempre desde .env, sin hardcode por env
**Timestamp**: 2026-05-02T00:12:00Z
**Decision**: `config.py` elimina el condicional que ignoraba `INGESTION_WORKERS` para `ENV.LOCAL`.
**Original Design** (src/config.py): `ingestion_workers=4 if env == ENV.LOCAL else int(os.environ.get("INGESTION_WORKERS", "4"))` — hardcodeaba `4` para entorno local sin leer el .env.
**Actual Implementation**: `ingestion_workers=int(os.environ.get("INGESTION_WORKERS", "4"))` — siempre lee del entorno, fallback `"4"` solo si la variable no existe.
**Rationale**: `.env` debe ser la única fuente de verdad. El condicional previo hacía que cambiar `INGESTION_WORKERS` en `.env` no tuviera efecto en LOCAL, creando un bug silencioso.
**Affected Design Files**: src/config.py

---

## Post-Build Fix — OllamaEmbeddingsProvider Retry
**Timestamp**: 2026-04-30T21:35:00Z
**User Input**: "Documentalo tambien"
**AI Response**: Added retry/backoff (3 attempts, 1s/2s/4s) to `OllamaEmbeddingsProvider.embed()`. Updated PATTERN-03 in nfr-design-patterns.md to reflect that retry now covers both keywords and embeddings. Root cause: Ollama returns HTTP 500 when swapping models under concurrent load (4 workers calling gemma3 for keywords then nomic-embed-text for embeddings). Committed as `fix: add retry/backoff to Ollama embeddings + fix Docker port conflict`.
**Context**: Live pipeline run revealed hard failure on embeddings 500 errors. BR-09 graceful degradation only covered keywords; embeddings now also protected by retry before raising.

---

## Build and Test — Completed
**Timestamp**: 2026-04-30T00:00:00Z
**User Input**: "okay, let's continue with AI SDLC"
**AI Response**: Generated 5 Build and Test artifacts: build-instructions.md, unit-test-instructions.md, integration-test-instructions.md, performance-test-instructions.md, build-and-test-summary.md. ~31 unit tests + 7 PBT properties (~900 generated cases). aidlc-state.md updated: Construction Phase complete for unit-1.
**Context**: Build and Test — COMPLETED. Awaiting user approval.

---

## unit-1: ingestion-pipeline — Code Generation Complete
**Timestamp**: 2026-04-30T00:00:00Z
**AI Response**: All 16 steps complete. Generated 32 files under services/ingestion/. Stories US-17 and US-18 implemented. PBT coverage: 7 Hypothesis properties across 2 files. Awaiting approval.
**Context**: unit-1 Code Generation — Part 2 COMPLETED. Awaiting user approval.

---

## unit-1: ingestion-pipeline — Code Generation Approved
**Timestamp**: 2026-04-30T00:00:00Z
**User Input**: "yes"
**AI Response**: Plan approved. Starting Part 2 — code generation, 16 steps.
**Context**: unit-1 Code Generation — Part 2 (Generation) started.

---

## unit-1: ingestion-pipeline — Code Generation Plan Created
**Timestamp**: 2026-04-30T00:00:00Z
**AI Response**: Code generation plan created with 16 steps covering: domain entities, ports, PDFParser, KeywordsExtractor, EmbeddingGenerator, 5 infrastructure layers, ProviderFactory/Config/Logging, IngestionOrchestrator, CLI/Lambda, PBT tests (7 properties), and deployment artifacts. Awaiting approval before generation begins.
**Context**: unit-1 Code Generation — Part 1 (Planning) complete. Awaiting user approval.

---

## unit-1: ingestion-pipeline — Infrastructure Design Approved
**Timestamp**: 2026-04-30T00:00:00Z
**User Input**: "looks good"
**AI Response**: Infrastructure Design COMPLETED and APPROVED. Proceeding to Code Generation for unit-1.
**Context**: unit-1 Infrastructure Design — COMPLETED and APPROVED.

---

## unit-1: ingestion-pipeline — Infrastructure Design Completed
**Timestamp**: 2026-04-30T00:00:00Z
**User Input**: "Done" (Q1=Lambda/local for now, Q2=Fresh AWS setup/local for now, Q3=New RDS instance)
**AI Response**: Generated infrastructure-design.md (LOCAL: Docker+Ollama+filesystem; PRODUCTION: Lambda container + RDS pgvector + S3 + Bedrock + VPC) and deployment-architecture.md (ASCII diagrams + migration path + Dockerfile). Awaiting approval.
**Context**: unit-1 Infrastructure Design — COMPLETED. Awaiting user approval.

---

## unit-1: ingestion-pipeline — NFR Design Approved
**Timestamp**: 2026-04-30T00:00:00Z
**User Input**: "Looks good"
**AI Response**: NFR Design COMPLETED and APPROVED. Proceeding to Infrastructure Design for unit-1.
**Context**: unit-1 NFR Design — COMPLETED and APPROVED.

---

## unit-1: ingestion-pipeline — NFR Design Completed
**Timestamp**: 2026-04-30T00:00:00Z
**User Input**: "continue"
**AI Response**: NFR Requirements approved. Generated nfr-design-patterns.md (7 patterns: Thread-per-PDF Isolation, Provider Factory, Retry+Backoff, Idempotent Upsert, Thread-Safe Aggregation, Threaded Connection Pool, Dual-Handler Logging) and logical-components.md (7 components: IngestionOrchestrator, ProviderFactory, ThreadedConnectionPool, LoggingConfigurator, VectorDBRepository, KeywordsExtractor, PDFResult). Awaiting approval.
**Context**: unit-1 NFR Design — COMPLETED. Awaiting user approval.

---

## unit-1: ingestion-pipeline — NFR Requirements Answers Collected
**Timestamp**: 2026-04-30T00:00:00Z
**User Input**: "answered next" (answers provided directly in plan file: Q1=B, Q2=B, Q3=B, Q4=A with EventBridge future note, Q5=A with simple log file note)
**AI Response**: Generated nfr-requirements.md (PERF, SCAL, AVAIL, SEC, REL, OBS, MAINT categories) and tech-stack-decisions.md (TSD-01 through TSD-06). Plan checkboxes all marked complete. Awaiting approval.
**Context**: unit-1 NFR Requirements — COMPLETED. Awaiting user approval.

---

## Workspace Detection
**Timestamp**: 2026-04-23T00:00:00Z
**User Input**: "Si, quiero inicializar un proyecto. lee @PRD.md"
**AI Response**: Initiated AI-DLC workflow. Read PRD.md, CLAUDE.md, and all common rule files. Determined greenfield project.
**Context**: Workflow initialization — user provided PRD.md as the source of requirements.

---

## Workspace Detection Findings
**Timestamp**: 2026-04-23T00:00:00Z
**AI Response**: Workspace scan complete.
- Existing Code: No source files found (.py, .js, .ts, .java, etc.)
- Build Files: None found (no package.json, pom.xml, requirements.txt, etc.)
- Project Type: Greenfield
- PRD.md present: Yes — "DMC Sales Agent" v1.1
- Workspace Root: /Users/sebastianchavarry01/Documents/personal-github/ask-dmc
**Context**: Workspace Detection — Step 2 complete. Proceeding to Requirements Analysis.

---

## Requirements Analysis — Questions Created
**Timestamp**: 2026-04-23T00:00:00Z
**AI Response**: Created requirement-verification-questions.md with 13 questions covering: deployment environment, RAG/vector store strategy, AgentCore Memory approach, Mercado Pago setup, widget embedding, testing scope, auth setup, and extension opt-ins (security + PBT).
**Context**: Requirements Analysis — Step 6. Awaiting user answers before generating requirements.md.

---

## Requirements Analysis — Clarification Answers Received
**Timestamp**: 2026-04-23T00:00:00Z
**User Input (CQ1)**: "A. Pero, recuerda que deberia ser un websocket para facilitar el streaming de las respuestas."
**User Input (CQ2)**: "Crear una DB vectorial con los brochures estructurados. Para ello, deberiamos crear un pipeline de ingestion que procese los PDFs con Claude y genere embeddings de las secciones relevantes y agregamos metadata estructurada para facilitar la búsqueda."
**AI Response**: Clarifications resolved. Architecture: FastAPI thin layer (App Runner) + Strands Agent en AgentCore Runtime + WebSocket streaming + Vector DB con pipeline PDF→Claude→embeddings+metadata.
**Context**: Requirements Analysis — Ambiguities resolved.

---

## Requirements Analysis — Document Generated
**Timestamp**: 2026-04-23T00:00:00Z
**AI Response**: Generated aidlc-docs/inception/requirements/requirements.md. Extension configuration: Security Baseline ENABLED (full, blocking), PBT ENABLED (full enforcement, Hypothesis). Updated aidlc-state.md.
**Context**: Requirements Analysis — Step 7 complete. Awaiting user approval to proceed.

---

## Requirements Analysis — Amendment Round 1
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "Notes:
- For the LLM, let's use AWS Bedrock, not the official Claude API. This should be agnostic (consider this in the architecture design, something like a repository or infraestructure layer)
- Backend should be running in Lambda to create a websocket connection then invoking the Agent in AgentCore runtime.
- RF-09, if the human wants to talk to human, then the agents says that someone from the team will contact them, it should be flagged somewhere in the DB, and someone in the sales team should get an email notification. 
Guardrails adicionales:
- The agent cannot mention any other company or educational institute. Nor making comparisons.
- The agent scope is only to recommend and close sales, it cannot anything else (for example coding exercises)
- createdat should be a timestamp in miliseconds
- it should not have a full transcript attribute, conversations will be another table. 
- The agent can send presigned_urls of the original brochure as a tool (should have)"
**AI Response**: Updated requirements.md with: (1) AWS Bedrock via agnostic LLM infrastructure layer, (2) Lambda + API Gateway WebSocket replacing App Runner, (3) RF-09 enhanced with DB flag + SES email notification, (4) two new guardrails (no competitor mention/comparison, sales-only scope), (5) DynamoDB schema: created_at as ms timestamp, full_transcript removed, conversations as separate table, (6) S4 added to Should Have: presigned_url brochure tool.
**Context**: Requirements Analysis — Amendment applied. Awaiting user approval to proceed.

---

## Requirements Analysis — User Approval
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "Si, todo okay"
**AI Response**: Requirements v1.1 approved. Proceeding to User Stories assessment.
**Context**: Requirements Analysis — COMPLETED and APPROVED.

---

## User Stories — Plan Presented
**Timestamp**: 2026-04-28T00:00:00Z
**AI Response**: Assessment: ALWAYS execute (multi-persona, complex funnel, greenfield). Created user-stories-assessment.md and story-generation-plan.md. Presenting 6 questions to user before generation.
**Context**: User Stories — Part 1 Planning. Awaiting user answers.

---

## User Stories — Plan Questions Answered
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "spanish, C, C, C, C, A"
**AI Response**: Answers recorded. Q1=Spanish, Q2=Hybrid BDD, Q3=One epic with states as AC, Q4=Views+auth+escalation notification, Q5=Both standalone+embedded guardrails, Q6=Brochure URL in RECOMENDACIÓN epic. No ambiguities found. Presenting updated plan for approval.
**Context**: User Stories — Part 1 Planning. Awaiting plan approval before generation.

---

## User Stories — Plan Approved
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "correcto"
**AI Response**: Plan aprobado. Iniciando Part 2 — Generation. Generando personas.md y stories.md.
**Context**: User Stories — Part 2 Generation iniciada.

---

## User Stories — Generation Complete
**Timestamp**: 2026-04-28T00:00:00Z
**AI Response**: Generados personas.md (3 personas) y stories.md (16 stories, 4 epics). INVEST verificado. Mapa personas-stories generado. Pendiente aprobación del usuario.
**Context**: User Stories — Part 2 COMPLETED. Awaiting user approval.

---

## User Stories — Approved
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "Approved, let's continue with Workflow Planning"
**AI Response**: User Stories COMPLETED and APPROVED. 16 issues creados en GitHub Project #3 (Ask DMC). Procediendo a Workflow Planning.
**Context**: User Stories — COMPLETED and APPROVED.

---

## Workflow Planning — Plan Presentado
**Timestamp**: 2026-04-28T00:00:00Z
**AI Response**: Análisis completo. Risk: HIGH. 5 unidades identificadas. Todas las etapas CONSTRUCTION se ejecutan. Application Design y Units Generation se ejecutan. execution-plan.md generado. Pendiente aprobación del usuario.
**Context**: Workflow Planning — Awaiting user approval.

---

## Workflow Planning — Aprobado
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "Aprobar"
**AI Response**: Workflow Planning COMPLETADO y APROBADO. Procediendo a Application Design.
**Context**: Workflow Planning — COMPLETED and APPROVED.

---

## Application Design — Plan Presentado
**Timestamp**: 2026-04-28T00:00:00Z
**AI Response**: Plan de Application Design creado con 5 capas de componentes identificadas y 4 preguntas de diseño. Awaiting user answers.
**Context**: Application Design — Part 1. Awaiting answers before generating artifacts.

---

## Application Design — Respuestas y Artefactos Generados
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "B, C, B" (Q2=AgentCore Memory + current_state en dmc-conversations, Q3=Turborepo monorepo, Q4=Protocol)
**AI Response**: 5 artefactos generados: components.md (17 componentes en 5 capas), component-methods.md, services.md (6 servicios), component-dependency.md (4 data flow diagrams), application-design.md (consolidado). Pendiente aprobación.
**Context**: Application Design — COMPLETED. Awaiting user approval.

---

## Application Design — folder-structure.md Agregado
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "En esta etapa tenemos que definir bien la architectura del backend? domain, repo, service, etc. ademas, de la estructura de las carpetas de front?"
**AI Response**: Generado folder-structure.md con: backend Python (domain/ports/infrastructure/services/handlers), agent (tools/ports/infrastructure), ingestion pipeline, apps/widget, apps/backoffice, packages/ui (Turborepo). Tabla de reglas de dependencia por capa incluida.
**Context**: Application Design — artefacto adicional generado. Pendiente aprobación final.

---

## Application Design — Aprobado
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "Todo okay, sigamos"
**AI Response**: Application Design COMPLETADO y APROBADO. 6 artefactos: components.md, component-methods.md, services.md, component-dependency.md, application-design.md, folder-structure.md. Procediendo a Units Generation.
**Context**: Application Design — COMPLETED and APPROVED.

---

## Units Generation — Plan Listo para Aprobación
**Timestamp**: 2026-04-28T00:00:00Z
**AI Response**: Sin preguntas pendientes — contexto completo de Application Design. Plan creado con 5 unidades y 3 artefactos a generar. Solicitando aprobación antes de generación.
**Context**: Units Generation — Part 1. Awaiting approval.

---

## Units Generation — Aprobado
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "si"
**AI Response**: Plan aprobado. Iniciando Part 2 — generación de los 3 artefactos.
**Context**: Units Generation — Part 2 Generation iniciada.

---

## Units Generation — Artefactos Generados
**Timestamp**: 2026-04-28T00:00:00Z
**AI Response**: 3 artefactos generados. unit-of-work.md (5 unidades con criterios entrada/salida), unit-of-work-dependency.md (matriz + riesgos), unit-of-work-story-map.md (16/16 stories asignadas). Pendiente aprobación.
**Context**: Units Generation — COMPLETED. Awaiting user approval.

---

## Units Generation — Aprobado / Construction Phase Iniciada
**Timestamp**: 2026-04-28T00:00:00Z
**User Input**: "implementalo"
**AI Response**: Units Generation APROBADO. Iniciando CONSTRUCTION PHASE — unit-1: ingestion-pipeline.
**Context**: CONSTRUCTION PHASE — unit-1 iniciada.

---

## unit-1: ingestion-pipeline — Functional Design Completado
**Timestamp**: 2026-04-28T00:00:00Z
**AI Response**: Generados: domain-entities.md (SectionType, BrochureSection, EmbeddedChunk, IngestionReport), business-rules.md (BR-01 a BR-09), business-logic-model.md (algoritmos de pipeline, extracción y embeddings). Sin preguntas — diseño completamente derivado de requirements. Pendiente aprobación.
**Context**: unit-1 Functional Design — COMPLETED. Awaiting approval.

---

## unit-1: ingestion-pipeline — Functional Design Aprobado
**Timestamp**: 2026-04-29T00:00:00Z
**User Input**: "Yes"
**AI Response**: Functional Design COMPLETADO y APROBADO (v2 con parsing determinístico + ENV support). Procediendo a NFR Requirements para unit-1.
**Context**: unit-1 Functional Design — COMPLETED and APPROVED.

---

## Divergence Decision — DIV-01
**Timestamp**: 2026-04-29T00:00:00Z
**User Input**: "B"
**AI Response**: Logged DIV-01 in aidlc-state.md. Inception docs kept as historical record; construction artifacts take precedence. No inception files modified.
**Context**: Divergence tracking — PDF extraction approach changed from LLM-based to deterministic parser.

---

## Session Resumption
**Timestamp**: 2026-04-29T00:00:00Z
**User Input**: "Let's continue with AI SDLC"
**AI Response**: Session resumed. Loaded functional design artifacts for unit-1: ingestion-pipeline. Presenting welcome back prompt and functional design approval request.
**Context**: Session Continuity — Resuming CONSTRUCTION PHASE, unit-1: ingestion-pipeline.

---

## unit-1: ingestion-pipeline — Functional Design Amendment Round 1
**Timestamp**: 2026-04-29T00:00:00Z
**User Input**: "Notes on Business Rules:\n- I do not believe that using a LLM is the right choice to extract the data from the PDFs, the content is predictable, so we need a deterministic script to get the data.\n- We should probably save somewhere those errors reports (not in a DB for now)\n- For the keywords generation, we should use a cheap LLM like haiku or probably gemma 4 from google\n\nNotes on Business Logic Model:\n- Let's add an ENV\n- When it's local, let's use the @knowledge_source directory instead of S3\n- when it's local let's use ollama, let's use an open source model for generating the embeddings"
**AI Response**: Applying amendments: (1) Replace LLM-based PDF extraction with deterministic pdfplumber parser, (2) Add error report persistence to file (not DB), (3) Keyword extraction via cheap LLM (Haiku/Gemma 4), (4) Add ENV enum with LOCAL/PRODUCTION routing — LOCAL uses knowledge_source/ + Ollama embeddings + local file reports; PRODUCTION uses S3 + Bedrock embeddings. Updating domain-entities.md, business-rules.md, business-logic-model.md.
**Context**: unit-1 Functional Design — Amendment applied. Awaiting user approval.

---
