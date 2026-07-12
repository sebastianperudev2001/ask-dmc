# Lead scoring & motivation — design

## Problem

Two issues found while investigating a "motivation shows as `undefined` in BackOffice" bug report:

1. **`Lead.motivation` is never set.** It defaults to `Motivation.UNDEFINED` (`src/domain/models.py:90,130`) and no code path ever writes anything else. The value travels unchanged to the BackOffice and is rendered raw (`apps/backoffice/components/LeadDetailModal.tsx:104`), so every lead shows the literal string "undefined".
2. **Lead scoring doesn't match the intended business rule.** Production scoring runs through `engagement_floor()` (`src/domain/lead_scoring.py:43-55`), which only ever raises a lead to `WARM` on form completion — `HOT` requires 10+ user messages. A separate, more complete formula, `score_lead()`/`ScoringSignals` (`lead_scoring.py:11-37`), already encodes a `purchase_intent`-driven path to `HOT`, but nothing in the codebase ever calls it — it's dead code, exercised only by its own unit test.

## Requirements (user-specified)

1. Motivation must be determined from what the user actually says about their background and desired stack — not asked as a separate question.
2. Every lead starts `COLD` by default, unless the first message (in practice: as soon as the agent detects it) already shows the visitor is certain/decided — in which case it should start `WARM`.
3. Completing the profile-data form should take the lead to `HOT`.
4. Remove the dead code this investigation surfaced.

## Non-goals

- No new Postgres migration — `Lead.motivation` and `Lead.motivation_detail` columns already exist and are unused; scoring already has `score`/`score_justification`.
- No new frontend form field — motivation is inferred by the agent from the conversation, never asked to the visitor directly (explicit user correction during design).
- `profile_fits_recommendation` / `urgent` signals from the old `score_lead()` formula are dropped — nothing in the codebase produces them and the user's 4 requirements don't call for them. Reintroducing them without a data source would be speculative.
- The 5+/10+ user-message engagement floor is kept as-is (explicit user decision — see Q&A below), layered alongside the new rules, not replaced by them.

## Design

### Why motivation classification happens *after* the widget, not before

`collect_profile_data` is called by the agent with its own best-guess `professional_background`/`desired_stack` *before* the user has seen the form. The user only provides the authoritative values when they submit the widget (`ProfileDataSubmittedIn`, resolved via `PendingToolCallRegistry`). Since requirement 1 says motivation must come from what the user actually answers, classification cannot happen at the initial `collect_profile_data` call — it must happen after the widget resolves, when `chat_agent_client.py:293-299` returns the confirmed `background`/`stack_deseado` back to the agent as the tool result.

### New tool: `set_lead_motivation`

```python
async def _set_lead_motivation(self, motivation: str, motivation_detail: str = "") -> str:
    try:
        motivation_enum = Motivation(motivation)
    except ValueError:
        motivation_enum = Motivation.UNDEFINED
    await self._upsert_lead(motivation=motivation_enum, motivation_detail=motivation_detail)
    return "Motivación registrada."
```

Registered as a fourth/fifth tool on the `Agent` alongside `collect_profile_data`, `get_course_recommendations`, `create_payment_link`. `_AGENT_INSTRUCTIONS` gains a sentence requiring the agent to call `set_lead_motivation` immediately after receiving the confirmed data from `collect_profile_data`'s result — before doing anything else (e.g. before `get_course_recommendations`) — inferring one of `growth`/`salary`/`company_requirement`/`academic` from the confirmed `background`/`stack_deseado`. Invalid/omitted values fall back to `Motivation.UNDEFINED` (boundary parsing — the agent's tool-call arguments are external input, same treatment as any other tool argument).

### New tool: `flag_purchase_intent`

```python
async def _flag_purchase_intent(self, reason: str) -> str:
    await self._raise_score_floor(LeadScore.WARM, f"Intención de compra temprana: {reason}")
    return "Señal de intención de compra registrada."
```

`_AGENT_INSTRUCTIONS` gains a sentence: as soon as the agent detects the visitor is already decided (not just exploring) — typically but not exclusively on the first message — call this tool. This satisfies requirement 2's "unless the first message signals certainty"; it can't be a literal first-message-only check because `record_user_message()` (`chat_websocket_handler.py:141`) runs before the agent has processed that message's content, so only the agent itself, via its own reasoning, can raise this signal.

### Scoring: consolidate three floors behind one mechanism

`lead_scoring.py` keeps the monotonic "floor" pattern (a lead's score only ever goes up) but stops hardcoding *which* floors exist inside `engagement_floor()`. Each call site now computes its own floor and merges it in:

```python
def message_count_floor(user_message_count: int) -> tuple[LeadScore, str] | None:
    if user_message_count >= 10:
        return LeadScore.HOT, "10+ mensajes del usuario en la conversación."
    if user_message_count >= 5:
        return LeadScore.WARM, "5+ mensajes del usuario en la conversación."
    return None

def apply_score_floor(
    current_score: LeadScore,
    current_justification: str,
    floor_score: LeadScore,
    floor_justification: str,
) -> tuple[LeadScore, str] | None:
    if _SCORE_RANK[floor_score] > _SCORE_RANK[current_score]:
        return floor_score, floor_justification
    return None
```

`ScoringSignals` and `score_lead()` are deleted (dead code — requirement 4).

`chat_agent_client.py` gains a shared helper:

```python
async def _raise_score_floor(self, floor_score: LeadScore, floor_justification: str) -> None:
    lead = await self._lead_repository.find_by_service_session_id(self._conversation_id)
    current_score = lead.score if lead is not None else LeadScore.COLD
    current_justification = lead.score_justification if lead is not None else ""
    result = apply_score_floor(current_score, current_justification, floor_score, floor_justification)
    if result is not None:
        score, justification = result
        await self._upsert_lead(score=score, score_justification=justification)
```

Three call sites feed it:

- `record_user_message()` — computes `message_count_floor(self._user_message_count)`; calls `_raise_score_floor` only if it returned non-`None`. (Unchanged behavior — still 5+/10+ messages.)
- `_flag_purchase_intent` (new) — floor `(WARM, "Intención de compra temprana: {reason}")`.
- `_collect_profile_data`, on widget resolution — floor becomes `(HOT, "Completó el formulario de perfil con datos de contacto confirmados.")`, replacing today's `form_completed=True` → `WARM` path. Since the widget always requires name+email, this preserves the implicit "hot needs complete contact data" invariant without needing to track it as a separate signal.

Every lead still defaults to `COLD` (`Lead.score: LeadScore = LeadScore.COLD`, unchanged) until one of these three floors fires.

### Frontend: humanize the motivation display

`apps/backoffice/components/LeadDetailModal.tsx:104` currently renders `lead.motivation` raw. Even after this change, a lead can legitimately still be `undefined` (created before the form/motivation step completes). Add a label map:

```ts
const MOTIVATION_LABELS: Record<string, string> = {
  growth: "Crecimiento profesional",
  salary: "Aumento salarial",
  company_requirement: "Requisito de la empresa",
  academic: "Fines académicos",
  undefined: "Sin definir aún",
};
```

Same fallback pattern already used elsewhere in that file (`?? 'Sin nombre'`, `|| '—'`).

## Testing

- `tests/unit/test_lead_scoring.py` — rewritten: drop all `ScoringSignals`/`score_lead`/`engagement_floor` cases, add cases for `message_count_floor()` (below 5 → `None`, 5-9 → warm, 10+ → hot) and `apply_score_floor()` against explicit `(floor_score, floor_justification)` inputs (never-downgrades property, kept as a Hypothesis property test).
- `tests/unit/test_chat_agent_client_scoring.py` — update to the new call sites (`_raise_score_floor`, the `HOT` floor on form completion, `_flag_purchase_intent` reaching `WARM`).
- New unit coverage for `_set_lead_motivation`'s defensive parsing (valid category, invalid string → falls back to `UNDEFINED`).
- Frontend: extend existing `LeadDetailModal` test coverage (if any) or add a small test for the label map fallback; `KanbanBoard.test.tsx`/`useLeadsSocket.test.ts` fixtures that hardcode `motivation: "undefined"` stay valid (label map still maps that value, just renders differently).

## Open items resolved during design (for reference)

- Keep or drop the 5+/10+ message-count floor → **keep**, layered alongside the new rules.
- How to classify motivation → **agent/LLM classification**, not a local keyword heuristic — the agent already elicits background/stack conversationally, so no separate infra call is added.
- When to classify motivation → **after** the widget resolves (confirmed data), not at the initial tool call (user correction — the initial call only carries the agent's pre-widget guess).
