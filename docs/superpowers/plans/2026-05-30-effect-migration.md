# Effect Migration — Chat Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `apps/chat/` logic layer to Effect — replacing async generators and `try/catch` with typed Streams, Services, and Layers.

**Architecture:** Define a `ChatService` Effect tag; implement it as `HttpChatServiceLive` (requires `HttpClient` from context) composed with `BrowserHttpClient` for production use. A `ManagedRuntime` is built from these layers and provided to React via a `RuntimeProvider` context. The `useChat` hook acquires the runtime and calls `runtime.runFork()` to drive streaming state updates — components are untouched.

**Tech Stack:** `effect`, `@effect/platform`, `@effect/platform-browser`, Next.js 15, React 19, Vitest

**Spec:** `docs/superpowers/specs/2026-05-30-effect-migration-design.md`

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `types/errors.ts` | Create | `NetworkError`, `ParseError`, `ChatError` |
| `lib/ChatService.ts` | Create | `ChatService` tag, `ChatChunk` union type |
| `lib/ChatService.test.ts` | Create | Contract tests via `TestChatService` layer |
| `lib/HttpChatService.ts` | Create | `HttpChatServiceLive` (requires `HttpClient`) + `HttpChatService` (self-contained) |
| `lib/HttpChatService.test.ts` | Create | Error mapping and chunk streaming tests via mock `HttpClient` layer |
| `lib/runtime.ts` | Create | `AppRuntime` via `ManagedRuntime.make` |
| `lib/RuntimeProvider.tsx` | Create | `'use client'` React context + `useRuntime` hook |
| `app/layout.tsx` | Modify | Wrap `<body>` in `<RuntimeProvider>` |
| `hooks/useChat.ts` | Rewrite | `runtime.runFork()` internals; same external API (`{ messages, busy, sendMessage, clearMessages }`) |
| `hooks/useChat.test.ts` | Modify | Remove `vi.mock('@/lib/api')` import; keep pure helper tests verbatim |
| `lib/api.ts` | Delete | Replaced by `ChatService` + `HttpChatService` |
| `lib/api.test.ts` | Delete | Coverage moved to `ChatService.test.ts` and `HttpChatService.test.ts` |

---

## Task 1: Install packages

**Files:**
- Modify: `apps/chat/package.json`

- [ ] **Step 1: Install Effect packages**

```bash
cd apps/chat && npm install effect @effect/platform @effect/platform-browser
```

- [ ] **Step 2: Verify TypeScript can resolve the packages**

```bash
cd apps/chat && npx tsc --noEmit
```

Expected: no new errors (application code is unchanged at this point).

- [ ] **Step 3: Commit**

```bash
git add apps/chat/package.json apps/chat/package-lock.json
git commit -m "chore(chat): install effect, @effect/platform, @effect/platform-browser"
```

---

## Task 2: Add typed errors

**Files:**
- Create: `apps/chat/types/errors.ts`

- [ ] **Step 1: Create `types/errors.ts`**

```ts
import { Data } from "effect"

export class NetworkError extends Data.TaggedError("NetworkError")<{
  status: number
}> {}

export class ParseError extends Data.TaggedError("ParseError")<{
  cause: unknown
}> {}

export type ChatError = NetworkError | ParseError
```

`Data.TaggedError` gives each class a `._tag` discriminant (for pattern matching), structural equality, and a `.message` property — no boilerplate needed.

- [ ] **Step 2: Verify types compile**

```bash
cd apps/chat && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/chat/types/errors.ts
git commit -m "feat(chat): add typed Effect error classes NetworkError and ParseError"
```

---

## Task 3: Add ChatService interface

**Files:**
- Create: `apps/chat/lib/ChatService.ts`

- [ ] **Step 1: Create `lib/ChatService.ts`**

```ts
import { Context, Stream } from "effect"
import type { ChatError } from "@/types/errors"
import type { Source } from "@/types/chat"

export type ChatChunk =
  | { _tag: "text"; chunk: string }
  | { _tag: "sources"; sources: Source[] }

export class ChatService extends Context.Tag("ChatService")<
  ChatService,
  {
    readonly stream: (question: string) => Stream.Stream<ChatChunk, ChatError>
  }
>() {}
```

`Context.Tag` is Effect's service locator. Any `Layer` that satisfies `ChatService` can be substituted — tests use `TestChatService` (in-memory), production uses `HttpChatService` (real HTTP). `ChatChunk` replaces the old `onSources` callback: sources arrive as a tagged event inside the same stream.

- [ ] **Step 2: Verify types compile**

```bash
cd apps/chat && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/chat/lib/ChatService.ts
git commit -m "feat(chat): add ChatService Effect tag and ChatChunk type"
```

---

## Task 4: Write ChatService contract tests

**Files:**
- Create: `apps/chat/lib/ChatService.test.ts`

These tests define the contract every `ChatService` implementation must satisfy. They run against a `TestChatService` layer — no HTTP.

- [ ] **Step 1: Write the test file**

```ts
// apps/chat/lib/ChatService.test.ts
import { describe, it, expect } from "vitest"
import { Effect, Layer, Stream } from "effect"
import { ChatService, type ChatChunk } from "./ChatService"
import type { Source } from "@/types/chat"

const makeTestLayer = (chunks: ChatChunk[]) =>
  Layer.succeed(ChatService, {
    stream: (_question: string) => Stream.fromIterable(chunks),
  })

const run = <A>(chunks: ChatChunk[], eff: Effect.Effect<A, unknown, ChatService>) =>
  Effect.provide(eff, makeTestLayer(chunks)).pipe(Effect.runPromise)

describe("ChatService contract", () => {
  it("streams text chunks in order", async () => {
    const input: ChatChunk[] = [
      { _tag: "text", chunk: "Hola" },
      { _tag: "text", chunk: " mundo" },
    ]

    const result = await run(
      input,
      Effect.gen(function* () {
        const svc = yield* ChatService
        return yield* svc.stream("test").pipe(Stream.runCollect)
      })
    )

    expect(Array.from(result)).toEqual(input)
  })

  it("emits sources chunk after text chunks", async () => {
    const sources: Source[] = [{ course: "Power BI", section: "intro", distance: 0.1 }]
    const input: ChatChunk[] = [
      { _tag: "text", chunk: "respuesta" },
      { _tag: "sources", sources },
    ]

    const result = await run(
      input,
      Effect.gen(function* () {
        const svc = yield* ChatService
        return yield* svc.stream("pregunta").pipe(Stream.runCollect)
      })
    )

    const arr = Array.from(result)
    expect(arr.at(-1)).toEqual({ _tag: "sources", sources })
  })

  it("handles an empty stream without error", async () => {
    const result = await run(
      [],
      Effect.gen(function* () {
        const svc = yield* ChatService
        return yield* svc.stream("q").pipe(Stream.runCollect)
      })
    )

    expect(Array.from(result)).toEqual([])
  })
})
```

- [ ] **Step 2: Run tests — expect all three to pass**

```bash
cd apps/chat && npm test -- ChatService
```

Expected: `ChatService contract` — 3 passing. These use `TestChatService` so there is no HTTP involved.

- [ ] **Step 3: Commit**

```bash
git add apps/chat/lib/ChatService.test.ts
git commit -m "test(chat): add ChatService contract tests with TestChatService layer"
```

---

## Task 5: Implement HttpChatService (TDD)

**Files:**
- Create: `apps/chat/lib/HttpChatService.test.ts`
- Create: `apps/chat/lib/HttpChatService.ts`

`HttpChatService` exports two layers:
- `HttpChatServiceLive` — requires `HttpClient` from context. Used in tests via a mock `HttpClient` layer.
- `HttpChatService` — self-contained; wires in `BrowserHttpClient` for production.

- [ ] **Step 1: Write the tests first**

```ts
// apps/chat/lib/HttpChatService.test.ts
import { describe, it, expect } from "vitest"
import { Effect, Layer, Stream } from "effect"
import { HttpClient } from "@effect/platform"
import type { HttpClientResponse } from "@effect/platform"
import { HttpChatServiceLive } from "./HttpChatService"
import { ChatService } from "./ChatService"

const encoder = new TextEncoder()

// Build a mock HttpClient layer that returns a controlled fake response.
// The `as unknown as` casts avoid having to satisfy the full platform interface.
const makeMockClient = (
  status: number,
  bodyChunks: Uint8Array[],
  headers: Record<string, string> = {}
) =>
  Layer.succeed(HttpClient.HttpClient, {
    execute: (_req: unknown) =>
      Effect.succeed({
        status,
        headers,
        stream: Stream.fromIterable(bodyChunks),
      } as unknown as HttpClientResponse.HttpClientResponse),
  } as unknown as typeof HttpClient.HttpClient.Service)

const runStream = (
  question: string,
  status: number,
  bodyChunks: Uint8Array[],
  headers: Record<string, string> = {}
) =>
  Effect.gen(function* () {
    const svc = yield* ChatService
    return yield* svc.stream(question).pipe(Stream.runCollect)
  }).pipe(
    Effect.provide(Layer.provide(HttpChatServiceLive, makeMockClient(status, bodyChunks, headers))),
    Effect.runPromise
  )

describe("HttpChatService", () => {
  it("emits text chunks from the response body", async () => {
    const result = await runStream("test", 200, [
      encoder.encode("Hola"),
      encoder.encode(" mundo"),
    ])

    const arr = Array.from(result)
    const text = arr
      .filter((c): c is { _tag: "text"; chunk: string } => c._tag === "text")
      .map((c) => c.chunk)
      .join("")
    expect(text).toBe("Hola mundo")
  })

  it("emits a sources chunk when x-sources header is present", async () => {
    const sources = [{ course: "SQL", section: "joins", distance: 0.05 }]
    const result = await runStream(
      "test",
      200,
      [encoder.encode("respuesta")],
      { "x-sources": JSON.stringify(sources) }
    )

    const arr = Array.from(result)
    const sourcesChunk = arr.find(
      (c): c is { _tag: "sources"; sources: unknown[] } => c._tag === "sources"
    )
    expect(sourcesChunk).toBeDefined()
    expect(sourcesChunk?.sources).toEqual(sources)
  })

  it("fails with NetworkError on non-2xx status", async () => {
    await expect(runStream("test", 500, [])).rejects.toMatchObject({
      _tag: "NetworkError",
      status: 500,
    })
  })

  it("fails with ParseError when x-sources header is malformed JSON", async () => {
    await expect(
      runStream("test", 200, [encoder.encode("ok")], { "x-sources": "not-json{" })
    ).rejects.toMatchObject({ _tag: "ParseError" })
  })
})
```

- [ ] **Step 2: Run tests — expect them to FAIL (module not found)**

```bash
cd apps/chat && npm test -- HttpChatService
```

Expected: `Cannot find module './HttpChatService'`.

- [ ] **Step 3: Implement `lib/HttpChatService.ts`**

```ts
// apps/chat/lib/HttpChatService.ts
import { Effect, Layer, Stream } from "effect"
import { HttpClient, HttpClientRequest } from "@effect/platform"
import { BrowserHttpClient } from "@effect/platform-browser"
import { ChatService, type ChatChunk } from "./ChatService"
import { NetworkError, ParseError } from "@/types/errors"
import type { Source } from "@/types/chat"

const decoder = new TextDecoder()

// Requires HttpClient from context — testable by providing a mock HttpClient layer.
export const HttpChatServiceLive: Layer.Layer<ChatService, never, HttpClient.HttpClient> =
  Layer.effect(
    ChatService,
    Effect.gen(function* () {
      const client = yield* HttpClient.HttpClient

      return {
        stream: (question: string) => {
          const program = Effect.gen(function* () {
            const request = HttpClientRequest.post("/api/ask").pipe(
              HttpClientRequest.bodyJson({ question })
            )

            const response = yield* client.execute(request)

            if (response.status < 200 || response.status >= 300) {
              return yield* Effect.fail(new NetworkError({ status: response.status }))
            }

            const xSourcesRaw =
              (response.headers as Record<string, string>)["x-sources"] ?? null

            // Decode Uint8Array chunks to strings
            const textStream: Stream.Stream<ChatChunk, never> = response.stream.pipe(
              Stream.map((chunk) => ({
                _tag: "text" as const,
                chunk: decoder.decode(chunk, { stream: true }),
              }))
            )

            const sourcesStream: Stream.Stream<ChatChunk, ParseError> = xSourcesRaw
              ? Stream.fromEffect(
                  Effect.try({
                    try: () => JSON.parse(xSourcesRaw) as Source[],
                    catch: (e) => new ParseError({ cause: e }),
                  }).pipe(
                    Effect.map((sources): ChatChunk => ({ _tag: "sources", sources }))
                  )
                )
              : Stream.empty

            return Stream.concat(
              textStream,
              sourcesStream
            ) as Stream.Stream<ChatChunk, ParseError>
          })

          // Stream.unwrapScoped handles any Scope requirement from client.execute
          return Stream.unwrapScoped(
            program as Effect.Effect<
              Stream.Stream<ChatChunk, NetworkError | ParseError>,
              NetworkError | ParseError,
              HttpClient.HttpClient
            >
          )
        },
      }
    })
  )

// Self-contained for production: wires in the browser's fetch-based HttpClient.
export const HttpChatService: Layer.Layer<ChatService> = Layer.provide(
  HttpChatServiceLive,
  BrowserHttpClient.layer
)
```

> **Note on `@effect/platform` API:** The exact import paths and method names evolve between releases. If `HttpClientRequest.bodyJson`, `client.execute`, or `response.stream` don't compile, check the installed version's types with `cmd+click` in your editor or run `node_modules/@effect/platform/dist/index.d.ts`. The key methods are: `post(url)`, `bodyJson(body)`, `execute(request)`, and `response.stream` (a `Stream<Uint8Array, ...>`).

- [ ] **Step 4: Run tests — expect all four to pass**

```bash
cd apps/chat && npm test -- HttpChatService
```

Expected: 4 passing. If any fail with type errors, see the note above.

- [ ] **Step 5: Commit**

```bash
git add apps/chat/lib/HttpChatService.ts apps/chat/lib/HttpChatService.test.ts
git commit -m "feat(chat): implement HttpChatServiceLive layer with typed error mapping and streaming"
```

---

## Task 6: Wire runtime and RuntimeProvider

**Files:**
- Create: `apps/chat/lib/runtime.ts`
- Create: `apps/chat/lib/RuntimeProvider.tsx`
- Modify: `apps/chat/app/layout.tsx`

- [ ] **Step 1: Create `lib/runtime.ts`**

```ts
// apps/chat/lib/runtime.ts
import { ManagedRuntime } from "effect"
import { HttpChatService } from "./HttpChatService"

export const AppRuntime = ManagedRuntime.make(HttpChatService)
```

`ManagedRuntime.make(layer)` composes the layer stack into a runtime object exposing `.runFork()`, `.runPromise()`, etc. The layer is built once and reused across all `runFork` calls.

- [ ] **Step 2: Create `lib/RuntimeProvider.tsx`**

```tsx
// apps/chat/lib/RuntimeProvider.tsx
'use client'
import { createContext, useContext } from "react"
import { AppRuntime } from "./runtime"

type AppRuntimeType = typeof AppRuntime

const RuntimeContext = createContext<AppRuntimeType>(AppRuntime)

export const useRuntime = () => useContext(RuntimeContext)

export const RuntimeProvider = ({ children }: { children: React.ReactNode }) => (
  <RuntimeContext.Provider value={AppRuntime}>
    {children}
  </RuntimeContext.Provider>
)
```

The `'use client'` directive is required — `createContext` cannot be called in a Next.js Server Component. `layout.tsx` can still be a Server Component; it just renders this client component as a child.

- [ ] **Step 3: Modify `app/layout.tsx`**

```tsx
// apps/chat/app/layout.tsx
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'
import { RuntimeProvider } from '@/lib/RuntimeProvider'

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
    <body>
      <RuntimeProvider>{children}</RuntimeProvider>
    </body>
  </html>
)

export default RootLayout
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd apps/chat && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add apps/chat/lib/runtime.ts apps/chat/lib/RuntimeProvider.tsx apps/chat/app/layout.tsx
git commit -m "feat(chat): add ManagedRuntime and RuntimeProvider context"
```

---

## Task 7: Rewrite useChat hook

**Files:**
- Modify: `apps/chat/hooks/useChat.ts`
- Modify: `apps/chat/hooks/useChat.test.ts`

The external API (`{ messages, busy, sendMessage, clearMessages }`) stays identical — no component changes are needed. `sendMessage` return type becomes `void` instead of `Promise<void>`, but `Composer.tsx` and `Welcome.tsx` already declare `(text: string) => void` so this is a non-breaking alignment.

- [ ] **Step 1: Update `hooks/useChat.test.ts`**

Remove the `vi.mock('@/lib/api')` block and the `streamAsk` import. Keep all pure helper tests verbatim.

```ts
// apps/chat/hooks/useChat.test.ts
import { describe, it, expect } from "vitest"
import { buildUserMsg, initialBotMsg, applyChunk, applyDone } from "./useChat"
import type { Source } from "@/types/chat"

describe("buildUserMsg", () => {
  it("creates a user message with the given text", () => {
    const msg = buildUserMsg("hola")
    expect(msg.role).toBe("user")
    expect(msg.text).toBe("hola")
    expect(msg.id).toBeTruthy()
  })
})

describe("initialBotMsg", () => {
  it("creates a bot message in searching phase", () => {
    const msg = initialBotMsg("pregunta")
    expect(msg.role).toBe("bot")
    expect(msg.phase).toBe("searching")
    expect(msg.question).toBe("pregunta")
    expect(msg.answer).toBe("")
    expect(msg.answerDone).toBe(false)
    expect(msg.sources).toEqual([])
    expect(msg.id).toBeTruthy()
  })
})

describe("applyChunk", () => {
  it("appends chunk to answer and sets phase to streaming", () => {
    const msg = initialBotMsg("q")
    const updated = applyChunk(msg, "Hola")
    expect(updated.answer).toBe("Hola")
    expect(updated.phase).toBe("streaming")
  })

  it("accumulates chunks", () => {
    const msg = initialBotMsg("q")
    const updated = applyChunk(applyChunk(msg, "Hola"), " mundo")
    expect(updated.answer).toBe("Hola mundo")
  })
})

describe("applyDone", () => {
  it("sets answerDone=true, phase=done, and attaches sources", () => {
    const msg = initialBotMsg("q")
    const sources: Source[] = [{ course: "Power BI", section: "precios", distance: 0.1 }]
    const updated = applyDone(msg, sources)
    expect(updated.answerDone).toBe(true)
    expect(updated.phase).toBe("done")
    expect(updated.sources).toEqual(sources)
  })
})
```

- [ ] **Step 2: Run the updated test file — expect all tests to pass**

```bash
cd apps/chat && npm test -- useChat
```

Expected: 5 passing. (These only test pure functions so `api.ts` still existing doesn't matter yet.)

- [ ] **Step 3: Rewrite `hooks/useChat.ts`**

```ts
// apps/chat/hooks/useChat.ts
'use client'
import { useState, useCallback } from 'react'
import { Effect, Stream } from 'effect'
import type { Message, BotMsg, UserMsg, Source } from '@/types/chat'
import { ChatService } from '@/lib/ChatService'
import { useRuntime } from '@/lib/RuntimeProvider'

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
  sendMessage: (text: string) => void
  clearMessages: () => void
}

export const useChat = (): UseChatReturn => {
  const runtime = useRuntime()
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

  const sendMessage = useCallback((text: string) => {
    if (busy) return

    const userMsg = buildUserMsg(text)
    const botMsg = initialBotMsg(text)
    setMessages((prev) => [...prev, userMsg, botMsg])
    setBusy(true)

    runtime.runFork(
      Effect.gen(function* () {
        const svc = yield* ChatService
        yield* svc.stream(text).pipe(
          Stream.tap((chunk) =>
            Effect.sync(() => {
              if (chunk._tag === 'text') patchLast((b) => applyChunk(b, chunk.chunk))
              if (chunk._tag === 'sources') patchLast((b) => applyDone(b, chunk.sources))
            })
          ),
          Stream.catchAll(() =>
            Stream.fromEffect(Effect.sync(() => patchLast((b) => applyDone(b, []))))
          ),
          Stream.ensuring(Effect.sync(() => setBusy(false))),
          Stream.runDrain,
        )
      })
    )
  }, [runtime, busy])

  const clearMessages = useCallback(() => {
    if (!busy) setMessages([])
  }, [busy])

  return { messages, busy, sendMessage, clearMessages }
}
```

- [ ] **Step 4: Run tests — expect all to pass**

```bash
cd apps/chat && npm test -- useChat
```

Expected: 5 passing.

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd apps/chat && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/chat/hooks/useChat.ts apps/chat/hooks/useChat.test.ts
git commit -m "feat(chat): rewrite useChat hook with Effect runtime and typed stream"
```

---

## Task 8: Delete old files and run full suite

**Files:**
- Delete: `apps/chat/lib/api.ts`
- Delete: `apps/chat/lib/api.test.ts`

- [ ] **Step 1: Delete the old API files**

```bash
rm apps/chat/lib/api.ts apps/chat/lib/api.test.ts
```

- [ ] **Step 2: Verify nothing still imports the deleted files**

```bash
grep -r "lib/api" apps/chat --include="*.ts" --include="*.tsx"
```

Expected: no output. If any matches appear, update those imports before continuing.

- [ ] **Step 3: Run the full test suite**

```bash
cd apps/chat && npm test
```

Expected: all tests passing across `ChatService.test.ts`, `HttpChatService.test.ts`, and `useChat.test.ts`. Zero failures.

- [ ] **Step 4: Verify TypeScript compiles cleanly**

```bash
cd apps/chat && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(chat): complete Effect migration — remove legacy api.ts, all tests green"
```
