# Services — DMC Sales Agent

**Fecha**: 2026-04-28

Los servicios de aplicación orquestan los componentes de dominio. Cada servicio tiene una única responsabilidad y no accede directamente a infraestructura — delega a repositorios.

---

## ChatSessionService

**Responsabilidad**: Orquesta el flujo completo de un mensaje de chat — desde que llega al WebSocket handler hasta que el token final se envía al cliente.

**Flujo de ejecución**:
```
WebSocketHandler.handle_message()
    │
    ├── Extrae connectionId, session_id, user_message del evento
    │
    └── ChatSessionService.process_message(connectionId, session_id, message)
            │
            ├── StrandsAgent.invoke(session_id, message) → streaming tokens
            │
            ├── [por cada token] → apigateway_mgmt.post_to_connection(connectionId, token)
            │
            └── Al finalizar: señaliza fin de stream al cliente
```

**Interacciones**:
- → `StrandsAgent` (invoca el agente en AgentCore Runtime)
- → API Gateway Management API (push de tokens via `post_to_connection`)

**Notas**:
- El `connectionId` vive solo en memoria dentro del invocation Lambda
- El `session_id` se mapea al session ID de AgentCore Memory (persistencia entre turnos)

---

## LeadService

**Responsabilidad**: Lógica de negocio central de leads — ciclo de vida completo desde creación hasta finalización.

**Flujo — creación y calificación**:
```
ChatSessionService (al recibir datos del visitante)
    └── LeadService.create_or_get(email, name)
            └── LeadRepository.get_by_email() || LeadRepository.save()

Agente (al calificar via QualifyLeadTool)
    └── LeadService.update_qualification(lead_id, qualification)
            └── LeadRepository.update()
```

**Flujo — cierre**:
```
Agente (al detectar intención de compra o fin de sesión)
    └── LeadService.finalize(lead_id)
            ├── LeadService.score_lead() → LeadScore
            └── LeadRepository.update(score, conversation_summary)
```

**Flujo — escalación**:
```
Agente (al detectar solicitud de humano)
    └── LeadService.flag_escalation(lead_id)
            ├── LeadRepository.update(escalated_to_human: true)
            └── NotificationService.notify_escalation(lead)
```

**Interacciones**:
- → `LeadRepository` (persistencia)
- → `NotificationService` (on escalation)

---

## NotificationService

**Responsabilidad**: Envío de notificaciones email al equipo comercial via Amazon SES.

**Flujo**:
```
LeadService.flag_escalation()
    └── NotificationService.notify_escalation(lead)
            └── SES.send_email(
                    to=SES_SALES_EMAIL,
                    from=SES_FROM_EMAIL,
                    subject="Nuevo lead solicita contacto humano",
                    body={name, email, motivation, score, summary}
                )
```

**Interacciones**:
- → Amazon SES (boto3)

---

## PaymentService

**Responsabilidad**: Generación de links de pago Mercado Pago. Llamado desde `GeneratePaymentLinkTool` del agente, que a su vez invoca el endpoint de Lambda.

**Flujo**:
```
GeneratePaymentLinkTool.execute(course_name, lead_id)
    └── PaymentService.create_payment_link(course_name, lead_id)
            ├── Mercado Pago Checkout API → checkout_url
            └── LeadRepository.update(payment_link_sent: true, mercado_pago_url)
```

**Interacciones**:
- → Mercado Pago API (HTTP, sandbox)
- → `LeadRepository` (actualiza estado del lead)

---

## Ingestion Pipeline Service

**Responsabilidad**: Orquestación del pipeline de ingestion de brochures. Servicio independiente, no invocado en runtime del chat.

**Flujo**:
```
IngestionOrchestrator.run(bucket, prefix)
    ├── S3Repository.list_brochures() → [pdf_key, ...]
    │
    └── [por cada PDF]
            ├── S3Repository.get_object(key) → pdf_bytes
            ├── PDFExtractor.extract(pdf_bytes, course_name) → [BrochureSection, ...]
            ├── EmbeddingGenerator.generate(sections) → [EmbeddedChunk, ...]
            └── VectorDBRepository.upsert(chunks)
```

**Interacciones**:
- → `S3Repository`
- → `PDFExtractor` → `LLMProvider` (BedrockLLMProvider)
- → `EmbeddingGenerator` → Bedrock Embeddings
- → `VectorDBRepository`

---

## Auth Service (Backoffice)

**Responsabilidad**: Validación de tokens JWT de Cognito. Actúa como middleware en todos los endpoints `/admin/*`.

**Flujo**:
```
Request → LeadsAPIHandler
    └── AuthMiddleware.require_auth(handler)
            ├── Extrae Bearer token del header Authorization
            ├── AuthMiddleware.validate_token(token)
            │       ├── Descarga JWKS de Cognito (cacheado)
            │       ├── Verifica firma, expiración, iss, aud
            │       └── Retorna CognitoClaims
            └── Inyecta claims en handler → ejecuta lógica de negocio
```

**Interacciones**:
- → AWS Cognito JWKS endpoint (HTTP, cacheado en memoria Lambda)

---

## Dependency Injection Summary

Todos los servicios reciben sus dependencias por constructor (no instancian infraestructura internamente):

```python
# Ejemplo de wiring en Lambda handler
llm_provider = BedrockLLMProvider(model_id=BEDROCK_MODEL_ID, region=AWS_REGION)
vector_repo = ConcreteVectorDBRepository(...)  # implementación decidida en NFR Design
lead_repo = LeadRepository(table_name=DYNAMODB_TABLE_LEADS)
conv_repo = ConversationRepository(table_name=DYNAMODB_TABLE_CONVERSATIONS)
s3_repo = S3Repository(bucket=S3_BUCKET_NAME)

payment_service = PaymentService(access_token=MERCADO_PAGO_ACCESS_TOKEN)
notification_service = NotificationService(ses_client=boto3.client("ses"))
lead_service = LeadService(lead_repo=lead_repo, notification_service=notification_service)
chat_service = ChatSessionService(agent=strands_agent)
```
