import { describe, it, expect, beforeEach, vi } from "vitest"
import { Effect, Fiber } from "effect"
import { toLeadWireEvent, WsLeadsServiceLive } from "./WsLeadsService"
import { LeadsService } from "./LeadsService"

// Minimal fake matching the subset of the WebSocket API WsLeadsService uses — same
// technique as apps/chat/lib/WsChatService.test.ts (environment: 'node' has no browser
// WebSocket global).
class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  listeners: Record<string, Array<(event: any) => void>> = {}

  constructor(public url: string) {
    FakeWebSocket.instances.push(this)
  }

  addEventListener(type: string, handler: (event: any) => void) {
    ;(this.listeners[type] ??= []).push(handler)
  }

  removeEventListener(type: string, handler: (event: any) => void) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((h) => h !== handler)
  }

  dispatch(type: string, event: any = {}) {
    for (const handler of [...(this.listeners[type] ?? [])]) handler(event)
  }
}

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.stubGlobal("WebSocket", FakeWebSocket)
})

const rawLead = {
  id: "lead-1",
  created_at: "2026-07-11T00:00:00Z",
  name: "Ana Torres",
  email: "ana@example.com",
  profile_summary: "Analista de datos",
  motivation: "growth",
  motivation_detail: "Quiere avanzar en su carrera",
  recommended_programs: ["diploma-data-analyst"],
  payment_link_sent: false,
  payment_confirmed: false,
  payment_confirmed_at: null,
  score: "warm" as const,
  score_justification: "Motivación clara",
}

const expectedLead = {
  id: "lead-1",
  createdAt: "2026-07-11T00:00:00Z",
  name: "Ana Torres",
  email: "ana@example.com",
  profileSummary: "Analista de datos",
  motivation: "growth",
  motivationDetail: "Quiere avanzar en su carrera",
  recommendedPrograms: ["diploma-data-analyst"],
  paymentLinkSent: false,
  paymentConfirmed: false,
  paymentConfirmedAt: null,
  score: "warm",
  scoreJustification: "Motivación clara",
}

describe("toLeadWireEvent (wire protocol translation)", () => {
  it("translates a snapshot message, mapping each lead to camelCase", () => {
    expect(toLeadWireEvent({ type: "snapshot", leads: [rawLead] })).toEqual({
      _tag: "snapshot",
      leads: [expectedLead],
    })
  })

  it("translates an empty snapshot", () => {
    expect(toLeadWireEvent({ type: "snapshot", leads: [] })).toEqual({ _tag: "snapshot", leads: [] })
  })

  it("translates a lead_event message (created)", () => {
    expect(toLeadWireEvent({ type: "lead_event", event_type: "created", lead: rawLead })).toEqual({
      _tag: "leadEvent",
      eventType: "created",
      lead: expectedLead,
    })
  })

  it("translates a lead_event message (score_changed)", () => {
    expect(
      toLeadWireEvent({ type: "lead_event", event_type: "score_changed", lead: { ...rawLead, score: "hot" } })
    ).toEqual({
      _tag: "leadEvent",
      eventType: "score_changed",
      lead: { ...expectedLead, score: "hot" },
    })
  })

  it("returns null for unrecognized message types", () => {
    expect(toLeadWireEvent({ type: "unknown" })).toBeNull()
  })
})

describe("WsLeadsServiceLive", () => {
  it("connects to the leads WebSocket URL and gates construction until the socket opens", async () => {
    const program = Effect.gen(function* () {
      yield* LeadsService
      return "connected"
    })

    const fiber = Effect.runFork(Effect.provide(program, WsLeadsServiceLive))

    await vi.waitFor(() => expect(FakeWebSocket.instances.length).toBe(1))
    const ws = FakeWebSocket.instances[0]
    expect(ws.url).toContain("/ws/leads")

    ws.dispatch("open")

    const result = await Effect.runPromise(Fiber.join(fiber))
    expect(result).toBe("connected")
  })
})
