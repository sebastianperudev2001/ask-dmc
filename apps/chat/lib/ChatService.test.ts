// apps/chat/lib/ChatService.test.ts
import { describe, it, expect } from "vitest"
import { Effect, Layer, Stream } from "effect"
import { ChatService, type ChatEvent } from "./ChatService"

const makeTestLayer = (events: ChatEvent[], sent: string[]) =>
  Layer.succeed(ChatService, {
    events: Stream.fromIterable(events),
    sendMessage: (text: string) => Effect.sync(() => sent.push(`user_message:${text}`)),
    submitProfileData: (callId: string) => Effect.sync(() => sent.push(`profile_data_submitted:${callId}`)),
  })

describe("ChatService contract (Incremento 2 — WebSocket, business-logic-model.md Section 9)", () => {
  it("streams events in order", async () => {
    const input: ChatEvent[] = [
      { _tag: "delta", text: "Hola" },
      { _tag: "delta", text: " mundo" },
      { _tag: "turnDone" },
    ]

    const result = await Effect.runPromise(
      Effect.provide(
        Effect.gen(function* () {
          const svc = yield* ChatService
          return yield* Stream.runCollect(svc.events)
        }),
        makeTestLayer(input, [])
      )
    )

    expect(Array.from(result)).toEqual(input)
  })

  it("sendMessage writes to the underlying transport", async () => {
    const sent: string[] = []
    await Effect.runPromise(
      Effect.provide(
        Effect.gen(function* () {
          const svc = yield* ChatService
          yield* svc.sendMessage("hola")
        }),
        makeTestLayer([], sent)
      )
    )
    expect(sent).toEqual(["user_message:hola"])
  })

  it("submitProfileData writes to the underlying transport", async () => {
    const sent: string[] = []
    await Effect.runPromise(
      Effect.provide(
        Effect.gen(function* () {
          const svc = yield* ChatService
          yield* svc.submitProfileData("call_1", {
            budget: 500,
            maxDurationWeeks: 8,
            professionalBackground: "analista",
            desiredStack: "azure",
          })
        }),
        makeTestLayer([], sent)
      )
    )
    expect(sent).toEqual(["profile_data_submitted:call_1"])
  })

  it("handles an empty event stream without error", async () => {
    const result = await Effect.runPromise(
      Effect.provide(
        Effect.gen(function* () {
          const svc = yield* ChatService
          return yield* Stream.runCollect(svc.events)
        }),
        makeTestLayer([], [])
      )
    )
    expect(Array.from(result)).toEqual([])
  })
})
