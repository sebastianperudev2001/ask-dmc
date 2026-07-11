import { describe, it, expect } from "vitest"
import { groupLeadsByScore } from "./KanbanBoard"
import type { LeadOut } from "@/types/leads"

const lead = (id: string, score: LeadOut["score"]): LeadOut => ({
  id,
  createdAt: "2026-07-11T00:00:00Z",
  name: `Lead ${id}`,
  email: null,
  profileSummary: "",
  motivation: "undefined",
  motivationDetail: "",
  recommendedPrograms: [],
  paymentLinkSent: false,
  paymentConfirmed: false,
  paymentConfirmedAt: null,
  score,
  scoreJustification: "",
})

describe("groupLeadsByScore", () => {
  it("groups leads into hot/warm/cold columns", () => {
    const leads = [lead("a", "hot"), lead("b", "warm"), lead("c", "cold"), lead("d", "hot")]

    const result = groupLeadsByScore(leads)

    expect(result.hot.map((l) => l.id)).toEqual(["a", "d"])
    expect(result.warm.map((l) => l.id)).toEqual(["b"])
    expect(result.cold.map((l) => l.id)).toEqual(["c"])
  })

  it("a tier with no leads renders as an empty array, not an error (Story 1 AC)", () => {
    const result = groupLeadsByScore([lead("a", "hot")])

    expect(result.warm).toEqual([])
    expect(result.cold).toEqual([])
  })

  it("handles an empty lead list entirely", () => {
    const result = groupLeadsByScore([])

    expect(result).toEqual({ hot: [], warm: [], cold: [] })
  })
})
