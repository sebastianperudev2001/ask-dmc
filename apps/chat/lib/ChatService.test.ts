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
