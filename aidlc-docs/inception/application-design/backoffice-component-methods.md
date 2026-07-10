# Component Methods — BackOffice Lead Qualification View

**Date**: 2026-07-10
**Note**: Method signatures only — high-level input/output contracts. Business rules (validation, state machine transitions, exact dedupe semantics) are detailed in Functional Design (Construction phase).

---

## agent-service — Read Path

### `LeadQueryService`
| Method | Input | Output | Purpose |
|---|---|---|---|
| `list_leads` | — | `list[Lead]` | Returns all leads for the board (FR-7). No filtering/pagination at this stage (demo-scale, NFR-4). |

### `LeadRepository` (extended)
| Method | Input | Output | Purpose |
|---|---|---|---|
| `list_leads` | — | `list[Lead]` | New method; backs `LeadQueryService.list_leads`. |

---

## agent-service — Event Fan-Out

### `LeadEventPublisher`
| Method | Input | Output | Purpose |
|---|---|---|---|
| `publish` | `event: LeadEvent` | `None` | Fans out one event to all subscribed handlers, in-process. |
| `subscribe` | `handler: Callable[[LeadEvent], Awaitable[None]]` | `None` | Registers a consumer (`LeadBroadcaster`, `OutreachAgentService`). |

**`LeadEvent`** (indicative shape, refined in Functional Design): a tagged union covering at minimum lead-created and score-changed occurrences, carrying `lead_id` and the new `LeadScore`.

### `LeadBroadcaster`
| Method | Input | Output | Purpose |
|---|---|---|---|
| `handle_connection` | `websocket` | `None` | Accepts a `/ws/leads` connection; sends an initial snapshot (`LeadQueryService.list_leads()`), then streams events until disconnect. |
| `broadcast` | `event: LeadEvent` | `None` | Sends one event to all currently connected clients. Registered as a `LeadEventPublisher` subscriber. |

### `ChatAgentClient` (extended)
| Method | Input | Output | Purpose |
|---|---|---|---|
| *(existing `_apply_engagement_floor`, extended)* | — | — | After persisting an updated `Lead.score`, calls `LeadEventPublisher.publish(...)`. No new public method. |

---

## agent-service — Outreach Agent

### `OutreachAgentService`
| Method | Input | Output | Purpose |
|---|---|---|---|
| `generate_draft` | `lead_id: str` | `OutreachDraft` | Generates a personalized draft using the lead's `profile_summary`, `motivation`, `motivation_detail`, `recommended_programs` (FR-9). Enforces one-active-draft-per-lead (Story 4) — exact conflict behavior (replace/warn/return existing) deferred to Functional Design. Invoked both on-demand (FR-11) and automatically as a `LeadEventPublisher` subscriber when a lead's score becomes `hot` (FR-10). |
| `get_active_draft` | `lead_id: str` | `OutreachDraft \| None` | Used by `DraftPanel` when the detail popup opens, to show an existing draft without generating a new one. |
| `send_draft` | `draft_id: str` | `OutreachDraft` | Human-gated send action (FR-12). Calls `EmailSender.send(...)` to `Lead.email`, then marks the draft `sent`. |
| `discard_draft` | `draft_id: str` | `OutreachDraft` | Marks the draft `discarded` (Story 6) without sending. |

### `OutreachDraft` (domain model — indicative)
| Field | Type | Notes |
|---|---|---|
| `draft_id` | `str` | |
| `lead_id` | `str` | |
| `subject` | `str` | |
| `body` | `str` | |
| `status` | enum | `pending` \| `sent` \| `discarded` — exact state machine in Functional Design |
| `trigger` | enum | `auto` \| `on_demand` |
| `created_at` | `datetime` | |
| `sent_at` | `datetime \| None` | |

### `DraftRepository`
| Method | Input | Output | Purpose |
|---|---|---|---|
| `save` | `draft: OutreachDraft` | `None` | Insert/update. |
| `find_active_by_lead_id` | `lead_id: str` | `OutreachDraft \| None` | Backs the dedupe check in `generate_draft` and `DraftPanel`'s initial fetch. |
| `find_by_id` | `draft_id: str` | `OutreachDraft \| None` | Backs `send_draft`/`discard_draft`. |

### `EmailSender` (port only — no adapter yet)
| Method | Input | Output | Purpose |
|---|---|---|---|
| `send` | `to_email: str, subject: str, body: str` | `None` | Concrete provider chosen in NFR Requirements (NFR-5). |

---

## apps/backoffice — Frontend Components

### `KanbanBoard`
| Method/Hook | Purpose |
|---|---|
| `useEffect` (mount) | `GET /leads` → initial `Lead[]`, grouped into Hot/Warm/Cold |
| `useLeadsSocket` subscription | applies live `LeadEvent`s (create/score-change) to the in-memory board state |

### `LeadCard`
| Prop | Type | Purpose |
|---|---|---|
| `lead` | `Lead` | rendered summary |
| `onClick` | `(leadId: string) => void` | opens `LeadDetailModal` |

### `LeadDetailModal`
| Prop | Type | Purpose |
|---|---|---|
| `lead` | `Lead` | full field set (FR-4), sourced from the already-fetched board list (Q5 = B — no `GET /leads/{id}`) |
| `onClose` | `() => void` | |

### `DraftPanel`
| Method/Hook | Purpose |
|---|---|
| `useEffect` (on modal open) | fetches active draft for `lead_id` (backed by `OutreachAgentService.get_active_draft`) |
| `onGenerateDraft` | calls the on-demand draft-generation endpoint (FR-11) |
| `onSend` | calls the send endpoint (FR-12) |
| `onDiscard` | calls the discard endpoint (Story 6) |

### `NotificationCenter`
| Method/Hook | Purpose |
|---|---|
| `useLeadsSocket` subscription | filters for score-change events where new score is `hot`; appends to an in-memory, dismissable notification list |
| `onNotificationClick` | opens `LeadDetailModal` for the referenced `lead_id` |

### `WsLeadsClient` / `useLeadsSocket`
| Method | Purpose |
|---|---|
| `connect` | opens the single shared `/ws/leads` connection |
| `subscribe` | registers a local callback (used by both `KanbanBoard` and `NotificationCenter`) |
| `reconnect` (internal) | on drop, reconnects and triggers a fresh snapshot fetch, mirroring `LeadBroadcaster`'s reconciliation behavior (Story 3 AC) |
