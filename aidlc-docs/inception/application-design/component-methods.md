# Component Methods — DMC Sales Agent

**Fecha**: 2026-04-28  
**Nota**: Las firmas aquí son de alto nivel. La lógica de negocio detallada se define en Functional Design (Construction phase).

---

## Infrastructure Layer

### LLMProvider (Protocol)

```python
from typing import Protocol, AsyncIterator

class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
        **kwargs,
    ) -> str: ...

    async def stream(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]: ...
```

### BedrockLLMProvider

```python
class BedrockLLMProvider:
    def __init__(self, model_id: str, region: str) -> None: ...
    async def complete(self, messages, system, max_tokens, **kwargs) -> str: ...
    async def stream(self, messages, system, max_tokens, **kwargs) -> AsyncIterator[str]: ...
```

### VectorDBRepository (Protocol)

```python
class VectorDBRepository(Protocol):
    async def search(
        self,
        query: str,
        profile: UserProfile,
        top_k: int = 5,
    ) -> list[Chunk]: ...

    async def upsert(self, chunks: list[EmbeddedChunk]) -> None: ...
    async def delete(self, chunk_ids: list[str]) -> None: ...
```

### LeadRepository

```python
class LeadRepository:
    async def save(self, lead: Lead) -> None: ...
    async def get_by_id(self, lead_id: str) -> Lead | None: ...
    async def get_by_email(self, email: str) -> Lead | None: ...
    async def list(self, filters: LeadFilters) -> list[Lead]: ...
    async def update(self, lead_id: str, updates: dict) -> None: ...
```

### ConversationRepository

```python
class ConversationRepository:
    async def save_message(
        self,
        lead_id: str,
        message: ConversationMessage,  # includes current_state field
    ) -> None: ...

    async def get_messages(self, lead_id: str) -> list[ConversationMessage]: ...
```

### S3Repository

```python
class S3Repository:
    def generate_presigned_url(
        self,
        key: str,
        expiry_seconds: int = 3600,
    ) -> str: ...

    def list_brochures(self) -> list[str]: ...
```

---

## Agent Layer

### StrandsAgent

```python
class StrandsAgent:
    async def invoke(
        self,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]: ...
```

### SearchCoursesTool

```python
class SearchCoursesTool:
    async def execute(
        self,
        query: str,
        user_profile: UserProfile,
    ) -> list[CourseChunk]: ...
```

### QualifyLeadTool

```python
class QualifyLeadTool:
    async def execute(
        self,
        conversation_context: ConversationContext,
    ) -> LeadQualification:
        # Returns: motivation, score signals, profile_summary
        ...
```

### GeneratePaymentLinkTool

```python
class GeneratePaymentLinkTool:
    async def execute(
        self,
        course_name: str,
        lead_id: str,
    ) -> str:  # Mercado Pago checkout URL
        ...
```

### GetBrochureUrlTool

```python
class GetBrochureUrlTool:
    async def execute(
        self,
        course_name: str,
    ) -> str:  # S3 presigned URL
        ...
```

---

## Ingestion Pipeline

### IngestionOrchestrator

```python
class IngestionOrchestrator:
    async def run(
        self,
        bucket: str,
        prefix: str = "brochures/",
    ) -> IngestionReport: ...
```

### PDFExtractor

```python
class PDFExtractor:
    async def extract(
        self,
        pdf_bytes: bytes,
        course_name: str,
    ) -> list[BrochureSection]:
        # Sections: presentacion, sobre_este_diploma, como_impulsamos,
        # por_que_estudiar, objetivo, a_quien_dirigido, requisitos,
        # herramientas, malla_curricular, propuesta_capacitacion,
        # certificacion, docentes
        ...
```

### EmbeddingGenerator

```python
class EmbeddingGenerator:
    async def generate(
        self,
        sections: list[BrochureSection],
    ) -> list[EmbeddedChunk]:
        # Each chunk: text, embedding vector, metadata (course_name, section_type, keywords)
        ...
```

---

## Backend Application Layer

### WebSocketHandler

```python
async def handle_connect(event: dict) -> dict:
    # Validates origin, returns 200
    ...

async def handle_disconnect(event: dict) -> dict:
    # Cleanup, returns 200
    ...

async def handle_message(event: dict) -> dict:
    # Extracts connectionId from event["requestContext"]["connectionId"]
    # Delegates to ChatSessionService
    # Streams tokens back via post_to_connection
    ...
```

### LeadsAPIHandler

```python
async def list_leads(
    filters: LeadFilters,
    claims: CognitoClaims,  # injected by AuthMiddleware
) -> LeadListResponse: ...

async def get_lead(
    lead_id: str,
    claims: CognitoClaims,
) -> LeadDetailResponse: ...
```

### AuthMiddleware

```python
class AuthMiddleware:
    def validate_token(self, token: str) -> CognitoClaims:
        # Verifies JWT signature against Cognito JWKS
        # Checks expiry, iss, aud claims
        ...

    def require_auth(self, handler: Callable) -> Callable:
        # Decorator: extracts Bearer token, calls validate_token, injects claims
        ...
```

### ChatSessionService

```python
class ChatSessionService:
    async def process_message(
        self,
        connection_id: str,   # from WebSocket event (in-memory only)
        session_id: str,       # AgentCore Memory session identifier
        message: str,
    ) -> AsyncIterator[str]:
        # Invokes StrandsAgent.invoke()
        # Yields token chunks to caller (WebSocketHandler streams via post_to_connection)
        ...
```

### LeadService

```python
class LeadService:
    async def create_or_get(self, email: str, name: str) -> Lead: ...

    async def update_qualification(
        self,
        lead_id: str,
        qualification: LeadQualification,
    ) -> None: ...

    async def score_lead(
        self,
        lead_id: str,
        signals: ScoringSignals,
    ) -> LeadScore:
        # hot: payment link requested
        # warm: clear motivation, no purchase decision
        # cold: vague motivation
        ...

    async def finalize(self, lead_id: str) -> None:
        # Persists final score, summary, closes session
        ...

    async def flag_escalation(self, lead_id: str) -> None:
        # Sets escalated_to_human: true in dmc-leads
        # Triggers NotificationService
        ...
```

### NotificationService

```python
class NotificationService:
    async def notify_escalation(self, lead: Lead) -> None:
        # Sends SES email to SES_SALES_EMAIL
        # Body: lead name, email, motivation, score, summary
        ...
```

### PaymentService

```python
class PaymentService:
    async def create_payment_link(
        self,
        course_name: str,
        lead_id: str,
    ) -> str:
        # Calls Mercado Pago Checkout API (sandbox)
        # Returns checkout URL
        ...
```
