import { describe, it, expect } from "vitest"
import { motivationLabel } from "./LeadDetailModal"

describe("motivationLabel", () => {
  it("maps each known motivation category to a Spanish label", () => {
    expect(motivationLabel("growth")).toBe("Crecimiento profesional")
    expect(motivationLabel("salary")).toBe("Aumento salarial")
    expect(motivationLabel("company_requirement")).toBe("Requisito de la empresa")
    expect(motivationLabel("academic")).toBe("Fines académicos")
  })

  it("maps the undefined default to a human label instead of showing it raw", () => {
    expect(motivationLabel("undefined")).toBe("Sin definir aún")
  })

  it("falls back to the raw value for an unrecognized category", () => {
    expect(motivationLabel("something-new")).toBe("something-new")
  })
})
