# Lead Scoring & Motivation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Lead.motivation` reflect what the visitor actually says (fixing the "undefined" shown in BackOffice), and rewire lead scoring so a lead starts `cold`, an early purchase-certainty signal raises it to `warm`, and completing the profile-data form raises it to `hot` — while deleting the dead `score_lead()`/`ScoringSignals` formula this investigation surfaced.

**Architecture:** `services/agent-service` stays hexagonal. `src/domain/lead_scoring.py` keeps a small set of pure, Hypothesis-tested functions; `src/adapters/chat_agent_client.py` gains two new Microsoft Agent Framework tools (`flag_purchase_intent`, `set_lead_motivation`) that the agent invokes as part of its normal tool-calling loop — no new infra calls, no new Postgres columns (both `Lead.motivation`/`motivation_detail` and `Lead.score`/`score_justification` already exist). `apps/backoffice` gets a pure label-mapping function so the BackOffice never renders the raw string `"undefined"`.

**Tech Stack:** Python 3.14, `agent-framework-foundry` (Microsoft Agent Framework), pytest + pytest-asyncio + Hypothesis, Next.js 15 / TypeScript, Vitest.

## Global Constraints

- No new Postgres migration — `Lead.motivation`, `Lead.motivation_detail`, `Lead.score`, `Lead.score_justification` columns already exist (spec: Non-goals).
- No new frontend form field — motivation is inferred by the agent from the conversation, never asked to the visitor directly (spec: Non-goals, explicit user correction).
- The 5+/10+ user-message engagement floor is kept as-is, layered alongside the new rules (spec: Non-goals, explicit user decision).
- `profile_fits_recommendation` / `urgent` signals from the old `score_lead()` formula are dropped, not reimplemented (spec: Non-goals).
- Agent-facing strings (`_AGENT_INSTRUCTIONS`, tool descriptions) are Spanish, no accented characters in code identifiers but accents are fine in the Spanish prose itself (matches existing file convention — see current `_AGENT_INSTRUCTIONS` in `chat_agent_client.py`).
- `motivation` values are exactly one of `growth`, `salary`, `company_requirement`, `academic` (`src/domain/models.py:86-89`) — any other value from the agent must fall back to `Motivation.UNDEFINED`, never raise.

---

## File Structure

- **Modify** `services/agent-service/src/domain/lead_scoring.py` — delete `ScoringSignals`/`score_lead()`; keep `_SCORE_RANK`; rename/shrink `engagement_floor()` to `message_count_floor()`; simplify `apply_score_floor()`'s signature to take an already-computed floor.
- **Modify** `services/agent-service/src/adapters/chat_agent_client.py` — replace `_apply_engagement_floor()` with a generic `_raise_score_floor()`; add `_flag_purchase_intent` and `_set_lead_motivation` tool methods; register both as tools; extend `_AGENT_INSTRUCTIONS`.
- **Modify** `services/agent-service/tests/unit/test_lead_scoring.py` — full rewrite against the new function names.
- **Modify** `services/agent-service/tests/unit/test_chat_agent_client_scoring.py` — update header comment, extend `_build_client` to allow overriding `on_profile_data_requested`/`pending_tool_calls`, add tests for the three floor-raising tools.
- **Modify** `apps/backoffice/components/LeadDetailModal.tsx` — add exported `motivationLabel()` pure function, use it in the "Motivación" row.
- **Create** `apps/backoffice/components/LeadDetailModal.test.tsx` — tests for `motivationLabel()`.

---

### Task 1: Consolidate lead-scoring floors (`lead_scoring.py` + wiring)

**Files:**
- Modify: `services/agent-service/src/domain/lead_scoring.py` (full rewrite, currently 71 lines)
- Modify: `services/agent-service/src/adapters/chat_agent_client.py:37` (import), `chat_agent_client.py:203-221` (`record_user_message`/`_apply_engagement_floor`), `chat_agent_client.py:291` (`_collect_profile_data`'s form-completion call site)
- Test: `services/agent-service/tests/unit/test_lead_scoring.py` (full rewrite)
- Test: `services/agent-service/tests/unit/test_chat_agent_client_scoring.py` (header comment only in this task — new tool tests come in Tasks 2-3)

**Interfaces:**
- Produces: `message_count_floor(user_message_count: int) -> tuple[LeadScore, str] | None` — `None` below 5 messages, `(WARM, "...")` at 5-9, `(HOT, "...")` at 10+.
- Produces: `apply_score_floor(current_score: LeadScore, floor_score: LeadScore, floor_justification: str) -> tuple[LeadScore, str] | None` — merges monotonically, `None` if the floor doesn't exceed `current_score`.
- Produces (on `ChatAgentClient`): `async def _raise_score_floor(self, floor_score: LeadScore, floor_justification: str) -> None` — the shared merge-and-persist helper Tasks 2 and 3 will also call.
- Consumes: `LeadScore` from `src/domain/models.py` (unchanged).

- [ ] **Step 1: Write the failing tests for the new `lead_scoring.py` API**

Replace the entire contents of `services/agent-service/tests/unit/test_lead_scoring.py`:

```python
"""Property-based tests (Hypothesis) for BR-17b lead-scoring floors — P9 (determinism)
and the monotonic never-downgrades invariant (business-logic-model.md Section 12,
Incremento 2/3). Each ChatAgentClient call site computes its own floor and merges it
via apply_score_floor(); a lead's score only ever goes up."""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.domain.lead_scoring import apply_score_floor, message_count_floor
from src.domain.models import LeadScore

_RANK = {LeadScore.COLD: 0, LeadScore.WARM: 1, LeadScore.HOT: 2}


def test_message_count_floor_below_5_is_none():
    assert message_count_floor(4) is None


def test_message_count_floor_at_5_is_warm():
    score, _ = message_count_floor(5)
    assert score == LeadScore.WARM


def test_message_count_floor_at_10_is_hot():
    score, _ = message_count_floor(10)
    assert score == LeadScore.HOT


@given(count=st.integers(min_value=0, max_value=4))
def test_message_count_floor_always_none_below_5(count):
    assert message_count_floor(count) is None


@given(count=st.integers(min_value=5, max_value=9))
def test_message_count_floor_always_warm_between_5_and_9(count):
    score, _ = message_count_floor(count)
    assert score == LeadScore.WARM


@given(count=st.integers(min_value=10, max_value=1000))
def test_message_count_floor_always_hot_at_or_above_10(count):
    score, _ = message_count_floor(count)
    assert score == LeadScore.HOT


_lead_scores = st.sampled_from(list(LeadScore))


@given(current_score=_lead_scores, floor_score=_lead_scores)
def test_apply_score_floor_never_downgrades(current_score, floor_score):
    result = apply_score_floor(current_score, floor_score, "some justification")
    new_score = result[0] if result is not None else current_score
    assert _RANK[new_score] >= _RANK[current_score]


def test_apply_score_floor_returns_none_when_floor_does_not_exceed_current():
    assert apply_score_floor(LeadScore.HOT, LeadScore.WARM, "not enough") is None


def test_apply_score_floor_upgrades_cold_to_warm():
    result = apply_score_floor(LeadScore.COLD, LeadScore.WARM, "5+ mensajes")
    assert result == (LeadScore.WARM, "5+ mensajes")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/agent-service && pytest tests/unit/test_lead_scoring.py -v`
Expected: FAIL — `ImportError: cannot import name 'message_count_floor' from 'src.domain.lead_scoring'` (the old file still only exports `ScoringSignals`, `score_lead`, `engagement_floor`, `apply_score_floor`).

- [ ] **Step 3: Rewrite `lead_scoring.py`**

Replace the entire contents of `services/agent-service/src/domain/lead_scoring.py`:

```python
"""BR-17b (business-rules.md Incremento 2/3): hot/warm/cold lead scoring. Pure
functions — no infrastructure dependency, deterministic (P9), so they can be
property-tested with Hypothesis without a live Postgres/agent connection.

Each ChatAgentClient call site (record_user_message, _flag_purchase_intent,
_collect_profile_data — see chat_agent_client.py) computes its own floor and merges it
via apply_score_floor(). A lead's score only ever goes up, never down, across these
independent signals."""
from __future__ import annotations

from src.domain.models import LeadScore

_SCORE_RANK: dict[LeadScore, int] = {LeadScore.COLD: 0, LeadScore.WARM: 1, LeadScore.HOT: 2}


def message_count_floor(user_message_count: int) -> tuple[LeadScore, str] | None:
    """Engagement-based minimum score from raw message volume alone. Returns None
    below the first threshold — nothing to raise yet."""
    if user_message_count >= 10:
        return LeadScore.HOT, "10+ mensajes del usuario en la conversación."
    if user_message_count >= 5:
        return LeadScore.WARM, "5+ mensajes del usuario en la conversación."
    return None


def apply_score_floor(
    current_score: LeadScore,
    floor_score: LeadScore,
    floor_justification: str,
) -> tuple[LeadScore, str] | None:
    """Merges a computed floor with the lead's current score, monotonically (never
    downgrades). Returns the new (score, justification) if the floor exceeds the
    current score, or None if nothing changes."""
    if _SCORE_RANK[floor_score] > _SCORE_RANK[current_score]:
        return floor_score, floor_justification
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd services/agent-service && pytest tests/unit/test_lead_scoring.py -v`
Expected: PASS (all tests green). This will also make `src/adapters/chat_agent_client.py` fail to import (`apply_score_floor` is now called with the old 4-arg signature) — expected at this point, fixed in the next steps.

- [ ] **Step 5: Update the import in `chat_agent_client.py`**

In `services/agent-service/src/adapters/chat_agent_client.py:37`, change:

```python
from src.domain.lead_scoring import apply_score_floor
```

to:

```python
from src.domain.lead_scoring import apply_score_floor, message_count_floor
```

- [ ] **Step 6: Replace `_apply_engagement_floor` with `_raise_score_floor`**

In `services/agent-service/src/adapters/chat_agent_client.py`, replace lines 203-221 (the `record_user_message` and `_apply_engagement_floor` methods):

```python
    async def record_user_message(self) -> None:
        """BR-17b: called once per user turn (ChatWebSocketHandler) so the engagement
        floor (5+ user messages -> warm, 10+ -> hot) re-evaluates after every message."""
        self._user_message_count += 1
        await self._apply_engagement_floor()

    async def _apply_engagement_floor(self, *, form_completed: bool = False) -> None:
        """BR-17b: raises Lead.score to the engagement floor if it exceeds the current
        score — monotonic (never downgrades), see apply_score_floor()."""
        lead = await self._lead_repository.find_by_service_session_id(self._conversation_id)
        current_score = lead.score if lead is not None else LeadScore.COLD
        current_justification = lead.score_justification if lead is not None else ""
        result = apply_score_floor(
            current_score, current_justification, self._user_message_count, form_completed
        )
        if result is not None:
            score, justification = result
            await self._upsert_lead(score=score, score_justification=justification)
```

with:

```python
    async def record_user_message(self) -> None:
        """BR-17b: called once per user turn (ChatWebSocketHandler) so the message-count
        floor (5+ user messages -> warm, 10+ -> hot) re-evaluates after every message."""
        self._user_message_count += 1
        floor = message_count_floor(self._user_message_count)
        if floor is not None:
            await self._raise_score_floor(*floor)

    async def _raise_score_floor(self, floor_score: LeadScore, floor_justification: str) -> None:
        """Merges a computed score floor into the lead's persisted score — monotonic
        (never downgrades). Shared by record_user_message (message-count floor),
        _flag_purchase_intent (early-certainty floor), and _collect_profile_data
        (form-completion floor)."""
        lead = await self._lead_repository.find_by_service_session_id(self._conversation_id)
        current_score = lead.score if lead is not None else LeadScore.COLD
        result = apply_score_floor(current_score, floor_score, floor_justification)
        if result is not None:
            score, justification = result
            await self._upsert_lead(score=score, score_justification=justification)
```

- [ ] **Step 7: Update `_collect_profile_data`'s form-completion call site**

In `services/agent-service/src/adapters/chat_agent_client.py:291`, change:

```python
        await self._apply_engagement_floor(form_completed=True)
```

to:

```python
        await self._raise_score_floor(
            LeadScore.HOT, "Completó el formulario de perfil con datos de contacto confirmados."
        )
```

- [ ] **Step 8: Update the header comment in `test_chat_agent_client_scoring.py`**

In `services/agent-service/tests/unit/test_chat_agent_client_scoring.py:1-3`, change:

```python
"""BR-17b — engagement-based lead scoring wired into ChatAgentClient. `Agent` and
`FoundryChatClient` are patched at construction time (no real Foundry/network calls);
only the scoring wiring (record_user_message, _apply_engagement_floor) is under test."""
```

to:

```python
"""BR-17b — lead scoring wired into ChatAgentClient. `Agent` and `FoundryChatClient`
are patched at construction time (no real Foundry/network calls); only the scoring
wiring (record_user_message, _raise_score_floor, _flag_purchase_intent,
_collect_profile_data's form-completion floor) is under test."""
```

- [ ] **Step 9: Run the full agent-service unit test suite**

Run: `cd services/agent-service && pytest tests/unit -v`
Expected: PASS — including the existing `test_record_user_message_*` and `test_upsert_lead_*` tests in `test_chat_agent_client_scoring.py`, unchanged in behavior since `message_count_floor` preserves the same 5/10 thresholds as the old `engagement_floor`.

- [ ] **Step 10: Commit**

```bash
git add services/agent-service/src/domain/lead_scoring.py services/agent-service/src/adapters/chat_agent_client.py services/agent-service/tests/unit/test_lead_scoring.py services/agent-service/tests/unit/test_chat_agent_client_scoring.py
git commit -m "refactor(agent-service): consolidate lead-scoring floors, drop dead score_lead()

ScoringSignals/score_lead() were never wired into production — engagement_floor()
was standing in for the purchase-intent/motivation signals they needed. Splits the
message-count floor out as its own function and generalizes apply_score_floor() to
take any precomputed floor, so upcoming purchase-intent and form-completion floors
can reuse it without collapsing back into one do-everything function."
```

---

### Task 2: Add `flag_purchase_intent` tool (early-certainty → warm)

**Files:**
- Modify: `services/agent-service/src/adapters/chat_agent_client.py` (add `_flag_purchase_intent`, register tool, extend `_AGENT_INSTRUCTIONS`)
- Test: `services/agent-service/tests/unit/test_chat_agent_client_scoring.py`

**Interfaces:**
- Consumes: `_raise_score_floor` from Task 1 (`async def _raise_score_floor(self, floor_score: LeadScore, floor_justification: str) -> None`).
- Produces: `async def _flag_purchase_intent(self, reason: str) -> str` — registered as tool name `flag_purchase_intent`, callable by any test that constructs a `ChatAgentClient` via `_build_client`.

- [ ] **Step 1: Write the failing tests**

Add to `services/agent-service/tests/unit/test_chat_agent_client_scoring.py` (after the existing `test_record_user_message_never_downgrades_an_already_hot_lead` test, before the `# ── Incremento 3` section):

```python
@pytest.mark.asyncio
async def test_flag_purchase_intent_raises_score_to_warm():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client._flag_purchase_intent("Dijo que quiere inscribirse ya mismo")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.WARM
    assert "Dijo que quiere inscribirse ya mismo" in stored.score_justification


@pytest.mark.asyncio
async def test_flag_purchase_intent_creates_a_lead_when_none_exists_yet():
    repo = FakeLeadRepository()
    client = _build_client(repo)

    await client._flag_purchase_intent("Primer mensaje: quiere comprar de inmediato")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored is not None
    assert stored.score == LeadScore.WARM


@pytest.mark.asyncio
async def test_flag_purchase_intent_never_downgrades_an_already_hot_lead():
    lead = Lead(
        id="lead-1",
        created_at=datetime.now(timezone.utc),
        service_session_id="conv-1",
        score=LeadScore.HOT,
        score_justification="ya hot",
    )
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client._flag_purchase_intent("mensaje temprano")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.HOT
    assert stored.score_justification == "ya hot"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/agent-service && pytest tests/unit/test_chat_agent_client_scoring.py -v -k flag_purchase_intent`
Expected: FAIL with `AttributeError: 'ChatAgentClient' object has no attribute '_flag_purchase_intent'`.

- [ ] **Step 3: Implement `_flag_purchase_intent` and register it as a tool**

In `services/agent-service/src/adapters/chat_agent_client.py`, add the method right after `_raise_score_floor` (added in Task 1, currently the block right before `_upsert_lead`):

```python
    async def _flag_purchase_intent(self, reason: str) -> str:
        """Tool: the agent calls this as soon as it detects the visitor is already
        decided/certain about enrolling — often but not necessarily on their very
        first message — to raise the lead's floor to warm even before contact data
        is collected."""
        await self._raise_score_floor(LeadScore.WARM, f"Intención de compra temprana: {reason}")
        return "Señal de intención de compra registrada."
```

Then register it in the `tools=[...]` list (currently ending after the `create_payment_link` tool block, `chat_agent_client.py:179-186`), adding a fourth entry:

```python
                tool(
                    self._flag_purchase_intent,
                    name="flag_purchase_intent",
                    description=(
                        "Registra que el visitante ya muestra intencion de compra clara "
                        "y decidida (no solo exploracion), incluso si es en su primer "
                        "mensaje y aun no tienes sus datos de contacto. Llamala en cuanto "
                        "detectes esa senal, antes de pedir mas datos."
                    ),
                ),
```

- [ ] **Step 4: Extend `_AGENT_INSTRUCTIONS`**

In `services/agent-service/src/adapters/chat_agent_client.py:52-70`, replace the `_AGENT_INSTRUCTIONS` constant:

```python
_AGENT_INSTRUCTIONS = (
    "Eres el asesor de ventas de DMC Institute, un asistente de IA (identificate como "
    "tal si te preguntan). Conversa libremente con el visitante para entender su "
    "background profesional, motivacion y que quiere aprender — nunca presentes "
    "formularios ni hagas varias preguntas en el mismo turno. Si en cualquier momento "
    "de la conversacion, incluso en el primer mensaje del visitante, notas que ya esta "
    "decidido a inscribirse (no solo explorando opciones), invoca flag_purchase_intent "
    "con una razon breve, antes de pedir mas datos. Cuando necesites datos "
    "estructurados de calificacion (presupuesto, duracion maxima disponible en semanas, "
    "background profesional, stack deseado, nombre completo y email de contacto), invoca "
    "collect_profile_data con los valores que ya infieras de la conversacion (nombre y "
    "email vacios si aun no te los dio) — el usuario los confirmara o completara en un "
    "widget. Una vez tengas esos datos confirmados, invoca get_course_recommendations con "
    "ellos para buscar programas reales del catalogo — nunca inventes cursos, precios "
    "ni mallas curriculares fuera de lo que esa tool te devuelva. Si esa tool te dice "
    "que no hay match exacto y te sugiere un rango ampliado, ofrece esa alternativa al "
    "usuario en tus propias palabras y, si acepta, vuelve a llamar a "
    "get_course_recommendations con accept_relaxed_filters=true. Cuando el usuario "
    "exprese intencion de compra de un programa, invoca create_payment_link con el "
    "monto y la descripcion del programa. Si el usuario pide hablar con una persona, "
    "dile que alguien del equipo se pondra en contacto, sin dar telefono ni WhatsApp."
)
```

(This is the same text as before plus the new second sentence about `flag_purchase_intent` — Task 3 will extend it further with `set_lead_motivation`.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd services/agent-service && pytest tests/unit/test_chat_agent_client_scoring.py -v`
Expected: PASS (all tests, old and new).

- [ ] **Step 6: Commit**

```bash
git add services/agent-service/src/adapters/chat_agent_client.py services/agent-service/tests/unit/test_chat_agent_client_scoring.py
git commit -m "feat(agent-service): add flag_purchase_intent tool for early-certainty scoring

Lets the agent raise a lead straight to warm as soon as it detects real buying
certainty, even on the visitor's first message — record_user_message() can't do
this itself since it runs before the agent has processed that message's content."
```

---

### Task 3: Add `set_lead_motivation` tool (fixes the "undefined" motivation)

**Files:**
- Modify: `services/agent-service/src/adapters/chat_agent_client.py` (import `Motivation`, add `_set_lead_motivation`, register tool, extend `_AGENT_INSTRUCTIONS` again)
- Test: `services/agent-service/tests/unit/test_chat_agent_client_scoring.py`

**Interfaces:**
- Consumes: `_upsert_lead(**fields)` (existing, `chat_agent_client.py:222-245`), `Motivation` enum from `src/domain/models.py:83-90`.
- Produces: `async def _set_lead_motivation(self, motivation: str, motivation_detail: str = "") -> str` — registered as tool name `set_lead_motivation`.

- [ ] **Step 1: Write the failing tests**

Add to `services/agent-service/tests/unit/test_chat_agent_client_scoring.py`, right after the three `test_flag_purchase_intent_*` tests added in Task 2. First add `Motivation` to the existing model import at the top of the file — change:

```python
from src.domain.models import Lead, LeadScore
```

to:

```python
from src.domain.models import Lead, LeadScore, Motivation
```

Then add the tests:

```python
@pytest.mark.asyncio
async def test_set_lead_motivation_persists_a_valid_category():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client._set_lead_motivation("salary", "Quiere un aumento de sueldo")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.motivation == Motivation.SALARY
    assert stored.motivation_detail == "Quiere un aumento de sueldo"


@pytest.mark.asyncio
async def test_set_lead_motivation_falls_back_to_undefined_on_an_invalid_value():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    client = _build_client(repo)

    await client._set_lead_motivation("not-a-real-category")

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.motivation == Motivation.UNDEFINED
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/agent-service && pytest tests/unit/test_chat_agent_client_scoring.py -v -k set_lead_motivation`
Expected: FAIL with `AttributeError: 'ChatAgentClient' object has no attribute '_set_lead_motivation'`.

- [ ] **Step 3: Import `Motivation` in `chat_agent_client.py`**

In `services/agent-service/src/adapters/chat_agent_client.py:38-45`, change:

```python
from src.domain.models import (
    Lead,
    LeadEvent,
    LeadScore,
    ProfileQuery,
    RecommendationCandidate,
    RecommendationRequest,
)
```

to:

```python
from src.domain.models import (
    Lead,
    LeadEvent,
    LeadScore,
    Motivation,
    ProfileQuery,
    RecommendationCandidate,
    RecommendationRequest,
)
```

- [ ] **Step 4: Implement `_set_lead_motivation` and register it as a tool**

Add the method right after `_flag_purchase_intent` (added in Task 2):

```python
    async def _set_lead_motivation(self, motivation: str, motivation_detail: str = "") -> str:
        """Tool: the agent calls this immediately after collect_profile_data resolves,
        inferring the category from the now-confirmed professional_background/
        desired_stack — never asked to the visitor directly. Falls back to UNDEFINED
        on an unrecognized value (defensive boundary parsing of the agent's tool-call
        arguments, same treatment as any other external input)."""
        try:
            motivation_enum = Motivation(motivation)
        except ValueError:
            motivation_enum = Motivation.UNDEFINED
        await self._upsert_lead(motivation=motivation_enum, motivation_detail=motivation_detail)
        return "Motivación registrada."
```

Register it in `tools=[...]`, right after the `flag_purchase_intent` entry added in Task 2:

```python
                tool(
                    self._set_lead_motivation,
                    name="set_lead_motivation",
                    description=(
                        "Registra la motivacion del visitante para aprender, inferida "
                        "del background profesional y stack deseado ya confirmados por "
                        "el usuario en el widget de collect_profile_data. Llamala "
                        "siempre inmediatamente despues de que collect_profile_data se "
                        "resuelva, antes de cualquier otra tool. motivation debe ser "
                        "exactamente uno de: growth, salary, company_requirement, "
                        "academic."
                    ),
                ),
```

- [ ] **Step 5: Extend `_AGENT_INSTRUCTIONS` again**

In `services/agent-service/src/adapters/chat_agent_client.py`, replace the `_AGENT_INSTRUCTIONS` constant (as left by Task 2) with:

```python
_AGENT_INSTRUCTIONS = (
    "Eres el asesor de ventas de DMC Institute, un asistente de IA (identificate como "
    "tal si te preguntan). Conversa libremente con el visitante para entender su "
    "background profesional, motivacion y que quiere aprender — nunca presentes "
    "formularios ni hagas varias preguntas en el mismo turno. Si en cualquier momento "
    "de la conversacion, incluso en el primer mensaje del visitante, notas que ya esta "
    "decidido a inscribirse (no solo explorando opciones), invoca flag_purchase_intent "
    "con una razon breve, antes de pedir mas datos. Cuando necesites datos "
    "estructurados de calificacion (presupuesto, duracion maxima disponible en semanas, "
    "background profesional, stack deseado, nombre completo y email de contacto), invoca "
    "collect_profile_data con los valores que ya infieras de la conversacion (nombre y "
    "email vacios si aun no te los dio) — el usuario los confirmara o completara en un "
    "widget. Apenas collect_profile_data se resuelva con los datos confirmados, invoca "
    "set_lead_motivation infiriendo la categoria (growth, salary, company_requirement o "
    "academic) a partir del background profesional y stack deseado ya confirmados — "
    "nunca se lo preguntes directamente al visitante. Luego invoca "
    "get_course_recommendations con esos datos confirmados para buscar programas reales "
    "del catalogo — nunca inventes cursos, precios ni mallas curriculares fuera de lo "
    "que esa tool te devuelva. Si esa tool te dice que no hay match exacto y te sugiere "
    "un rango ampliado, ofrece esa alternativa al usuario en tus propias palabras y, si "
    "acepta, vuelve a llamar a get_course_recommendations con "
    "accept_relaxed_filters=true. Cuando el usuario exprese intencion de compra de un "
    "programa, invoca create_payment_link con el monto y la descripcion del programa. "
    "Si el usuario pide hablar con una persona, dile que alguien del equipo se pondra "
    "en contacto, sin dar telefono ni WhatsApp."
)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd services/agent-service && pytest tests/unit/test_chat_agent_client_scoring.py -v`
Expected: PASS (all tests, old and new).

- [ ] **Step 7: Add a `_collect_profile_data`-resolution test proving the form-completion floor reaches `hot`**

This exercises the real pause/resume path (`PendingToolCallRegistry`) that Task 1 rewired, so it belongs here where the file's asyncio/pending-call test infrastructure is being touched anyway. First extend `_build_client` — replace it in `services/agent-service/tests/unit/test_chat_agent_client_scoring.py`:

```python
def _build_client(
    lead_repository: FakeLeadRepository,
    conversation_id: str = "conv-1",
    lead_event_publisher: LeadEventPublisher | None = None,
    on_profile_data_requested=None,
    pending_tool_calls: PendingToolCallRegistry | None = None,
) -> ChatAgentClient:
    with patch("src.adapters.chat_agent_client.FoundryChatClient"), patch(
        "src.adapters.chat_agent_client.Agent"
    ):
        return ChatAgentClient(
            project_endpoint="https://fake.example",
            model_deployment="fake-model",
            credential=MagicMock(),
            retry_policy=MagicMock(),
            payment_client=MagicMock(),
            pending_tool_calls=pending_tool_calls or PendingToolCallRegistry(),
            on_profile_data_requested=on_profile_data_requested or MagicMock(),
            orchestrator=MagicMock(),
            embedding_service=MagicMock(),
            lead_repository=lead_repository,
            conversation_id=conversation_id,
            lead_event_publisher=lead_event_publisher,
        )
```

Add `import asyncio` at the top of the file (before `from datetime import ...`). Then add the test, at the end of the file:

```python
@pytest.mark.asyncio
async def test_collect_profile_data_resolution_raises_score_to_hot():
    lead = Lead(id="lead-1", created_at=datetime.now(timezone.utc), service_session_id="conv-1")
    repo = FakeLeadRepository([lead])
    requested = []

    async def on_requested(event):
        requested.append(event)

    pending = PendingToolCallRegistry()
    client = _build_client(repo, on_profile_data_requested=on_requested, pending_tool_calls=pending)

    task = asyncio.create_task(
        client._collect_profile_data(
            budget=500.0,
            max_duration_weeks=8,
            professional_background="analista",
            desired_stack="data",
        )
    )
    await asyncio.sleep(0)  # let it reach the pause point
    call_id = requested[0].call_id
    pending.resolve(
        call_id,
        {
            "budget": 500.0,
            "max_duration_weeks": 8,
            "professional_background": "analista",
            "desired_stack": "data",
            "name": "Juan Pérez",
            "email": "juan@example.com",
        },
    )
    await task

    stored = await repo.find_by_service_session_id("conv-1")
    assert stored.score == LeadScore.HOT
    assert stored.score_justification == "Completó el formulario de perfil con datos de contacto confirmados."
```

- [ ] **Step 8: Run the full file again**

Run: `cd services/agent-service && pytest tests/unit/test_chat_agent_client_scoring.py -v`
Expected: PASS (all tests).

- [ ] **Step 9: Run the full agent-service test suite (unit, no DB needed)**

Run: `cd services/agent-service && pytest tests/unit -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add services/agent-service/src/adapters/chat_agent_client.py services/agent-service/tests/unit/test_chat_agent_client_scoring.py
git commit -m "feat(agent-service): add set_lead_motivation tool, fix undefined motivation

Lead.motivation defaulted to Motivation.UNDEFINED and nothing ever set it — every
lead showed 'undefined' in the BackOffice. The agent now infers the category from
the visitor's confirmed background/desired stack right after collect_profile_data
resolves, and persists it via a dedicated tool rather than guessing before the
widget confirms the real data."
```

---

### Task 4: Humanize motivation display in BackOffice

**Files:**
- Modify: `apps/backoffice/components/LeadDetailModal.tsx:1-13` (add exported `motivationLabel`), `:102-106` (use it)
- Create: `apps/backoffice/components/LeadDetailModal.test.tsx`

**Interfaces:**
- Produces: `export const motivationLabel = (motivation: string): string`.
- Consumes: nothing new — `LeadOut.motivation`/`motivationDetail` (`apps/backoffice/types/leads.ts`, unchanged).

- [ ] **Step 1: Write the failing test**

Create `apps/backoffice/components/LeadDetailModal.test.tsx`:

```tsx
import { describe, it, expect } from "vitest"
import { motivationLabel } from "./LeadDetailModal"

describe("motivationLabel", () => {
  it("maps each known motivation category to a Spanish label", () => {
    expect(motivationLabel("growth")).toBe("Crecimiento profesional")
    expect(motivationLabel("salary")).toBe("Aumento salarial")
    expect(motivationLabel("company_requirement")).toBe("Requisito de la empresa")
    expect(motivationLabel("academic")).toBe("Fines académicos")
  })

  it("maps the undefined default to a human label instead of showing it raw", () => {
    expect(motivationLabel("undefined")).toBe("Sin definir aún")
  })

  it("falls back to the raw value for an unrecognized category", () => {
    expect(motivationLabel("something-new")).toBe("something-new")
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/backoffice && npm test -- LeadDetailModal`
Expected: FAIL — `motivationLabel` is not exported from `./LeadDetailModal` (only a default export exists today).

- [ ] **Step 3: Add `motivationLabel` and use it in the component**

In `apps/backoffice/components/LeadDetailModal.tsx`, after the imports (lines 1-2) and before the `type LeadDetailModalProps` declaration (line 4), add:

```tsx
// ── Pure (exported for testing) ─────────────────────────────────────────────
export const motivationLabel = (motivation: string): string => {
  const labels: Record<string, string> = {
    growth: 'Crecimiento profesional',
    salary: 'Aumento salarial',
    company_requirement: 'Requisito de la empresa',
    academic: 'Fines académicos',
    undefined: 'Sin definir aún',
  }
  return labels[motivation] ?? motivation
}
```

Then, at lines 102-106, change:

```tsx
            <dt style={{ color: 'var(--color-text-muted)' }}>Motivación</dt>
            <dd style={{ margin: 0 }}>
              {lead.motivation}
              {lead.motivationDetail ? ` — ${lead.motivationDetail}` : ''}
            </dd>
```

to:

```tsx
            <dt style={{ color: 'var(--color-text-muted)' }}>Motivación</dt>
            <dd style={{ margin: 0 }}>
              {motivationLabel(lead.motivation)}
              {lead.motivationDetail ? ` — ${lead.motivationDetail}` : ''}
            </dd>
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/backoffice && npm test -- LeadDetailModal`
Expected: PASS (all 3 cases).

- [ ] **Step 5: Run the full backoffice test suite**

Run: `cd apps/backoffice && npm test`
Expected: PASS — including `KanbanBoard.test.tsx`, whose fixtures hardcode `motivation: "undefined"` (`components/KanbanBoard.test.tsx:11`); that test doesn't render `LeadDetailModal`, so it's unaffected by this change.

- [ ] **Step 6: Type-check and build**

Run: `cd apps/backoffice && npm run build`
Expected: succeeds with no new TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add apps/backoffice/components/LeadDetailModal.tsx apps/backoffice/components/LeadDetailModal.test.tsx
git commit -m "fix(backoffice): show a human label instead of raw 'undefined' motivation

Even with the agent now setting Lead.motivation (previous commits), a lead can
still legitimately be undefined before collect_profile_data resolves — render
that state with a real label instead of the literal string 'undefined'."
```

---

## Manual verification (after all 4 tasks)

The agent-side tool wiring (`flag_purchase_intent`, `set_lead_motivation`, the new `_AGENT_INSTRUCTIONS`) can't be fully verified by unit tests alone — they depend on the real Foundry agent choosing to call the new tools appropriately. After merging:

```bash
cd services/agent-service
python -m scripts.manual_chat_check
```

Drive a conversation that (a) opens with clear buying certainty (e.g. "quiero inscribirme ya, tengo el presupuesto listo") and confirm the lead reaches `warm` before the form is filled; (b) completes the `collect_profile_data` widget and confirm the lead reaches `hot` with a non-`undefined` `motivation` in the BackOffice (`apps/backoffice`, `npm run dev`, `/leads`).
