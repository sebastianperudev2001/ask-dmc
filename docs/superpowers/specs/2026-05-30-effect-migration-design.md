# Effect Migration Design — Frontend (ask-dmc chat)

**Date:** 2026-05-30
**Scope:** `apps/chat/` logic layer
**Approach:** Effect Services + Layers + Runtime provider (Approach 2)

---

## Goals

- Typed errors: API failures tracked in the return type, not lost in `catch (err: unknown)`
- Better async: Effect `Stream` + `Fiber` replace async generators and imperative `try/catch`
- Foundation: `Layer` / `Runtime` / `Context.Tag` as the pattern for all future logic
- Learning: full Effect stack at a scope small enough to finish

## Out of scope

- `@effect/rx` or reactive bindings in components (revisit once foundation is solid)
- Backend / `services/api/` — untouched
- Any UI changes — all components unchanged

---

## File changes

### New files

| File | Purpose |
|---|---|
| `types/errors.ts` | Tagged Effect error classes |
| `lib/ChatService.ts` | Service interface (`Context.Tag`) + `ChatChunk` type |
| `lib/HttpChatService.ts` | HTTP implementation `Layer` via `@effect/platform-browser` |
| `lib/runtime.ts` | Composes layers into a `ManagedRuntime` |
| `lib/RuntimeProvider.tsx` | React context holding the runtime |

### Rewritten

| File | Change |
|---|---|
| `hooks/useChat.ts` | Internals use `runtime.runFork()` + Effect `Stream`; external API unchanged |

### Deleted

| File | Reason |
|---|---|
| `lib/api.ts` | Replaced by `ChatService` + `HttpChatService` |
| `lib/api.test.ts` | Coverage split between `ChatService.test.ts` and `HttpChatService.test.ts` |

### Unchanged

- `types/chat.ts` — domain types (`Message`, `BotMsg`, `Source`, etc.)
- `components/**` — all untouched
- `app/**` — all untouched
- Pure state helpers in `hooks/useChat.ts` (`buildUserMsg`, `applyChunk`, `applyDone`) — stay as plain functions, existing tests kept

---

## New packages

```
effect                    ← Core: Effect, Stream, Layer, Context, Runtime, Queue, Fiber, Data
@effect/platform          ← HttpClient abstraction
@effect/platform-browser  ← Browser implementation of HttpClient
```

---

## Typed errors

**`types/errors.ts`**

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

- `NetworkError` — non-2xx HTTP response
- `ParseError` — malformed JSON in the `x-sources` response header

---

## Service interface

**`lib/ChatService.ts`**

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

`ChatChunk` replaces the old `onSources` callback: sources arrive as a tagged event at the end of the same stream, not out-of-band. This is the natural Effect model for heterogeneous events over a single channel.

---

## HTTP implementation layer

**`lib/HttpChatService.ts`**

```ts
export const HttpChatService: Layer.Layer<ChatService> = Layer.effect(
  ChatService,
  Effect.gen(function* () {
    const client = yield* HttpClient.HttpClient

    return {
      stream: (question) =>
        Effect.gen(function* () {
          const response = yield* client.post("/api/ask", {
            body: HttpBody.json({ question }),
          })

          // Use .filterStatusOk() to catch non-2xx, then map the platform error to NetworkError
          // e.g. response.pipe(HttpClientResponse.filterStatusOk, Effect.mapError(e => new NetworkError({ status: e.response.status })))

          const xSourcesRaw = response.headers["x-sources"] ?? null

          const textStream = response.stream.pipe(
            Stream.decodeText(),
            Stream.map((chunk): ChatChunk => ({ _tag: "text", chunk })),
          )

          const sourcesEffect = Effect.sync((): ChatChunk[] => {
            if (!xSourcesRaw) return []
            try {
              return [{ _tag: "sources", sources: JSON.parse(xSourcesRaw) }]
            } catch (e) {
              throw new ParseError({ cause: e })
            }
          })

          return Stream.concat(
            textStream,
            Stream.fromEffect(sourcesEffect).pipe(Stream.flatMap(Stream.fromIterable)),
          )
        }).pipe(Stream.unwrap),
    }
  })
).pipe(Layer.provide(BrowserHttpClient.layer))
```

Layer composition:
```
BrowserHttpClient.layer
        ↓
HttpChatService          ← satisfies ChatService
```

---

## Runtime + React bridge

**`lib/runtime.ts`**

```ts
import { ManagedRuntime } from "effect"
import { HttpChatService } from "./HttpChatService"

export const AppRuntime = ManagedRuntime.make(HttpChatService)
```

**`lib/RuntimeProvider.tsx`**

```tsx
import { createContext, useContext } from "react"
import { AppRuntime } from "./runtime"

const RuntimeContext = createContext(AppRuntime)

export const useRuntime = () => useContext(RuntimeContext)

export const RuntimeProvider = ({ children }: { children: React.ReactNode }) => (
  <RuntimeContext.Provider value={AppRuntime}>
    {children}
  </RuntimeContext.Provider>
)
```

`RuntimeProvider` wraps the app root in `app/layout.tsx`.

---

## Hook internals

**`hooks/useChat.ts`** — external API unchanged: `{ messages, busy, sendMessage, clearMessages }`

```ts
export const useChat = (): UseChatReturn => {
  const runtime = useRuntime()
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)

  const patchLast = (patch: (prev: BotMsg) => BotMsg) => {
    setMessages((prev) => {
      const idx = prev.findLastIndex((m) => m.role === "bot")
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
      ChatService.stream(text).pipe(
        Stream.tap((chunk) =>
          Effect.sync(() => {
            if (chunk._tag === "text") patchLast((b) => applyChunk(b, chunk.chunk))
            if (chunk._tag === "sources") patchLast((b) => applyDone(b, chunk.sources))
          })
        ),
        Stream.catchAll(() =>
          Stream.fromEffect(Effect.sync(() => patchLast((b) => applyDone(b, []))))
        ),
        Stream.ensuring(Effect.sync(() => setBusy(false))),
        Stream.runDrain,
      )
    )
  }, [runtime, busy])

  const clearMessages = useCallback(() => {
    if (!busy) setMessages([])
  }, [busy])

  return { messages, busy, sendMessage, clearMessages }
}
```

`runtime.runFork()` fires the stream on the Effect runtime and returns a `Fiber` — React never awaits it. State updates flow through `setMessages` callbacks as before.

---

## Testing

### Pattern

Tests use `Layer.succeed` to provide a `TestChatService` — no fetch mocking, no `vi.stubGlobal`.

```ts
const TestChatService = (chunks: ChatChunk[]) =>
  Layer.succeed(ChatService, {
    stream: (_question) => Stream.fromIterable(chunks),
  })

const runWith = (chunks: ChatChunk[]) => <A, E>(effect: Effect.Effect<A, E, ChatService>) =>
  effect.pipe(Effect.provide(TestChatService(chunks)), Effect.runPromise)
```

### Coverage split

| Old file | New file | What it covers |
|---|---|---|
| `lib/api.test.ts` (deleted) | `lib/ChatService.test.ts` | Stream shape, chunk ordering, sources emission |
| — | `lib/HttpChatService.test.ts` | HTTP status → `NetworkError`, bad header → `ParseError` (integration, optional in unit runs) |
| `hooks/useChat.test.ts` | `hooks/useChat.test.ts` | Pure helpers (`buildUserMsg`, `applyChunk`, `applyDone`) keep existing tests; `sendMessage` integration tested by providing `TestChatService` via a test runtime and asserting on resulting `messages` state |

Pure state helper tests (`buildUserMsg`, `applyChunk`, `applyDone`) are untouched.

---

## What stays the same

- External API of `useChat` hook — components don't change
- `types/chat.ts` domain types
- All component files
- Pure state helpers and their tests
- Vitest as the test runner
