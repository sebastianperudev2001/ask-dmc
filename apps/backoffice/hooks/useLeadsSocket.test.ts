import { describe, it, expect } from "vitest"
import { applyLeadWireEvent, deriveNotification } from "./useLeadsSocket"
import type { LeadOut } from "@/types/leads"
import type { LeadWireEvent } from "@/lib/LeadsService"

const lead = (overrides: Partial<LeadOut> = {}): LeadOut => ({
  id: "lead-1",
  createdAt: "2026-07-11T00:00:00Z",
  name: "Ana Torres",
  email: "ana@example.com",
  profileSummary: "",
  motivation: "undefined",
  motivationDetail: "",
  recommendedPrograms: [],
  paymentLinkSent: false,
  paymentConfirmed: false,
  paymentConfirmedAt: null,
  score: "cold",
  scoreJustification: "",
  ...overrides,
})

describe("applyLeadWireEvent", () => {
  it("a snapshot fully replaces state, keyed by lead id", () => {
    const event: LeadWireEvent = { _tag: "snapshot", leads: [lead({ id: "a" }), lead({ id: "b" })] }

    const result = applyLeadWireEvent({ stale: lead({ id: "stale" }) }, event)

    expect(Object.keys(result).sort()).toEqual(["a", "b"])
    expect(result.stale).toBeUndefined() // reconciles away stale/duplicate cards (Story 3 AC)
  })

  it("an empty snapshot clears all prior state", () => {
    const result = applyLeadWireEvent({ a: lead({ id: "a" }) }, { _tag: "snapshot", leads: [] })

    expect(result).toEqual({})
  })

  it("a leadEvent upserts a single entry by id, leaving others untouched", () => {
    const state = { a: lead({ id: "a", score: "cold" }) }
    const event: LeadWireEvent = {
      _tag: "leadEvent",
      eventType: "score_changed",
      lead: lead({ id: "a", score: "warm" }),
    }

    const result = applyLeadWireEvent(state, event)

    expect(result.a.score).toBe("warm")
  })

  it("a leadEvent for a new lead adds it without removing existing ones", () => {
    const state = { a: lead({ id: "a" }) }
    const event: LeadWireEvent = { _tag: "leadEvent", eventType: "created", lead: lead({ id: "b" }) }

    const result = applyLeadWireEvent(state, event)

    expect(Object.keys(result).sort()).toEqual(["a", "b"])
  })
})

describe("deriveNotification", () => {
  it("returns a notification when a lead's score changes to hot", () => {
    const event: LeadWireEvent = {
      _tag: "leadEvent",
      eventType: "score_changed",
      lead: lead({ id: "lead-2", name: "Beto", score: "hot" }),
    }

    const notification = deriveNotification(event)

    expect(notification).not.toBeNull()
    expect(notification?.leadId).toBe("lead-2")
    expect(notification?.leadName).toBe("Beto")
  })

  it("returns null when the score changes but is not hot", () => {
    const event: LeadWireEvent = {
      _tag: "leadEvent",
      eventType: "score_changed",
      lead: lead({ score: "warm" }),
    }

    expect(deriveNotification(event)).toBeNull()
  })

  it("returns null for a created event even if the lead is already hot", () => {
    const event: LeadWireEvent = { _tag: "leadEvent", eventType: "created", lead: lead({ score: "hot" }) }

    expect(deriveNotification(event)).toBeNull()
  })

  it("returns null for a snapshot event", () => {
    expect(deriveNotification({ _tag: "snapshot", leads: [] })).toBeNull()
  })
})
