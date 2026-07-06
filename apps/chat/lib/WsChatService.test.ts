import { describe, it, expect, beforeEach, vi } from "vitest"
import { Effect } from "effect"
import { toChatEvent, WsChatServiceLive } from "./WsChatService"
import { ChatService } from "./ChatService"

// Minimal fake matching the subset of the WebSocket API WsChatService uses —
// environment: 'node' in vitest.config.ts has no browser WebSocket global.
class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  listeners: Record<string, Array<(event: any) => void>> = {}
  sent: string[] = []

  constructor(public url: string) {
    FakeWebSocket.instances.push(this)
  }

  addEventListener(type: string, handler: (event: any) => void) {
    ;(this.listeners[type] ??= []).push(handler)
  }

  removeEventListener(type: string, handler: (event: any) => void) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((h) => h !== handler)
  }

  send(data: string) {
    this.sent.push(data)
  }

  dispatch(type: string, event: any = {}) {
    for (const handler of [...(this.listeners[type] ?? [])]) handler(event)
  }
}

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.stubGlobal("WebSocket", FakeWebSocket)
})

describe("toChatEvent (wire protocol translation, business-logic-model.md Section 9)", () => {
  it("translates recommendation_delta to a delta event", () => {
    expect(toChatEvent({ type: "recommendation_delta", delta: "Hola" })).toEqual({
      _tag: "delta",
      text: "Hola",
    })
  })

  it("translates profile_data_requested to camelCase prefill", () => {
    expect(
      toChatEvent({
        type: "profile_data_requested",
        call_id: "call_1",
        prefill: {
          budget: 500,
          max_duration_weeks: 8,
          professional_background: "analista",
          desired_stack: "azure",
        },
      })
    ).toEqual({
      _tag: "profileDataRequested",
      callId: "call_1",
      prefill: {
        budget: 500,
        maxDurationWeeks: 8,
        professionalBackground: "analista",
        desiredStack: "azure",
      },
    })
  })

  it("translates recommendation_done candidates to camelCase", () => {
    expect(
      toChatEvent({
        type: "recommendation_done",
        candidates: [{ course_id: "c1", name: "Diploma", similarity_score: 0.9 }],
      })
    ).toEqual({
      _tag: "recommendationsReady",
      candidates: [{ courseId: "c1", name: "Diploma", similarityScore: 0.9 }],
    })
  })

  it("translates payment_link_created and turn_done and session_created", () => {
    expect(toChatEvent({ type: "payment_link_created", checkout_url: "https://mp.example/pay" })).toEqual({
      _tag: "paymentLinkCreated",
      checkoutUrl: "https://mp.example/pay",
    })
    expect(toChatEvent({ type: "turn_done" })).toEqual({ _tag: "turnDone" })
    expect(toChatEvent({ type: "session_created", service_session_id: "sess-1" })).toEqual({
      _tag: "sessionCreated",
      serviceSessionId: "sess-1",
    })
  })

  it("returns null for unrecognized/informational event types", () => {
    expect(toChatEvent({ type: "relax_filters_offer", message: "..." })).toBeNull()
    expect(toChatEvent({ type: "no_recommendation", reason: "agent_unavailable" })).toBeNull()
  })
})

describe("WsChatServiceLive", () => {
  // Covers the open-gating + outgoing message shape, which is what actually needs
  // WsChatService-specific wiring. The incoming-event side reuses Stream.asyncPush
  // exactly per Effect's own documented pattern (see WsChatService.ts) and its
  // translation is already covered above (toChatEvent) — full receive-side wiring is
  // exercised manually against the real backend (scripts/manual_chat_check.py), not
  // worth fighting fiber-scheduling timing for in a unit test here.
  it("waits for the socket to open before sending the first message", async () => {
    const program = Effect.gen(function* () {
      const svc = yield* ChatService
      yield* svc.sendMessage("hola")
    })

    Effect.runFork(Effect.provide(program, WsChatServiceLive))

    await vi.waitFor(() => expect(FakeWebSocket.instances.length).toBe(1))
    const ws = FakeWebSocket.instances[0]
    expect(ws.sent).toEqual([]) // not sent yet — socket isn't open

    ws.dispatch("open")

    await vi.waitFor(() => expect(ws.sent.length).toBe(1))
    expect(JSON.parse(ws.sent[0])).toEqual({ type: "user_message", text: "hola" })
  })
})
