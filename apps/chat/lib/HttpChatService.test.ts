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
