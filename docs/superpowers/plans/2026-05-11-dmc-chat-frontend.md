# DMC Chat Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pixel-perfect full-page student chat portal at `apps/chat/` in Next.js 15 + Tailwind CSS v4, connected to the existing FastAPI RAG backend at `services/api/`.

**Architecture:** Next.js App Router with a proxy API route (`/api/ask`) that forwards streaming requests to the FastAPI backend and relays the `X-Sources` header. All chat state lives in a `useChat` hook. The bot reply shows a collapsible `ToolCallBlock` ("Buscando en brochures…") while waiting for the first token, then streams the answer and renders source chips.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS v4, Geist font via `next/font/google`, Fetch Streams API (no extra client libs), Vitest for logic tests.

**Component rule:** Every React component is an arrow function (`const Foo = () => …`). No `function` keyword components anywhere.

**Design source:** `/tmp/dmc-design/dmc-chatbot/project/` — the Claude Design prototype. Recreate pixel-perfectly; do not copy its internal structure.

---

## File Map

### New files

| Path | Responsibility |
|---|---|
| `apps/chat/package.json` | Dependencies and scripts |
| `apps/chat/next.config.ts` | Minimal Next.js config |
| `apps/chat/tsconfig.json` | TypeScript config |
| `apps/chat/postcss.config.mjs` | Tailwind v4 PostCSS plugin |
| `apps/chat/.env.local` | `API_URL=http://localhost:8000` |
| `apps/chat/app/globals.css` | `@import tailwindcss`, `@theme` tokens, dark overrides, animation keyframes, named CSS classes for avatars/thinking/tool-call blocks |
| `apps/chat/app/layout.tsx` | Geist fonts, `<html lang="es-PE">` |
| `apps/chat/app/page.tsx` | Renders `<ChatApp />` |
| `apps/chat/app/api/ask/route.ts` | Proxy: forwards POST to FastAPI, relays stream + X-Sources header |
| `apps/chat/types/chat.ts` | `Source`, `UserMsg`, `BotMsg`, `Message`, `ChatPhase` |
| `apps/chat/data/mock.ts` | Static sidebar history groups + suggestion cards |
| `apps/chat/lib/api.ts` | `streamAsk(question, onSources)` — async generator |
| `apps/chat/lib/api.test.ts` | Vitest tests for `streamAsk` |
| `apps/chat/components/icons.tsx` | All SVG icons as arrow-function components |
| `apps/chat/components/BotAvatar.tsx` | Animated concentric node |
| `apps/chat/components/ThinkingBlock.tsx` | Collapsible thinking panel (scaffolded, not driven yet) |
| `apps/chat/components/ToolCallBlock.tsx` | Collapsible tool-call panel: calling / running / done |
| `apps/chat/components/SourceChips.tsx` | Teal course-name pills from X-Sources |
| `apps/chat/components/Welcome.tsx` | Centered welcome state + suggestion cards |
| `apps/chat/components/Composer.tsx` | Auto-growing textarea + send button |
| `apps/chat/components/UserMessage.tsx` | Right-aligned navy bubble |
| `apps/chat/components/BotMessage.tsx` | Avatar + ThinkingBlock + ToolCallBlock + stream + SourceChips |
| `apps/chat/components/MessageList.tsx` | Scrollable chat area, max-width 760px |
| `apps/chat/components/Sidebar.tsx` | 272px aside: brandmark, history, user chip, dark toggle |
| `apps/chat/components/TopBar.tsx` | 56px header: avatar, title, search |
| `apps/chat/components/ChatApp.tsx` | Root: dark mode state, CSS Grid layout |
| `apps/chat/hooks/useChat.ts` | All chat + streaming state logic |
| `apps/chat/hooks/useChat.test.ts` | Vitest tests for hook state machine |
| `apps/chat/hooks/useDarkMode.ts` | Dark mode toggle — flips `.dark` class on `<html>` |

### Modified files

| Path | Change |
|---|---|
| `services/api/main.py` | Add `CORSMiddleware` for local dev |

---

## Task 1: Scaffold `apps/chat`

**Files:**
- Create: `apps/chat/package.json`
- Create: `apps/chat/next.config.ts`
- Create: `apps/chat/tsconfig.json`
- Create: `apps/chat/postcss.config.mjs`
- Create: `apps/chat/.env.local`

- [ ] **Step 1: Create directory and package.json**

```bash
mkdir -p /Users/sebastianchavarry01/Documents/ask-dmc/apps/chat
```

Create `apps/chat/package.json`:

```json
{
  "name": "dmc-chat",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --port 3000",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.0.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.0.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create next.config.ts**

```ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {}

export default nextConfig
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Create postcss.config.mjs**

```mjs
const config = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}

export default config
```

- [ ] **Step 5: Create .env.local**

```
API_URL=http://localhost:8000
```

- [ ] **Step 6: Install dependencies**

```bash
cd /Users/sebastianchavarry01/Documents/ask-dmc/apps/chat && npm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 7: Create required Next.js directories**

```bash
mkdir -p apps/chat/app/api/ask apps/chat/components apps/chat/hooks apps/chat/lib apps/chat/data apps/chat/types
```

- [ ] **Step 8: Commit**

```bash
git add apps/chat/
git commit -m "feat(chat): scaffold Next.js 15 + Tailwind v4 app"
```

---

## Task 2: Design tokens + base CSS

**Files:**
- Create: `apps/chat/app/globals.css`
- Create: `apps/chat/app/layout.tsx`
- Create: `apps/chat/app/page.tsx` (placeholder)

- [ ] **Step 1: Create globals.css**

This file: imports Tailwind, defines all design tokens in `@theme`, overrides for dark mode, keyframe animations, and named CSS classes that can't be expressed as Tailwind utilities (avatars, shimmer, tool-call blocks).

```css
@import "tailwindcss";

/* Dark mode: applied when .dark class is on <html> */
@variant dark (&:where(.dark, .dark *));

/* ── Design tokens ── */
@theme {
  --color-brand:        #0b1e3f;
  --color-brand-2:      #1e3b73;
  --color-brand-ink:    #ffffff;
  --color-accent:       #f2c14e;
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
  --color-danger:       #b3261e;

  --font-sans: "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "Geist Mono", ui-monospace, "SF Mono", Menlo, monospace;

  --shadow-sm: 0 1px 2px rgba(11,30,63,.05);
  --shadow:    0 1px 3px rgba(11,30,63,.06), 0 4px 12px rgba(11,30,63,.04);
  --shadow-lg: 0 12px 40px rgba(11,30,63,.12);
}

/* ── Dark mode overrides ── */
.dark {
  --color-brand:        #4a7dd1;
  --color-brand-2:      #6a96e0;
  --color-brand-ink:    #0c0f15;
  --color-accent:       #f5cd6a;
  --color-accent-deep:  #f2c14e;
  --color-tool:         #5fbfa6;
  --color-tool-bg:      #15302a;
  --color-think-bg:     #1e1a2e;
  --color-think-ink:    #b6a8e0;
  --color-bg:           #0c0f15;
  --color-surface:      #141821;
  --color-surface-2:    #1a1f2a;
  --color-surface-3:    #232936;
  --color-border:       #232936;
  --color-border-strong:#303849;
  --color-text:         #eef0f4;
  --color-text-muted:   #9aa3b2;
  --color-text-faint:   #6a7385;
}

/* ── Base ── */
*, *::before, *::after { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body {
  font-family: var(--font-sans);
  background: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "ss01", "cv11";
  overflow: hidden;
}
button { font-family: inherit; cursor: pointer; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--color-border-strong);
  border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover { background: var(--color-text-faint); }

/* ── Keyframes ── */
@keyframes blink  { 50% { opacity: 0; } }
@keyframes spin   { to  { transform: rotate(360deg); } }
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@keyframes ring {
  0%   { opacity: 0.6; transform: scale(0.7); }
  100% { opacity: 0;   transform: scale(1.4); }
}
@keyframes core {
  0%, 100% { transform: scale(1); }
  50%       { transform: scale(0.85); }
}
@keyframes pulse {
  0%   { box-shadow: 0 0 0 0 color-mix(in oklab, var(--color-accent) 70%, transparent); }
  70%  { box-shadow: 0 0 0 6px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
}

/* ── BotAvatar ── */
.bot-avatar {
  border-radius: 50%;
  background: var(--color-brand);
  display: grid;
  place-items: center;
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
}
.bot-avatar svg { display: block; }
.bot-avatar .ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1.5px solid var(--color-accent);
  opacity: 0;
  animation: ring 2.4s ease-out infinite;
}
.bot-avatar .ring.r2 { animation-delay: 1.2s; }
.bot-avatar.thinking .core {
  animation: core 1.4s ease-in-out infinite;
}

/* ── Thinking block ── */
.thinking {
  background: var(--color-think-bg);
  border: 1px solid color-mix(in oklab, var(--color-think-ink) 18%, transparent);
  border-radius: 12px;
  margin-bottom: 12px;
  font-size: 13px;
  overflow: hidden;
}
.thinking-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
  color: var(--color-think-ink);
  font-weight: 500;
}
.thinking-head .chev { margin-left: auto; transition: transform .15s; opacity: .7; }
.thinking.open .thinking-head .chev { transform: rotate(90deg); }
.thinking-body {
  padding: 10px 12px 12px;
  color: var(--color-think-ink);
  line-height: 1.55;
  border-top: 1px dashed color-mix(in oklab, var(--color-think-ink) 25%, transparent);
  font-size: 12.5px;
}
.thinking-body p { margin: 0 0 8px; }
.thinking-body p:last-child { margin-bottom: 0; }
.thinking-body .pending {
  background: linear-gradient(
    90deg,
    color-mix(in oklab, var(--color-think-ink) 50%, transparent) 0%,
    color-mix(in oklab, var(--color-think-ink) 90%, transparent) 50%,
    color-mix(in oklab, var(--color-think-ink) 50%, transparent) 100%
  );
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: shimmer 1.6s linear infinite;
}
.thinking.live .thinking-head .spinner {
  width: 12px; height: 12px;
  border-radius: 50%;
  border: 1.5px solid color-mix(in oklab, var(--color-think-ink) 30%, transparent);
  border-top-color: var(--color-think-ink);
  animation: spin 0.8s linear infinite;
}

/* ── Tool-call block ── */
.toolcall {
  background: var(--color-tool-bg);
  border: 1px solid color-mix(in oklab, var(--color-tool) 25%, transparent);
  border-radius: 12px;
  margin-bottom: 12px;
  font-family: var(--font-mono);
  font-size: 12.5px;
  overflow: hidden;
}
.toolcall-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
  color: var(--color-tool);
}
.toolcall-head .name { font-weight: 600; letter-spacing: -0.01em; }
.toolcall-head .status {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  opacity: .85;
}
.toolcall-head .chev { transition: transform .15s; opacity: .6; }
.toolcall.open .toolcall-head .chev { transform: rotate(90deg); }
.toolcall-body {
  border-top: 1px dashed color-mix(in oklab, var(--color-tool) 30%, transparent);
  padding: 10px 12px;
  color: color-mix(in oklab, var(--color-tool) 85%, var(--color-text));
  white-space: pre-wrap;
  line-height: 1.5;
  background: color-mix(in oklab, var(--color-tool-bg) 70%, var(--color-surface));
}
.toolcall.running .toolcall-head .dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: pulse 1.2s infinite;
}

/* ── Streaming cursor ── */
.cursor {
  display: inline-block;
  width: 7px;
  height: 16px;
  background: var(--color-text);
  margin-left: 2px;
  vertical-align: -2px;
  animation: blink 1s steps(1) infinite;
}
```

- [ ] **Step 2: Create app/layout.tsx**

```tsx
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'

const geistSans = Geist({
  subsets: ['latin'],
  variable: '--font-geist',
})

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
})

export const metadata: Metadata = {
  title: 'Asesor Académico DMC',
  description: 'Orientación personalizada de cursos DMC Institute',
}

const RootLayout = ({ children }: { children: React.ReactNode }) => (
  <html lang="es-PE" className={`${geistSans.variable} ${geistMono.variable}`}>
    <body>{children}</body>
  </html>
)

export default RootLayout
```

- [ ] **Step 3: Create placeholder app/page.tsx**

```tsx
const Page = () => <div style={{ padding: 24 }}>DMC Chat — placeholder</div>

export default Page
```

- [ ] **Step 4: Verify dev server starts**

```bash
cd apps/chat && npm run dev
```

Expected: server running at http://localhost:3000, no compilation errors. Visit the URL and see "DMC Chat — placeholder".

Stop the server (`Ctrl+C`).

- [ ] **Step 5: Commit**

```bash
git add apps/chat/app/
git commit -m "feat(chat): add design tokens, base CSS, layout"
```

---

## Task 3: TypeScript types + mock data

**Files:**
- Create: `apps/chat/types/chat.ts`
- Create: `apps/chat/data/mock.ts`

- [ ] **Step 1: Create types/chat.ts**

```ts
export type Source = {
  course: string
  section: string
  distance: number
}

export type ChatPhase = 'searching' | 'streaming' | 'done'

export type UserMsg = {
  id: string
  role: 'user'
  text: string
}

export type BotMsg = {
  id: string
  role: 'bot'
  phase: ChatPhase
  question: string      // the user's original question — shown in ToolCallBlock args
  answer: string
  answerDone: boolean
  sources: Source[]
}

export type Message = UserMsg | BotMsg

export type HistoryItem = {
  id: string
  title: string
  preview: string
  active?: boolean
}

export type HistoryGroup = {
  group: string
  items: HistoryItem[]
}

export type Suggestion = {
  title: string
  sub: string
}
```

- [ ] **Step 2: Create data/mock.ts**

```ts
import type { HistoryGroup, Suggestion } from '@/types/chat'

export const HISTORY: HistoryGroup[] = [
  {
    group: 'Hoy',
    items: [
      { id: 'h-1', title: 'Ruta para analista junior', preview: 'Recomendaste Python + SQL + Power BI…', active: true },
    ],
  },
  {
    group: 'Ayer',
    items: [
      { id: 'h-2', title: 'Diferencias entre diplomas', preview: 'Comparativa Business Analyst vs Data Science' },
      { id: 'h-3', title: 'Quiero migrar a roles de datos', preview: 'Vengo del área comercial, ¿por dónde empiezo?' },
    ],
  },
  {
    group: 'Semana pasada',
    items: [
      { id: 'h-4', title: 'Prerrequisitos de Machine Learning', preview: 'Necesito bases de Python primero' },
      { id: 'h-5', title: 'Modalidad híbrida vs en vivo', preview: 'Diferencias y carga horaria' },
      { id: 'h-6', title: 'Certificaciones DMC', preview: 'Vigencia y reconocimiento corporativo' },
      { id: 'h-7', title: 'Becas y financiamiento', preview: 'Opciones de pago en cuotas' },
    ],
  },
]

export const SUGGESTIONS: Suggestion[] = [
  { title: 'Soy analista junior y quiero crecer en datos', sub: 'Recomiéndame una ruta de aprendizaje' },
  { title: 'Quiero aprender Machine Learning desde cero', sub: '¿Qué requisitos previos necesito?' },
  { title: 'Compara el Diploma Business Analyst con Data Science', sub: 'Ayúdame a decidir según mi perfil' },
  { title: 'Necesito dominar Power BI para mi trabajo actual', sub: 'Curso corto y aplicado, por favor' },
]
```

- [ ] **Step 3: Commit**

```bash
git add apps/chat/types/ apps/chat/data/
git commit -m "feat(chat): add TypeScript types and mock data"
```

---

## Task 4: Proxy route + API lib + tests

**Files:**
- Create: `apps/chat/app/api/ask/route.ts`
- Create: `apps/chat/lib/api.ts`
- Create: `apps/chat/lib/api.test.ts`
- Create: `apps/chat/vitest.config.ts`

- [ ] **Step 1: Create vitest.config.ts**

```ts
import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  test: {
    environment: 'node',
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
})
```

- [ ] **Step 2: Write failing tests for streamAsk**

Create `apps/chat/lib/api.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { streamAsk } from './api'
import type { Source } from '@/types/chat'

const encoder = new TextEncoder()

const makeStream = (chunks: string[]) => {
  let i = 0
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]))
      } else {
        controller.close()
      }
    },
  })
}

const makeFetch = (chunks: string[], xSources: Source[] = []) =>
  vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: {
      get: (h: string) =>
        h.toLowerCase() === 'x-sources' ? JSON.stringify(xSources) : null,
    },
    body: makeStream(chunks),
  } as unknown as Response)

beforeEach(() => {
  vi.stubGlobal('fetch', makeFetch(['Hola', ' mundo']))
})

describe('streamAsk', () => {
  it('yields text chunks from the stream', async () => {
    const chunks: string[] = []
    const sources: Source[] = []

    for await (const chunk of streamAsk('test question', (s) => sources.push(...s))) {
      chunks.push(chunk)
    }

    expect(chunks.join('')).toContain('Hola')
  })

  it('calls onSources with parsed X-Sources after stream ends', async () => {
    const xSources: Source[] = [{ course: 'Power BI', section: 'precios', distance: 0.12 }]
    vi.stubGlobal('fetch', makeFetch(['respuesta'], xSources))

    const received: Source[] = []
    for await (const _ of streamAsk('pregunta', (s) => received.push(...s))) { /* consume */ }

    expect(received).toEqual(xSources)
  })

  it('calls /api/ask with POST and question body', async () => {
    const mockFetch = makeFetch(['ok'])
    vi.stubGlobal('fetch', mockFetch)

    for await (const _ of streamAsk('¿cuánto cuesta?', () => {})) { /* consume */ }

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/ask',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ question: '¿cuánto cuesta?' }),
      })
    )
  })

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))

    const gen = streamAsk('q', () => {})
    await expect(gen.next()).rejects.toThrow('API error: 500')
  })
})
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
cd apps/chat && npm test
```

Expected: FAIL — `streamAsk` is not defined.

- [ ] **Step 4: Implement lib/api.ts**

```ts
import type { Source } from '@/types/chat'

export async function* streamAsk(
  question: string,
  onSources: (sources: Source[]) => void,
): AsyncGenerator<string> {
  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  const xSourcesRaw = response.headers.get('x-sources')

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      yield decoder.decode(value, { stream: true })
    }
  } finally {
    reader.releaseLock()
  }

  if (xSourcesRaw) {
    try {
      onSources(JSON.parse(xSourcesRaw) as Source[])
    } catch {
      // malformed header — ignore
    }
  }
}
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd apps/chat && npm test
```

Expected: 4 tests pass.

- [ ] **Step 6: Create proxy route app/api/ask/route.ts**

```ts
import { NextRequest } from 'next/server'

export const POST = async (req: NextRequest): Promise<Response> => {
  const body = await req.json()

  const upstream = await fetch(`${process.env.API_URL}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!upstream.ok) {
    return new Response(JSON.stringify({ error: 'Upstream error' }), {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const xSources = upstream.headers.get('x-sources')

  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      ...(xSources ? { 'X-Sources': xSources } : {}),
    },
  })
}
```

- [ ] **Step 7: Commit**

```bash
git add apps/chat/lib/ apps/chat/app/api/ apps/chat/vitest.config.ts
git commit -m "feat(chat): add streaming API lib, proxy route, and tests"
```

---

## Task 5: Icons + BotAvatar

**Files:**
- Create: `apps/chat/components/icons.tsx`
- Create: `apps/chat/components/BotAvatar.tsx`

- [ ] **Step 1: Create components/icons.tsx**

```tsx
type IconProps = {
  size?: number
  strokeWidth?: number
  className?: string
}

const iconPath = (name: string) => {
  switch (name) {
    case 'plus':     return <path d="M12 5v14M5 12h14" />
    case 'send':     return <path d="M5 12l14-7-5 16-3-7-6-2z" />
    case 'sun':      return (<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>)
    case 'moon':     return <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    case 'search':   return (<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>)
    case 'chev':     return <path d="M9 6l6 6-6 6" />
    case 'settings': return (<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 1 1 7 4.9l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>)
    case 'check':    return <path d="M5 12l4 4 10-10" />
    case 'brain':    return (<><path d="M9 4a3 3 0 0 0-3 3v1a3 3 0 0 0-2 5 3 3 0 0 0 2 5v1a3 3 0 0 0 6 0V4a3 3 0 0 0-3 0z" /><path d="M15 4a3 3 0 0 1 3 3v1a3 3 0 0 1 2 5 3 3 0 0 1-2 5v1a3 3 0 0 1-6 0" /></>)
    case 'tool':     return <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6 6 2.4 2.4 6-6a4 4 0 0 0 5.4-5.4l-2.7 2.7-2-2 2.7-2.7z" />
    default:         return null
  }
}

export const Icon = ({ name, size = 16, strokeWidth = 1.75, className }: IconProps & { name: string }) => (
  <svg
    width={size} height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    {iconPath(name)}
  </svg>
)
```

- [ ] **Step 2: Create components/BotAvatar.tsx**

```tsx
type BotAvatarProps = {
  size?: number
  state?: 'idle' | 'thinking'
}

const BotAvatar = ({ size = 32, state = 'idle' }: BotAvatarProps) => {
  const r1 = size * 0.18
  const r2 = size * 0.32
  return (
    <div
      className={`bot-avatar${state === 'thinking' ? ' thinking' : ''}`}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2} cy={size / 2} r={r2}
          fill="none"
          stroke="var(--color-accent)"
          strokeOpacity="0.5"
          strokeWidth="1"
        />
        <circle
          className="core"
          cx={size / 2} cy={size / 2} r={r1}
          fill="var(--color-accent)"
          style={{ transformOrigin: 'center' }}
        />
      </svg>
      <span className="ring" />
      <span className="ring r2" />
    </div>
  )
}

export default BotAvatar
```

- [ ] **Step 3: Commit**

```bash
git add apps/chat/components/icons.tsx apps/chat/components/BotAvatar.tsx
git commit -m "feat(chat): add icons and animated BotAvatar"
```

---

## Task 6: ThinkingBlock + ToolCallBlock + SourceChips

**Files:**
- Create: `apps/chat/components/ThinkingBlock.tsx`
- Create: `apps/chat/components/ToolCallBlock.tsx`
- Create: `apps/chat/components/SourceChips.tsx`

- [ ] **Step 1: Create components/ThinkingBlock.tsx**

Scaffolded for the future Strands agent. In the current flow this component is never rendered, but it must exist for `BotMessage` to import it.

```tsx
'use client'
import { useState, useEffect } from 'react'
import { Icon } from './icons'

type ThinkingBlockProps = {
  steps: string[]
  live?: boolean
}

const ThinkingBlock = ({ steps, live = false }: ThinkingBlockProps) => {
  const [open, setOpen] = useState(live)

  useEffect(() => {
    if (live) setOpen(true)
  }, [live])

  return (
    <div className={`thinking${open ? ' open' : ''}${live ? ' live' : ''}`}>
      <div className="thinking-head" onClick={() => setOpen((o) => !o)}>
        {live ? <span className="spinner" /> : <Icon name="brain" size={14} />}
        <span>{live ? 'Razonando…' : `Razonamiento (${steps.length} pasos)`}</span>
        <Icon name="chev" size={14} className="chev" />
      </div>
      {open && (
        <div className="thinking-body">
          {steps.map((s, i) => (
            <p key={i} className={live && i === steps.length - 1 ? 'pending' : ''}>{s}</p>
          ))}
        </div>
      )}
    </div>
  )
}

export default ThinkingBlock
```

- [ ] **Step 2: Create components/ToolCallBlock.tsx**

```tsx
'use client'
import { useState, useEffect } from 'react'
import { Icon } from './icons'

export type ToolCallStatus = 'calling' | 'running' | 'done'

type ToolCallBlockProps = {
  name: string
  args: string
  result: string | null
  status: ToolCallStatus
}

const STATUS_LABEL: Record<ToolCallStatus, string> = {
  calling: 'Llamando',
  running: 'Ejecutando',
  done:    'Completado',
}

const ToolCallBlock = ({ name, args, result, status }: ToolCallBlockProps) => {
  const [open, setOpen] = useState(status !== 'done')

  useEffect(() => {
    if (status === 'done') setOpen(false)
  }, [status])

  return (
    <div className={`toolcall${open ? ' open' : ''} ${status}`}>
      <div className="toolcall-head" onClick={() => setOpen((o) => !o)}>
        <Icon name="tool" size={14} />
        <span className="name">{name}()</span>
        <span className="status">
          {status === 'done'
            ? <Icon name="check" size={12} />
            : <span className="dot" />}
          {STATUS_LABEL[status]}
        </span>
        <Icon name="chev" size={14} className="chev" />
      </div>
      {open && (
        <div className="toolcall-body">
          <div style={{ opacity: 0.7, marginBottom: 6 }}>// argumentos</div>
          {args}
          {status === 'done' && result && (
            <>
              <div style={{ opacity: 0.7, margin: '10px 0 6px' }}>// resultado</div>
              {result}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default ToolCallBlock
```

- [ ] **Step 3: Create components/SourceChips.tsx**

```tsx
import type { Source } from '@/types/chat'

type SourceChipsProps = {
  sources: Source[]
}

const SourceChips = ({ sources }: SourceChipsProps) => {
  const unique = Array.from(new Set(sources.map((s) => s.course)))
  if (!unique.length) return null

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 6,
        marginTop: 10,
      }}
    >
      {unique.map((course) => (
        <span
          key={course}
          style={{
            fontSize: 11,
            fontWeight: 500,
            padding: '3px 8px',
            borderRadius: 999,
            background: 'var(--color-tool-bg)',
            color: 'var(--color-tool)',
            border: '1px solid color-mix(in oklab, var(--color-tool) 25%, transparent)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {course}
        </span>
      ))}
    </div>
  )
}

export default SourceChips
```

- [ ] **Step 4: Commit**

```bash
git add apps/chat/components/ThinkingBlock.tsx apps/chat/components/ToolCallBlock.tsx apps/chat/components/SourceChips.tsx
git commit -m "feat(chat): add ThinkingBlock, ToolCallBlock, SourceChips"
```

---

## Task 7: Welcome + Composer

**Files:**
- Create: `apps/chat/components/Welcome.tsx`
- Create: `apps/chat/components/Composer.tsx`

- [ ] **Step 1: Create components/Welcome.tsx**

```tsx
import BotAvatar from './BotAvatar'
import { SUGGESTIONS } from '@/data/mock'

type WelcomeProps = {
  onPick: (text: string) => void
}

const Welcome = ({ onPick }: WelcomeProps) => (
  <div
    style={{
      minHeight: 'calc(100vh - 56px - 160px)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      textAlign: 'center',
      padding: '24px 0',
    }}
  >
    <div style={{ marginBottom: 22 }}>
      <BotAvatar size={56} />
    </div>
    <h2
      style={{
        margin: '0 0 8px',
        fontSize: 28,
        fontWeight: 500,
        letterSpacing: '-0.02em',
        color: 'var(--color-text)',
      }}
    >
      Hola, soy tu asesor académico DMC
    </h2>
    <p
      style={{
        margin: '0 0 28px',
        color: 'var(--color-text-muted)',
        fontSize: 15,
        maxWidth: 460,
      }}
    >
      Te oriento para elegir el curso, especialización o diploma que mejor se ajuste a tu perfil
      profesional y objetivos de carrera.
    </p>
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 10,
        width: '100%',
        maxWidth: 620,
      }}
    >
      {SUGGESTIONS.map((s, i) => (
        <button
          key={i}
          onClick={() => onPick(s.title)}
          style={{
            textAlign: 'left',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 12,
            padding: '14px 16px',
            cursor: 'pointer',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            transition: 'border-color .15s, transform .15s, box-shadow .15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-brand)'
            e.currentTarget.style.boxShadow = 'var(--shadow)'
            e.currentTarget.style.transform = 'translateY(-1px)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-border)'
            e.currentTarget.style.boxShadow = 'none'
            e.currentTarget.style.transform = 'none'
          }}
        >
          <span style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-text)', lineHeight: 1.35 }}>
            {s.title}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-faint)' }}>
            {s.sub}
          </span>
        </button>
      ))}
    </div>
  </div>
)

export default Welcome
```

- [ ] **Step 2: Create components/Composer.tsx**

```tsx
'use client'
import { useState, useRef, useCallback, useEffect } from 'react'
import { Icon } from './icons'

type ComposerProps = {
  onSend: (text: string) => void
  disabled: boolean
}

const Composer = ({ onSend, disabled }: ComposerProps) => {
  const [val, setVal] = useState('')
  const taRef = useRef<HTMLTextAreaElement>(null)

  const grow = useCallback(() => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = '24px'
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }, [])

  useEffect(() => { grow() }, [val, grow])

  const submit = () => {
    const v = val.trim()
    if (!v || disabled) return
    onSend(v)
    setVal('')
  }

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 272,
        right: 0,
        padding: '14px 28px 22px',
        background: 'linear-gradient(to bottom, transparent 0%, var(--color-bg) 30%)',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          pointerEvents: 'auto',
          maxWidth: 760,
          margin: '0 auto',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border-strong)',
          borderRadius: 18,
          padding: '10px 10px 10px 16px',
          display: 'flex',
          alignItems: 'flex-end',
          gap: 8,
          boxShadow: 'var(--shadow)',
        }}
      >
        <textarea
          ref={taRef}
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder="Escribe tu consulta sobre cursos, especializaciones o tu ruta de aprendizaje…"
          rows={1}
          style={{
            flex: 1,
            border: 0,
            outline: 0,
            resize: 'none',
            background: 'transparent',
            fontFamily: 'inherit',
            fontSize: 14.5,
            color: 'var(--color-text)',
            lineHeight: 1.5,
            padding: '8px 0',
            maxHeight: 200,
            minHeight: 24,
          }}
        />
        <button
          disabled={!val.trim() || disabled}
          onClick={submit}
          style={{
            width: 36,
            height: 36,
            borderRadius: 12,
            background: !val.trim() || disabled ? 'var(--color-surface-3)' : 'var(--color-brand)',
            color: !val.trim() || disabled ? 'var(--color-text-faint)' : 'var(--color-brand-ink)',
            border: 0,
            display: 'grid',
            placeItems: 'center',
            cursor: !val.trim() || disabled ? 'not-allowed' : 'pointer',
            flexShrink: 0,
          }}
        >
          <Icon name="send" size={16} />
        </button>
      </div>
      <p
        style={{
          textAlign: 'center',
          fontSize: 11,
          color: 'var(--color-text-faint)',
          margin: '8px 0 0',
          pointerEvents: 'none',
        }}
      >
        El asesor puede equivocarse. Verifica detalles con el área académica.
        {' '}<kbd style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderBottomWidth: 2, borderRadius: 4, padding: '1px 5px' }}>Enter</kbd> para enviar ·{' '}
        <kbd style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderBottomWidth: 2, borderRadius: 4, padding: '1px 5px' }}>Shift</kbd>+<kbd style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderBottomWidth: 2, borderRadius: 4, padding: '1px 5px' }}>Enter</kbd> nueva línea
      </p>
    </div>
  )
}

export default Composer
```

- [ ] **Step 3: Commit**

```bash
git add apps/chat/components/Welcome.tsx apps/chat/components/Composer.tsx
git commit -m "feat(chat): add Welcome and Composer components"
```

---

## Task 8: Message components + MessageList

**Files:**
- Create: `apps/chat/components/UserMessage.tsx`
- Create: `apps/chat/components/BotMessage.tsx`
- Create: `apps/chat/components/MessageList.tsx`

- [ ] **Step 1: Create components/UserMessage.tsx**

```tsx
type UserMessageProps = { text: string }

const UserMessage = ({ text }: UserMessageProps) => (
  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 24 }}>
    <div
      style={{
        background: 'var(--color-brand)',
        color: 'var(--color-brand-ink)',
        padding: '10px 14px',
        borderRadius: '16px 16px 4px 16px',
        maxWidth: '80%',
        fontSize: 14.5,
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
      }}
    >
      {text}
    </div>
  </div>
)

export default UserMessage
```

- [ ] **Step 2: Create components/BotMessage.tsx**

```tsx
import type { BotMsg } from '@/types/chat'
import BotAvatar from './BotAvatar'
import ThinkingBlock from './ThinkingBlock'
import ToolCallBlock from './ToolCallBlock'
import SourceChips from './SourceChips'

type BotMessageProps = { msg: BotMsg }

const BotMessage = ({ msg }: BotMessageProps) => {
  const isThinking = msg.phase === 'searching' || msg.phase === 'streaming'
  const toolStatus = msg.phase === 'searching' ? 'running' : 'done'

  return (
    <div
      style={{
        display: 'flex',
        gap: 14,
        marginBottom: 24,
        alignItems: 'flex-start',
      }}
    >
      <div style={{ flexShrink: 0, marginTop: 2 }}>
        <BotAvatar size={32} state={isThinking ? 'thinking' : 'idle'} />
      </div>
      <div style={{ flex: 1, minWidth: 0, fontSize: 14.5, lineHeight: 1.6 }}>
        <ToolCallBlock
          name="search_brochures"
          args={`{ "question": "${msg.question}" }`}
          result={
            msg.sources.length
              ? msg.sources.map((s) => `→ ${s.course} / ${s.section}`).join('\n')
              : null
          }
          status={toolStatus}
        />
        {(msg.answer || msg.phase === 'streaming') && (
          <div style={{ whiteSpace: 'pre-wrap', color: 'var(--color-text)' }}>
            {msg.answer}
            {!msg.answerDone && <span className="cursor" />}
          </div>
        )}
        {msg.answerDone && <SourceChips sources={msg.sources} />}
      </div>
    </div>
  )
}

export default BotMessage
```

- [ ] **Step 3: Create components/MessageList.tsx**

```tsx
'use client'
import { useEffect, useRef } from 'react'
import type { Message } from '@/types/chat'
import UserMessage from './UserMessage'
import BotMessage from './BotMessage'

type MessageListProps = { messages: Message[] }

const MessageList = ({ messages }: MessageListProps) => {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    requestAnimationFrame(() => {
      if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
    })
  }, [messages])

  return (
    <div
      ref={ref}
      style={{
        flex: 1,
        overflowY: 'auto',
        scrollbarWidth: 'thin',
      }}
    >
      <div
        style={{
          maxWidth: 760,
          margin: '0 auto',
          padding: '32px 28px 140px',
        }}
      >
        {messages.map((m) =>
          m.role === 'user'
            ? <UserMessage key={m.id} text={m.text} />
            : <BotMessage key={m.id} msg={m} />
        )}
      </div>
    </div>
  )
}

export default MessageList
```

- [ ] **Step 4: Commit**

```bash
git add apps/chat/components/UserMessage.tsx apps/chat/components/BotMessage.tsx apps/chat/components/MessageList.tsx
git commit -m "feat(chat): add UserMessage, BotMessage, MessageList"
```

---

## Task 9: Sidebar + TopBar

**Files:**
- Create: `apps/chat/components/Sidebar.tsx`
- Create: `apps/chat/components/TopBar.tsx`

- [ ] **Step 1: Create components/Sidebar.tsx**

```tsx
'use client'
import { useState } from 'react'
import { Icon } from './icons'
import { HISTORY } from '@/data/mock'

type SidebarProps = {
  dark: boolean
  onToggleDark: () => void
  onNew: () => void
}

const Sidebar = ({ dark, onToggleDark, onNew }: SidebarProps) => {
  const [activeId, setActiveId] = useState('h-1')

  return (
    <aside
      style={{
        width: 272,
        background: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '18px 18px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--color-text)', fontSize: 15 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--color-brand)', color: 'var(--color-brand-ink)', display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 12, letterSpacing: '0.04em' }}>
            DMC
          </div>
          <div>Asesor<span style={{ color: 'var(--color-accent-deep)', fontWeight: 500 }}> · IA</span></div>
        </div>
        <button
          onClick={onToggleDark}
          title="Cambiar tema"
          style={{ width: 32, height: 32, borderRadius: 8, border: '1px solid transparent', background: 'transparent', color: 'var(--color-text-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer' }}
        >
          <Icon name={dark ? 'sun' : 'moon'} size={16} />
        </button>
      </div>

      {/* New chat */}
      <button
        onClick={onNew}
        style={{
          margin: '4px 12px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 12px',
          borderRadius: 10,
          background: 'var(--color-brand)',
          color: 'var(--color-brand-ink)',
          border: '1px solid var(--color-brand)',
          fontSize: 13.5,
          fontWeight: 500,
        }}
      >
        <Icon name="plus" size={16} />
        Nueva conversación
      </button>

      {/* History */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px 16px', scrollbarWidth: 'thin' }}>
        {HISTORY.map((g) => (
          <div key={g.group}>
            <div style={{ padding: '12px 10px 6px', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-faint)' }}>
              {g.group}
            </div>
            {g.items.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveId(item.id)}
                title={item.title}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  background: activeId === item.id ? 'var(--color-surface-2)' : 'transparent',
                  border: `1px solid ${activeId === item.id ? 'var(--color-border)' : 'transparent'}`,
                  borderRadius: 8,
                  padding: '8px 10px',
                  fontSize: 13,
                  color: 'var(--color-text)',
                  cursor: 'pointer',
                  display: 'block',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {item.title}
                <div style={{ fontSize: 11.5, color: 'var(--color-text-faint)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.preview}
                </div>
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={{ borderTop: '1px solid var(--color-border)', padding: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
          <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'var(--color-surface-3)', color: 'var(--color-text)', display: 'grid', placeItems: 'center', fontSize: 12, fontWeight: 600, flexShrink: 0 }}>
            MC
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>María Castillo</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>Estudiante · Plan Anual</div>
          </div>
        </div>
        <button title="Ajustes" style={{ width: 32, height: 32, borderRadius: 8, border: '1px solid transparent', background: 'transparent', color: 'var(--color-text-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer' }}>
          <Icon name="settings" size={16} />
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
```

- [ ] **Step 2: Create components/TopBar.tsx**

```tsx
import BotAvatar from './BotAvatar'
import { Icon } from './icons'

type TopBarProps = { busy: boolean }

const TopBar = ({ busy }: TopBarProps) => (
  <div
    style={{
      height: 56,
      padding: '0 20px 0 24px',
      borderBottom: '1px solid var(--color-border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
      background: 'var(--color-surface)',
      flexShrink: 0,
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
      <BotAvatar size={26} state={busy ? 'thinking' : 'idle'} />
      <h1 style={{ margin: 0, fontSize: 14.5, fontWeight: 500, letterSpacing: '-0.005em', color: 'var(--color-text)', whiteSpace: 'nowrap' }}>
        Asesor Académico DMC
      </h1>
      <span style={{ color: 'var(--color-text-faint)', fontSize: 13 }}>· Recomendación de cursos</span>
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <button
        title="Buscar"
        style={{ width: 32, height: 32, borderRadius: 8, border: '1px solid transparent', background: 'transparent', color: 'var(--color-text-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer' }}
      >
        <Icon name="search" size={16} />
      </button>
    </div>
  </div>
)

export default TopBar
```

- [ ] **Step 3: Commit**

```bash
git add apps/chat/components/Sidebar.tsx apps/chat/components/TopBar.tsx
git commit -m "feat(chat): add Sidebar and TopBar"
```

---

## Task 10: `useChat` hook + tests

**Files:**
- Create: `apps/chat/hooks/useChat.ts`
- Create: `apps/chat/hooks/useChat.test.ts`

- [ ] **Step 1: Write failing tests for useChat**

Create `apps/chat/hooks/useChat.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock streamAsk before importing useChat
vi.mock('@/lib/api', () => ({
  streamAsk: vi.fn(),
}))

import { streamAsk } from '@/lib/api'
import { buildUserMsg, buildBotMsg, initialBotMsg, applyChunk, applyDone } from './useChat'
import type { Source } from '@/types/chat'

describe('buildUserMsg', () => {
  it('creates a user message with the given text', () => {
    const msg = buildUserMsg('hola')
    expect(msg.role).toBe('user')
    expect(msg.text).toBe('hola')
    expect(msg.id).toBeTruthy()
  })
})

describe('buildBotMsg / initialBotMsg', () => {
  it('creates a bot message in searching phase', () => {
    const msg = initialBotMsg('pregunta')
    expect(msg.role).toBe('bot')
    expect(msg.phase).toBe('searching')
    expect(msg.question).toBe('pregunta')
    expect(msg.answer).toBe('')
    expect(msg.answerDone).toBe(false)
    expect(msg.sources).toEqual([])
    expect(msg.id).toBeTruthy()            // UUID, not the question text
  })
})

describe('applyChunk', () => {
  it('appends chunk to answer and sets phase to streaming', () => {
    const msg = initialBotMsg('q')
    const updated = applyChunk(msg, 'Hola')
    expect(updated.answer).toBe('Hola')
    expect(updated.phase).toBe('streaming')
  })

  it('accumulates chunks', () => {
    const msg = initialBotMsg('q')
    const updated = applyChunk(applyChunk(msg, 'Hola'), ' mundo')
    expect(updated.answer).toBe('Hola mundo')
  })
})

describe('applyDone', () => {
  it('sets answerDone=true, phase=done, and attaches sources', () => {
    const msg = initialBotMsg('q')
    const sources: Source[] = [{ course: 'Power BI', section: 'precios', distance: 0.1 }]
    const updated = applyDone(msg, sources)
    expect(updated.answerDone).toBe(true)
    expect(updated.phase).toBe('done')
    expect(updated.sources).toEqual(sources)
  })
})
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd apps/chat && npm test -- hooks/useChat.test.ts
```

Expected: FAIL — `buildUserMsg` not exported.

- [ ] **Step 3: Implement hooks/useChat.ts**

```ts
'use client'
import { useState, useCallback } from 'react'
import type { Message, BotMsg, UserMsg, Source } from '@/types/chat'
import { streamAsk } from '@/lib/api'

// ── Pure state helpers (exported for testing) ──────────────────────────────

export const buildUserMsg = (text: string): UserMsg => ({
  id: crypto.randomUUID(),
  role: 'user',
  text,
})

export const initialBotMsg = (question: string): BotMsg => ({
  id: crypto.randomUUID(),
  role: 'bot',
  phase: 'searching',
  question,
  answer: '',
  answerDone: false,
  sources: [],
})

export const applyChunk = (msg: BotMsg, chunk: string): BotMsg => ({
  ...msg,
  phase: 'streaming',
  answer: msg.answer + chunk,
})

export const applyDone = (msg: BotMsg, sources: Source[]): BotMsg => ({
  ...msg,
  phase: 'done',
  answerDone: true,
  sources,
})

// ── Hook ───────────────────────────────────────────────────────────────────

type UseChatReturn = {
  messages: Message[]
  busy: boolean
  sendMessage: (text: string) => Promise<void>
  clearMessages: () => void
}

export const useChat = (): UseChatReturn => {
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)

  const patchLast = (patch: (prev: BotMsg) => BotMsg) => {
    setMessages((prev) => {
      const idx = prev.findLastIndex((m) => m.role === 'bot')
      if (idx === -1) return prev
      const next = [...prev]
      next[idx] = patch(next[idx] as BotMsg)
      return next
    })
  }

  const sendMessage = useCallback(async (text: string) => {
    if (busy) return

    const userMsg = buildUserMsg(text)
    const botMsg  = initialBotMsg(text)

    setMessages((prev) => [...prev, userMsg, botMsg])
    setBusy(true)

    try {
      for await (const chunk of streamAsk(text, (sources) => {
        patchLast((b) => applyDone(b, sources))
      })) {
        patchLast((b) => applyChunk(b, chunk))
      }
    } catch (err) {
      patchLast((b) => applyDone(b, []))
      console.error('Chat error:', err)
    } finally {
      setBusy(false)
    }
  }, [busy])

  const clearMessages = useCallback(() => {
    if (!busy) setMessages([])
  }, [busy])

  return { messages, busy, sendMessage, clearMessages }
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd apps/chat && npm test
```

Expected: all tests pass (4 from api.test.ts + 6 from useChat.test.ts = 10 total).

- [ ] **Step 5: Commit**

```bash
git add apps/chat/hooks/
git commit -m "feat(chat): add useChat hook with pure state helpers and tests"
```

---

## Task 11: ChatApp + layout + page

**Files:**
- Create: `apps/chat/components/ChatApp.tsx`
- Modify: `apps/chat/app/page.tsx`

- [ ] **Step 1: Create components/ChatApp.tsx**

```tsx
'use client'
import { useEffect } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Welcome from './Welcome'
import MessageList from './MessageList'
import Composer from './Composer'
import { useChat } from '@/hooks/useChat'
import { useDarkMode } from '@/hooks/useDarkMode'

const ChatApp = () => {
  const { messages, busy, sendMessage, clearMessages } = useChat()
  const { dark, toggle } = useDarkMode()
  const showWelcome = messages.length === 0

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '272px 1fr', height: '100vh', width: '100vw', background: 'var(--color-bg)' }}>
      <Sidebar dark={dark} onToggleDark={toggle} onNew={clearMessages} />
      <main style={{ display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0, background: 'var(--color-bg)', position: 'relative' }}>
        <TopBar busy={busy} />
        {showWelcome
          ? <Welcome onPick={sendMessage} />
          : <MessageList messages={messages} />}
        <Composer onSend={sendMessage} disabled={busy} />
      </main>
    </div>
  )
}

export default ChatApp
```

- [ ] **Step 2: Create hooks/useDarkMode.ts**

```ts
'use client'
import { useState, useEffect } from 'react'

export const useDarkMode = () => {
  const [dark, setDark] = useState(false)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  const toggle = () => setDark((d) => !d)

  return { dark, toggle }
}
```

- [ ] **Step 3: Update app/page.tsx**

```tsx
import ChatApp from '@/components/ChatApp'

const Page = () => <ChatApp />

export default Page
```

- [ ] **Step 4: Commit**

```bash
git add apps/chat/components/ChatApp.tsx apps/chat/hooks/useDarkMode.ts apps/chat/app/page.tsx
git commit -m "feat(chat): wire ChatApp, dark mode, and page"
```

---

## Task 12: CORS on FastAPI backend

**Files:**
- Modify: `services/api/main.py`

The proxy route (`/api/ask`) avoids CORS for the Next.js frontend. Adding CORS here is for direct API testing (e.g., curl, Postman, other clients).

- [ ] **Step 1: Add CORSMiddleware to services/api/main.py**

Find the line `app = FastAPI(title="DMC RAG API", lifespan=lifespan)` and add the middleware right after:

```python
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="DMC RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
    expose_headers=["X-Sources"],
)
```

- [ ] **Step 2: Commit**

```bash
git add services/api/main.py
git commit -m "feat(api): add CORS middleware for local dev"
```

---

## Task 13: Smoke test (full integration)

- [ ] **Step 1: Start the FastAPI backend**

In terminal 1:
```bash
cd services/api && uvicorn main:app --reload --port 8000
```

Expected: `INFO: Application startup complete.`

- [ ] **Step 2: Start the Next.js dev server**

In terminal 2:
```bash
cd apps/chat && npm run dev
```

Expected: `▲ Next.js ... ready on http://localhost:3000`

- [ ] **Step 3: Verify the welcome screen**

Open http://localhost:3000 in a browser.

Expected:
- Full-page layout: 272px dark navy sidebar on the left, main chat area on the right
- Sidebar shows: "DMC · IA" brandmark, moon icon, "Nueva conversación" button, session history groups (Hoy / Ayer / Semana pasada)
- Center: BotAvatar (56px) with pulsing amber rings, heading "Hola, soy tu asesor académico DMC", 4 suggestion cards in a 2×2 grid

- [ ] **Step 4: Send a message via suggestion card**

Click "Soy analista junior y quiero crecer en datos".

Expected:
1. User bubble (navy, right-aligned) appears with the clicked text
2. Bot message appears with a `search_brochures()` ToolCallBlock in "running" state (pulsing amber dot)
3. ToolCallBlock transitions to "done" (teal check) when first streaming token arrives
4. Answer streams in character by character with blinking cursor
5. After stream ends, source chips (teal pills with course names) appear below the answer

- [ ] **Step 5: Test dark mode**

Click the moon icon in the sidebar. Verify the entire UI switches to the dark palette (dark navy background, lighter text, all surfaces updated).

- [ ] **Step 6: Test "Nueva conversación"**

Click "Nueva conversación". Verify: messages clear, welcome screen returns.

- [ ] **Step 7: Run full test suite**

```bash
cd apps/chat && npm test
```

Expected: 10 tests pass, 0 failures.

- [ ] **Step 8: Final commit**

```bash
git add .
git commit -m "feat(chat): complete DMC chat portal — pixel-perfect from Claude Design"
```
