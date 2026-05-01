# AI-DLC Audit Log

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
