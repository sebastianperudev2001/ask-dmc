# DMC Chat Frontend — Design Spec

**Date**: 2026-05-11  
**Status**: Approved  
**Source**: Claude Design bundle (`dmc-chatbot/project/`)

---

## 1. Scope

Full-page student-facing chat portal. Demo surface only — not an embeddable widget. Covers Unit 4 of the DMC Sales Agent project plan.

**Out of scope**: Backoffice portal (Unit 5), Mercado Pago integration, DynamoDB lead persistence, Cognito auth.

---

## 2. Stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | Next.js 15 App Router | TypeScript, `app/` directory |
| Styling | Tailwind CSS v4 | CSS variables in `@theme` block |
| Fonts | `next/font/google` | Geist + Geist Mono, no CDN |
| State | React hooks only | No external state library |
| API | Fetch Streams API | Native, no axios/SWR |

**Component style**: All React components are arrow functions (`const Foo = () => ...`). No `function` keyword components.

---

## 3. Directory Structure

```
apps/chat/
├── app/
│   ├── layout.tsx              # Geist fonts, html lang="es-PE"
│   ├── page.tsx                # Root shell — renders <ChatApp />
│   ├── globals.css             # @theme block + base styles
│   └── api/
│       └── ask/
│           └── route.ts        # Proxy → services/api POST /ask
├── components/
│   ├── ChatApp.tsx             # Top-level: dark mode state, layout grid
│   ├── Sidebar.tsx             # 272px aside: brandmark, history, user chip
│   ├── TopBar.tsx              # 56px header: avatar, title, search
│   ├── Welcome.tsx             # Centered welcome state + suggestion cards
│   ├── MessageList.tsx         # Scrollable chat area, max-width 760px
│   ├── UserMessage.tsx         # Right-aligned navy bubble
│   ├── BotMessage.tsx          # Avatar + ThinkingBlock + ToolCallBlock + answer + sources
│   ├── ThinkingBlock.tsx       # Collapsible thinking panel (for future Strands agent)
│   ├── ToolCallBlock.tsx       # Collapsible tool call: calling → running → done
│   ├── SourceChips.tsx         # Course name pills from X-Sources header
│   ├── Composer.tsx            # Auto-growing textarea + send button
│   └── BotAvatar.tsx           # Animated concentric node SVG
├── hooks/
│   └── useChat.ts              # All chat state + streaming logic
├── lib/
│   └── api.ts                  # streamAsk(question): AsyncGenerator<string>
├── data/
│   └── mock.ts                 # Static sidebar history + suggestion cards
├── types/
│   └── chat.ts                 # UserMessage, BotMessage, Source, ChatPhase types
├── .env.local                  # API_URL=http://localhost:8000
├── next.config.ts
├── tailwind.config.ts
└── package.json
```

---

## 4. Design Tokens (Tailwind v4 `@theme`)

All tokens match the Claude Design CSS exactly. Mapped to `@theme` in `globals.css`:

```css
@theme {
  --color-brand:        #0b1e3f;   /* deep institutional navy */
  --color-brand-2:      #1e3b73;
  --color-brand-ink:    #ffffff;
  --color-accent:       #f2c14e;   /* warm amber */
  --color-accent-deep:  #c8951f;
  --color-tool:         #2d6a5a;
  --color-tool-bg:      #e6f0ec;
  --color-think-bg:     #f0eef6;
  --color-think-ink:    #4a3f7a;
  --color-bg:           #f7f7f4;
  --color-surface:      #ffffff;
  --color-surface-2:    #f1f1ec;
  --color-surface-3:    #e8e8e1;
  --color-border:       #e4e4dc;
  --color-border-strong:#d4d4ca;
  --color-text:         #14181f;
  --color-text-muted:   #5b6472;
  --color-text-faint:   #8b94a3;
}

.dark {
  --color-brand:        #4a7dd1;
  /* Full token list: see Claude Design styles.css .dark block */
}
```

Dark mode: Tailwind `darkMode: 'class'`. Toggle flips `.dark` on `<html>` via `useState` in `ChatApp`.

---

## 5. API Integration

### Proxy Route

`app/api/ask/route.ts` — streams from `services/api/`:

```
POST /api/ask { question: string }
  → forward to process.env.API_URL/ask
  → pipe StreamingResponse back to client
  → forward X-Sources header
```

### `lib/api.ts`

```ts
async function* streamAsk(
  question: string,
  onSources: (sources: Source[]) => void
): AsyncGenerator<string>
// 1. POST /api/ask { question }
// 2. Read X-Sources header immediately from Response object (available before body)
// 3. Call onSources(parsed) once at stream end
// 4. Yield text chunks from ReadableStream body
```

### Bot message phases

```
"searching"  → ToolCallBlock status="running"  (waiting for first byte)
"streaming"  → ToolCallBlock status="done", answer accumulates
"done"       → SourceChips rendered from X-Sources
```

### `types/chat.ts`

```ts
type Source = { course: string; section: string; distance: number }

type BotMsg = {
  id: string
  role: "bot"
  phase: "searching" | "streaming" | "done"
  answer: string
  answerDone: boolean
  sources: Source[]
}

type UserMsg = { id: string; role: "user"; text: string }
type Message = UserMsg | BotMsg
```

---

## 6. Components

### `BotAvatar`
SVG with two concentric circles (amber outer ring + amber filled core). Two `span` ring elements with `@keyframes ring` (scale + opacity pulse). Core gets `@keyframes core` (0.85 scale) when `state="thinking"`. Sizes: 32px (chat) and 56px (welcome).

### `ThinkingBlock`
Collapsible panel. Not used in current API flow — scaffolded for the Strands agent (Unit 2). Props: `steps: string[]`, `live: boolean`. When `live`: spinner + shimmer on last step. When done: brain icon + step count.

### `ToolCallBlock`
Collapsible. Props: `name: string`, `args: string`, `result: string | null`, `status: "calling" | "running" | "done"`. In the real API flow: `name = "search_brochures"`, `args = { question }`, `result` = formatted X-Sources list.

### `SourceChips`
Row of small teal pills, one per unique `course` from `X-Sources`. Appears below the streamed answer when `phase === "done"`.

### `Composer`
`textarea` ref tracks height. `onChange` resets height to 24px then sets to `scrollHeight` (max 200px). `Enter` submits, `Shift+Enter` newlines. Send button disabled when `!value.trim() || busy`.

### `Sidebar`
Static. Groups: Hoy / Ayer / Semana pasada from `data/mock.ts`. Active item highlighted. Dark mode toggle (sun/moon icon). New chat button clears `messages` state if `!busy`.

---

## 7. Streaming State Machine (`useChat.ts`)

```
idle
  → user sends → busy = true
  → append UserMsg
  → append BotMsg { phase: "searching", answer: "", sources: [] }
  → call streamAsk(question)

searching
  → ToolCallBlock "running"
  → first chunk received → phase = "streaming"

streaming
  → ToolCallBlock "done" (collapsed)
  → answer accumulates via setMessages patch
  → scroll to bottom on each chunk

done (stream ends)
  → answerDone = true
  → sources set from X-Sources
  → busy = false
```

---

## 8. What's Not in Scope

- Session history is static mock data — clicking history items does nothing
- No lead capture (name/email) — that's Unit 3 (backend-api)
- No course cards — API returns free-form text, not structured recommendations
- No Mercado Pago link generation
- No localStorage persistence of visitor identity
- ThinkingBlock is scaffolded but not driven by real data
