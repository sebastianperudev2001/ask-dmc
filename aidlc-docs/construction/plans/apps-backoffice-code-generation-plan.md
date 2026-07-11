# Code Generation Plan — apps/backoffice

**Date**: 2026-07-11
**Based on**: `aidlc-docs/construction/apps-backoffice/functional-design/frontend-components.md` (approved)
**Unit**: `apps/backoffice` (new, standalone Next.js app, sibling to `apps/chat/`)
**Workspace root for code**: `apps/backoffice/` (never `aidlc-docs/`)
**Stories**: 1–7 (full frontend ownership) — `backoffice-unit-of-work-story-map.md`
**Grounded in**: `apps/chat`'s actual code (`lib/ChatService.ts`, `WsChatService.ts`, `runtime.ts`, `RuntimeProvider.tsx`, `hooks/useChat.ts`, `package.json`, `tsconfig.json`, `vitest.config.ts`, `app/globals.css`) — read directly, not assumed, to mirror conventions exactly.

---

## Step 1 — Project structure setup [x]
**Files** (all new): `package.json` (name `dmc-backoffice`, same scripts/deps as `apps/chat` minus `react-markdown`), `tsconfig.json`, `next.config.ts`, `postcss.config.mjs`, `vitest.config.ts`, `vitest.setup.ts`, `.env.example`/`.env.local` (`NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/leads`, `NEXT_PUBLIC_API_URL=http://localhost:8000`), `app/layout.tsx`, `app/globals.css` (base reset + neutral placeholder tokens — real visual identity comes in Step 9 via the `frontend-design` skill), `app/page.tsx` (renders `BackofficeApp`).
Also update root `.gitignore` (add `apps/backoffice/.next/`, `node_modules/`, `.env.local` entries, mirroring the existing `apps/chat` block).

## Step 2 — Wire types [x]
**File**: `types/leads.ts` (new) — `LeadOut`, `OutreachDraftOut` (camelCase, mirrors the snake_case→camelCase translation boundary pattern from `apps/chat`'s `types/chat.ts`), `Notification`.

## Step 3 — Data layer (Effect) — service + errors [x]
**Files**: `types/errors.ts` (`NetworkError`, `ParseError` — same shape as `apps/chat`), `lib/LeadsService.ts` (`Context.Tag` exposing `events: Stream.Stream<LeadWireEvent, LeadsError>`, no `sendMessage`-equivalent — this channel is push-only, matches Functional Design Section 1).

## Step 4 — Data layer (Effect) — WS implementation + runtime [x]
**Files**: `lib/WsLeadsService.ts` (`WsLeadsServiceLive`, `toLeadWireEvent` translation function — mirrors `WsChatService.ts`'s `toChatEvent` shape exactly), `lib/leadsRuntime.ts` (`LeadsAppRuntime = ManagedRuntime.make(WsLeadsServiceLive)`), `lib/LeadsRuntimeProvider.tsx`.

## Step 5 — Data layer unit tests [x]
Verified: 6/6 passing.
**File**: `lib/WsLeadsService.test.ts` — `toLeadWireEvent` translation (snapshot, lead_event/created, lead_event/score_changed, unknown type → null), hand-rolled `FakeWebSocket` (mirrors `WsChatService.test.ts`'s pattern).

## Step 6 — `useLeadsSocket` hook (pure reducers + hook) [x]
**File**: `hooks/useLeadsSocket.ts` — `applyLeadWireEvent`, `deriveNotification` (exported pure functions, Functional Design Section 3), the hook itself (subscribes once via `runtime.runFork`, cleans up via `Fiber.interrupt`, same shape as `useChat`'s WS-subscription `useEffect`).

## Step 7 — Hook unit tests [x]
Verified: 8/8 passing.
**File**: `hooks/useLeadsSocket.test.ts` — `applyLeadWireEvent` (snapshot replaces, lead_event upserts by id), `deriveNotification` (hot → Notification, warm/cold/created → null) tested as plain functions, no WS mock needed (same convention as `applyDelta`/`messagesFromHistory` tests).

## Step 8 — Components [x]
Verified: `tsc --noEmit` clean.
**Files** (all new, `components/`): `KanbanBoard.tsx` (+ exported pure `groupLeadsByScore`), `LeadCard.tsx`, `LeadDetailModal.tsx`, `DraftPanel.tsx`, `NotificationCenter.tsx`, `BackofficeApp.tsx` (top-level, sole `useLeadsSocket()` call site — mirrors `ChatApp.tsx`'s role).
`DraftPanel` calls `GET/POST` against `NEXT_PUBLIC_API_URL` directly (`fetch`) — no Effect involved here (Functional Design confines Effect to the WS layer only, matching `apps/chat`'s precedent where `fetchConversationHistory`/`fetchConversations` are plain `fetch` too).

## Step 9 — Component unit tests [x]
Verified: full suite 17/17 passing (3 test files).
**Files**: `components/KanbanBoard.test.tsx` (`groupLeadsByScore` as a plain function test — three tiers, empty tier renders empty not error per Story 1 AC verified at the pure-function level).

## Step 10 — Visual design pass (NFR-2)
Invoke the `frontend-design` skill to give `apps/backoffice` a distinct "internal tool" identity, aligned to dmc.pe brand guidelines, deliberately not matching `apps/chat`'s consumer-facing navy/gold branding. Updates `app/globals.css` tokens and component styling (inline `style={{ var(--color-*) }}`, same mechanism `apps/chat` uses) — no new component files, styling only.

---

## Explicitly Out of Scope for This Plan
- NFR Requirements/Design/Infrastructure Design — skipped for this unit (Units Generation decision, local `next dev` only).
- End-to-end browser verification against the real running `agent-service` — Build and Test stage, not Code Generation.
- Any change to `apps/chat` — untouched, confirmed independent in Application Design and Functional Design.
